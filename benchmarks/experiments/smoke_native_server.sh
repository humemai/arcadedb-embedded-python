#!/bin/bash
# Smoke for the native server arm (#222): plumbing only, at the smallest scale. Run from the measurement lane, never from a tool shell on the laptop.
#
# Starts upstream's native-image ArcadeDB server image as the served arm (the runner swaps it in because the pinned wheel is the native build),
# runs ONE served cell of l2 (arcadedb_graph_server) and ONE of docs_oltp (l1 oltp, arcadedb_server), then checks the rows: build, settings
# stamps read back from the engine, engine commit, CPU baseline. Exits non-zero on any miss. The engine commit is READ from SELECT version() and
# REPORTED, not asserted equal to the wheel's: this checks the plumbing, not the pair (the stage pre-flight checks the pair).
#
# usage: smoke_native_server.sh [<native-server-image>] [<native-wheel>]
set -uo pipefail
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
IMG="${1:-arcadedata/arcadedb:26.11.1-SNAPSHOT-native}"
WHEEL="${2:-/home/tk/build-scratch/native-e353330c5c/dist/arcadedb-26.11.1.dev0-py3-none-manylinux_2_28_x86_64.whl}"
OUT="${SMOKE_OUT:-/home/tk/build-scratch/smoke-native-server}"
TAG="smoke_native_server_$(date +%s)"
[ -f "$WHEEL" ] || { echo "SMOKE FAIL: no native wheel $WHEEL"; exit 1; }
case "$(basename "$WHEEL")" in arcadedb-[0-9]*) ;; *) echo "SMOKE FAIL: $WHEEL is not the native (arcadedb-<v>) wheel"; exit 1 ;; esac
mkdir -p "$OUT" || exit 1
docker image inspect "$IMG" >/dev/null 2>&1 || docker pull -q "$IMG" >/dev/null || { echo "SMOKE FAIL: cannot pull $IMG"; exit 1; }
# the image answers on its own before the runner starts it (reports the commit; no sha asserted)
bash "$HERE/verify_native_server_image.sh" "$IMG" > "$OUT/verify.txt" 2>&1 || { cat "$OUT/verify.txt"; echo "SMOKE FAIL: the native server image did not answer"; exit 1; }
COMMIT=$(sed -n 's/^NATIVE_SERVER_COMMIT=//p' "$OUT/verify.txt")
[ -n "$COMMIT" ] || { echo "SMOKE FAIL: no commit read from SELECT version()"; exit 1; }
echo "native server commit (reported, not asserted): $COMMIT"
# ARCADEDB_SERVER_IMAGE is the JVM image the F5 rule wants set beside the wheel; the native chain never starts it, so a name is enough here.
export ARCADEDB_WHEEL="$WHEEL" ARCADEDB_SERVER_IMAGE="arcadedb-c25:${COMMIT:0:9}" ARCADEDB_NATIVE_SERVER_IMAGE="$IMG" BENCH_SERVER_BUILD=native
export BENCH_CPUSET="${BENCH_CPUSET:-4,5}" BENCH_INSTRUMENT=2026-11
cd "$HERE" || exit 1
rc=0
for CELL in "l2 arcadedb_graph_server oltp" "l1 arcadedb_server oltp"; do
  set -- $CELL
  uv run --no-project --python 3.12 --with numpy python runner.py --lanes "$1" --backends "$2" --workloads "$3" --scale tiny --reps 1 --tier sweep \
    --results-file "$TAG.jsonl" > "$OUT/run_$1.log" 2>&1 || { tail -20 "$OUT/run_$1.log"; echo "SMOKE FAIL: runner exited non-zero for $1"; rc=1; }
done
[ "$rc" = 0 ] || exit 1
RESULTS_FILE="$HERE/results/$TAG.jsonl" EXPECT_COMMIT="$COMMIT" uv run --no-project --python 3.12 python -I - <<'PY'
import json, os, sys
sys.path.insert(0, os.getcwd())
import arm_identity as AI
rows = [json.loads(l) for l in open(os.environ["RESULTS_FILE"]) if l.strip()]
bad = []
want = {"l2": "arcadedb_graph_server", "l1": "arcadedb_server"}
for lane, arm in want.items():
    got = [r for r in rows if r.get("lane") == lane and r.get("backend") == arm]
    if len(got) != 1:
        bad.append(f"{lane}/{arm}: {len(got)} rows, expected 1")
        continue
    r = got[0]
    def need(cond, msg):
        if not cond:
            bad.append(f"{lane}/{arm}: {msg}")
    need(not r.get("error") and r.get("rc") == 0, f"error={r.get('error')!r} rc={r.get('rc')!r}")
    need(r.get("engine_backend") == "native" and r.get("server_build") == "native", f"engine_backend={r.get('engine_backend')!r} server_build={r.get('server_build')!r}")
    need(AI.build_of(r) == "native" and AI.served(r), "arm_identity does not read it as a native served row")
    need(r.get("cpu_baseline", "").startswith("native server image: -march="), f"cpu_baseline={r.get('cpu_baseline')!r}")
    s = r.get("server_settings") or {}
    for k, v in (("arcadedb.server.mode", "development"), ("arcadedb.server.httpIncomingHost", "0.0.0.0"),
                 ("arcadedb.server.httpIncomingPort", "2480"), ("arcadedb.txWalFlush", "0")):
        need(str(s.get(k)) == v, f"server_settings[{k}]={s.get(k)!r}, expected {v!r} (unlisted: {r.get('server_settings_unlisted')})")
    need("read from the engine over HTTP" in str(r.get("server_settings_source")), f"settings source: {r.get('server_settings_source')!r}")
    need(str(r.get("server_engine_commit") or "").startswith(os.environ["EXPECT_COMMIT"][:7]), f"server_engine_commit={r.get('server_engine_commit')!r}")
    need("UseCompactObjectHeaders" in str(r.get("native_dropped_flags")), f"native_dropped_flags={r.get('native_dropped_flags')!r}")
    need("-Xmx" in str(r.get("server_cmd")) and "-Darcadedb.txWalFlush=0" in str(r.get("server_cmd")), f"server_cmd={r.get('server_cmd')!r}")
    print(f"{lane}/{arm}: build={r.get('engine_backend')} commit={r.get('server_engine_commit')} heap={r.get('server_heap')} cpu_baseline={r.get('cpu_baseline')!r} settings={s}")
pair = AI.server_settings_problems(rows)
bad += pair
if bad:
    print("SMOKE FAIL:\n  " + "\n  ".join(bad))
    sys.exit(1)
print("SMOKE PASS native server arm")
PY
