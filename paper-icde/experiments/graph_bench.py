#!/usr/bin/env python3
"""Graph lane: OLTP (point/1-hop reads + transactional node writes) and OLAP (traversals).

Backends: ladybug, arcadedb. Graph: (User)-[:POSTED]->(Post), (Post)-[:ANSWERS]->(Post).
(LadybugDB is the maintained continuation of Kùzu; package `real_ladybug`, Kùzu-compatible API.)
Records lifecycle phase timings, on-disk size, and full per-op latency stats. RESULT {json}.
"""
import argparse
import json
import os
import random
import time

import pandas as pd

import bench_common as bc


def load_graph(data_dir, limit):
    posts = pd.read_parquet(os.path.join(data_dir, "posts.parquet"), columns=["id"])
    users = pd.read_parquet(os.path.join(data_dir, "users.parquet"), columns=["id"])
    posted = pd.read_parquet(os.path.join(data_dir, "edges_posted.parquet"))
    answers = pd.read_parquet(os.path.join(data_dir, "edges_answers.parquet"))
    if limit:
        posts, users = posts.head(limit), users.head(limit)
    pset = set(int(x) for x in posts["id"])
    uset = set(int(x) for x in users["id"])
    posted = [(int(u), int(p)) for u, p in posted.itertuples(index=False, name=None)
              if int(u) in uset and int(p) in pset]
    answers = [(int(a), int(q)) for a, q in answers.itertuples(index=False, name=None)
               if int(a) in pset and int(q) in pset]
    return sorted(uset), sorted(pset), posted, answers


OLAP = [
    "MATCH (u:User)-[:POSTED]->(p:Post) RETURN u.id, count(p) AS c ORDER BY c DESC LIMIT 10",
    "MATCH (a:Post)-[:ANSWERS]->(q:Post) RETURN q.id, count(a) AS c ORDER BY c DESC LIMIT 10",
    "MATCH (u:User)-[:POSTED]->(:Post)-[:ANSWERS]->(:Post) RETURN count(*) AS c",
    "MATCH (:Post)-[r:ANSWERS]->(:Post) RETURN count(r) AS c",
]


def be_ladybug(users, posts, posted, answers, workload):
    import tempfile
    with bc.timed() as t_imp:
        import real_ladybug as lb  # maintained continuation of Kùzu; Kùzu-compatible API
    path = tempfile.mkdtemp(prefix="gb_ladybug_") + "/db.lbug"
    with bc.timed() as t_open:
        db = lb.Database(path)
        conn = lb.Connection(db)
    with bc.timed() as t_schema:
        conn.execute("CREATE NODE TABLE User(id INT64, PRIMARY KEY(id))")
        conn.execute("CREATE NODE TABLE Post(id INT64, PRIMARY KEY(id))")
        conn.execute("CREATE REL TABLE POSTED(FROM User TO Post)")
        conn.execute("CREATE REL TABLE ANSWERS(FROM Post TO Post)")
    d = tempfile.mkdtemp(prefix="gb_ladybug_data_")
    pd.DataFrame({"id": users}).to_parquet(f"{d}/u.parquet")
    pd.DataFrame({"id": posts}).to_parquet(f"{d}/p.parquet")
    pd.DataFrame(posted, columns=["f", "t"]).to_parquet(f"{d}/posted.parquet")
    pd.DataFrame(answers, columns=["f", "t"]).to_parquet(f"{d}/answers.parquet")
    with bc.timed() as t_ing:
        conn.execute(f"COPY User FROM '{d}/u.parquet'")
        conn.execute(f"COPY Post FROM '{d}/p.parquet'")
        conn.execute(f"COPY POSTED FROM '{d}/posted.parquet'")
        conn.execute(f"COPY ANSWERS FROM '{d}/answers.parquet'")

    def query(q):
        r = conn.execute(q)
        n = 0
        while r.has_next():
            r.get_next(); n += 1
        return n

    return dict(import_s=t_imp.s, jvm_init_s=0.0, open_s=t_open.s, schema_s=t_schema.s,
                ingest_s=t_ing.s, index_build_s=0.0, gav_build_s=0.0, db_path=path,
                query=query, write=lambda q: conn.execute(q),
                close=lambda: None, version=lb.__version__)


GAV_NAME = "gbOlap"


def be_arcadedb(users, posts, posted, answers, workload):
    import tempfile
    with bc.timed() as t_imp:
        import arcadedb_embedded as arcadedb
        from arcadedb_embedded import jvm
    path = tempfile.mkdtemp(prefix="gb_arcadedb_") + "/db"
    heap = os.environ.get("ARCADEDB_HEAP", "4g")
    with bc.timed() as t_jvm:
        jvm.start_jvm(heap_size=heap)  # heap must match (else medium OOMs)
    with bc.timed() as t_open:
        ctx = arcadedb.create_database(path, jvm_kwargs={"heap_size": heap})
        db = ctx.__enter__()
    with bc.timed() as t_schema:
        for v in ("User", "Post"):
            db.command("sql", f"CREATE VERTEX TYPE {v}")
            db.command("sql", f"CREATE PROPERTY {v}.id LONG")
            db.command("sql", f"CREATE INDEX ON {v} (id) UNIQUE_HASH")  # point lookups (ex 09)
        db.command("sql", "CREATE EDGE TYPE POSTED")
        db.command("sql", "CREATE EDGE TYPE ANSWERS")

    pf = db.async_executor().get_parallel_level() > 1
    with bc.timed() as t_ing:
        for vtype, ids in (("User", users), ("Post", posts)):
            with db.graph_batch(batch_size=max(1, len(ids)), expected_edge_count=0,
                                bidirectional=False, commit_every=max(1, len(ids)),
                                use_wal=False, parallel_flush=pf) as b:
                b.create_vertices(vtype, [{"id": i} for i in ids])
        urid = {int(r["id"]): r["rid"] for r in
                db.query("sql", "SELECT id, @rid as rid FROM User").to_json_list()}
        prid = {int(r["id"]): r["rid"] for r in
                db.query("sql", "SELECT id, @rid as rid FROM Post").to_json_list()}
        for etype, edges, frm, to in (("POSTED", posted, urid, prid),
                                      ("ANSWERS", answers, prid, prid)):
            with db.graph_batch(batch_size=max(1, len(edges)), expected_edge_count=max(1, len(edges)),
                                bidirectional=False, commit_every=max(1, len(edges)),
                                use_wal=False, parallel_flush=pf) as b:
                b.new_edges([frm[a] for a, _ in edges], etype,
                            [to[c] for _, c in edges])

    gav_build_s = 0.0
    with bc.timed() as t_idx:
        if workload == "olap":  # GAV accelerates the SAME OpenCypher queries (ex 10)
            g0 = time.time()
            db.command("sql", f"CREATE GRAPH ANALYTICAL VIEW {GAV_NAME} "
                       "VERTEX TYPES (User, Post) EDGE TYPES (POSTED, ANSWERS) "
                       "PROPERTIES (id) UPDATE MODE OFF")
            while True:
                row = db.query("sql", "SELECT FROM schema:graphAnalyticalViews WHERE name = ?",
                               GAV_NAME).first()
                if row is not None and row.get("status") == "READY":
                    break
                if time.time() - g0 > 1800:
                    raise RuntimeError("GAV did not reach READY")
                time.sleep(0.25)
            gav_build_s = time.time() - g0

    def query(q):
        return db.query("opencypher", q).count()

    def write(q):
        db.begin()
        try:
            db.command("opencypher", q); db.commit()
        except Exception:
            db.rollback()

    return dict(import_s=t_imp.s, jvm_init_s=t_jvm.s, open_s=t_open.s, schema_s=t_schema.s,
                ingest_s=t_ing.s, index_build_s=t_idx.s, gav_build_s=gav_build_s, db_path=path,
                query=query, write=write, close=lambda: ctx.__exit__(None, None, None),
                version=getattr(arcadedb, "__version__", "?"))


BACKENDS = {"ladybug": be_ladybug, "arcadedb": be_arcadedb}


def run_oltp(be, users, posts, n_ops, seed=0):
    rnd = random.Random(seed)
    next_id = max(posts) + 1
    lat = {"point": [], "hop": [], "write": []}
    t0 = time.time()
    for _ in range(n_ops):
        x = rnd.random()
        s = time.time()
        if x < 0.5:
            be["query"](f"MATCH (p:Post {{id:{rnd.choice(posts)}}}) RETURN p.id"); k = "point"
        elif x < 0.85:
            be["query"](f"MATCH (u:User {{id:{rnd.choice(users)}}})-[:POSTED]->(p:Post) RETURN p.id"); k = "hop"
        else:
            be["write"](f"CREATE (:Post {{id:{next_id}}})"); next_id += 1; k = "write"
        lat[k].append((time.time() - s) * 1000)
    total = time.time() - t0
    out = {"oltp_total_s": round(total, 3), "oltp_ops_per_s": round(n_ops / total, 1)}
    alllat = []
    for k, v in lat.items():
        out.update(bc.latstats(k, v)); alllat.extend(v)
    out.update(bc.latstats("oltp", alllat))
    return out, lat


def run_olap(be, reps=7):
    per_mean, per_std, raw = [], [], {}
    for idx, q in enumerate(OLAP):
        samples = [_time(be, q) for _ in range(reps)]
        raw[f"olap_q{idx}"] = samples
        s = bc.latstats(f"olap_q{idx}", samples)
        per_mean.append(round(s[f"olap_q{idx}_mean_ms"], 3))
        per_std.append(round(s[f"olap_q{idx}_std_ms"], 3))
    out = {"olap_query_ms": per_mean, "olap_query_std_ms": per_std,
           "olap_total_ms": round(sum(per_mean), 3)}
    out.update(bc.latstats("olap", [x for v in raw.values() for x in v]))
    return out, raw


def _time(be, q):
    s = time.time(); be["query"](q); return (time.time() - s) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=BACKENDS)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--workload", required=True, choices=["oltp", "olap"])
    ap.add_argument("--ops", type=int, default=2000)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    users, posts, posted, answers = load_graph(args.data_dir, args.limit)
    be = BACKENDS[args.backend](users, posts, posted, answers, args.workload)
    ingest_s = be["ingest_s"]
    res = {"backend": args.backend, "lib_version": be["version"], "lane": "graph",
           "workload": args.workload, "n_users": len(users), "n_posts": len(posts),
           "n_posted": len(posted), "n_answers": len(answers),
           "import_s": round(be["import_s"], 4), "jvm_init_s": round(be["jvm_init_s"], 4),
           "open_s": round(be["open_s"], 4), "schema_s": round(be["schema_s"], 4),
           "ingest_s": round(ingest_s, 3), "index_build_s": round(be["index_build_s"], 3),
           "load_s": round(ingest_s, 3),  # continuity
           "ingest_edges_per_s": round((len(posted) + len(answers)) / ingest_s, 1) if ingest_s else None}
    if be.get("gav_build_s"):
        res["gav_build_s"] = round(be["gav_build_s"], 3)
        res["gav"] = True
    if args.workload == "oltp":
        m, raw = run_oltp(be, users, posts, args.ops)
    else:
        m, raw = run_olap(be)
    res.update(m)
    with bc.timed() as t_close:
        be["close"]()
    res["close_s"] = round(t_close.s, 4)
    res["db_size_mb"] = bc.dir_size_mb(be["db_path"])
    bc.dump_latencies(os.environ.get("RUN_LABEL"), raw)
    print("RESULT " + json.dumps(res))


if __name__ == "__main__":
    main()
