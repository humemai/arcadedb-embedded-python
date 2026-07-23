#!/usr/bin/env python3
"""Generate the paper's LaTeX tables (T2-T5) from results/runs.jsonl +
results/l4_tsbs.jsonl.

Canonical-row rule (see CAMPAIGN_2026-07.md): latest row per
(lane, scale, workload, backend, rep), rc==0, paper scales only.
Cells are median [min-max] over N=5 reps. Raw rows are never edited;
rerun this script after the October freeze re-measure.

Outputs: ../latex/tables/t{2,3,4,5}_*.tex + tables_summary.md (prose crib).
"""
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(HERE, "..", "..", ".notes", "papers", "icde-2027", "latex", "tables")

PAPER_SCALES = {"l1": ["medium"], "l1tpc": ["tpch1"], "l2": ["sf1", "sf10"],
                "l3s": ["tiny", "small"], "l3d": ["small", "deep10m"],
                "e2": ["e2"]}

NAMES = {
    "arcadedb_embedded": "ArcadeDB (emb)", "arcadedb_server": "ArcadeDB (srv)",
    "duckdb": "DuckDB", "postgres": "PostgreSQL",
    "arcadedb_graph_embedded": "ArcadeDB (emb)",
    "arcadedb_graph_server": "ArcadeDB (srv)",
    "neo4j_graph": "Neo4j", "ladybug_graph": "LadybugDB",
    "arcadedb_sparse_embedded": "ArcadeDB (emb, int8)",
    "arcadedb_sparse_embedded_fp32": "ArcadeDB (emb, fp32)",
    "arcadedb_sparse_embedded_nocompact": "ArcadeDB (emb, no settle)",
    "arcadedb_sparse_server": "ArcadeDB (srv)",
    "qdrant_sparse": "Qdrant", "milvus_sparse": "Milvus",
    "elasticsearch_sparse": "Elasticsearch",
    "arcadedb_dense_embedded": "ArcadeDB (emb)",
    "arcadedb_dense_server": "ArcadeDB (srv)",
    "qdrant_dense": "Qdrant", "milvus_dense": "Milvus",
    "chroma_dense": "Chroma", "lancedb_dense": "LanceDB",
    "sqlite_vec_dense": "sqlite-vec", "duckdb_vss_dense": "DuckDB-VSS",
    "arcadedb_e2": "ArcadeDB (one txn)", "surrealdb_e2": "SurrealDB (one txn)",
    "composed_qdrant_neo4j": "Qdrant+Neo4j (composed)",
    "questdb": "QuestDB", "arcadedb": "ArcadeDB (emb)",
}


def load_canonical():
    # Dedupe on PAYLOAD fields, never run_id: pre-2026-07-21 run_ids were not
    # scale-qualified, so different scales collided under one id (the 100k
    # sparse tier was invisible under run_id-keyed dedupe).
    rows = [json.loads(l) for l in open(os.path.join(RESULTS, "runs.jsonl"))
            if l.strip()]
    best = {}
    for r in rows:
        if r.get("rc") != 0:
            continue
        if r["scale"] not in PAPER_SCALES.get(r["lane"], []):
            continue
        k = (r["lane"], r["scale"], r.get("n_docs"), r.get("workload"),
             r["backend"], r["rep"])
        if k not in best or r["ts_utc"] > best[k]["ts_utc"]:
            best[k] = r
    return list(best.values())


def cells(rows, key):
    g = {}
    for r in rows:
        g.setdefault(key(r), []).append(r)
    return g


def fmt(v, unit=""):
    if v is None:
        return "--"
    if abs(v) >= 10000:
        return f"{v:,.0f}{unit}"
    if abs(v) >= 100:
        return f"{v:.0f}{unit}"
    if abs(v) >= 1:
        return f"{v:.2f}{unit}"
    return f"{v:.3f}{unit}"


def mmm(rs, field, scale=1.0):
    v = [r[field] * scale for r in rs if isinstance(r.get(field), (int, float))]
    if not v:
        return "--"
    if len(v) < 5:
        pass  # still report, caption states N per cell
    return f"{fmt(st.median(v))} [{fmt(min(v))}--{fmt(max(v))}]"


def write(name, body):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w") as f:
        f.write(body)
    print("wrote", name)


def tabular_table(rows):
    l1 = [r for r in rows if r["lane"] == "l1"]
    tpc = [r for r in rows if r["lane"] == "l1tpc"]
    order = ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres"]
    lines = [r"\begin{tabular}{lrrrrr}", r"\toprule",
             r"System & Ingest (rows/s) & OLTP (ops/s) & Insert p99 (ms) & "
             r"TPC-H Q1 (ms) & Q6 (ms) \\", r"\midrule"]
    for be in order:
        oltp = [r for r in l1 if r["backend"] == be and r["workload"] == "oltp"]
        tq = [r for r in tpc if r["backend"] == be and r["workload"] == "olap"]
        lines.append(" & ".join([
            NAMES[be], mmm(oltp, "ingest_rows_per_s"),
            mmm(oltp, "oltp_ops_per_s"), mmm(oltp, "insert_p99_ms"),
            mmm(tq, "q1_ms"), mmm(tq, "q6_ms")]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t2_tabular.tex", "\n".join(lines) + "\n")


def graph_table(rows):
    l2 = [r for r in rows if r["lane"] == "l2"]
    order = ["arcadedb_graph_embedded", "arcadedb_graph_server",
             "neo4j_graph", "ladybug_graph"]
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"System & Scale & Build (s) & 1-hop p50 (ms) & 1-hop p99 (ms) & "
             r"2-hop p99 (ms) \\", r"\midrule"]
    for be in order:
        for sc in ("sf1", "sf10"):
            g = [r for r in l2 if r["backend"] == be and r["scale"] == sc
                 and r["workload"] == "oltp"]
            if not g:
                continue
            lines.append(" & ".join([
                NAMES[be], sc.upper(), mmm(g, "build_s"),
                mmm(g, "hop1_p50_ms"), mmm(g, "hop1_p99_ms"),
                mmm(g, "hop2_p99_ms")]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t3_graph.tex", "\n".join(lines) + "\n")


def sparse_table(rows):
    l3s = [r for r in rows if r["lane"] == "l3s"]
    order = ["arcadedb_sparse_embedded", "arcadedb_sparse_embedded_fp32",
             "arcadedb_sparse_server", "qdrant_sparse", "milvus_sparse",
             "elasticsearch_sparse"]
    lines = [r"\begin{tabular}{llrrrr}", r"\toprule",
             r"System & Corpus & Build (s) & p50 (ms) & p99 (ms) & "
             r"Recall@10 \\", r"\midrule"]
    for be in order:
        for sc, label in (("tiny", "100k"), ("small", "1M")):
            g = [r for r in l3s if r["backend"] == be and r["scale"] == sc]
            if not g:
                continue
            lines.append(" & ".join([
                NAMES[be], label, mmm(g, "build_s"),
                mmm(g, "query_p50_ms"), mmm(g, "query_p99_ms"),
                mmm(g, "recall_at_10")]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t4_sparse.tex", "\n".join(lines) + "\n")


def dense_ts_table(rows):
    l3d = [r for r in rows if r["lane"] == "l3d" and r["scale"] == "deep10m"]
    order = ["arcadedb_dense_embedded", "arcadedb_dense_server", "qdrant_dense",
             "milvus_dense", "chroma_dense", "lancedb_dense",
             "sqlite_vec_dense", "duckdb_vss_dense"]
    lines = [r"\begin{tabular}{lrrrr}", r"\toprule",
             r"\multicolumn{5}{l}{\textit{Dense ANN, DEEP-10M "
             r"(10M$\times$96d), degree-matched}} \\",
             r"System & Build (s) & p50 (ms) & p99 (ms) & Recall@10 \\",
             r"\midrule"]
    for be in order:
        g = [r for r in l3d if r["backend"] == be]
        if not g:
            continue
        lines.append(" & ".join([
            NAMES[be], mmm(g, "build_s"), mmm(g, "query_p50_ms"),
            mmm(g, "query_p99_ms"), mmm(g, "recall_at_10")]) + r" \\")
    ts = [json.loads(l) for l in open(os.path.join(RESULTS, "l4_tsbs.jsonl"))
          if l.strip()]
    lines += [r"\midrule",
              r"\multicolumn{5}{l}{\textit{Time series, TSBS cpu-only "
              r"(2.59M points)}} \\",
              r"System & Ingest (pts/s) & Last point (ms) & 1h bucket (ms) & "
              r"12h global (ms) \\", r"\midrule"]
    for be in ("arcadedb", "duckdb", "questdb"):
        g = [r for r in ts if r["backend"] == be]
        lines.append(" & ".join([
            NAMES[be], mmm(g, "ingest_pts_per_s"), mmm(g, "q_last_ms"),
            mmm(g, "q_range_ms"), mmm(g, "q_global_ms")]) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("t5_dense_ts.tex", "\n".join(lines) + "\n")


def e2_summary(rows):
    e2 = [r for r in rows if r["lane"] == "e2"]
    out = ["# E2 + prose numbers crib (not a table; quoted in text)\n"]
    for be in ("arcadedb_e2", "surrealdb_e2", "composed_qdrant_neo4j"):
        h = [r for r in e2 if r["backend"] == be and r["workload"] == "hybrid"]
        a = [r for r in e2 if r["backend"] == be and r["workload"] == "atomicity"]
        torn = [r.get("torn_state") for r in a]
        out.append(f"- {NAMES[be]}: hybrid p50 {mmm(h, 'hybrid_p50_ms')} ms, "
                   f"p99 {mmm(h, 'hybrid_p99_ms')} ms; torn state "
                   f"{sum(bool(t) for t in torn)}/{len(torn)} trials")
    write("tables_summary.md", "\n".join(out) + "\n")


def main():
    rows = load_canonical()
    print(f"{len(rows)} canonical rows")
    tabular_table(rows)
    graph_table(rows)
    sparse_table(rows)
    dense_ts_table(rows)
    e2_summary(rows)


if __name__ == "__main__":
    main()
