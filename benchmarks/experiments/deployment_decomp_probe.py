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

THE CLIENT AXIS (CAMPAIGN section 7 row 72, 2026-10-06). "Protocol" above was never only the protocol: the HTTP arms are timed
through a Python client, and the client is a cost of its own. The served lanes moved from requests.Session to one persistent
http.client connection (lean_http.py), which costs about a quarter of what requests does for a small call, so a decomposition
that kept describing the old client would put a number on the table that no served cell pays any more. Every HTTP arm is
therefore measured under BOTH clients, in the same interleave and against the same server:

    inproc_http, docker_http            the probe's own session, as it always was: requests when it imports, and the urllib
                                        shim e4_decomp.py installs when the client image has none (the e4 cell's image, dbbench:arcadedb,
                                        has none, so the cell's `legacy` client is the shim, which opens a connection per call)
    inproc_http_lean, docker_http_lean  lean_http.LeanSession, one persistent connection

and the artifact names the client of every arm (`meta.arm_clients`, `meta.client_names`) and records it on the measurement
(`arcadedb_http_client`), so engine (embedded), client (legacy minus lean at the same wire), protocol (in-process HTTP minus embedded,
per client) and boundary (container minus in-process, per client) each come from a pair of arms that differ in that one thing.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import time

import lean_http
from bench_common import latstats, result_digest, run_conditions

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


def ensure_docker_db(session, base_url: str, auth, db_name: str, total: int) -> None:
    """The served arm needs the same corpus in the container. August's run
    loaded it by hand; this loads it over HTTP: create the database, the
    schema, then SQLSCRIPT batches of INSERTs. Not timed."""
    r = session.post(f"{base_url}/api/v1/server", auth=auth,
                     json={"command": f"create database {db_name}"}, timeout=120)
    if r.status_code not in (200, 400):   # 400: already exists
        r.raise_for_status()
    def cmd(text, language="sql"):
        rr = session.post(f"{base_url}/api/v1/command/{db_name}", auth=auth,
                          json={"language": language, "command": text}, timeout=600)
        rr.raise_for_status()
    for stmt in SCHEMA:
        cmd(stmt)
    buf = []
    for row in gen_rows(total):
        buf.append(f"INSERT INTO orders SET id = {row['id']}, customer_id = {row['customer_id']}, "
                   f"amount = {row['amount']}, region = '{row['region']}'")
        if len(buf) >= 5000:
            cmd(";".join(buf), "sqlscript"); buf = []
    if buf:
        cmd(";".join(buf), "sqlscript")


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
    keys = list(fns)
    for rnd in range(reps):
        # ONE REP OF EACH, ROUND-ROBIN, STARTING ONE ARM LATER EACH ROUND (row 72). With five arms in a fixed order, the arm that
        # always ran right after the 100,000-row embedded call inherited its garbage and its cache state; rotating the start gives every
        # arm every position, so the legacy-versus-lean comparison cannot be a position effect.
        order = keys[rnd % len(keys):] + keys[:rnd % len(keys)]
        for k in order:
            t0 = time.perf_counter()
            got[k] = fns[k](n)
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


# THE CLIENT AXIS. The arm names `inproc_http` and `docker_http` keep their meaning (the probe's own session); `_lean` is the same arm
# through lean_http.LeanSession.
LEAN_SUFFIX = "_lean"
LEAN_KEY = "lean"


def legacy_client(session):
    """(short key, full name) of the probe's own session: real requests, or the urllib shim e4_decomp installs when the client
    image has no requests (the shim names itself)."""
    key = getattr(session, "client_key", None)
    if key:
        return key, getattr(session, "client_name", key)
    import requests
    return "requests", f"requests {requests.__version__}"


def arm_clients(legacy_key: str, with_docker: bool) -> dict:
    """arm -> the short key of the client it was measured through. The embedded arm has no HTTP client and is absent."""
    arms = ["inproc_http"] + (["docker_http"] if with_docker else [])
    return {**{a: legacy_key for a in arms}, **{a + LEAN_SUFFIX: LEAN_KEY for a in arms}}


def client_decomposition(results: dict, sizes) -> list:
    """The client rows of the decomposition, per size: how much of each HTTP arm is the client. client = legacy arm minus the lean
    arm at the same place (in-process server, container), the same server answering both. Only where both exist."""
    out = []
    for n in sizes:
        row = {"rows": n}
        for place in ("inproc_http", "docker_http"):
            a, b = results.get(place, {}).get(n), results.get(place + LEAN_SUFFIX, {}).get(n)
            if a and b:
                row[place] = {"legacy_ms": a["p50_ms"], "lean_ms": b["p50_ms"], "client_ms": round(a["p50_ms"] - b["p50_ms"], 4),
                              "ratio": round(a["p50_ms"] / b["p50_ms"], 3)}
        if len(row) > 1:
            out.append(row)
    return out


def report(results: dict) -> None:
    arms = [a for a in ("embedded", "inproc_http", "inproc_http" + LEAN_SUFFIX, "docker_http", "docker_http" + LEAN_SUFFIX) if a in results]
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
    cd = client_decomposition(results, SIZES)
    if cd:
        print("\nCLIENT (ms the legacy client adds over the lean client, same server, same wire; and the ratio):")
        for row in cd:
            cells = "  ".join(f"{p}: {row[p]['client_ms']:>+9.3f} ({row[p]['ratio']:.2f}x)" for p in ("inproc_http", "docker_http") if p in row)
            print(f"{row['rows']:>8}  {cells}")


# THE COLUMNS EVERY PATH IS ASKED FOR, so metadata a path adds to a row (an
# @rid, a @type) is not part of its answer.
ANSWER_COLUMNS = ["id", "customer_id", "amount", "region"]


def http_rows(session, base_url: str, auth, db_name: str):
    """The same request as http_runner, returning the rows instead of their count.

    Used only for the answer check after the timed sweep, never inside it, so
    the timed path is exactly what it was.
    """

    def rows(n: int) -> list:
        r = session.post(f"{base_url}/api/v1/query/{db_name}", auth=auth,
                         json={"language": "sql", "command": query(n), "limit": -1},
                         timeout=300)
        r.raise_for_status()
        return r.json().get("result", [])

    return rows


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
        # STAMP WHAT THIS RAN UNDER, so the page does not have to infer it.
        # The exporter dated this artifact by its directory name, which works
        # only because the directory carries the pin; a table fed by a file
        # with a fixed name had no way to say which instrument produced it,
        # and defaulted to the older one. An artifact that names its own
        # instrument cannot be misdated by a reader written later.
        "instrument": os.environ.get("BENCH_INSTRUMENT", "2026-09"),
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
        sess.get(f"{base}/api/v1/server?mode=basic", auth=auth, timeout=120)

        run_http = http_runner(sess, base, auth, DB_NAME)
        lsess = lean_http.LeanSession()          # the lean client, whatever BENCH_ARCADEDB_HTTP_CLIENT says: both are measured
        lsess.get(f"{base}/api/v1/server?mode=basic", auth=auth, timeout=120)
        legacy_key, legacy_name = legacy_client(sess)
        arms = {
            "embedded": lambda k: len(db.query("sql", query(k)).to_json_list()),
            "inproc_http": run_http,
            "inproc_http" + LEAN_SUFFIX: http_runner(lsess, base, auth, DB_NAME),
        }
        # The Docker arm joins the SAME interleave. Running it in its own loop
        # afterwards would repeat the bias just removed, and worse here: the
        # container's JVM would be cold for its whole arm while the in-process
        # server's JVM was warmed by the embedded arm, so the "boundary" number
        # would be measuring JIT state across two different JVMs.
        if args.docker:
            dsess = requests.Session()
            dauth = ("root", args.docker_password)
            ensure_docker_db(dsess, args.docker.rstrip("/"), dauth, DB_NAME, ROWS)
            print(f"loaded {ROWS:,} rows into the served database at {args.docker}", flush=True)
            arms["docker_http"] = http_runner(dsess, args.docker.rstrip("/"),
                                              dauth, DB_NAME)
            dlsess = lean_http.LeanSession()
            arms["docker_http" + LEAN_SUFFIX] = http_runner(dlsess, args.docker.rstrip("/"), dauth, DB_NAME)
            results["docker_http"] = {}
            results["docker_http" + LEAN_SUFFIX] = {}
            # run_conditions reads THIS process's cgroup, which is the client,
            # not the server container. Recorded as client_* so no reader takes
            # it for the engine's envelope (the #109 lesson).
            meta["docker_client_conditions"] = run_conditions(lane="e4_decomp",
                                                              role="docker_client")
            meta["docker_url"] = args.docker
        results["embedded"] = {}
        results["inproc_http"] = {}
        results["inproc_http" + LEAN_SUFFIX] = {}
        clients = arm_clients(legacy_key, bool(args.docker))
        meta["arm_clients"] = clients
        meta["client_names"] = {legacy_key: legacy_name, LEAN_KEY: lean_http.LEAN_NAME}
        meta["arm_order"] = "rotated one place each round, every arm warmed at every size first"
        for n in SIZES:
            paired = timeit_paired(arms, n, REPS, WARMUP)
            line = f"  {n:>7} rows "
            for arm, (lat, got) in paired.items():
                st = latstats("x", lat)
                results[arm][n] = {"p50_ms": st["x_p50_ms"], "rows_returned": got,
                                   **{k[2:]: v for k, v in st.items()}}
                if arm in clients:          # THE CLIENT, ON THE MEASUREMENT (row 72): read from the session this arm ran with
                    results[arm][n]["arcadedb_http_client"] = meta["client_names"][clients[arm]]
                line += f"  {arm} {st['x_p50_ms']:8.3f} ms"
            print(line, flush=True)

        # WHAT EACH PATH RETURNED, not only how many rows (DECISIONS #88, BUGS
        # F129). The row-count guard below catches a truncated answer; it cannot
        # catch a path returning different rows, and this lane recorded no answer
        # digest at all, which the equivalence gate's E6 rule fails. Fetched once
        # per size AFTER the timed sweep, so no timed call changes; digested the
        # way every lane digests (order-free: the query defines no order).
        fetch = {"embedded": lambda k: db.query("sql", query(k)).to_json_list(),
                 "inproc_http": http_rows(sess, base, auth, DB_NAME),
                 "inproc_http" + LEAN_SUFFIX: http_rows(lsess, base, auth, DB_NAME)}
        if args.docker:
            fetch["docker_http"] = http_rows(dsess, args.docker.rstrip("/"), dauth, DB_NAME)
            fetch["docker_http" + LEAN_SUFFIX] = http_rows(dlsess, args.docker.rstrip("/"), dauth, DB_NAME)
        answers = {n: {arm: result_digest(f(n), columns=ANSWER_COLUMNS) for arm, f in fetch.items()}
                   for n in SIZES}

        meta.update(run_conditions(lane="e4_decomp", role="embedded+inproc_server"))

    # Every arm must have returned the same rows, or the comparison is void.
    mismatch = []
    for n in SIZES:
        got = {a: results[a][n]["rows_returned"] for a in results if n in results[a]}
        if len(set(got.values())) > 1:
            mismatch.append((n, got))
    meta["row_count_agreement"] = "ok" if not mismatch else mismatch
    if mismatch:
        print(f"\n!! ARMS DISAGREE ON ROW COUNTS, comparison is void: {mismatch}")
    answer_mismatch = [(n, {a: d["digest"] for a, d in per.items()})
                       for n, per in answers.items() if len({d["digest"] for d in per.values()}) > 1]
    meta["answers"] = {str(n): per for n, per in answers.items()}
    meta["answer_agreement"] = "ok" if not answer_mismatch else answer_mismatch
    if answer_mismatch:
        print(f"\n!! ARMS RETURNED DIFFERENT ROWS, comparison is void: {answer_mismatch}")

    report(results)
    meta["client_decomposition"] = client_decomposition(results, SIZES)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"meta": meta, "results": {a: {str(k): v for k, v in d.items()}
                                             for a, d in results.items()}}, f, indent=2)
    print(f"\nwrote {args.out}")
    return 1 if (mismatch or answer_mismatch) else 0


if __name__ == "__main__":
    raise SystemExit(main())
