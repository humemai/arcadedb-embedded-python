#!/bin/bash
# Start mongod and mongot in one container, in the order MongoDB's own
# quick-start documents, and print ONE readiness marker when both are up.
#
# WHY A SCRIPT AND NOT TWO CONTAINERS. mongot is a separate process by design;
# the client only ever talks to mongod, which routes $search/$vectorSearch to
# mongot over gRPC. Running both here keeps the whole engine inside the single
# server cgroup the runner caps and samples, so MongoDB's memory column means
# the same thing as ArcadeDB's, ArangoDB's and SurrealDB's. A second container
# would be unsampled and its memory would silently vanish from the row.
#
# The readiness marker is the last thing printed, after mongot answers SERVING,
# so runner.wait_ready cannot hand a cell a mongod whose search process is
# still starting.
set -eu

MONGOT_DIR=/mongot-community
STATE=/mongot-state
ROOT_USER=${MONGO_BENCH_USER:-root}
ROOT_PW=${MONGO_BENCH_PASSWORD:-dbbenchpass}
MONGOT_USER=mongotUser
MONGOT_PW=${MONGOT_PASSWORD:-dbbenchmongot}
RS=${MONGO_BENCH_REPLSET:-rs0}

mkdir -p "$STATE/data"
# The key file is internal replica-set auth, which mongod requires as soon as
# access control is on. Generated per container: a key baked into the image
# would be a credential in a public repository.
openssl rand -base64 756 > "$STATE/keyfile"
chmod 400 "$STATE/keyfile"
# No trailing newline: the shipped config says the password file must not have
# one, and a newline here fails authentication with a message that names TLS.
printf '%s' "$MONGOT_PW" > "$STATE/passwordFile"
chmod 400 "$STATE/passwordFile"

# Anything the runner appended (server_cmd) is passed through to mongod.
mongod --replSet "$RS" --bind_ip_all --keyFile "$STATE/keyfile" \
       --setParameter mongotHost=localhost:27028 \
       --setParameter searchIndexManagementHostAndPort=localhost:27028 \
       --setParameter skipAuthenticationToSearchIndexManagementServer=false \
       --setParameter useGrpcForSearch=true \
       "$@" &
MONGOD_PID=$!

mongosh_try() {  # mongosh with the localhost exception, before any user exists
    mongosh --quiet --host 127.0.0.1 --port 27017 --eval "$1" 2>&1
}
mongosh_auth() {
    mongosh --quiet --host 127.0.0.1 --port 27017 \
            -u "$ROOT_USER" -p "$ROOT_PW" --authenticationDatabase admin \
            --eval "$1" 2>&1
}

for _ in $(seq 1 240); do
    if mongosh_try 'db.adminCommand({ping:1}).ok' | grep -q '^1$'; then break; fi
    sleep 0.5
done

# rs.initiate through the localhost exception; already-initiated is not an error
# (a restarted container reuses the data directory).
mongosh_try "try { rs.initiate({_id:'$RS', members:[{_id:0, host:'localhost:27017'}]}) } catch (e) { print(e.codeName) }" >/dev/null
for _ in $(seq 1 240); do
    if mongosh_try 'db.hello().isWritablePrimary' | grep -q '^true$'; then break; fi
    sleep 0.5
done

# The FIRST user is created through the localhost exception; everything after
# it authenticates.
mongosh_try "db.getSiblingDB('admin').createUser({user:'$ROOT_USER', pwd:'$ROOT_PW', roles:[{role:'root', db:'admin'}]})" >/dev/null 2>&1 || true
mongosh_auth "db.getSiblingDB('admin').createUser({user:'$MONGOT_USER', pwd:'$MONGOT_PW', roles:[{role:'searchCoordinator', db:'admin'}]})" >/dev/null 2>&1 || true

"$MONGOT_DIR/mongot" --config "$MONGOT_DIR/config.default.yml" &
MONGOT_PID=$!

# HEALTH OVER bash's /dev/tcp, NOT curl. The mongo image ships no curl and no
# nc, and assuming a vendor image has either is how a readiness probe becomes a
# silent no-op.
health() {
    exec 3<>/dev/tcp/127.0.0.1/8080 || return 1
    printf 'GET /health HTTP/1.0\r\nHost: localhost\r\n\r\n' >&3
    local body
    body=$(timeout 5 cat <&3 || true)
    exec 3<&- 2>/dev/null || true
    exec 3>&- 2>/dev/null || true
    [[ $body == *SERVING* && $body != *NOT_SERVING* ]]
}
ready=0
for _ in $(seq 1 240); do
    if health; then ready=1; break; fi
    if ! kill -0 "$MONGOT_PID" 2>/dev/null; then
        echo "DBBENCH mongot exited before reporting SERVING" >&2
        exit 1
    fi
    sleep 0.5
done
[ "$ready" = 1 ] || { echo "DBBENCH mongot never reported SERVING" >&2; exit 1; }

# PUT MONGOT'S OWN VERSION SOMEWHERE THE CLIENT CAN READ IT. mongod answers
# for its own build and knows nothing about the binary serving $vectorSearch,
# and the client container cannot see this filesystem or mongot's
# localhost-bound health port. So the version the image actually shipped is
# written into a collection the adapters read back, which makes engine_version
# evidence rather than a constant somebody remembered to bump. `dbbench` is a
# separate database from `bench`, which every adapter drops on connect.
MONGOT_VER=$(head -1 "$MONGOT_DIR/VERSION.txt" | tr -d '\r')
mongosh_auth "db.getSiblingDB('dbbench').build.replaceOne({_id:'mongot'}, {_id:'mongot', version:'${MONGOT_VER}'}, {upsert:true})" >/dev/null 2>&1 || true

echo "DBBENCH mongod+mongot ready"
wait -n "$MONGOD_PID" "$MONGOT_PID"
