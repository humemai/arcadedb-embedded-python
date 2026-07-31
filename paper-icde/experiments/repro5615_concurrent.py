"""#5615 with the condition robfrank actually identified: rebuilds in flight.

My first attempt ran 900 trials of create-index / insert-4 / query and found
nothing, and I reported that as "Linux does not reproduce it". Reading his
third round properly, that harness never created the condition: his control
is 20 settled graphs and 36,000 self-queries with 0 misses, and what survives
is "a search misses a vector that is fully indexed, correctly mapped and
correctly scored, ONLY WHILE REBUILDS ARE RUNNING".

So drive rebuilds continuously and query across them. mutations_before_rebuild
is settable per index, so a low value keeps the rebuild path hot while readers
search for vectors that were committed long before and must always be found.

A miss here is unambiguous for the same reason his is: the query IS one of the
committed vectors, so the nearest neighbour must be that vector at distance ~0.

    TRIALS=... WRITERS=... READERS=... python repro5615_concurrent.py
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import random as _random
import math as _math

import arcadedb_embedded as arcadedb

SECONDS = float(os.environ.get("SECONDS", "60"))
WRITERS = int(os.environ.get("WRITERS", "1"))
READERS = int(os.environ.get("READERS", "3"))
BASE = int(os.environ.get("BASE", "400"))     # committed up front, must persist
DIM = 8

stop = threading.Event()
misses, errors, queries, writes, rebuild_hint = [], [], [0], [0], []
lock = threading.Lock()


def vec(i):
    """Deterministic unit vectors, well separated in ANGLE.

    Third attempt at this function, and the first two failures were the same
    mistake: a generator degenerate for the metric actually in use. The index
    defaults to COSINE, which ignores magnitude.
      1. (i*7 + j*3) % 97 had period 97, so ids 0/97/194 were identical.
      2. base-16 digits made vec(0) the zero vector (COSINE rejects it) and
         made every small id a multiple of e1, so all of them were parallel
         and at cosine distance 0 from each other.
    Gaussian components normalised to unit length give distinct directions,
    never a zero vector, and are reproducible from the id alone.
    """
    rnd = _random.Random(i * 2654435761 + 12345)
    v = [rnd.gauss(0.0, 1.0) for _ in range(DIM)]
    n = _math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def attach():
    try:
        import jpype
        if not jpype.isThreadAttachedToJVM():
            jpype.attachThreadToJVM()
    except Exception:
        pass


def writer(db, tid):
    """Single writer, explicit transactions. The first version called
    db.command from several threads with no transaction and every write failed
    with "Transaction not begun", so no rebuild ever ran and the whole point
    of the harness was lost while it still printed a result."""
    attach()
    n = BASE + tid * 1000000
    while not stop.is_set():
        try:
            db.begin()
            for _ in range(10):
                db.command("sql", "INSERT INTO V SET vid = ?, embedding = ?",
                           n, arcadedb.to_java_float_array(vec(n)))
                n += 1
            db.commit()
            with lock:
                writes[0] += 10
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            with lock:
                errors.append(f"writer{tid}: {e.__class__.__name__}: {e}")
            time.sleep(0.02)


def reader(db, idx, tid):
    attach()
    i = 0
    while not stop.is_set():
        target = i % BASE
        try:
            got = idx.find_nearest(arcadedb.to_java_float_array(vec(target)), k=3)
            names = [r[0].get("vid") for r in got]
            with lock:
                queries[0] += 1
            if target not in names:
                with lock:
                    misses.append((target, list(names)))
                print(f"  MISS vid={target} not in {names}", flush=True)
        except Exception as e:
            with lock:
                errors.append(f"reader{tid}: {e.__class__.__name__}: {e}")
            time.sleep(0.01)
        i += 1


def main():
    root = tempfile.mkdtemp(prefix="r5615c_")
    db = arcadedb.create_database(os.path.join(root, "db"),
                                  jvm_kwargs={"heap_size": "3g"})
    try:
        db.command("sql", "CREATE DOCUMENT TYPE V")
        db.command("sql", "CREATE PROPERTY V.vid INTEGER")
        db.command("sql", "CREATE PROPERTY V.embedding ARRAY_OF_FLOATS")
        # low threshold = the rebuild path stays hot, which is the condition
        idx = db.create_vector_index("V", "embedding", dimensions=DIM,
                                     mutations_before_rebuild=5)
        db.begin()
        for i in range(BASE):
            db.command("sql", "INSERT INTO V SET vid = ?, embedding = ?",
                       i, arcadedb.to_java_float_array(vec(i)))
        db.commit()
        print(f"  committed {BASE} base vectors; "
              f"{WRITERS} writers + {READERS} readers for {SECONDS:.0f}s",
              flush=True)

        ts = ([threading.Thread(target=writer, args=(db, i), daemon=True)
               for i in range(WRITERS)] +
              [threading.Thread(target=reader, args=(db, idx, i), daemon=True)
               for i in range(READERS)])
        for t in ts:
            t.start()
        time.sleep(SECONDS)
        stop.set()
        for t in ts:
            t.join(timeout=10)

        print(f"\nRESULT engine={arcadedb.__version__}")
        print(f"  {queries[0]:,} queries, {writes[0]:,} writes")
        print(f"  {len(misses)} MISS(es), {len(errors)} error(s)")
        for m in misses[:10]:
            print("   ", m)
        seen = set()
        for e in errors:
            k = e.split(":")[0] + e.split(":")[1] if ":" in e else e
            if k not in seen:
                seen.add(k)
                print("    err:", e[:160])
    finally:
        try:
            db.close()
        except Exception:
            pass
        shutil.rmtree(root, ignore_errors=True)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
