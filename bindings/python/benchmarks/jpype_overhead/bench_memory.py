"""Round-4: memory-behavior measurements for the Python bindings.

Java-heap truth comes from MemoryMXBean (sampled after forced full GC on both
sides); process truth from /proc/self RSS. Each experiment prints:

  MEM,<experiment>,<metric>,<value>

Experiments:
  baseline    RSS/heap right after JVM start (what users misread as "Python bloat")
  rs-leak     10k undrained .first() queries: heap growth undrained vs drained
              vs explicitly closed — quantifies the missing ResultSet.close()
  pinning     100k Document wrappers held in a Python list vs converted dicts:
              pinned Java heap, and whether release returns it
  peaks       to_list vs to_json_list transient peak heap on a 100k-row scan

Usage: uv run python bench_memory.py <experiment> <docs_db_dir>
"""

import gc
import sys
import time

import arcadedb_embedded as arcadedb


def rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    return -1.0


def _jvm():
    import jpype

    mgmt = jpype.JClass("java.lang.management.ManagementFactory")
    system = jpype.JClass("java.lang.System")
    return mgmt, system


def heap_mb_after_gc() -> float:
    """Force both GCs, then read committed Java heap usage."""
    mgmt, system = _jvm()
    gc.collect()
    system.gc()
    time.sleep(0.2)
    system.gc()
    time.sleep(0.2)
    used = mgmt.getMemoryMXBean().getHeapMemoryUsage().getUsed()
    return float(used) / (1024 * 1024)


def reset_peak():
    mgmt, _ = _jvm()
    for pool in mgmt.getMemoryPoolMXBeans():
        try:
            pool.resetPeakUsage()
        except Exception:
            pass


def peak_heap_mb() -> float:
    mgmt, _ = _jvm()
    total = 0
    for pool in mgmt.getMemoryPoolMXBeans():
        if "heap" in str(pool.getType()).lower():
            total += int(pool.getPeakUsage().getUsed())
    return total / (1024 * 1024)


def exp_baseline(db_dir: str):
    rss_before = rss_mb()
    db = arcadedb.open_database(db_dir)  # starts the JVM
    print(f"MEM,baseline,rss_after_jvm_open_mb,{rss_mb():.0f}")
    print(f"MEM,baseline,rss_python_only_mb,{rss_before:.0f}")
    print(f"MEM,baseline,java_heap_used_mb,{heap_mb_after_gc():.0f}")
    db.close()


def exp_rs_leak(db_dir: str):
    with arcadedb.open_database(db_dir) as db:
        heap0 = heap_mb_after_gc()
        n = 10_000

        # variant A: undrained .first() — wrapper dropped immediately, Java
        # ResultSet never closed nor drained (the common bindings pattern)
        for _ in range(n):
            db.query("sql", "SELECT id, name FROM Doc LIMIT 10").first()
        heap_undrained_pre_gc = float(
            _jvm()[0].getMemoryMXBean().getHeapMemoryUsage().getUsed()
        ) / (1024 * 1024)
        heap_a = heap_mb_after_gc()

        # variant B: fully drained
        for _ in range(n):
            for _row in db.query("sql", "SELECT id, name FROM Doc LIMIT 10"):
                pass
        heap_b = heap_mb_after_gc()

        # variant C: undrained + explicit Java-side close
        for _ in range(n):
            rs = db.query("sql", "SELECT id, name FROM Doc LIMIT 10")
            rs.first()
            rs._java_result_set.close()
        heap_c = heap_mb_after_gc()

        print(f"MEM,rs-leak,heap_start_mb,{heap0:.0f}")
        print(f"MEM,rs-leak,heap_undrained_pre_gc_mb,{heap_undrained_pre_gc:.0f}")
        print(f"MEM,rs-leak,heap_after_10k_undrained_mb,{heap_a:.0f}")
        print(f"MEM,rs-leak,heap_after_10k_drained_mb,{heap_b:.0f}")
        print(f"MEM,rs-leak,heap_after_10k_closed_mb,{heap_c:.0f}")

        # sustained variant: does undrained keep growing linearly? 5 waves
        for wave in range(5):
            for _ in range(n):
                db.query("sql", "SELECT id, name FROM Doc LIMIT 10").first()
            print(f"MEM,rs-leak,heap_wave{wave}_mb,{heap_mb_after_gc():.0f}")


def exp_pinning(db_dir: str):
    with arcadedb.open_database(db_dir) as db:
        heap0 = heap_mb_after_gc()
        rss0 = rss_mb()

        # hold 100k wrapper objects (each pins a Java record)
        wrappers = [row for row in db.query("sql", "SELECT FROM Doc LIMIT 100000")]
        heap_held = heap_mb_after_gc()
        rss_held = rss_mb()
        print(f"MEM,pinning,heap_start_mb,{heap0:.0f}")
        print(f"MEM,pinning,heap_100k_wrappers_held_mb,{heap_held:.0f}")
        print(f"MEM,pinning,rss_100k_wrappers_held_mb,{rss_held:.0f}")
        print(
            f"MEM,pinning,pinned_java_bytes_per_row,{(heap_held - heap0) * 1024 * 1024 / 100000:.0f}"
        )

        del wrappers
        heap_released = heap_mb_after_gc()
        print(f"MEM,pinning,heap_after_release_mb,{heap_released:.0f}")

        # same rows as plain dicts (no Java references held)
        dicts = db.query("sql", "SELECT FROM Doc LIMIT 100000").to_json_list()
        heap_dicts = heap_mb_after_gc()
        rss_dicts = rss_mb()
        print(f"MEM,pinning,heap_100k_dicts_held_mb,{heap_dicts:.0f}")
        print(f"MEM,pinning,rss_100k_dicts_held_mb,{rss_dicts:.0f}")
        del dicts
        print(f"MEM,pinning,rss_start_mb,{rss0:.0f}")


def exp_peaks(db_dir: str):
    with arcadedb.open_database(db_dir) as db:
        sql = "SELECT id, score, name, category, active, created, counts FROM Doc LIMIT 100000"

        reset_peak()
        rows = db.query("sql", sql).to_list()
        print(f"MEM,peaks,to_list_peak_heap_mb,{peak_heap_mb():.0f}")
        print(f"MEM,peaks,to_list_rss_mb,{rss_mb():.0f}")
        del rows
        heap_mb_after_gc()

        reset_peak()
        rows = db.query("sql", sql).to_json_list()
        print(f"MEM,peaks,to_json_list_peak_heap_mb,{peak_heap_mb():.0f}")
        print(f"MEM,peaks,to_json_list_rss_mb,{rss_mb():.0f}")
        del rows


if __name__ == "__main__":
    exp, db_dir = sys.argv[1], sys.argv[2]
    {
        "baseline": exp_baseline,
        "rs-leak": exp_rs_leak,
        "pinning": exp_pinning,
        "peaks": exp_peaks,
    }[exp](db_dir)
