#!/usr/bin/env bash
# Part B: which Postgres-wire tools work against ArcadeDB's Postgres plugin (README Part B).
# NEED_GB=6 JOB_MEM_GB=5  (server 2 GB + one client container at a time, Metabase 3 GB the largest). Cores 14,15.
# Starts one ArcadeDB server, seeds a tiny dataset, probes psql, psycopg 3, SQLAlchemy 2, pgJDBC, Grafana, Metabase
# one after the other, appends one JSON line per step to $OUT/matrix.jsonl and removes every container on exit.
# Usage: OUT=/home/tk/build-scratch/sql-evidence/matrix-<stamp> bash tool_matrix.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OUT:-/home/tk/build-scratch/sql-evidence/matrix-$(date -u +%Y%m%d-%H%M%S)}"
ARCADEDB_IMAGE="${ARCADEDB_IMAGE:-arcadedata/arcadedb:${ARCADEDB_VERSION:-26.10.2}}"
PSQL_IMAGE="${PSQL_IMAGE:-postgres:18.6}"
JDK_IMAGE="${JDK_IMAGE:-eclipse-temurin:25-jdk}"
GRAFANA_IMAGE="${GRAFANA_IMAGE:-grafana/grafana:13.3.0}"
METABASE_IMAGE="${METABASE_IMAGE:-metabase/metabase:v0.65.2}"
PGJDBC_VERSION="${PGJDBC_VERSION:-42.7.14}"
PGPW="sqlev-Pass-2026"
GFPW="sqlev-Grafana-2026"
CPUSET="14,15"
ID="sqlev-$$-$(date +%s)"
NET="$ID-net"
SRV="$ID-arcadedb"
CONTAINERS=("$SRV")
mkdir -p "$OUT/work"
cd "$HERE"

cleanup() {
  for c in "${CONTAINERS[@]}"; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

pick_port() {  # a free loopback port
  local p
  while :; do
    p=$((20000 + RANDOM % 20000))
    if [ -z "$(ss -ltnH "sport = :$p")" ]; then echo "$p"; return; fi
  done
}
PG_PORT="$(pick_port)"; HTTP_PORT="$(pick_port)"; GRAF_PORT="$(pick_port)"; MB_PORT="$(pick_port)"

wait_for() {  # wait_for <seconds> <description> <command...>
  local deadline=$((SECONDS + $1)); local what="$2"; shift 2
  until "$@" >/dev/null 2>&1; do
    if [ "$SECONDS" -ge "$deadline" ]; then echo "TIMEOUT waiting for $what" >&2; return 1; fi
    sleep 3
  done
}

for img in "$ARCADEDB_IMAGE" "$PSQL_IMAGE" "$JDK_IMAGE" "$GRAFANA_IMAGE" "$METABASE_IMAGE"; do
  docker image inspect "$img" >/dev/null 2>&1 || docker pull -q "$img" >/dev/null
  printf '%s\t%s\n' "$img" "$(docker image inspect --format '{{index .RepoDigests 0}}' "$img" 2>/dev/null || echo none)" >> "$OUT/images.txt"
done

curl -fsSL -o "$OUT/work/postgresql.jar" "https://repo1.maven.org/maven2/org/postgresql/postgresql/${PGJDBC_VERSION}/postgresql-${PGJDBC_VERSION}.jar"
sha256sum "$OUT/work/postgresql.jar" > "$OUT/pgjdbc.sha256"
cp "$HERE/PgJdbcProbe.java" "$OUT/work/"

docker network create "$NET" >/dev/null
docker run -d --rm --name "$SRV" --network "$NET" --cpuset-cpus "$CPUSET" -m 2g \
  -p "127.0.0.1:$PG_PORT:5432" -p "127.0.0.1:$HTTP_PORT:2480" \
  -e JAVA_OPTS="-Xmx1g -Darcadedb.server.rootPassword=$PGPW -Darcadedb.server.defaultDatabases=sqlev[root] -Darcadedb.server.plugins=Postgres:com.arcadedb.postgres.PostgresProtocolPlugin" \
  "$ARCADEDB_IMAGE" >/dev/null
wait_for 180 "ArcadeDB HTTP server" bash -c "docker logs '$SRV' 2>&1 | grep -q 'HTTP Server started'"
docker logs "$SRV" > "$OUT/server-start.log" 2>&1 || true
{ echo "image=$ARCADEDB_IMAGE"; grep -i -E 'postgres|version' "$OUT/server-start.log" | head -20; } > "$OUT/server-facts.txt" || true

uv run --no-project python seed_pgwire.py 127.0.0.1 "$HTTP_PORT" "$PGPW" > "$OUT/seed.json"

M="$OUT/matrix.jsonl"
: > "$M"
run_probe() {  # run_probe <name> <command...>: a failed probe is recorded and the matrix continues
  local name="$1"; shift
  "$@" >> "$M" 2> "$OUT/$name.err" || echo "{\"client\":\"$name\",\"client_version\":\"?\",\"step\":\"probe\",\"ok\":false,\"error\":\"probe script exited non-zero, see $name.err\"}" >> "$M"
}

run_probe psql uv run --no-project python probe_psql.py "$NET" "$PSQL_IMAGE" "$SRV" 5432 root "$PGPW"
run_probe python uv run --no-project --with 'psycopg[binary]==3.3.7' --with 'sqlalchemy==2.1.8' python probe_python.py 127.0.0.1 "$PG_PORT" root "$PGPW"
run_probe pgjdbc docker run --rm --network "$NET" --cpuset-cpus "$CPUSET" -m 1g -v "$OUT/work:/w:ro" "$JDK_IMAGE" \
  java -cp /w/postgresql.jar /w/PgJdbcProbe.java "$SRV" 5432 root "$PGPW"

# Grafana: provisioned Postgres datasource, health check, then /api/ds/query
mkdir -p "$OUT/grafana-prov/datasources"
cat > "$OUT/grafana-prov/datasources/arcadedb.yaml" <<YAML
apiVersion: 1
datasources:
  - name: arcadedb
    uid: sqlev
    type: grafana-postgresql-datasource
    access: proxy
    url: $SRV:5432
    user: root
    jsonData:
      database: sqlev
      sslmode: disable
      postgresVersion: 1500
      timescaledb: false
    secureJsonData:
      password: $PGPW
YAML
GRAF="$ID-grafana"; CONTAINERS+=("$GRAF")
docker run -d --rm --name "$GRAF" --network "$NET" --cpuset-cpus "$CPUSET" -m 1g -p "127.0.0.1:$GRAF_PORT:3000" \
  -e GF_SECURITY_ADMIN_PASSWORD="$GFPW" -v "$OUT/grafana-prov:/etc/grafana/provisioning:ro" "$GRAFANA_IMAGE" >/dev/null
wait_for 180 "Grafana" curl -fsS "http://127.0.0.1:$GRAF_PORT/api/health"
run_probe grafana uv run --no-project python probe_grafana.py "http://127.0.0.1:$GRAF_PORT" sqlev admin "$GFPW"
docker logs "$GRAF" > "$OUT/grafana.log" 2>&1 || true
docker rm -f "$GRAF" >/dev/null 2>&1 || true

# Metabase: setup API, add database, sync, native queries
MB="$ID-metabase"; CONTAINERS+=("$MB")
docker run -d --rm --name "$MB" --network "$NET" --cpuset-cpus "$CPUSET" -m 3g -p "127.0.0.1:$MB_PORT:3000" \
  -e JAVA_OPTS="-Xmx1536m" "$METABASE_IMAGE" >/dev/null
wait_for 420 "Metabase" curl -fsS "http://127.0.0.1:$MB_PORT/api/health"
run_probe metabase uv run --no-project python probe_metabase.py "http://127.0.0.1:$MB_PORT" "$SRV" 5432 root "$PGPW"
docker logs "$MB" > "$OUT/metabase.log" 2>&1 || true
docker logs "$SRV" > "$OUT/server-end.log" 2>&1 || true

uv run --no-project python matrix_table.py "$M" > "$OUT/matrix.md"
cat "$OUT/matrix.md"
echo "DONE $OUT"
