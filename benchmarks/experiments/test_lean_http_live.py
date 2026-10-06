#!/usr/bin/env python3
"""The served ArcadeDB arms give identical answers through lean_http and through requests, against a LIVE server (CAMPAIGN section 7 row 72).

Skipped unless LEAN_HTTP_LIVE=host:port names a running ArcadeDB 26.10.1 server (database `bench` created, root password dbbenchpass), for
instance `docker run ... arcadedb-c25:26.10.1` with `-Darcadedb.server.defaultDatabases=bench[root]`; live_clients.sh in the levers audit
directory starts one on the laptop's cores 6-7 and runs this file. It resets the databases `bench` and `lc` between clients.

Each test runs the LANE'S OWN adapter (l1_tabular, l1_tpc, l2_graph, l3_sparse, l3d_dense, l4_tsbs twice, e2_hybrid, l5_lifecycle_server's main)
once per client, on a fresh database, with the lane's own data generators at a small size, and compares the lane's own answer digests
(bench_common.record_result with the lane's digest declaration), the post-state of every write, and the error text of a failing statement.
Every answer must be non-degenerate (rows and more than one distinct value where the lane's profile says so), so two clients agreeing on
nothing cannot pass. Where an approximate index makes two separate builds differ by themselves (dense LSM_VECTOR), the server is built ONCE and
the session is swapped between the clients instead. BENCH_ARCADEDB_HTTP_CLIENT is set per run, so the adapters' own connect() builds
the client under test and records it in `row_extra`.
"""
import json
import os
import random
import subprocess
import sys
import types
from collections import namedtuple
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LIVE = os.environ.get("LEAN_HTTP_LIVE", "")
pytestmark = pytest.mark.skipif(not LIVE, reason="LEAN_HTTP_LIVE=host:port names a running ArcadeDB server")

np = pytest.importorskip("numpy")
requests = pytest.importorskip("requests")

import bench_common  # noqa: E402
import lean_http as LH  # noqa: E402

CLIENTS = ("lean", "requests")
RQ_NAME = f"requests {requests.__version__}" if hasattr(requests, "__version__") else "requests"


# ------------------------------------------------------------------------------------------------------------- the server
def _host_port():
    host, _, port = LIVE.partition(":")
    return host or "127.0.0.1", port or "2480"


def _admin(command, ok_missing=False):
    host, port = _host_port()
    s = requests.Session()
    s.auth = ("root", "dbbenchpass")
    r = s.post(f"http://{host}:{port}/api/v1/server", json={"command": command}, timeout=300)
    if r.status_code >= 400 and not ok_missing:
        r.raise_for_status()
    return r


def reset_db(name="bench"):
    _admin(f"drop database {name}", ok_missing=True)
    _admin(f"create database {name}")


@pytest.fixture
def env(monkeypatch):
    host, port = _host_port()
    monkeypatch.setenv("BENCH_SERVER_HOST", host)
    monkeypatch.setenv("BENCH_SERVER_PORT", port)

    def use(choice):
        monkeypatch.setenv(LH.CLIENT_ENV, choice)
    return use


def digests(out):
    """The res_<name>_* fields record_result wrote, as {name: (digest, n)}."""
    return {k[4:-7]: (out[k], out[k[:-7] + "_n"]) for k in out if k.startswith("res_") and k.endswith("_digest")}


def answers_of(adapter_runs):
    """adapter_runs: {client: out dict}. The digests must be identical, none empty, and the client recorded must be the one that ran."""
    lean, req = adapter_runs["lean"], adapter_runs["requests"]
    dl, dr = digests(lean), digests(req)
    assert dl and set(dl) == set(dr)
    bad = {k: (dl[k], dr[k]) for k in dl if dl[k] != dr[k]}
    assert not bad, f"answers differ between the clients: {bad}"
    if os.environ.get("LEAN_HTTP_LIVE_VERBOSE"):
        print("\nANSWERS", {k: f"{v[0]}/n={v[1]}" for k, v in dl.items()})
    return dl


def non_degenerate(profile_out, allow_empty=()):
    for k, (d, n) in digests(profile_out).items():
        if k in allow_empty or k.endswith("_empty"):
            assert n == 0, f"{k} should be empty"
        else:
            assert n >= 1, f"{k} answered nothing, so agreeing on it means nothing"


# ------------------------------------------------------------------------------------------------------------ l2 graph
def run_graph(env, choice):
    import graph_common as G
    import l2_graph as L2
    reset_db("bench")
    env(choice)
    ad = L2.ArcadeGraphServer()
    ad.connect()
    assert ad.row_extra["arcadedb_http_client"] == (LH.LEAN_NAME if choice == "lean" else RQ_NAME)
    n = 250
    ad.build(n)
    out = {}
    ids = G.pick_query_ids(n, 10)
    for op in G.OLTP_READS:
        rows = [r for pid in ids for r in ad.run_read(op, pid)]
        bench_common.record_result(out, f"read_{op}", rows, **G.READ_DIGEST[op])
    visited = [dict(id=pid, n=len(ad.run_visited(pid))) for pid in ids[:5]]
    bench_common.record_result(out, "visited", visited, **G.VISITED_DIGEST)
    for qn in ("top_degree", "same_city_edges", "friend_age_by_city", "degree_dist"):
        bench_common.record_result(out, f"olap_{qn}", ad.run_olap(qn), **G.OLAP_DIGEST[qn])
    base = 1_000_000
    for k, pid in enumerate(ids[:5]):
        ad.run_write(pid, base + k)
    bench_common.record_result(out, "persons_after_write", ad.person_scan(base), **G.PERSON_STATE_DIGEST)
    bench_common.record_result(out, "edges_after_write", ad.edge_scan(base), **G.EDGE_STATE_DIGEST)
    for k in range(5):
        ad.run_update(base + k)
    bench_common.record_result(out, "persons_after_update", ad.person_scan(base), **G.PERSON_STATE_DIGEST)
    for k in range(5):
        ad.run_delete(base + k)
    bench_common.record_result(out, "persons_after_delete_empty", ad.person_scan(base), **G.PERSON_STATE_DIGEST)
    # a failing statement: the same exception text from both clients
    with pytest.raises(Exception) as e:
        ad._http("query", "sql", "SELECT FROM NoSuchTypeAnywhere")
    out["error_text"] = str(e.value)
    out["row_extra"] = dict(ad.row_extra)
    return out


def test_l2_graph_answers_identical(env):
    runs = {c: run_graph(env, c) for c in CLIENTS}
    answers_of(runs)
    non_degenerate(runs["lean"])
    assert runs["lean"]["error_text"].split(" for url:")[0] == runs["requests"]["error_text"].split(" for url:")[0]
    assert runs["lean"]["error_text"].startswith("5") or runs["lean"]["error_text"].startswith("4")


# --------------------------------------------------------------------------------------------------------- l1 tabular
def run_tabular(env, choice):
    import l1_tabular as L1
    reset_db("bench")
    env(choice)
    ad = L1.ArcadeServer()
    ad.connect()
    assert ad.row_extra["arcadedb_http_client"] == (LH.LEAN_NAME if choice == "lean" else RQ_NAME)
    ad.schema()
    n = 3000
    ad.ingest(n, batch=500)
    out = {}
    cols = ("id", "customer_id", "region", "status", "amount", "quantity")
    for rid in (0, 1, 17, 999, 2999):
        rows = ad.query_all(f"SELECT {', '.join(cols)} FROM orders WHERE id = ?", (rid,))
        bench_common.record_result(out, f"read_{rid}", rows, columns=cols)
    for name, sql in L1.OLAP_SQL:
        bench_common.record_result(out, f"olap_{name}", ad.query_all(sql))
    # the OLTP writes, through the lane's own ops, on ids the rest of the table never touches
    base = 10_000_000
    rows = list(L1.gen_rows(5, seed=7))
    for k, row in enumerate(rows):
        ad.op_insert((base + k,) + tuple(row[1:]))
    ad.op_update(0)
    ad.op_update(1)
    bench_common.record_result(out, "state_after_insert_update",
                               ad.query_all(f"SELECT {', '.join(cols)} FROM orders WHERE id >= {base} OR id < 2"), columns=cols)
    ad.exec(f"DELETE FROM orders WHERE id >= {base}")
    bench_common.record_result(out, "state_after_delete",
                               ad.query_all(f"SELECT {', '.join(cols)} FROM orders WHERE id >= {base} OR id < 2"), columns=cols)
    # an index readback and the schema:indexes answer, which the lane writes on its rows
    out["index_kinds"] = str(ad.index_readback())
    return out


def test_l1_tabular_answers_identical(env):
    runs = {c: run_tabular(env, c) for c in CLIENTS}
    answers_of(runs)
    non_degenerate(runs["lean"])
    assert runs["lean"]["index_kinds"] == runs["requests"]["index_kinds"]


# --------------------------------------------------------------------------------------------------------------- l1 tpc
LI = namedtuple("LI", "l_orderkey l_partkey l_quantity l_extendedprice l_discount l_returnflag l_linestatus l_shipdate l_shipmode l_tax")


class SyntheticLineItems:
    def __init__(self, n, parts):
        self.n, self.parts = n, parts

    def records(self):
        rng = random.Random(5)
        for i in range(self.n):
            yield LI(i // 4, rng.randrange(self.parts), float(rng.randint(1, 50)), round(rng.uniform(900, 100000), 2),
                     round(rng.choice([0.0, 0.02, 0.05, 0.1]), 2), rng.choice("ARN"), rng.choice("OF"),
                     f"199{rng.randint(2, 8)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                     rng.choice(["AIR", "MAIL", "RAIL", "SHIP", "TRUCK"]), round(rng.choice([0.0, 0.04, 0.08]), 2))


def run_tpc(env, choice):
    import pandas as pd
    import l1_tpc as TP
    reset_db("bench")
    env(choice)
    ad = TP.ArcadeServerTPC()
    ad.connect()
    host, port = _host_port()
    ad.base = f"http://{host}:{port}/api/v1"            # the adapter hard-codes 2480
    assert ad.row_extra["arcadedb_http_client"] == (LH.LEAN_NAME if choice == "lean" else RQ_NAME)
    parts = 400
    part = pd.DataFrame({"p_partkey": list(range(parts)), "p_retailprice": [900.0 + (i % 97) for i in range(parts)]})
    ad.build(SyntheticLineItems(6000, parts), part)
    out = {}
    for which in TP.ARCADE_OLAP:
        bench_common.record_result(out, f"olap_{which}", ad.olap(which), **TP.OLAP_DIGEST[which])
    for i in range(20):
        ad.new_order(i, i % parts)
    for i in range(0, 20, 2):
        ad.payment(i)
    bench_common.record_result(out, "orders_after", ad.oltp_scan(), **TP.OLTP_STATE_DIGEST)
    bench_common.record_result(out, "stock_after", ad.stock_scan(), **TP.STOCK_DIGEST)
    out["payments_n"] = ad.payments_n()
    for i in range(30):
        ad.crud_insert(i, i % parts)
    bench_common.record_result(out, "crud_after_insert", ad.crud_scan(), **TP.CRUD_DIGEST)
    for i in range(30):
        ad.crud_read(i)
    bench_common.record_result(out, "crud_read_7", ad.crud_read(7), **TP.CRUD_READ_DIGEST)
    for i in range(30):
        ad.crud_update(i)
    bench_common.record_result(out, "crud_after_update", ad.crud_scan(), **TP.CRUD_DIGEST)
    for i in range(30):
        ad.crud_delete(i)
    bench_common.record_result(out, "crud_after_delete_empty", ad.crud_scan(), **TP.CRUD_DIGEST)
    return out


def test_l1_tpc_answers_identical(env):
    runs = {c: run_tpc(env, c) for c in CLIENTS}
    answers_of(runs)
    non_degenerate(runs["lean"])
    assert runs["lean"]["payments_n"] == runs["requests"]["payments_n"] == 10


# ----------------------------------------------------------------------------------------------------------- l3 sparse
def test_l3_sparse_answers_identical(env):
    import l3_sparse as SP
    import sparse_common as SC
    reset_db("bench")
    env("lean")
    ad = SP.ArcadeServer()
    ad.connect()
    ad.build(1500)
    ad.post_build()
    qs = list(SC.gen_queries(12))
    per = {}
    for choice in ("lean", "requests", "lean", "requests"):
        env(choice)
        ad.rq = LH.Session()
        ad.rq.auth = ("root", "dbbenchpass")
        out = {}
        found = [r for (idx, vals) in qs for r in [{"ids": ",".join(map(str, ad.search(idx, vals, 10)))}]]
        bench_common.record_result(out, "sparse_topk", found, columns=("ids",), order_matters=True, order_key="ids")
        assert digests(out)["sparse_topk"][1] == 12 and any(r["ids"] for r in found)
        per.setdefault(choice, []).append((found, digests(out)))
    assert per["lean"][0] == per["lean"][1] == per["requests"][0] == per["requests"][1]


# ------------------------------------------------------------------------------------------------------------ l3d dense
def test_l3d_dense_answers_identical(env):
    import l3d_dense as DN
    reset_db("bench")
    env("lean")
    rng = np.random.default_rng(3)
    vecs = rng.standard_normal((1200, DN.DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    ad = DN.ArcadeServer()
    ad.connect()
    ad.build(vecs)
    qv = vecs[rng.integers(0, 1200, 15)] + 0.01 * rng.standard_normal((15, DN.DIM)).astype(np.float32)
    runs = {}
    for choice in ("lean", "requests", "lean", "requests"):
        env(choice)
        ad.rq = LH.Session()
        ad.rq.auth = ("root", "dbbenchpass")
        runs.setdefault(choice, []).append([ad.search(q, 10) for q in qv])
    assert all(len(r) == 10 for r in runs["lean"][0])
    assert runs["lean"][0] == runs["lean"][1] == runs["requests"][0] == runs["requests"][1]
    # the insert path (a 200-row CONTENT batch) and the delete of what it wrote
    for choice in CLIENTS:
        env(choice)
        ad.rq = LH.Session()
        ad.rq.auth = ("root", "dbbenchpass")
        ad.insert_vectors(list(range(5000, 5010)), vecs[:10])
        got = ad._cmd("sql", "SELECT count(*) AS n FROM Article WHERE vid >= 5000")[0]["n"]
        assert got == 10
        ad._cmd("sql", "DELETE FROM Article WHERE vid >= 5000")


# ---------------------------------------------------------------------------------------------------------------- l4 ts
def _points(n_hosts=6, per=400):
    import l4_tsbs as T4
    rng = random.Random(11)
    pts = []
    for h in range(n_hosts):
        for i in range(per):
            pts.append((f"host_{h + 40}", T4.T0 + i * 60, round(rng.uniform(0, 100), 3), round(rng.uniform(0, 100), 3),
                        round(rng.uniform(0, 100), 3)))
    return pts


@pytest.mark.parametrize("cls", ["ArcadeTSServer", "ArcadeNativeTSServer"])
def test_l4_tsbs_answers_identical(env, cls):
    import l4_tsbs as T4
    runs = {}
    for choice in CLIENTS:
        reset_db("bench")
        env(choice)
        ad = getattr(T4, cls)()
        ad.connect()
        assert ad.row_extra["arcadedb_http_client"] == (LH.LEAN_NAME if choice == "lean" else RQ_NAME)
        ad.ingest(_points())
        if cls == "ArcadeNativeTSServer":
            ad.settle()
        out = {}
        for qn in ("q_last", "q_range", "q_global", "q_groupby", "q_high", "q_orderlimit"):
            bench_common.record_result(out, qn, getattr(ad, qn)(), **T4.Q_DIGEST[qn])
        runs[choice] = out
    answers_of(runs)
    non_degenerate(runs["lean"])


# ------------------------------------------------------------------------------------------------------------- e2 hybrid
def test_e2_hybrid_answers_identical(env):
    import e2_hybrid as E2
    rng = np.random.default_rng(9)
    n = 400
    vecs = rng.standard_normal((n, E2.DIM)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    r = random.Random(9)
    edges = [(i, r.randrange(n)) for i in range(n) for _ in range(3)]
    edges = [(a, b) for a, b in edges if a != b]
    qs = [(vecs[i] + 0.02 * rng.standard_normal(E2.DIM)).astype(np.float32) for i in range(0, 60, 5)]
    runs = {}
    for choice in CLIENTS:
        reset_db("bench")
        env(choice)
        ad = E2.ArcadeE2Server()
        assert ad.row_extra["arcadedb_http_client"] == (LH.LEAN_NAME if choice == "lean" else RQ_NAME)
        ad.build(vecs, edges)                 # the chunked /batch body, then the vector index
        out = {}
        pids = list(range(n))
        bench_common.record_result(out, "docs_before", ad._docs(pids), **E2.RETRIEVAL_DIGEST)
        tops = [dict(q=i, pid=p) for i, q in enumerate(qs) for p in ad._vec_topk(q, E2.K)]
        bench_common.record_result(out, "topk", tops, columns=("q", "pid"))
        hops = [dict(q=i, pid=p) for i, q in enumerate(qs) for p in ad._hop(ad._vec_topk(q, 3))]
        bench_common.record_result(out, "hops", hops, columns=("q", "pid"))
        touched = [ad.hybrid_op(q) for q in qs]
        crashed = 0
        for q in qs[:3]:
            with pytest.raises(RuntimeError, match="injected-crash"):
                ad.hybrid_op(q, crash=True)
            crashed += 1
        after = {int(d["pid"]): int(d["views"]) for d in ad._docs(pids)}
        deltas = [dict(pid=p, views=v) for p, v in sorted(after.items()) if v]
        bench_common.record_result(out, "views_after_ops", deltas, columns=("pid", "views"))
        out["touched"], out["total_views"], out["crashed"] = touched, ad.total_views(), crashed
        runs[choice] = out
    answers_of(runs)
    non_degenerate(runs["lean"])
    a, b = runs["lean"], runs["requests"]
    assert a["touched"] == b["touched"] and a["total_views"] == b["total_views"] == sum(a["touched"]) and a["crashed"] == 3


# ------------------------------------------------------------------------------------------------------ l5 lifecycle
@pytest.mark.parametrize("workload", ["doc", "graph"])
def test_l5_lifecycle_server_read_identical(env, workload, tmp_path):
    import l5_lifecycle_server as L5
    runs = {}
    for choice in CLIENTS:
        env(choice)
        outp = tmp_path / f"{workload}-{choice}.json"
        L5.L.SCALE_ROWS["lc_live"] = 600 if workload == "doc" else 40
        args = types.SimpleNamespace(scale="lc_live", workload=workload, out=str(outp))
        L5.main(args)
        runs[choice] = json.loads(outp.read_text())
    assert runs["lean"]["arcadedb_http_client"] == LH.LEAN_NAME and runs["requests"]["arcadedb_http_client"] == RQ_NAME
    dl, dr = digests(runs["lean"]), digests(runs["requests"])
    assert dl == dr, (dl, dr)
    assert runs["lean"].get("lifecycle_read_situation") == runs["requests"].get("lifecycle_read_situation")
    if dl:
        non_degenerate(runs["lean"])


# ------------------------------------------------------------------------------------- e4 deployment decomposition (row 72 addendum)
@pytest.mark.parametrize("legacy", ["requests", "shim"])
def test_e4_decomposition_measures_both_clients_and_every_path_returns_the_same_rows(legacy, tmp_path):
    """The e4 lane (e4_decomp.py, with a real in-process engine and a real server) at a small corpus, once with requests importable and once
    with it blocked, which is the e4 cell's own condition (its image has none, so the probe's client is the urllib shim)."""
    pytest.importorskip("arcadedb_embedded")
    host, port = _host_port()
    _admin("drop database deploy_decomp", ok_missing=True)
    out = tmp_path / f"e4-{legacy}.json"
    code = ("import runpy, sys\n" + ("sys.modules['requests'] = None\n" if legacy == "shim" else "") +
            f"sys.argv = ['e4_decomp.py', '--backend', 'arcadedb_e4', '--workload', 'decomp', '--scale', 'e2', '--out', {str(out)!r}]\n"
            f"runpy.run_path({str(HERE / 'e4_decomp.py')!r}, run_name='__main__')\n")
    env = dict(os.environ, BENCH_SERVER_HOST=host, BENCH_SERVER_PORT=port, ARCADEDB_HEAP="1g", ROWS="3000", SIZES="1,10,100,1000",
               REPS="3", WARMUP="1")
    r = subprocess.run([sys.executable, "-c", code], env=env, cwd=str(HERE), capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    art = json.loads(out.read_text())
    meta, res = art["meta"], art["results"]
    assert set(res) == {"embedded", "inproc_http", "inproc_http_lean", "docker_http", "docker_http_lean"}
    key = "requests" if legacy == "requests" else "urllib_shim"
    assert meta["arm_clients"]["docker_http"] == key and meta["arm_clients"]["docker_http_lean"] == "lean"
    assert meta["row_count_agreement"] == "ok" and meta["answer_agreement"] == "ok"
    for size, per in meta["answers"].items():
        assert len({d["digest"] for d in per.values()}) == 1 and len(per) == 5 and next(iter(per.values()))["n"] == int(size)
    assert art["arcadedb_http_clients"][-1] == LH.LEAN_NAME and len(art["arcadedb_http_clients"]) == 2
