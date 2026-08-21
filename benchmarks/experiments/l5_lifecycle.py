"""L5: what it costs to OPEN and CLOSE a database, by what is in it.

WHY THIS IS A LANE AND NOT A PROBE. Opening and closing is the one operation
every embedded deployment performs and no benchmark measures, and this engine
has produced three defects in it: #5747 (a session that never ran a vector
search paid a full HNSW rebuild on close), #6489 (a build that orphaned any node
left the index MUTABLE, so close rebuilt the whole graph; ours, fixed by PR
#6490) and #5872 (close does not reliably cancel an in-flight build). A number
that can slide from 8 ms to 30 s between releases with nobody watching is what a
regression gate is for.

THE INVARIANT, from lifecycle-open-close.md and DECISIONS #50:

    Close should be O(what was written), not O(what is stored),
    and on the order of 100 ms.

Grounded twice: close should not cost more than getting started, and JVM startup
here is ~160 ms; and it should sit under the ~100 ms at which a script stops
feeling instant. Eight of the ten situations in the original matrix already
satisfy it, which is worth stating positively -- the multi-model substrate
closes cheaply and two optional accelerators do not.

WHAT EACH SITUATION EARNS ITS PLACE FOR:
  empty        the floor: what close costs with nothing in the database
  doc          records only, no index
  doc_idx10    the per-index cost (~0.4 ms/index, and it is I/O: it vanishes
               on tmpfs, which is how it was separated from the compute cost)
  graph        vertices and edges, no accelerator
  graph_gav    the Graph Analytical View, whose CSR is re-derived every open
  vector       the JVector HNSW graph, the worst case historically
  sparse       LSM_SPARSE_VECTOR, which is NOT affected and must be shown so
  ts           the time-series type, likewise

THREE MODES, because the read mode changes the picture completely. v1 of this
matrix measured open-then-close WITHOUT EVER QUERYING and inflated the vector
rows by up to 617x, because a session that never touches the index leaves it in
a state close then has to resolve. That is not a neutral protocol, it is one
specific case (#5747), so all three are measured and reported separately.
"""
import argparse
import json
import os
import statistics as st
import sys
import time

import bench_common
import pagecache

DB = "/lcdb/lc"          # a HOST directory bind-mounted here; see _assert_fs
DIM = 64
ITERS = int(os.environ.get("BENCH_LC_ITERS", "3"))
WARMUP = int(os.environ.get("BENCH_LC_WARMUP", "1"))

SCALE_ROWS = {"lc10k": 10_000, "lc100k": 100_000}

SITUATIONS = ["empty", "doc", "doc_idx10", "graph", "graph_gav",
              "vector", "sparse", "ts"]


def _assert_fs():
    """Refuse to report a cold column from a filesystem that cannot go cold.

    posix_fadvise cannot evict a container's overlay upper layer, and tmpfs
    pages ARE memory so there is nothing to evict. Either placement yields a
    'cold' open indistinguishable from a warm one, which is a fabricated
    number rather than a failed measurement. Both hosts run the overlayfs
    storage driver and have /tmp on tmpfs, so this is a live hazard, not a
    hypothetical one.
    """
    real = os.path.realpath(os.path.dirname(DB))
    best = ("", "")
    for line in open("/proc/mounts"):
        f = line.split()
        if real == f[1] or real.startswith(f[1].rstrip("/") + "/"):
            if len(f[1]) > len(best[0]):
                best = (f[1], f[2])
    fs = best[1]
    if fs in ("overlay", "overlayfs", "tmpfs", ""):
        sys.stderr.write(
            f"l5_lifecycle: {os.path.dirname(DB)} is {fs!r}. A cold open cannot "
            "be measured there: fadvise does not evict an overlay upper layer, "
            "and tmpfs pages are memory. The bind mount is missing or points at "
            "the wrong host directory. Refusing to fabricate a cold column.\n")
        os._exit(1)
    return fs


def _rm(p):
    import shutil
    if os.path.isdir(p):
        shutil.rmtree(p)


def build(situation, n, heap):
    """Create the database for `situation` at `n` rows, then close it."""
    import arcadedb_embedded as arcadedb
    _rm(DB)
    db = arcadedb.create_database(
        DB, jvm_kwargs={"heap_size": heap, "jvm_args": f"-Xms{heap}"})
    c = db.command
    # ONE scratch type in every situation, holding no rows, so the write mode
    # is the SAME operation everywhere: insert one document, commit, close.
    # That is what makes the dirty-minus-clean delta comparable across
    # situations -- it isolates the fixed commit-and-close tax (~15.6 ms in the
    # original matrix) from anything the situation itself contributes. Creating
    # the type per iteration instead would time a schema change, and would fail
    # on the second iteration with "Type Scratch already exists".
    c("sql", "CREATE DOCUMENT TYPE Scratch")
    c("sql", "CREATE PROPERTY Scratch.n INTEGER")
    if situation == "empty":
        pass
    elif situation == "doc":
        c("sql", "CREATE DOCUMENT TYPE D")
        c("sql", "CREATE PROPERTY D.id INTEGER")
        _bulk(db, "INSERT INTO D SET id = %d", n)
    elif situation == "doc_idx10":
        c("sql", "CREATE DOCUMENT TYPE D")
        for i in range(10):
            c("sql", f"CREATE PROPERTY D.p{i} INTEGER")
            c("sql", f"CREATE INDEX ON D (p{i}) NOTUNIQUE")
        _bulk(db, "INSERT INTO D SET " + ", ".join(
            f"p{i} = %d" for i in range(10)), n, nargs=10)
    elif situation in ("graph", "graph_gav"):
        c("sql", "CREATE VERTEX TYPE P")
        c("sql", "CREATE PROPERTY P.id INTEGER")
        c("sql", "CREATE EDGE TYPE E")
        _bulk(db, "CREATE VERTEX P SET id = %d", n)
        # A fanout of 4, not a ring: a ring gives one two-hop path per vertex,
        # too little work for an accelerator to matter either way.
        db.begin()
        for i in range(n):
            for f in range(1, 5):
                c("sql", f"CREATE EDGE E FROM (SELECT FROM P WHERE id = {i}) "
                         f"TO (SELECT FROM P WHERE id = {(i + f * 7919) % n})")
            if (i + 1) % 2000 == 0:
                db.commit(); db.begin()
        db.commit()
        if situation == "graph_gav":
            c("sql", "CREATE GRAPH ANALYTICAL VIEW lcv VERTEX TYPES (P) "
                     "EDGE TYPES (E) PROPERTIES (id) UPDATE MODE OFF")
            _await_gav(db)
    elif situation == "vector":
        c("sql", "CREATE VERTEX TYPE V")
        c("sql", "CREATE PROPERTY V.id INTEGER")
        c("sql", "CREATE PROPERTY V.emb ARRAY_OF_FLOATS")
        _vectors(db, n)
        c("sql", f'CREATE INDEX ON V (emb) LSM_VECTOR METADATA '
                 f'{{ "dimensions": {DIM}, "similarity": "COSINE" }}')
    elif situation == "sparse":
        c("sql", "CREATE DOCUMENT TYPE S")
        c("sql", "CREATE PROPERTY S.tokens ARRAY_OF_INTEGERS")
        c("sql", "CREATE PROPERTY S.weights ARRAY_OF_FLOATS")
        _sparse(db, n)
        c("sql", "CREATE INDEX ON S (tokens, weights) LSM_SPARSE_VECTOR "
                 'METADATA { "dimensions": 30000 }')
    elif situation == "ts":
        c("sql", "CREATE TIMESERIES TYPE T")
        c("sql", "CREATE PROPERTY T.value DOUBLE")
        _bulk(db, "INSERT INTO T SET timestamp = %d, value = 1.0", n)
    else:
        raise SystemExit(f"unknown situation {situation}")
    db.close()


def _bulk(db, tmpl, n, nargs=1):
    db.begin()
    for i in range(n):
        db.command("sql", tmpl % ((i,) * nargs if nargs > 1 else i))
        if (i + 1) % 5000 == 0:
            db.commit(); db.begin()
    db.commit()


def _vectors(db, n):
    import random
    rnd = random.Random(17)
    db.begin()
    for i in range(n):
        v = ", ".join("%.6f" % rnd.random() for _ in range(DIM))
        db.command("sql", f"CREATE VERTEX V SET id = {i}, emb = [{v}]")
        if (i + 1) % 2000 == 0:
            db.commit(); db.begin()
    db.commit()


def _sparse(db, n):
    import random
    rnd = random.Random(23)
    db.begin()
    for i in range(n):
        toks = sorted(rnd.sample(range(30000), 40))
        t = ", ".join(str(x) for x in toks)
        w = ", ".join("%.6f" % rnd.random() for _ in toks)
        db.command("sql", f"INSERT INTO S SET tokens = [{t}], weights = [{w}]")
        if (i + 1) % 2000 == 0:
            db.commit(); db.begin()
    db.commit()


def _await_gav(db, timeout_s=900):
    t0 = time.time()
    while True:
        rs = db.query("sql", "SELECT FROM schema:graphAnalyticalViews "
                             "WHERE name = 'lcv'")
        rows = list(rs)
        if rows and str(rows[0].get("status")) == "READY":
            return
        if time.time() - t0 > timeout_s:
            raise SystemExit("GAV never became READY")
        time.sleep(0.05)


READS = {
    "doc":       "SELECT count(*) FROM D",
    "doc_idx10": "SELECT FROM D WHERE p0 = 5 LIMIT 10",
    "graph":     "SELECT count(*) FROM (SELECT expand(out('E')) FROM P LIMIT 100)",
    "graph_gav": "SELECT count(*) FROM (SELECT expand(out('E').out('E')) FROM P LIMIT 100)",
    "vector":    None,     # filled in at runtime, needs a probe vector
    "sparse":    "SELECT count(*) FROM S LIMIT 10",
    "ts":        "SELECT count(*) FROM T",
}


def _read(db, situation):
    if situation == "empty":
        return
    if situation == "vector":
        v = ", ".join("0.5" for _ in range(DIM))
        list(db.query("sql", f"SELECT FROM (SELECT expand(vectorNeighbors("
                             f"'V[emb]', [{v}], 10)))"))
        return
    q = READS.get(situation)
    if q:
        list(db.query("sql", q))


_WRITE_SEQ = [0]


def _write(db, situation):
    """One document into Scratch, in every situation.

    Deliberately NOT a write into the situation's own structure. Inserting a
    vector would make the vector row's dirty close include an index update
    while the doc row's did not, and the delta would then price two different
    things under one name. The question this mode asks is "what does committing
    ANYTHING cost at close", so the anything is held constant.
    """
    _WRITE_SEQ[0] += 1
    db.begin()
    db.command("sql", f"INSERT INTO Scratch SET n = {_WRITE_SEQ[0]}")
    db.commit()


def cycle(situation, mode, cold=False):
    """One open/close cycle. Returns (open_ms, close_ms)."""
    import arcadedb_embedded as arcadedb
    if cold:
        # Verified eviction: evict() raises if pages survive, so a cold number
        # cannot be reported for a database that was still cached.
        pagecache.evict(DB)
    t0 = time.perf_counter()
    db = arcadedb.open_database(DB)
    t1 = time.perf_counter()
    if mode == "read":
        _read(db, situation)
    elif mode == "write":
        _write(db, situation)
    t2 = time.perf_counter()
    db.close()
    t3 = time.perf_counter()
    return (t1 - t0) * 1000, (t3 - t2) * 1000


def measure(situation, mode, cold=False):
    o, c = [], []
    for i in range(WARMUP + ITERS):
        a, b = cycle(situation, mode, cold=cold)
        if i < WARMUP:
            continue
        o.append(a); c.append(b)
    return st.median(o), st.median(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True)
    ap.add_argument("--workload", required=True, choices=SITUATIONS)
    ap.add_argument("--scale", default="lc10k", choices=list(SCALE_ROWS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    fs = _assert_fs()
    n = SCALE_ROWS[args.scale]
    heap = os.environ.get("BENCH_HEAP", "8g")

    t0 = time.perf_counter()
    build(args.workload, n, heap)
    build_s = round(time.perf_counter() - t0, 3)

    out = bench_common.run_conditions(
        lane="lifecycle", backend=args.backend, workload=args.workload,
        scale=args.scale, n_rows=n, dims=DIM, fs_type=fs,
        lc_iters=ITERS, lc_warmup=WARMUP, build_s=build_s)

    # Cold FIRST, while the build's pages are the only thing that could be
    # cached: running it after the warm modes would measure an eviction of a
    # database that several cycles had just re-warmed, which is the same
    # number by construction but a weaker claim.
    o, c = measure(args.workload, "clean", cold=True)
    out["cold_open_ms"], out["cold_close_ms"] = round(o, 3), round(c, 3)

    for mode in ("clean", "read", "write"):
        o, c = measure(args.workload, mode)
        out[f"{mode}_open_ms"] = round(o, 3)
        out[f"{mode}_close_ms"] = round(c, 3)

    # The invariant, evaluated where the number is produced rather than left to
    # a downstream reader: close should be O(what was written), so a clean
    # close (nothing written) over 100 ms is a finding regardless of size.
    out["close_over_budget"] = out["clean_close_ms"] > 100.0

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"RESULT {json.dumps(out)[:400]}")


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(1)
