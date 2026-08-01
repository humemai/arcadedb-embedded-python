#!/usr/bin/env python3
"""E4's deployment axis measures embedded vs Docker-server, which is two costs
added together. This separates them.

The paper's deployment claim compares the wheel running in-process against the
`arcadedata/arcadedb` container over HTTP. That delta bundles:

  (a) the HTTP/JSON protocol: serialise a result set, push it through a socket,
      parse it back into Python objects; and
  (b) the process boundary: a second OS process, a second JVM with its own
      heap and GC, a second page cache, a container's cpuset and memory cap.

Both are real costs of the server deployment, but they have different fixes and
different lessons, and the current pair cannot tell you which dominates.

Server mode restored in 26.8.1.dev24 supplies the missing middle point. An
in-process server is served BY THE SAME PROCESS that holds the embedded handle:
one JVM, one heap, one GC, one engine instance, one page cache, one cpuset. So

    embedded -> in-process HTTP   = protocol only, everything else held fixed
    in-process HTTP -> Docker     = boundary only, protocol held fixed

and the two deltas sum to the number E4 already reports. The parity matrix in
PROTOCOL.md is satisfied by construction for the first pair rather than by
pinning heap/GC/JDK on two sides and hoping.

FAIRNESS: WHICH EMBEDDED MATERIALISATION.
An HTTP client receives a JSON body and parses it into a list of dicts. The
embedded arm must therefore be measured with `to_json_list()`, which produces
that same shape. Using `to_list()`/`iter_dicts()` (per-row JPype crossings) or
`to_columns()` (columnar, no dicts at all) would fold a materialisation-path
difference into a number labelled "transport" -- the exact error catalogued in
task #115, where lanes differ by 15-17x purely on this axis. So the embedded
arm is deliberately NOT run at its fastest available path here; it is run at
the path that returns what HTTP returns.

WHY A SWEEP AND NOT A NUMBER.
Protocol cost is dominated by serialise/parse, which scales with result size,
while boundary cost is closer to a fixed per-request charge. A single row count
would produce a ratio true only at that size. The sweep makes the crossover
visible instead of asserting it.

The Docker arm is optional (--docker URL). Without it the probe still answers
the protocol half, which is the half the new server mode unlocks.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import time

from bench_common import latstats, run_conditions

SIZES = [int(x) for x in os.environ.get("SIZES", "1,10,100,1000,10000,100000").split(",")]
ROWS = int(os.environ.get("ROWS", "200000"))
REPS = int(os.environ.get("REPS", "9"))
WARMUP = int(os.environ.get("WARMUP", "3"))
DB_NAME = "deploy_decomp"
PASSWORD = os.environ.get("BENCH_ROOT_PASSWORD", "deploy_decomp_pw_1")

SCHEMA = [
    "CREATE DOCUMENT TYPE orders",
    "CREATE PROPERTY orders.id LONG",
    "CREATE PROPERTY orders.customer_id LONG",
    "CREATE PROPERTY orders.amount DOUBLE",
    "CREATE PROPERTY orders.region STRING",
]


def query(n: int) -> str:
    return f"SELECT id, customer_id, amount, region FROM orders LIMIT {n}"


def gen_rows(total: int):
    for i in range(total):
        yield {
            "id": i,
            "customer_id": i % 1000,
            "amount": (i * 37 % 100000) / 100.0,
            "region": f"r{i % 8}",
        }


def load_embedded(db, total: int) -> None:
    for stmt in SCHEMA:
        db.command("sql", stmt)
    db.begin()
    buf = []
    for row in gen_rows(total):
        buf.append(row)
        if len(buf) >= 50_000:
            db.insert_many("orders", buf, commit_every=10_000)
            buf = []
    if buf:
        db.insert_many("orders", buf, commit_every=10_000)
    db.commit()


def timeit(fn, n: int, reps: int, warmup: int) -> tuple[list[float], int]:
    got = -1
    for _ in range(warmup):
        got = fn(n)
    lat = []
    for _ in range(reps):
        t0 = time.perf_counter()
        got = fn(n)
        lat.append((time.perf_counter() - t0) * 1000.0)
    return lat, got


def timeit_paired(fns: dict, n: int, reps: int, warmup: int) -> dict:
    """Interleave the arms at one size, after warming EVERY arm at that size.

    Running arm-by-arm (all embedded sizes, then all HTTP sizes) biases the
    comparison two ways, both measured: the arm that runs second inherits a JVM
    the first arm already warmed, and early sizes in a sweep are colder than
    late ones. At 1000 rows that read 6.830 ms when reached after 1/10/100 and
    2.724 ms when reached after four larger sizes, a 2.5x artifact in the arm
    that was supposed to be the baseline.

    So: warm all arms at this size first, then alternate one timed rep per arm
    per round. Any residual drift (JIT, thermal, page cache) then lands on both
    arms in the same proportion instead of on whichever ran first.
    """
    for _ in range(warmup):
        for fn in fns.values():
            fn(n)
    lat = {k: [] for k in fns}
    got = {k: -1 for k in fns}
    for _ in range(reps):
        for k, fn in fns.items():          # one rep of each, round-robin
            t0 = time.perf_counter()
            got[k] = fn(n)
            lat[k].append((time.perf_counter() - t0) * 1000.0)
    return {k: (lat[k], got[k]) for k in fns}


def http_runner(session, base_url: str, auth, db_name: str):
    """One HTTP query, returning the parsed row count.

    Deliberately counts JSON parsing: a caller cannot use the rows without it,
    so excluding it would measure a result nobody receives.
    """

    def run(n: int) -> int:
        r = session.post(
            f"{base_url}/api/v1/query/{db_name}",
            auth=auth,
            # "limit": -1 is REQUIRED, not tuning. The serializer caps at
            # AbstractQueryHandler.DEFAULT_LIMIT (20,000) and truncates silently:
            # HTTP 200, no flag, no count, and the SQL LIMIT the query asked for
            # is overridden. Without this the 100k cell returned 20k rows and
            # looked 4.7x FASTER than embedded, which is the row-count guard's
            # whole reason for existing. Filed upstream as #5711.
            json={"language": "sql", "command": query(n), "limit": -1},
            timeout=300,
        )
        r.raise_for_status()
        return len(r.json().get("result", []))

    return run


def report(results: dict) -> None:
    arms = [a for a in ("embedded", "inproc_http", "docker_http") if a in results]
    print()
    print(f"{'rows':>8}  " + "  ".join(f"{a:>16}" for a in arms))
    for n in SIZES:
        cells = []
        for a in arms:
            v = results[a].get(n)
            cells.append(f"{v['p50_ms']:>13.3f} ms" if v else f"{'-':>16}")
        print(f"{n:>8}  " + "  ".join(cells))

    if "inproc_http" in results and "embedded" in results:
        print("\nDECOMPOSITION (ms added over embedded, and as a multiple):")
        hdr = f"{'rows':>8}  {'protocol':>22}"
        if "docker_http" in results:
            hdr += f"  {'boundary':>22}  {'total (E4)':>22}"
        print(hdr)
        for n in SIZES:
            e = results["embedded"].get(n)
            i = results["inproc_http"].get(n)
            if not (e and i):
                continue
            proto = i["p50_ms"] - e["p50_ms"]
            line = f"{n:>8}  {proto:>+11.3f} ({i['p50_ms']/e['p50_ms']:.2f}x)"
            d = results.get("docker_http", {}).get(n)
            if d:
                bound = d["p50_ms"] - i["p50_ms"]
                tot = d["p50_ms"] - e["p50_ms"]
                line += (f"  {bound:>+11.3f} ({d['p50_ms']/i['p50_ms']:.2f}x)"
                         f"  {tot:>+11.3f} ({d['p50_ms']/e['p50_ms']:.2f}x)")
            print(line)
        print("\nprotocol = embedded -> in-process HTTP (same JVM, heap, GC, page cache)")
        if "docker_http" in results:
            print("boundary = in-process HTTP -> Docker (second process/JVM/page cache)")
            print("total    = what E4 reports today, now split into its two parts")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--docker", metavar="URL",
                    help="base URL of an already-running arcadedata/arcadedb "
                         "server holding the same corpus, e.g. http://localhost:2480")
    ap.add_argument("--docker-password", default=PASSWORD)
    ap.add_argument("--heap", default=os.environ.get("HEAP", "6g"))
    ap.add_argument("--out", default=os.environ.get("OUT", "results/deploy_decomp.json"))
    ap.add_argument("--root", default=os.path.expanduser("~/.cache/deploy_decomp_root"))
    args = ap.parse_args()

    import requests
    import arcadedb_embedded as arcadedb

    results: dict[str, dict] = {}
    meta = {
        "engine_version": arcadedb.__version__,
        "rows": ROWS,
        "sizes": SIZES,
        "reps": REPS,
        "warmup": WARMUP,
        "heap": args.heap,
        "embedded_materialisation": "to_json_list",
        "note": "embedded arm uses to_json_list so all three arms return list-of-dicts",
    }
    print(f"engine {arcadedb.__version__}  corpus {ROWS:,} rows  "
          f"reps {REPS} (+{WARMUP} warmup)  heap {args.heap}", flush=True)

    import shutil
    shutil.rmtree(args.root, ignore_errors=True)

    # create_server() takes no jvm_kwargs (create_database() does), so the heap
    # has to be pinned on the JVM before the server exists. Same -Xms=-Xmx
    # policy as every other lane: fixed heap for latency parity, with the
    # working set reported separately from cgroup anon.
    from arcadedb_embedded.jvm import start_jvm
    start_jvm(heap_size=args.heap, jvm_args=[f"-Xms{args.heap}"])

    # Arms 1 and 2 share this process, so they share the JVM, heap, GC, engine
    # instance and page cache. That sharing IS the control.
    with arcadedb.create_server(
        args.root,
        root_password=PASSWORD,
        config={"host": "127.0.0.1", "http_port": 2489, "mode": "development"},
    ) as server:
        db = server.create_database(DB_NAME)
        load_embedded(db, ROWS)
        print(f"loaded {ROWS:,} rows into the server-managed database", flush=True)

        port = server.get_http_port()
        base = f"http://127.0.0.1:{port}"
        sess = requests.Session()
        auth = ("root", PASSWORD)
        # The first request after start() pays a one-time warmup (lazy class
        # loading plus the password KDF); WARMUP absorbs it, but poke it once
        # here so the first sweep entry is not the one that eats it.
        sess.get(f"{base}/api/v1/server", auth=auth, timeout=120)

        run_http = http_runner(sess, base, auth, DB_NAME)
        arms = {
            "embedded": lambda k: len(db.query("sql", query(k)).to_json_list()),
            "inproc_http": run_http,
        }
        results["embedded"] = {}
        results["inproc_http"] = {}
        for n in SIZES:
            paired = timeit_paired(arms, n, REPS, WARMUP)
            line = f"  {n:>7} rows "
            for arm, (lat, got) in paired.items():
                st = latstats("x", lat)
                results[arm][n] = {"p50_ms": st["x_p50_ms"], "rows_returned": got,
                                   **{k[2:]: v for k, v in st.items()}}
                line += f"  {arm} {st['x_p50_ms']:8.3f} ms"
            print(line, flush=True)

        meta.update(run_conditions(lane="e4_decomp", role="embedded+inproc_server"))

    if args.docker:
        sess = requests.Session()
        auth = ("root", args.docker_password)
        run_http = http_runner(sess, args.docker.rstrip("/"), auth, DB_NAME)
        results["docker_http"] = {}
        for n in SIZES:
            lat, got = timeit(run_http, n, REPS, WARMUP)
            s = latstats("x", lat)
            results["docker_http"][n] = {"p50_ms": s["x_p50_ms"], "rows_returned": got,
                                         **{k[2:]: v for k, v in s.items()}}
            print(f"  docker_http  {n:>7} rows  p50 {s['x_p50_ms']:.3f} ms", flush=True)
        # run_conditions reads THIS process's cgroup, which is the client, not
        # the server container. Recorded as client_* so no reader mistakes it
        # for the engine's envelope (the #109 lesson).
        meta["docker_client_conditions"] = run_conditions(lane="e4_decomp", role="docker_client")
        meta["docker_url"] = args.docker

    # Every arm must have returned the same rows, or the comparison is void.
    mismatch = []
    for n in SIZES:
        got = {a: results[a][n]["rows_returned"] for a in results if n in results[a]}
        if len(set(got.values())) > 1:
            mismatch.append((n, got))
    meta["row_count_agreement"] = "ok" if not mismatch else mismatch
    if mismatch:
        print(f"\n!! ARMS DISAGREE ON ROW COUNTS, comparison is void: {mismatch}")

    report(results)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"meta": meta, "results": {a: {str(k): v for k, v in d.items()}
                                             for a, d in results.items()}}, f, indent=2)
    print(f"\nwrote {args.out}")
    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
