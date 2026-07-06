#!/usr/bin/env python3
"""Tabular lane: OLTP (mixed point ops) and OLAP (analytical queries) on the posts table.

Backends: sqlite, duckdb, arcadedb. Each loads the SAME normalized posts.parquet and uses
its idiomatic path (PK/index, bulk load). Records lifecycle phase timings, on-disk size, and
full per-op latency stats (mean/std/p50/p90/p95/p99). One backend per run. Prints RESULT {json}.

OLTP mix: 60% read / 20% update / 10% insert / 10% delete by id (default 5000 ops).
OLAP: a fixed set of GROUP BY / aggregate / top-N queries, each timed over several reps.
"""
import argparse
import json
import os
import random
import time

import pandas as pd

import bench_common as bc

COLS = ["id", "post_type", "owner_user_id", "score", "view_count", "title"]


def load_posts(data_dir, limit):
    df = pd.read_parquet(os.path.join(data_dir, "posts.parquet"), columns=COLS)
    return df.head(limit) if limit else df


def _tuples(df):
    rows = []
    for t in df.itertuples(index=False):
        rows.append((
            int(t.id),
            int(t.post_type) if pd.notna(t.post_type) else None,
            int(t.owner_user_id) if pd.notna(t.owner_user_id) else None,
            int(t.score) if pd.notna(t.score) else None,
            int(t.view_count) if pd.notna(t.view_count) else None,
            t.title if isinstance(t.title, str) else None,
        ))
    return rows


def olap_queries(table):
    return [
        f"SELECT post_type, count(*) AS c FROM {table} GROUP BY post_type",
        f"SELECT count(*) AS c, avg(score) AS a FROM {table}",
        f"SELECT id, score FROM {table} ORDER BY score DESC LIMIT 10",
        f"SELECT owner_user_id, count(*) AS c FROM {table} GROUP BY owner_user_id ORDER BY c DESC LIMIT 10",
        f"SELECT post_type, avg(view_count) AS v FROM {table} GROUP BY post_type",
    ]


# --- backends: return dict(phase timings, db_path, read/insert/update/delete, olap_one, close) --
def be_sqlite(df, workload):
    import tempfile
    with bc.timed() as t_imp:
        import sqlite3
    rows = _tuples(df)
    path = tempfile.mkdtemp(prefix="tb_sqlite_") + "/db.sqlite"
    with bc.timed() as t_open:
        con = sqlite3.connect(path)
    with bc.timed() as t_schema:
        con.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, post_type INT, "
                    "owner_user_id INT, score INT, view_count INT, title TEXT)")
    with bc.timed() as t_ing:
        con.executemany("INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?)", rows)
        con.commit()
    return dict(
        import_s=t_imp.s, jvm_init_s=0.0, open_s=t_open.s, schema_s=t_schema.s,
        ingest_s=t_ing.s, index_build_s=0.0, db_path=path,
        read=lambda i: con.execute("SELECT * FROM posts WHERE id=?", (i,)).fetchone(),
        insert=lambda r: (con.execute("INSERT OR IGNORE INTO posts VALUES (?,?,?,?,?,?)", r), con.commit()),
        update=lambda i, s: (con.execute("UPDATE posts SET score=? WHERE id=?", (s, i)), con.commit()),
        delete=lambda i: (con.execute("DELETE FROM posts WHERE id=?", (i,)), con.commit()),
        olap_one=lambda q: con.execute(q).fetchall(),
        close=con.close, version=sqlite3.sqlite_version,
    )


def be_duckdb(df, workload):
    import tempfile
    with bc.timed() as t_imp:
        import duckdb
    path = tempfile.mkdtemp(prefix="tb_duckdb_") + "/db.duckdb"
    with bc.timed() as t_open:
        con = duckdb.connect(path)
        con.execute(f"PRAGMA threads={os.cpu_count()}")
    with bc.timed() as t_schema:
        con.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, post_type INT, "
                    "owner_user_id INT, score INT, view_count INT, title VARCHAR)")
    with bc.timed() as t_ing:
        con.register("src", df)  # idiomatic DuckDB bulk load (vectorized from Arrow/pandas)
        con.execute("INSERT INTO posts SELECT * FROM src")
    return dict(
        import_s=t_imp.s, jvm_init_s=0.0, open_s=t_open.s, schema_s=t_schema.s,
        ingest_s=t_ing.s, index_build_s=0.0, db_path=path,
        read=lambda i: con.execute("SELECT * FROM posts WHERE id=?", [i]).fetchone(),
        insert=lambda r: con.execute("INSERT INTO posts VALUES (?,?,?,?,?,?)", list(r)),
        update=lambda i, s: con.execute("UPDATE posts SET score=? WHERE id=?", [s, i]),
        delete=lambda i: con.execute("DELETE FROM posts WHERE id=?", [i]),
        olap_one=lambda q: con.execute(q).fetchall(),
        close=con.close, version=duckdb.__version__,
    )


def be_arcadedb(df, workload):
    import tempfile
    with bc.timed() as t_imp:
        import arcadedb_embedded as arcadedb
        from arcadedb_embedded import jvm
    rows = _tuples(df)
    path = tempfile.mkdtemp(prefix="tb_arcadedb_") + "/db"
    heap = os.environ.get("ARCADEDB_HEAP", "4g")
    with bc.timed() as t_jvm:
        jvm.start_jvm(heap_size=heap)  # heap must match (else medium OOMs)
    with bc.timed() as t_open:
        ctx = arcadedb.create_database(path, jvm_kwargs={"heap_size": heap})
        db = ctx.__enter__()
    with bc.timed() as t_schema:
        db.command("sql", "CREATE DOCUMENT TYPE Post")
        for c, t in [("id", "LONG"), ("post_type", "INTEGER"), ("owner_user_id", "LONG"),
                     ("score", "INTEGER"), ("view_count", "INTEGER"), ("title", "STRING")]:
            db.command("sql", f"CREATE PROPERTY Post.{c} {t}")
        db.command("sql", "CREATE INDEX ON Post (id) UNIQUE_HASH")  # fast point lookups (ex 07)
    with bc.timed() as t_ing:
        db.begin()
        for n, r in enumerate(rows):
            db.command("sql", "INSERT INTO Post SET id=:id, post_type=:pt, owner_user_id=:o, "
                       "score=:s, view_count=:v, title=:t",
                       {"id": r[0], "pt": r[1], "o": r[2], "s": r[3], "v": r[4], "t": r[5]})
            if (n + 1) % 5000 == 0:
                db.commit(); db.begin()
        db.commit()
    with bc.timed() as t_idx:
        if workload == "olap":  # index grouped/filtered columns (ex 08) so no full scan
            for c in ("post_type", "owner_user_id", "score"):
                db.command("sql", f"CREATE INDEX ON Post ({c}) NOTUNIQUE")

    def _tx(fn):
        db.begin()
        try:
            fn(); db.commit()
        except Exception:
            db.rollback()
    return dict(
        import_s=t_imp.s, jvm_init_s=t_jvm.s, open_s=t_open.s, schema_s=t_schema.s,
        ingest_s=t_ing.s, index_build_s=t_idx.s, db_path=path,
        read=lambda i: db.query("sql", "SELECT FROM Post WHERE id=:i", {"i": i}).to_list(),
        insert=lambda r: _tx(lambda: db.command(
            "sql", "INSERT INTO Post SET id=:id, post_type=:pt, owner_user_id=:o, "
            "score=:s, view_count=:v, title=:t",
            {"id": r[0], "pt": r[1], "o": r[2], "s": r[3], "v": r[4], "t": r[5]})),
        update=lambda i, s: _tx(lambda: db.command(
            "sql", "UPDATE Post SET score=:s WHERE id=:i", {"s": s, "i": i})),
        delete=lambda i: _tx(lambda: db.command("sql", "DELETE FROM Post WHERE id=:i", {"i": i})),
        olap_one=lambda q: db.query("sql", q.replace("posts", "Post")).to_list(),
        close=lambda: ctx.__exit__(None, None, None),
        version=getattr(arcadedb, "__version__", "?"),
    )


BACKENDS = {"sqlite": be_sqlite, "duckdb": be_duckdb, "arcadedb": be_arcadedb}


def run_oltp(be, ids, n_ops, seed=0):
    rnd = random.Random(seed)
    next_id = max(ids) + 1
    lat = {"read": [], "insert": [], "update": [], "delete": []}
    t0 = time.time()
    for _ in range(n_ops):
        x = rnd.random()
        s = time.time()
        if x < 0.6:
            be["read"](rnd.choice(ids)); k = "read"
        elif x < 0.8:
            be["update"](rnd.choice(ids), rnd.randint(0, 100)); k = "update"
        elif x < 0.9:
            be["insert"]((next_id, 1, 1, rnd.randint(0, 100), 0, "x")); next_id += 1; k = "insert"
        else:
            be["delete"](rnd.choice(ids)); k = "delete"
        lat[k].append((time.time() - s) * 1000)
    total = time.time() - t0
    out = {"oltp_total_s": round(total, 3), "oltp_ops_per_s": round(n_ops / total, 1)}
    alllat = []
    for k, v in lat.items():
        out.update(bc.latstats(k, v))
        alllat.extend(v)
    out.update(bc.latstats("oltp", alllat))
    return out, lat


def run_olap(be, table, reps=7):
    qs = olap_queries(table)
    per_mean, per_std, raw = [], [], {}
    for idx, q in enumerate(qs):
        samples = [_time_one(be, q) for _ in range(reps)]
        raw[f"olap_q{idx}"] = samples
        s = bc.latstats(f"olap_q{idx}", samples)
        per_mean.append(round(s[f"olap_q{idx}_mean_ms"], 3))
        per_std.append(round(s[f"olap_q{idx}_std_ms"], 3))
    out = {"olap_query_ms": per_mean, "olap_query_std_ms": per_std,
           "olap_total_ms": round(sum(per_mean), 3)}
    pooled = [x for v in raw.values() for x in v]
    out.update(bc.latstats("olap", pooled))
    return out, raw


def _time_one(be, q):
    s = time.time()
    be["olap_one"](q)
    return (time.time() - s) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=BACKENDS)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--workload", required=True, choices=["oltp", "olap"])
    ap.add_argument("--ops", type=int, default=5000)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    df = load_posts(args.data_dir, args.limit)
    ids = df["id"].astype(int).tolist()
    be = BACKENDS[args.backend](df, args.workload)
    ingest_s = be["ingest_s"]
    res = {"backend": args.backend, "lib_version": be["version"], "lane": "tabular",
           "workload": args.workload, "n_rows": len(df),
           "import_s": round(be["import_s"], 4), "jvm_init_s": round(be["jvm_init_s"], 4),
           "open_s": round(be["open_s"], 4), "schema_s": round(be["schema_s"], 4),
           "ingest_s": round(ingest_s, 3), "index_build_s": round(be["index_build_s"], 3),
           "load_s": round(ingest_s, 3),  # continuity
           "ingest_rows_per_s": round(len(df) / ingest_s, 1) if ingest_s else None,
           "olap_indexed": args.backend == "arcadedb" and args.workload == "olap"}
    if args.workload == "oltp":
        m, raw = run_oltp(be, ids, args.ops)
    else:
        m, raw = run_olap(be, "posts")
    res.update(m)
    with bc.timed() as t_close:
        be["close"]()
    res["close_s"] = round(t_close.s, 4)
    res["db_size_mb"] = bc.dir_size_mb(be["db_path"])
    bc.dump_latencies(os.environ.get("RUN_LABEL"), raw)
    print("RESULT " + json.dumps(res))


if __name__ == "__main__":
    main()
