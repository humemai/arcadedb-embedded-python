#!/usr/bin/env python3
"""ctypes smoke test for libarcadedb.so (feasibility spike). Stdlib only.

Usage: python3 -I smoke.py /path/to/libarcadedb.so
Timings come from a shared GitHub runner: not for performance claims.
"""
import ctypes
import json
import os
import resource
import statistics
import sys
import tempfile
import time
import urllib.request

T = time.perf_counter
results = {}


def vmrss_kb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    return 0


lib_path = os.path.abspath(sys.argv[1])
rss0 = vmrss_kb()
t0 = T()
lib = ctypes.CDLL(lib_path)
t_load = T() - t0

isolate = ctypes.c_void_p()
thread = ctypes.c_void_p()
t0 = T()
rc = lib.graal_create_isolate(None, ctypes.byref(isolate), ctypes.byref(thread))
t_iso = T() - t0
assert rc == 0, f"graal_create_isolate rc={rc}"
results["library_load_ms"] = round(t_load * 1e3, 1)
results["isolate_start_ms"] = round(t_iso * 1e3, 1)
results["rss_after_isolate_kb"] = vmrss_kb()
results["rss_before_load_kb"] = rss0

lib.arcadedb_open.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lib.arcadedb_open.restype = ctypes.c_long
lib.arcadedb_last_error.argtypes = [ctypes.c_void_p]
lib.arcadedb_last_error.restype = ctypes.c_void_p
lib.arcadedb_command.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
lib.arcadedb_command.restype = ctypes.c_void_p
lib.arcadedb_close.argtypes = [ctypes.c_void_p, ctypes.c_long]
lib.arcadedb_close.restype = ctypes.c_int
lib.arcadedb_server_start.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
lib.arcadedb_server_start.restype = ctypes.c_int
lib.arcadedb_server_stop.argtypes = [ctypes.c_void_p]
lib.arcadedb_server_stop.restype = ctypes.c_int
lib.arcadedb_free.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.arcadedb_free.restype = None


def take(ptr):
    s = ctypes.string_at(ptr).decode("utf-8")
    lib.arcadedb_free(thread, ptr)
    return s


def last_error():
    return take(lib.arcadedb_last_error(thread))


def cmd(h, language, text, params=None):
    out = take(lib.arcadedb_command(thread, h, language.encode(), text.encode(), json.dumps(params or {}).encode()))
    obj = json.loads(out)
    if not obj["ok"]:
        raise RuntimeError(f"{language}: {text[:80]!r} -> {obj['error']}")
    return obj["result"]


tmp = tempfile.mkdtemp(prefix="arcadedb-native-")
dbpath = os.path.join(tmp, "databases", "smoke")
os.makedirs(os.path.dirname(dbpath))

t0 = T()
h = lib.arcadedb_open(thread, dbpath.encode())
results["open_create_ms"] = round((T() - t0) * 1e3, 1)
assert h, f"open failed: {last_error()}"

t0 = T()
cmd(h, "sql", "SELECT FROM schema:types")
results["first_query_ms"] = round((T() - t0) * 1e3, 1)
print("first query ok", flush=True)

cmd(h, "sql", "CREATE DOCUMENT TYPE Doc")
cmd(h, "sql", "CREATE PROPERTY Doc.id INTEGER")
cmd(h, "sql", "CREATE PROPERTY Doc.name STRING")
cmd(h, "sql", "CREATE PROPERTY Doc.embedding ARRAY_OF_FLOATS")
cmd(h, "sql", "CREATE INDEX ON Doc (id) UNIQUE")

N, DIM = 10_000, 8


def vec(i):
    return [round(((i * (j + 7)) % 97) / 97.0, 4) for j in range(DIM)]


t0 = T()
for start in range(0, N, 1000):
    stmts = ["BEGIN;"]
    for i in range(start, start + 1000):
        stmts.append(f"INSERT INTO Doc SET id = {i}, name = 'doc-{i}', embedding = {vec(i)};")
    stmts.append("COMMIT;")
    cmd(h, "sqlscript", "\n".join(stmts))
results["insert_10k_s"] = round(T() - t0, 2)

count = cmd(h, "sql", "SELECT count(*) AS c FROM Doc")[0]["c"]
assert count == N, count
results["count"] = count
print("count ok", count, flush=True)

cmd(h, "opencypher", "CREATE (a:Person {name:'Alice'})-[:KNOWS]->(b:Person {name:'Bob'})")
rows = cmd(h, "opencypher", "MATCH (a:Person)-[:KNOWS]->(b:Person) RETURN a.name AS a, b.name AS b")
assert rows and rows[0]["a"] == "Alice" and rows[0]["b"] == "Bob", rows
results["cypher_rows"] = len(rows)
print("cypher ok", flush=True)

t0 = T()
cmd(h, "sql", 'CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA {"dimensions": %d, "similarity": "COSINE"}' % DIM)
results["vector_index_create_s"] = round(T() - t0, 2)
q = vec(1234)
t0 = T()
nn = cmd(h, "sql", f"SELECT vectorNeighbors('Doc[embedding]', {q}, 5) AS res")
results["vector_first_query_ms"] = round((T() - t0) * 1e3, 1)
assert nn and nn[0]["res"], nn
results["vector_neighbors_top"] = json.dumps(nn[0]["res"])[:200]
print("vector ok", flush=True)

lat = []
for k in range(100):
    t0 = T()
    r = cmd(h, "sql", f"SELECT FROM Doc WHERE id = {(k * 97) % N}")
    lat.append((T() - t0) * 1e3)
    assert len(r) == 1
results["steady_query_median_ms"] = round(statistics.median(lat), 3)

assert lib.arcadedb_close(thread, h) == 0
t0 = T()
h2 = lib.arcadedb_open(thread, dbpath.encode())
assert h2, last_error()
assert cmd(h2, "sql", "SELECT count(*) AS c FROM Doc")[0]["c"] == N
results["reopen_and_count_ms"] = round((T() - t0) * 1e3, 1)
assert lib.arcadedb_close(thread, h2) == 0
print("reopen ok", flush=True)

# Optional: in-process HTTP server. Reported separately; does not fail the embedded smoke.
server_ok = False
try:
    t0 = T()
    rc = lib.arcadedb_server_start(thread, tmp.encode(), 2480, b"PlayWithData123!")
    if rc != 0:
        raise RuntimeError(last_error())
    results["server_start_ms"] = round((T() - t0) * 1e3, 1)
    with urllib.request.urlopen("http://127.0.0.1:2480/api/v1/ready", timeout=10) as resp:
        results["server_ready_status"] = resp.status
    try:
        with urllib.request.urlopen("http://127.0.0.1:2480/", timeout=10) as resp:
            body = resp.read(300).decode("utf-8", "replace")
            results["studio_root_status"] = resp.status
            results["studio_root_head"] = body[:80]
    except Exception as e:  # noqa: BLE001
        results["studio_root_error"] = repr(e)[:200]
    lib.arcadedb_server_stop(thread)
    server_ok = True
except Exception as e:  # noqa: BLE001
    results["server_error"] = repr(e)[:400]
results["server_ok"] = server_ok

results["rss_end_kb"] = vmrss_kb()
results["peak_rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
results["lib_size_bytes"] = os.path.getsize(lib_path)
print(json.dumps(results, indent=2))
print("SMOKE PASSED (embedded)")
os._exit(0)
