#!/usr/bin/env python3
"""Hybrid showcase: ONE in-process ArcadeDB, three query languages, one workflow.

The paper's centerpiece — the "only-possible-here from Python" payoff. Over a unified
Question/Answer/User graph (Cross Validated data) with question embeddings, run a single
retrieval workflow that mixes:

  1. VECTOR  — vectorNeighbors(): questions semantically similar to a seed
  2. SQL     — filter/rank those candidates by Score
  3. CYPHER  — graph-traverse to their answers + answerers' reputation

No single Python-embeddable alternative can express all three over the same data in one
process (SQLite=no graph/vector; DuckDB=no Cypher/OLTP; Kùzu=graph+vector, no SQL/document;
Chroma=vector only). Based on the tested patterns in examples/13_*hybrid*.

Usage: python hybrid_showcase.py --data-dir /data/<name>/prepared \
                                 --vectors-dir /data/<name>/vectors --name <name> [--limit N]
Prints RESULT {json} + a human-readable walkthrough.
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
import arcadedb_embedded as arcadedb


def load_question_embeddings(vectors_dir, name):
    base = os.path.join(vectors_dir, f"{name}-questions")
    meta = json.load(open(f"{base}.meta.json"))
    dim = meta["dim"]
    vecs = np.concatenate([
        np.fromfile(os.path.join(vectors_dir, os.path.basename(s["path"])),
                    dtype=np.float32).reshape(-1, dim)
        for s in meta["shards"]])
    pids = [json.loads(l)["post_id"] for l in open(f"{base}.ids.jsonl")]
    return dim, {int(pid): vecs[i] for i, pid in enumerate(pids)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--vectors-dir", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--limit", type=int, default=3000, help="cap #questions for the showcase")
    ap.add_argument("--score-min", type=int, default=1)
    ap.add_argument("--topn", type=int, default=200, help="vector candidates")
    ap.add_argument("--sql-keep", type=int, default=50, help="questions kept after SQL filter")
    ap.add_argument("--topk", type=int, default=10, help="final answers returned")
    ap.add_argument("--warmup", type=int, default=5, help="untimed warmup iterations")
    ap.add_argument("--query-reps", type=int, default=20, help="timed warm query iterations")
    args = ap.parse_args()

    dim, emb = load_question_embeddings(args.vectors_dir, args.name)
    posts = pd.read_parquet(os.path.join(args.data_dir, "posts.parquet"),
                            columns=["id", "post_type", "parent_id", "owner_user_id", "score", "title"])
    users = pd.read_parquet(os.path.join(args.data_dir, "users.parquet"),
                            columns=["id", "reputation"])

    # questions with an embedding (capped), then their answers, then the users involved
    q = posts[(posts.post_type == 1) & (posts.id.isin(emb.keys()))].head(args.limit)
    qids = set(int(x) for x in q.id)
    a = posts[(posts.post_type == 2) & (posts.parent_id.isin(qids))]
    uids = set(int(x) for x in pd.concat([q.owner_user_id, a.owner_user_id]).dropna())
    u = users[users.id.isin(uids)]
    urowset = set(int(x) for x in u.id)

    import tempfile
    t_build = time.time()
    with arcadedb.create_database(tempfile.mkdtemp(prefix="hybrid_") + "/db",
                                  jvm_kwargs={"heap_size": os.environ.get("ARCADEDB_HEAP", "4g")}) as db:
        db.command("sql", "CREATE VERTEX TYPE Question")
        for c, t in [("id", "LONG"), ("title", "STRING"), ("score", "INTEGER"),
                     ("embedding", "ARRAY_OF_FLOATS")]:
            db.command("sql", f"CREATE PROPERTY Question.{c} {t}")
        db.command("sql", "CREATE INDEX ON Question (id) UNIQUE_HASH")
        db.command("sql", "CREATE VERTEX TYPE Answer")
        for c, t in [("id", "LONG"), ("score", "INTEGER")]:
            db.command("sql", f"CREATE PROPERTY Answer.{c} {t}")
        db.command("sql", "CREATE INDEX ON Answer (id) UNIQUE_HASH")
        db.command("sql", "CREATE VERTEX TYPE Userx")  # 'User' is reserved-ish; use Userx
        for c, t in [("id", "LONG"), ("reputation", "INTEGER")]:
            db.command("sql", f"CREATE PROPERTY Userx.{c} {t}")
        db.command("sql", "CREATE INDEX ON Userx (id) UNIQUE_HASH")
        for e in ("ASKED", "HAS_ANSWER", "AUTHORED_BY"):
            db.command("sql", f"CREATE EDGE TYPE {e}")

        # --- load vertices (SQL inserts; embeddings via to_java_float_array) ---
        # Commit periodically across ALL loops so the transaction buffer/WAL stays bounded
        # (a single giant transaction blows up super-linearly at scale).
        BATCH = 5000
        n = 0
        db.begin()
        for r in q.itertuples(index=False):
            db.command("sql", "INSERT INTO Question SET id=:i, title=:t, score=:s, embedding=:e",
                       {"i": int(r.id), "t": (r.title if isinstance(r.title, str) else ""),
                        "s": int(r.score) if pd.notna(r.score) else 0,
                        "e": arcadedb.to_java_float_array(emb[int(r.id)])})
            n += 1
            if n % BATCH == 0:
                db.commit(); db.begin()
        for r in a.itertuples(index=False):
            db.command("sql", "INSERT INTO Answer SET id=:i, score=:s",
                       {"i": int(r.id), "s": int(r.score) if pd.notna(r.score) else 0})
            n += 1
            if n % BATCH == 0:
                db.commit(); db.begin()
        for r in u.itertuples(index=False):
            db.command("sql", "INSERT INTO Userx SET id=:i, reputation=:r",
                       {"i": int(r.id), "r": int(r.reputation) if pd.notna(r.reputation) else 0})
            n += 1
            if n % BATCH == 0:
                db.commit(); db.begin()
        db.commit()
        db.command("sql", f'''CREATE INDEX ON Question (embedding) LSM_VECTOR
            METADATA {{ "dimensions": {dim}, "similarity": "COSINE",
            "maxConnections": 16, "beamWidth": 100 }}''')

        # --- edges via graph_batch (@rid lookups) ---
        qrid = {int(r["id"]): r["rid"] for r in db.query("sql", "SELECT id,@rid as rid FROM Question").to_list()}
        arid = {int(r["id"]): r["rid"] for r in db.query("sql", "SELECT id,@rid as rid FROM Answer").to_list()}
        urid = {int(r["id"]): r["rid"] for r in db.query("sql", "SELECT id,@rid as rid FROM Userx").to_list()}
        pf = db.async_executor().get_parallel_level() > 1

        def batch_edges(pairs):
            with db.graph_batch(batch_size=max(1, len(pairs)), expected_edge_count=max(1, len(pairs)),
                                bidirectional=False, commit_every=max(1, len(pairs)),
                                use_wal=False, parallel_flush=pf) as b:
                for frm, etype, to in pairs:
                    b.new_edge(frm, etype, to)

        asked = [(urid[int(r.owner_user_id)], "ASKED", qrid[int(r.id)]) for r in q.itertuples(index=False)
                 if pd.notna(r.owner_user_id) and int(r.owner_user_id) in urid]
        has_ans = [(qrid[int(r.parent_id)], "HAS_ANSWER", arid[int(r.id)]) for r in a.itertuples(index=False)
                   if int(r.parent_id) in qrid]
        # authorship edge points Answer -> User (forward) so the whole traversal is forward-chained
        answered = [(arid[int(r.id)], "AUTHORED_BY", urid[int(r.owner_user_id)]) for r in a.itertuples(index=False)
                    if pd.notna(r.owner_user_id) and int(r.owner_user_id) in urid]
        batch_edges(asked); batch_edges(has_ans); batch_edges(answered)
        build_s = time.time() - t_build

        # ===================== THE HYBRID WORKFLOW =====================
        # seed = a popular (highest-score) question's vector — "find more like this"
        import statistics as st
        seed_qid = int(q.sort_values("score", ascending=False).iloc[0].id)
        seed = arcadedb.to_java_float_array(emb[seed_qid])

        _dbg = bool(os.environ.get("HYB_DEBUG"))

        def _d(msg):
            if _dbg:
                print(f"    .. {msg} (+{time.time()-t0:.1f}s)", flush=True)

        def run_once():
            global t0
            t0 = time.time()
            # 1) VECTOR: semantically similar questions
            _d("vector start")
            t = time.time()
            cands = db.query("sql",
                "SELECT id, score, distance FROM (SELECT expand(vectorNeighbors(?, ?, ?, ?))) "
                "ORDER BY distance",
                "Question[embedding]", seed, args.topn, 100).to_list()
            vt = time.time() - t
            # 2) SQL: filter/rank those candidates by Score
            _d(f"vector done ({len(cands)} cands); sql start")
            id_list = "[" + ",".join(str(int(c["id"])) for c in cands) + "]"
            t = time.time()
            filt = db.query("sql",
                f"SELECT id, title, score FROM Question WHERE id IN {id_list} "
                f"AND score >= {args.score_min} ORDER BY score DESC LIMIT {args.sql_keep}").to_list()
            stime = time.time() - t
            _d(f"sql done ({len(filt)} kept); graph start")
            # 3) GRAPH: traverse to answers + answerers' reputation via ArcadeDB's SQL MATCH.
            # (SQL MATCH, not OpenCypher: ArcadeDB OpenCypher returns 0 on a multi-edge pattern
            #  combined with a WHERE ... IN [list] filter; SQL MATCH handles it and is GAV-accelerated.)
            fids = "[" + ",".join(str(int(r["id"])) for r in filt) + "]"
            t = time.time()
            hits = db.query("sql",
                f"SELECT qid, aid, ascore, rep FROM ("
                f" MATCH {{type:Question, as:q, where:(id IN {fids})}}-HAS_ANSWER->"
                f"{{type:Answer, as:ans}}-AUTHORED_BY->{{type:Userx, as:usr}} "
                f" RETURN q.id AS qid, ans.id AS aid, ans.score AS ascore, usr.reputation AS rep"
                f") ORDER BY ascore DESC LIMIT {args.topk}").to_list()
            gt = time.time() - t
            return vt, stime, gt, cands, filt, hits

        # warm up (untimed) so we report steady-state latency, not a single cold run
        for i in range(args.warmup):
            vt, stime, gt, *_ = run_once()
            print(f"[warmup {i+1}/{args.warmup}] vec={vt*1000:.1f} sql={stime*1000:.1f} "
                  f"graph={gt*1000:.1f} ms", flush=True)
        vs, ss, gs, ts = [], [], [], []
        for i in range(args.query_reps):
            vt, stime, gt, cands, filt, hits = run_once()
            vs.append(vt * 1000); ss.append(stime * 1000); gs.append(gt * 1000)
            ts.append((vt + stime + gt) * 1000)
            print(f"[rep {i+1}/{args.query_reps}] vec={vt*1000:.1f} sql={stime*1000:.1f} "
                  f"graph={gt*1000:.1f} ms", flush=True)

        def stat(arr):
            return round(st.mean(arr), 2), round(st.pstdev(arr) if len(arr) > 1 else 0.0, 2)
        vm, vsd = stat(vs); sm, ssd = stat(ss); gm, gsd = stat(gs); tm, tsd = stat(ts)
        result = {
            "showcase": "vector->sql->graph(MATCH)", "dataset": args.name,
            "lib_version": getattr(arcadedb, "__version__", "?"),
            "n_questions": len(q), "n_answers": len(a), "n_users": len(u),
            "n_asked": len(asked), "n_has_answer": len(has_ans), "n_answered": len(answered),
            "build_s": round(build_s, 3), "warmup": args.warmup, "query_reps": args.query_reps,
            "vector_ms": vm, "vector_ms_std": vsd, "sql_ms": sm, "sql_ms_std": ssd,
            "graph_ms": gm, "graph_ms_std": gsd,
            "hybrid_total_ms": tm, "hybrid_total_ms_std": tsd,
            "vec_candidates": len(cands), "sql_filtered": len(filt), "graph_hits": len(hits),
            "systems": 1, "processes": 1, "etl_steps": 0,
        }
    print(f"\n=== Hybrid workflow (one in-process ArcadeDB; warm, {args.query_reps} reps) ===")
    print(f"  1. vector  → {len(cands)} similar questions   ({vm} ± {vsd} ms)")
    print(f"  2. sql     → {len(filt)} after Score filter    ({sm} ± {ssd} ms)")
    print(f"  3. graph   → {len(hits)} answers+authors        ({gm} ± {gsd} ms)")
    print(f"  total hybrid latency: {tm} ± {tsd} ms; build {result['build_s']}s; 1 system, 0 ETL")
    if hits:
        print(f"  sample hit: {hits[0]}")
    print("RESULT " + json.dumps(result))


if __name__ == "__main__":
    main()
