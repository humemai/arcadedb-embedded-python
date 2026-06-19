#!/usr/bin/env python3
"""Graph lane: OLTP (point/1-hop reads + transactional node writes) and OLAP (traversals).

Backends: kuzu, arcadedb. Graph: (User)-[:POSTED]->(Post), (Post)-[:ANSWERS]->(Post).
Loads from normalized parquet; edges filtered to existing endpoints (tiny caps tables at 10k).
Cypher queries are shared (ints embedded, no param-dialect issues). Prints RESULT {json}.
"""
import argparse
import json
import os
import random
import statistics as st
import tempfile
import time

import pandas as pd


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


def be_kuzu(users, posts, posted, answers, workload):
    import kuzu
    db = kuzu.Database(tempfile.mkdtemp(prefix="gb_kuzu_") + "/db")
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE User(id INT64, PRIMARY KEY(id))")
    conn.execute("CREATE NODE TABLE Post(id INT64, PRIMARY KEY(id))")
    conn.execute("CREATE REL TABLE POSTED(FROM User TO Post)")
    conn.execute("CREATE REL TABLE ANSWERS(FROM Post TO Post)")
    d = tempfile.mkdtemp(prefix="gb_kuzu_data_")
    pd.DataFrame({"id": users}).to_parquet(f"{d}/u.parquet")
    pd.DataFrame({"id": posts}).to_parquet(f"{d}/p.parquet")
    pd.DataFrame(posted, columns=["f", "t"]).to_parquet(f"{d}/posted.parquet")
    pd.DataFrame(answers, columns=["f", "t"]).to_parquet(f"{d}/answers.parquet")
    t0 = time.time()
    conn.execute(f"COPY User FROM '{d}/u.parquet'")
    conn.execute(f"COPY Post FROM '{d}/p.parquet'")
    conn.execute(f"COPY POSTED FROM '{d}/posted.parquet'")
    conn.execute(f"COPY ANSWERS FROM '{d}/answers.parquet'")
    load_s = time.time() - t0

    def query(q):
        r = conn.execute(q)
        n = 0
        while r.has_next():
            r.get_next(); n += 1
        return n

    def write(q):
        conn.execute(q)

    return dict(load_s=load_s, query=query, write=write, close=lambda: None,
                version=kuzu.__version__)


GAV_NAME = "gbOlap"


def be_arcadedb(users, posts, posted, answers, workload):
    import arcadedb_embedded as arcadedb
    ctx = arcadedb.create_database(tempfile.mkdtemp(prefix="gb_arcadedb_") + "/db")
    db = ctx.__enter__()
    for v in ("User", "Post"):
        db.command("sql", f"CREATE VERTEX TYPE {v}")
        db.command("sql", f"CREATE PROPERTY {v}.id LONG")
        db.command("sql", f"CREATE INDEX ON {v} (id) UNIQUE_HASH")  # fast point lookups (ex 09)
    db.command("sql", "CREATE EDGE TYPE POSTED")
    db.command("sql", "CREATE EDGE TYPE ANSWERS")

    pf = db.async_executor().get_parallel_level() > 1
    t0 = time.time()
    # vertices + edges via the tuned graph batch loader (ex 09), not per-row SQL
    for vtype, ids in (("User", users), ("Post", posts)):
        with db.graph_batch(batch_size=max(1, len(ids)), expected_edge_count=0,
                            bidirectional=False, commit_every=max(1, len(ids)),
                            use_wal=False, parallel_flush=pf) as b:
            b.create_vertices(vtype, [{"id": i} for i in ids])
    urid = {int(r["id"]): r["rid"] for r in
            db.query("sql", "SELECT id, @rid as rid FROM User").to_list()}
    prid = {int(r["id"]): r["rid"] for r in
            db.query("sql", "SELECT id, @rid as rid FROM Post").to_list()}
    for etype, edges, frm, to in (("POSTED", posted, urid, prid),
                                  ("ANSWERS", answers, prid, prid)):
        with db.graph_batch(batch_size=max(1, len(edges)), expected_edge_count=max(1, len(edges)),
                            bidirectional=False, commit_every=max(1, len(edges)),
                            use_wal=False, parallel_flush=pf) as b:
            for a, c in edges:
                b.new_edge(frm[a], etype, to[c])
    load_s = time.time() - t0

    gav_build_s = 0.0
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
        return len(db.query("opencypher", q).to_list())

    def write(q):
        db.begin()
        try:
            db.command("opencypher", q); db.commit()
        except Exception:
            db.rollback()

    return dict(load_s=load_s, gav_build_s=gav_build_s, query=query, write=write,
                close=lambda: ctx.__exit__(None, None, None),
                version=getattr(arcadedb, "__version__", "?"))


BACKENDS = {"kuzu": be_kuzu, "arcadedb": be_arcadedb}


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
    for k, v in lat.items():
        if v:
            out[f"{k}_p50_ms"] = round(st.median(v), 3)
    return out


def run_olap(be, reps=3):
    per = [round(min(_time(be, q) for _ in range(reps)), 3) for q in OLAP]
    return {"olap_query_ms": per, "olap_total_ms": round(sum(per), 3)}


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
    res = {"backend": args.backend, "lib_version": be["version"], "lane": "graph",
           "workload": args.workload, "n_users": len(users), "n_posts": len(posts),
           "n_posted": len(posted), "n_answers": len(answers), "load_s": round(be["load_s"], 3)}
    if be.get("gav_build_s"):
        res["gav_build_s"] = round(be["gav_build_s"], 3)
        res["gav"] = True
    res.update(run_oltp(be, users, posts, args.ops) if args.workload == "oltp" else run_olap(be))
    be["close"]()
    print("RESULT " + json.dumps(res))


if __name__ == "__main__":
    main()
