"""Many Python threads against one database and against one database each, on either backend.

Built for a free-threaded CPython (3.13t, 3.14t, no GIL) where Python threads run in parallel, but it also runs, and must
pass, with the GIL. Every thread runs the same deterministic workload (transactional inserts, numpy vector inserts, queries,
vector searches and, on the JPype backend, Python functions and record events), and the per-thread results and the final
database state are compared with a sequential run of the same workload.

    FT_THREADS=16 FT_REPEAT=50 python -X dev tests/test_free_threading.py      # as a script: repeat count, one line per scenario
    FT_THREADS=16 FT_REPEAT=3  pytest tests/test_free_threading.py             # as a test
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading

import arcadedb_embedded as arcadedb
import numpy as np
import pytest

THREADS = int(os.environ.get("FT_THREADS", "16"))
REPEAT = int(os.environ.get("FT_REPEAT", "1"))
ROWS = int(
    os.environ.get("FT_ROWS", "40")
)  # documents (and vertices with a vector) per thread
DIM = 8
BASE = 64  # vertices in the indexed type the searches run against
NATIVE = os.environ.get("ARCADEDB_BACKEND", "jpype").lower() == "native"
NN = "SELECT bid FROM (SELECT expand(vectorNeighbors('Base[embedding]', ?, ?)))"


def _val(tid, seq):
    return tid * 1000 + seq * 3 + 1


def _vec(tid, seq):
    """A float32 row far from the Base vectors (offset 1000), so a search for a Base vector never meets it."""
    return (np.random.default_rng(tid * 100003 + seq).random(DIM) + 1000.0).astype(
        np.float32
    )


def _base_vec(i):
    return np.random.default_rng(900001 + i).random(DIM).astype(np.float32)


def _mix(val, seq):
    return val * 31 + seq % 7


class Probes:
    """What the callbacks saw; the lock guards the call counter, the event list is appended to without one."""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = 0
        self.events = []  # (tid, seq) per after_create, appended without a lock

    def udf(self, val, seq):
        with self.lock:
            self.calls += 1
        return _mix(val, seq)

    def on_create(self, record):
        self.events.append((int(record.get("tid")), int(record.get("seq"))))


def _schema(db):
    db.command("sql", "CREATE DOCUMENT TYPE Doc")
    db.command("sql", "CREATE VERTEX TYPE Vec")
    db.command("sql", "CREATE VERTEX TYPE Base")
    db.command("sql", "CREATE PROPERTY Base.embedding ARRAY_OF_FLOATS")
    db.command("sql", "CREATE PROPERTY Vec.embedding ARRAY_OF_FLOATS")
    with db.transaction():
        for i in range(BASE):
            db.command(
                "sql", "CREATE VERTEX Base SET bid = ?, embedding = ?", i, _base_vec(i)
            )
    db.command(
        "sql",
        'CREATE INDEX ON Base (embedding) LSM_VECTOR METADATA {"dimensions": %d, "similarity": "EUCLIDEAN"}'
        % DIM,
    )


def _callbacks(db, probes, suffix):
    """Python function and event callbacks on this database (JPype backend only); returns the function name or None."""
    if NATIVE or not hasattr(db, "register_function"):
        return None
    name = f"py_mix{suffix}"
    db.register_function(name, probes.udf)
    db.on("after_create", probes.on_create, "Doc")
    return name


def _work(db, tid, udf_name):
    out = {"counts": [], "nn": []}
    for b in range(0, ROWS, 10):

        def batch(b=b):
            for s in range(b, min(b + 10, ROWS)):
                db.command(
                    "sql",
                    "INSERT INTO Doc SET tid = ?, seq = ?, val = ?",
                    tid,
                    s,
                    _val(tid, s),
                )
                db.command(
                    "sql",
                    "CREATE VERTEX Vec SET tid = ?, seq = ?, embedding = ?",
                    tid,
                    s,
                    _vec(tid, s),
                )

        # two threads that write the same page conflict at commit (ConcurrentModificationException): the engine's answer is a retry
        db.run_in_transaction(batch, retries=50)
        out["counts"].append(
            db.query("sql", "SELECT count(*) AS c FROM Doc WHERE tid = ?", tid)
            .first()
            .get("c")
        )
    out["rows"] = [
        (r["seq"], r["val"])
        for r in db.query(
            "sql", "SELECT seq, val FROM Doc WHERE tid = ? ORDER BY seq", tid
        ).to_list()
    ]
    out["vecs"] = [
        tuple(round(float(x), 3) for x in r["embedding"])
        for r in db.query(
            "sql", "SELECT embedding FROM Vec WHERE tid = ? ORDER BY seq", tid
        ).to_list()
    ]
    for j in range(6):
        i = (tid * 6 + j) % BASE
        out["nn"].append(
            (i, [int(r["bid"]) for r in db.query("sql", NN, _base_vec(i), 1).to_list()])
        )
    if udf_name:
        out["udf"] = [
            r["m"]
            for r in db.query(
                "sql",
                f"SELECT {udf_name}(val, seq) AS m FROM Doc WHERE tid = ? ORDER BY seq",
                tid,  # nosec B608
            ).to_list()
        ]
    return out


def _state(db):
    return (
        [
            tuple(r.values())
            for r in db.query(
                "sql",
                "SELECT tid, count(*) AS c, sum(val) AS s FROM Doc GROUP BY tid ORDER BY tid",
            ).to_list()
        ],
        db.query("sql", "SELECT count(*) AS c FROM Vec").first().get("c"),
    )


def _expect(tid):
    return {
        "counts": [min(b + 10, ROWS) for b in range(0, ROWS, 10)],
        "rows": [(s, _val(tid, s)) for s in range(ROWS)],
        "vecs": [tuple(round(float(x), 3) for x in _vec(tid, s)) for s in range(ROWS)],
        "nn": [((tid * 6 + j) % BASE, [(tid * 6 + j) % BASE]) for j in range(6)],
    }


def _check(tid, out, udf):
    for key, want in _expect(tid).items():
        assert (
            out[key] == want
        ), f"thread {tid}: {key} differs from the sequential result"
    if udf:
        assert out["udf"] == [
            _mix(_val(tid, s), s) for s in range(ROWS)
        ], f"thread {tid}: function results differ"


def _run_threads(n, target):
    errors, results = [], {}
    barrier = threading.Barrier(n)

    def run(tid):
        try:
            barrier.wait()
            results[tid] = target(tid)
        except BaseException as e:  # reported below with its thread
            errors.append((tid, repr(e)))

    threads = [threading.Thread(target=run, args=(t,)) for t in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    return results


def shared_database(tmp, n=THREADS):
    """One database, n threads; the final state equals the sequential run of the same workloads."""
    with arcadedb.create_database(os.path.join(tmp, "seq")) as db:
        _schema(db)
        probes = Probes()
        name = _callbacks(db, probes, "_seq")
        for tid in range(n):
            _check(tid, _work(db, tid, name), bool(name))
        seq_state = _state(db)
        seq_events = sorted(probes.events)
        if name:
            db.unregister_function(name)
    with arcadedb.create_database(os.path.join(tmp, "par")) as db:
        _schema(db)
        probes = Probes()
        name = _callbacks(db, probes, "_par")
        results = _run_threads(n, lambda tid: _work(db, tid, name))
        for tid, out in results.items():
            _check(tid, out, bool(name))
        assert _state(db) == seq_state
        if name:
            # an event fires per created record, also in an attempt that a commit conflict rolled back and a retry repeated
            assert (
                sorted(set(probes.events)) == seq_events
            ), "record events differ from the sequential run"
            assert probes.calls == n * ROWS, probes.calls
            db.unregister_function(name)


def database_per_thread(tmp, n=THREADS):
    """One database per thread (each with its own function name and event handler)."""

    def target(tid):
        with arcadedb.create_database(os.path.join(tmp, f"own{tid}")) as db:
            _schema(db)
            probes = Probes()
            name = _callbacks(db, probes, f"_own{tid}")
            out = _work(db, tid, name)
            _check(tid, out, bool(name))
            if name:
                assert sorted(set(probes.events)) == [
                    (tid, s) for s in range(ROWS)
                ], f"thread {tid}: events differ"
                assert probes.calls == ROWS
                db.unregister_function(name)
            assert _state(db)[1] == ROWS
            return out

    _run_threads(n, target)


def reopen_and_close_race(tmp, n=THREADS):
    """Threads open, read and close the same database path one after the other under contention; each read is exact."""
    path = os.path.join(tmp, "shared_open")
    with arcadedb.create_database(path) as db:
        _schema(db)
        with db.transaction():
            for s in range(ROWS):
                db.command(
                    "sql",
                    "INSERT INTO Doc SET tid = 0, seq = ?, val = ?",
                    s,
                    _val(0, s),
                )
    lock = (
        threading.Lock()
    )  # one database object per path in a process is the engine's rule: open one at a time

    def target(tid):
        for _ in range(3):
            with lock:
                with arcadedb.open_database(path) as db:
                    assert db.count_type("Doc") == ROWS
        return None

    _run_threads(n, target)


FIRST_START = textwrap.dedent("""
    import os, sys, threading
    import arcadedb_embedded as arcadedb
    n = int(sys.argv[1]); tmp = sys.argv[2]
    barrier = threading.Barrier(n); errors = []
    def run(tid):
        try:
            barrier.wait()
            with arcadedb.create_database(os.path.join(tmp, f"d{tid}")) as db:
                db.command("sql", "CREATE DOCUMENT TYPE T")
                with db.transaction():
                    db.command("sql", "INSERT INTO T SET a = ?", tid)
                assert db.query("sql", "SELECT a FROM T").first().get("a") == tid
        except BaseException as e:
            errors.append((tid, repr(e)))
    ts = [threading.Thread(target=run, args=(t,)) for t in range(n)]
    [t.start() for t in ts]; [t.join() for t in ts]
    print("FIRST_START", "ERRORS" if errors else "OK", errors[:3], flush=True)
    os._exit(1 if errors else 0)  # JPype 1.7.1 hangs at exit once a non-main thread has called Java
    """)


def first_start_race(tmp, n=THREADS):
    """The first call of every thread starts the JVM (or loads the library) in a fresh process: exactly one start wins."""
    script = os.path.join(tmp, "first_start.py")
    with open(script, "w") as f:
        f.write(FIRST_START)
    work = os.path.join(tmp, "fs")
    os.makedirs(work)
    r = subprocess.run(
        [sys.executable, script, str(n), work],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-3000:]


def proxy_classes_defined_once(tmp, n=THREADS):
    """Threads that register their first Python function or event together all get the one proxy class (JPype backend only)."""
    if NATIVE:
        return
    from arcadedb_embedded import callbacks
    from arcadedb_embedded.jvm import start_jvm

    start_jvm()
    for key, getter in (
        ("function", callbacks._function_proxy_class),
        ("event", callbacks._event_proxy_class),
    ):
        callbacks._PROXY_CLASSES.pop(key, None)
        classes = _run_threads(n, lambda tid, getter=getter: getter())
        assert (
            len({id(c) for c in classes.values()}) == 1
        ), f"{key}: {len({id(c) for c in classes.values()})} proxy classes were defined"


SCENARIOS = [
    shared_database,
    database_per_thread,
    reopen_and_close_race,
    first_start_race,
    proxy_classes_defined_once,
]


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="arcadedb_ft_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.__name__)
def test_threads(scenario, tmp):
    for rep in range(REPEAT):
        d = os.path.join(tmp, f"r{rep}")
        os.makedirs(d)
        scenario(d)


if __name__ == "__main__":
    gil = lambda: getattr(sys, "_is_gil_enabled", lambda: True)()
    print(
        f"FTSTRESS python={sys.version.split()[0]} gil={gil()} backend={'native' if NATIVE else 'jpype'} "
        f"threads={THREADS} repeat={REPEAT} rows={ROWS}",
        flush=True,
    )
    failed = 0
    only = os.environ.get("FT_ONLY")
    for scenario in SCENARIOS:
        if only and scenario.__name__ not in only.split(","):
            continue
        ok = 0
        for rep in range(REPEAT):
            d = tempfile.mkdtemp(prefix="arcadedb_ft_")
            try:
                scenario(d)
                ok += 1
            except (
                BaseException
            ) as e:  # keep going: the count of failing repeats is the result
                failed += 1
                print(
                    f"FTSTRESS FAIL {scenario.__name__} rep={rep}: {type(e).__name__}: {str(e)[:600]}",
                    flush=True,
                )
            finally:
                shutil.rmtree(d, ignore_errors=True)
        print(
            f"FTSTRESS {scenario.__name__}: {ok}/{REPEAT} repeats ok (gil={gil()})",
            flush=True,
        )
    print("FTSTRESS DONE failed=%d" % failed, flush=True)
    # JPype 1.7.1 hangs at interpreter exit once a non-main Python thread has called Java (also with the GIL, also on 3.12);
    # a result is printed, so leave without the shutdown
    os._exit(1 if failed else 0)
