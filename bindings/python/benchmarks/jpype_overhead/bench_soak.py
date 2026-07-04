"""Memory soak: sustained mixed workload with heap/RSS sampled on a timeline.

Cycles point-reads, scans (to_json_list), vector-style array round-trips,
inserts and updates against the docs DB for --minutes, sampling Java heap
(post-GC every Nth sample), raw heap, and RSS every 15s to a CSV. A leak shows
as monotonic post-GC heap growth; GC pressure as widening raw-vs-postGC gap.

Usage: uv run python bench_soak.py <docs_db_dir> <minutes> <out_csv>
"""

import gc
import random
import sys
import time

import arcadedb_embedded as arcadedb

db_dir, minutes, out_csv = sys.argv[1], float(sys.argv[2]), sys.argv[3]


def rss_mb():
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return -1.0


with arcadedb.open_database(db_dir) as db, open(out_csv, "w") as out:
    import jpype

    mgmt = jpype.JClass("java.lang.management.ManagementFactory")
    system = jpype.JClass("java.lang.System")
    bean = mgmt.getMemoryMXBean()

    try:
        db.command("sql", "CREATE INDEX ON Doc (id) UNIQUE")
    except Exception:
        pass

    out.write("elapsed_s,ops,heap_raw_mb,heap_postgc_mb,rss_mb\n")
    rnd = random.Random(7)
    start = time.time()
    next_sample = start
    ops = 0
    sample_i = 0
    deadline = start + minutes * 60

    while time.time() < deadline:
        roll = rnd.random()
        if roll < 0.6:
            for _r in db.query("sql", "SELECT score FROM Doc WHERE id = ?", rnd.randrange(100_000)):
                pass
        elif roll < 0.8:
            db.query("sql", "SELECT id, name, category FROM Doc LIMIT 2000").to_json_list()
        elif roll < 0.9:
            db.query("sql", "SELECT embedding FROM Doc LIMIT 500").to_list()
        else:
            with db.transaction():
                db.command(
                    "sql", "UPDATE Doc SET score = score + 1 WHERE id = ?", rnd.randrange(100_000)
                )
        ops += 1

        now = time.time()
        if now >= next_sample:
            raw = float(bean.getHeapMemoryUsage().getUsed()) / 1048576
            postgc = -1.0
            if sample_i % 4 == 0:  # full dual-GC only every minute
                gc.collect()
                system.gc()
                time.sleep(0.1)
                postgc = float(bean.getHeapMemoryUsage().getUsed()) / 1048576
            out.write(f"{now - start:.0f},{ops},{raw:.0f},{postgc:.0f},{rss_mb():.0f}\n")
            out.flush()
            sample_i += 1
            next_sample = now + 15

    print(f"SOAK,done,ops={ops},minutes={minutes}", flush=True)
