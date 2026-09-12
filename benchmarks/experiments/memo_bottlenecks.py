#!/usr/bin/env python3
"""The memo for the ArcadeDB maintainers: where the engine wins and loses.

Every number in the memo's tables is read from results/web_benchmarks.json,
the same payload the project page renders, so the memo cannot drift from the
page. The prose and the "how it was run" tables are the template below; the
few numbers inside prose are computed here too and never typed.

    python memo_bottlenecks.py            -> results/generated/memo_bottlenecks.html

Re-run after every publish that changes a row the memo reads; the file is
then re-published as the artifact the maintainers have the link to.
"""
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAYLOAD = os.path.join(HERE, "results", "web_benchmarks.json")
OUT = os.path.join(HERE, "results", "generated", "memo_bottlenecks.html")


# ------------------------------------------------------------------ data
def load():
    with open(PAYLOAD, encoding="utf-8") as fh:
        d = json.load(fh)
    return {t["id"]: t for t in d["tables"]}, d


def entries(T, tid, scale=None):
    out = []
    for e in T[tid]["entries"]:
        if scale is not None and str(e.get("scale")) != str(scale) and str(e.get("scale_label")) != str(scale):
            continue
        out.append(e)
    return out


def cell(e, col):
    m = e["metrics"].get(col)
    return None if not m or m.get("median") is None else float(m["median"])


def find(T, tid, backend, scale=None):
    for e in entries(T, tid, scale):
        if e["backend"] == backend:
            return e
    raise SystemExit(f"memo: no row {backend!r} in {tid} at {scale!r}; the page changed under the memo")


def best_other(T, tid, col, scale=None, direction="down", recall_floor=None, exclude=lambda e: e["is_arcadedb"]):
    """The comparator with the best value in `col` at `scale`; on vector rows
    only comparators whose recall is at least `recall_floor` qualify, the
    page's own rule for the summary figure."""
    cands = []
    for e in entries(T, tid, scale):
        if exclude(e):
            continue
        v = cell(e, col)
        if v is None:
            continue
        if recall_floor is not None:
            r = cell(e, "recall@10")
            if r is None or r < recall_floor:
                continue
        cands.append((v, e))
    if not cands:
        raise SystemExit(f"memo: no comparator for {tid}/{col} at {scale!r}")
    cands.sort(key=lambda x: x[0], reverse=(direction == "up"))
    return cands


# ------------------------------------------------------------------ format
def fmt_ms(v):
    if v >= 1000:
        return f"{v / 1000:.1f} s"
    if v >= 100:
        return f"{v:.0f} ms"
    if v >= 10:
        return f"{v:.1f} ms"
    if v >= 1:
        return f"{v:.2f} ms"
    return f"{v:.3f} ms" if v >= 0.01 else "<0.01 ms"


def fmt_s(v):
    return f"{v:,.0f} s" if v >= 100 else f"{v:.1f} s"


def fmt_rate(v, unit):
    if v >= 1e6:
        return f"{v / 1e6:.2f}M {unit}/s"
    if v >= 1e3:
        return f"{v / 1e3:.0f}k {unit}/s"
    return f"{v:.0f} {unit}/s"


def fmt_x(r):
    return f"{r:.1f}x" if r < 10 else f"{r:.0f}x"


def ratio_text(ours, theirs, direction):
    """'3.8x ahead' or '660x behind', from the two values and the direction."""
    if direction == "down":
        r = theirs / ours if ours else float("inf")
    else:
        r = ours / theirs if theirs else float("inf")
    if 0.95 <= r <= 1.05:
        return "parity", "even"
    return (f"{fmt_x(r)} ahead", "ahead") if r > 1 else (f"{fmt_x(1 / r)} behind", "behind")


def esc(s):
    return html.escape(str(s), quote=False)


# ------------------------------------------------------------------ rows
def row(cls, model, op, size, ours, theirs, ratio):
    return (f'      <tr class="{cls}"><td class="model">{esc(model)}</td><td>{esc(op)}</td><td>{esc(size)}</td>'
            f'<td class="num">{esc(ours)}</td><td class="num">{esc(theirs)}</td><td class="ratio">{esc(ratio)}</td></tr>')


def compare_row(T, model, op, size, tid, ours_backend, col, scale, direction, fmt, unit=None,
                recall_floor=False, warm_col=None, top=1, skip=()):
    ours = find(T, tid, ours_backend, scale)
    ov = cell(ours, col)
    floor = cell(ours, "recall@10") if recall_floor else None
    # `skip`: comparator labels that do not do the operation the row names
    # (sqlite-vec builds no index, so its "build" is an insert).
    cands = best_other(T, tid, col, scale, direction, recall_floor=floor,
                       exclude=lambda e: e["is_arcadedb"] or any(e["backend"].startswith(k) for k in skip))
    text, cls = ratio_text(ov, cands[0][0], direction)
    if warm_col:
        wo = cell(ours, warm_col)
        # the same comparator on the repeat pass, read by name: the page's rule
        wt = cell(cands[0][1], warm_col)
        if wo is not None and wt is not None:
            wtext, _ = ratio_text(wo, wt, direction)
            text = f"{text}, {wtext} warm"
    f = (lambda v: fmt(v, unit)) if unit else fmt
    theirs = ", ".join(f"{c[1]['backend']} {f(c[0])}" for c in cands[:top])
    return row(cls, model, op, size, f(ov), theirs, text), cls


def wire_row(T, model, op, tid, emb, srv, col, scale, direction, fmt, unit=None):
    a, b = cell(find(T, tid, emb, scale), col), cell(find(T, tid, srv, scale), col)
    r = (b / a) if direction == "down" else (a / b)
    cls = "behind" if r > 1.15 else ""
    f = (lambda v: fmt(v, unit)) if unit else fmt
    return (f'      <tr class="{cls}"><td class="model">{esc(model)}</td><td>{esc(op)}</td>'
            f'<td class="num">{esc(f(a))}</td><td class="num">{esc(f(b))}</td><td class="ratio">{fmt_x(r)}</td></tr>')


def section_tag(classes):
    n_ahead = sum(1 for c in classes if c == "ahead")
    n_behind = sum(1 for c in classes if c == "behind")
    if n_behind == 0:
        return '<span class="tag ahead">ahead</span>'
    if n_ahead == 0:
        return '<span class="tag behind">behind</span>'
    return f'<span class="tag behind">{n_ahead} ahead, {n_behind} behind</span>'


# ------------------------------------------------------------------ build
def build():
    T, d = load()
    pin = ", ".join(d.get("arcadedb_commits") or []) or d.get("arcadedb_version", "")
    E = "ArcadeDB (embedded)"

    # --- strong
    strong, cls = [], []
    for args in (
        ("Documents", "TPC-C new-order transaction: read a part, insert an order line, update stock", "TPC-H scale 1, 6.0M line items",
         "docs_oltp", E, "new-order p50 ms", "tpch1", "down", fmt_ms, None, False, None, 2),
        ("Graph", "Create one edge between two existing vertices, Cypher", "SF10, 73k people",
         "l2", E, "write p50 ms", "sf10", "down", fmt_ms, None, False, None, 1),
        ("Graph", "One-hop traversal from a person over KNOWS edges", "SF10, 73k people",
         "l2", E, "1-hop p50 ms", "sf10", "down", fmt_ms, None, False, None, 1),
        ("Graph", "Two-hop traversal from a person", "SF10, 73k people",
         "l2", E, "2-hop p50 ms", "sf10", "down", fmt_ms, None, False, None, 1),
        ("Cross-model", "Vector search hit, expand over graph edges, update a document, one transaction", "50k products",
         "e2", "ArcadeDB (one transaction)", "p50 ms", "e2", "down", fmt_ms, None, False, None, 1),
        ("Time series", "Ingest through the native time-series type, embedded", "2.59M points",
         "l4", "ArcadeDB (embedded, native time series)", "ingest points/s", None, "up", fmt_rate, "points", False, None, 1),
    ):
        r, c = compare_row(T, *args)
        strong.append(r); cls.append(c)
    strong_tag = section_tag(cls)

    # --- weakness 1: scans
    w1, cls1 = [], []
    for args in (
        ("Documents", "TPC-H Q1: scan every line item, group, and sum", "6.0M line items",
         "docs_olap", E, "Q1 p50 ms", "tpch1", "down", fmt_ms, None, False, None, 2),
        ("Documents", "TPC-H Q6: filter a date range, sum one column", "6.0M line items",
         "docs_olap", E, "Q6 p50 ms", "tpch1", "down", fmt_ms, None, False, None, 2),
        ("Graph", "Whole-graph analytics, most friends: every person's degree, top ten", "SF10, 73k people",
         "l2olap", E, "most friends p50 ms", "sf10", "down", fmt_ms, None, False, None, 1),
        ("Graph", "The same query with the graph analytical view built beforehand", "SF10, 73k people",
         "l2olap", "ArcadeDB (embedded, GAV)", "most friends p50 ms", "sf10", "down", fmt_ms, None, False, None, 1),
        ("Time series", "Twelve-hour aggregate over all series, native type", "2.59M points",
         "l4", "ArcadeDB (embedded, native time series)", "12h aggregate p50 ms", None, "down", fmt_ms, None, False, None, 1),
    ):
        r, c = compare_row(T, *args)
        w1.append(r); cls1.append(c)
    q1_pg = cell(find(T, "docs_olap", "PostgreSQL", "tpch1"), "Q1 p50 ms")
    q1_us = cell(find(T, "docs_olap", E, "tpch1"), "Q1 p50 ms")
    q6_pg = cell(find(T, "docs_olap", "PostgreSQL", "tpch1"), "Q6 p50 ms")
    q6_us = cell(find(T, "docs_olap", E, "tpch1"), "Q6 p50 ms")
    pg_scan_ratio = f"{fmt_x(q6_us / q6_pg)} to {fmt_x(q1_us / q1_pg)}"

    # --- weakness 2: ingest
    w2, cls2 = [], []
    for args in (
        ("Documents", "Load the line items, batched inserts, embedded", "6.0M line items",
         "docs_oltp", E, "ingest documents/s", "tpch1", "up", fmt_rate, "documents", False, None, 2),
        ("Time series", "The same points stored as ordinary documents", "2.59M points",
         "l4", "ArcadeDB (embedded, document path)", "ingest points/s", None, "up", fmt_rate, "points", False, None, 1),
        ("Time series", "The same points through the native time-series type", "2.59M points",
         "l4", "ArcadeDB (embedded, native time series)", "ingest points/s", None, "up", fmt_rate, "points", False, None, 1),
        ("Dense vectors", "Ingest and build the index, 96 dimensions, fp32", "9.99M vectors",
         "l3d", "ArcadeDB (embedded, fp32)", "ingest+index total s", "deep10m", "down", fmt_s, None, False, None, 2, ("sqlite-vec",)),
    ):
        r, c = compare_row(T, *args)
        w2.append(r); cls2.append(c)
    doc_path = cell(find(T, "l4", "ArcadeDB (embedded, document path)"), "ingest points/s")
    native = cell(find(T, "l4", "ArcadeDB (embedded, native time series)"), "ingest points/s")
    native_vs_doc = fmt_x(native / doc_path)

    # --- weakness 3: wire
    w3 = [
        wire_row(T, "Sparse vectors", "Ingest and build the index over 8.84M documents", "l3s",
                 "ArcadeDB (embedded, int8)", "ArcadeDB (server, int8)", "ingest+index total s", "medium", "down", fmt_s),
        wire_row(T, "Time series", "Native-type ingest", "l4",
                 "ArcadeDB (embedded, native time series)", "ArcadeDB (server, native time series)", "ingest points/s", None, "up", fmt_rate, "points"),
        wire_row(T, "Documents", "Batched inserts of the line items", "docs_oltp",
                 E, "ArcadeDB (server)", "ingest documents/s", "tpch1", "up", fmt_rate, "documents"),
    ]

    # --- vectors
    v, clsv = [], []
    for args in (
        ("Dense", "Top-10 nearest neighbours, first pass after the build", "9.99M",
         "l3d", "ArcadeDB (embedded, fp32)", "cold p50 ms", "deep10m", "down", fmt_ms, None, True, None, 1),
        ("Dense", "The same query set again, index resident", "9.99M",
         "l3d", "ArcadeDB (embedded, fp32)", "warm p50 ms", "deep10m", "down", fmt_ms, None, True, None, 1),
        ("Dense", "Top-10, first pass", "1M",
         "l3d", "ArcadeDB (embedded, fp32)", "cold p50 ms", "small", "down", fmt_ms, None, True, "warm p50 ms", 1),
        ("Sparse", "Top-10 over 30k-dimensional weighted-term vectors, first pass", "8.84M",
         "l3s", "ArcadeDB (embedded, int8)", "cold p50 ms", "medium", "down", fmt_ms, None, True, "warm p50 ms", 1),
    ):
        r, c = compare_row(T, *args)
        v.append(r); clsv.append(c)

    # --- numbers the prose needs
    sq = find(T, "docs_oltp", "SQLite", "tpch1")
    sqlite_vs_us = fmt_x(cell(sq, "OLTP ops/s") / cell(find(T, "docs_oltp", E, "tpch1"), "OLTP ops/s"))
    pg_new_order = fmt_x(cell(find(T, "docs_oltp", "PostgreSQL", "tpch1"), "new-order p50 ms")
                         / cell(find(T, "docs_oltp", E, "tpch1"), "new-order p50 ms"))

    tables = {
        "strong": "\n".join(strong), "strong_tag": strong_tag,
        "w1": "\n".join(w1), "w1_tag": section_tag(cls1),
        "w2": "\n".join(w2), "w2_tag": section_tag(cls2),
        "w3": "\n".join(w3),
        "v": "\n".join(v), "v_tag": section_tag(clsv),
        "pin": esc(pin), "pg_scan_ratio": pg_scan_ratio, "native_vs_doc": native_vs_doc,
        "sqlite_vs_us": sqlite_vs_us, "pg_new_order": pg_new_order,
    }
    return TEMPLATE.format(**tables)


# ------------------------------------------------------------------ template
# Doubled braces are literal; single braces are filled from `tables`.
TEMPLATE = r'''<title>ArcadeDB Bottlenecks</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,600&display=swap">
<style>
  :root {{ --ground: #f6f7f8; --paper: #ffffff; --ink: #1b1f26; --ink-2: #4a515c; --ink-3: #7b8290; --rule: #d9dde3; --accent: #1f5f8b; --ahead: #1a6e5a; --ahead-bg: #e3f2ec; --behind: #a8392b; --behind-bg: #f9e6e2; --note-bg: #eef2f6; }}
  @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --ground: #15181d; --paper: #1c2026; --ink: #e8eaee; --ink-2: #b4bac4; --ink-3: #848c99; --rule: #333a44; --accent: #7fb3d9; --ahead: #6fcfae; --ahead-bg: #163b31; --behind: #f08a78; --behind-bg: #44221d; --note-bg: #232931; }} }}
  :root[data-theme="dark"] {{ --ground: #15181d; --paper: #1c2026; --ink: #e8eaee; --ink-2: #b4bac4; --ink-3: #848c99; --rule: #333a44; --accent: #7fb3d9; --ahead: #6fcfae; --ahead-bg: #163b31; --behind: #f08a78; --behind-bg: #44221d; --note-bg: #232931; }}
  body {{ background: var(--ground); color: var(--ink); font-family: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif; font-size: 15px; line-height: 1.55; margin: 0; }}
  main {{ max-width: min(100ch, 94vw); margin: 0 auto; padding: 40px 0 72px; }}
  header {{ border-bottom: 1px solid var(--rule); padding-bottom: 20px; margin-bottom: 32px; }}
  h1 {{ font-family: "Source Serif 4", Georgia, serif; font-weight: 600; font-size: 2rem; line-height: 1.15; margin: 0 0 10px; text-wrap: balance; }}
  .lede {{ color: var(--ink-2); max-width: 70ch; margin: 0; }}
  .meta {{ color: var(--ink-3); font-size: 0.82rem; letter-spacing: 0.04em; text-transform: uppercase; margin: 0 0 8px; }}
  h2 {{ font-family: "Source Serif 4", Georgia, serif; font-weight: 600; font-size: 1.35rem; margin: 40px 0 6px; text-wrap: balance; }}
  h2 .tag {{ font-family: "IBM Plex Sans", sans-serif; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; vertical-align: middle; margin-left: 10px; padding: 2px 8px; border-radius: 3px; }}
  .tag.ahead {{ color: var(--ahead); background: var(--ahead-bg); }}
  .tag.behind {{ color: var(--behind); background: var(--behind-bg); }}
  p {{ max-width: 70ch; }}
  .tablewrap {{ overflow-x: auto; margin: 14px 0 6px; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 760px; font-size: 0.9rem; background: var(--paper); table-layout: fixed; }}
  col.c-model {{ width: 11%; }} col.c-op {{ width: 41%; }} col.c-size {{ width: 11%; }} col.c-a {{ width: 12%; }} col.c-b {{ width: 15%; }} col.c-r {{ width: 10%; }}
  table.wire col.c-op {{ width: 44%; }} table.wire col.c-a, table.wire col.c-b {{ width: 14%; }} table.wire col.c-r {{ width: 17%; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--rule); vertical-align: top; }}
  th {{ font-size: 0.74rem; letter-spacing: 0.05em; text-transform: uppercase; color: var(--ink-3); font-weight: 600; border-bottom: 2px solid var(--rule); }}
  td.num, th.num {{ font-family: "IBM Plex Mono", Menlo, monospace; font-variant-numeric: tabular-nums; font-size: 0.84rem; }}
  td.model {{ color: var(--ink-2); }}
  td.ratio {{ font-family: "IBM Plex Mono", Menlo, monospace; font-weight: 500; font-size: 0.84rem; }}
  tr.ahead td.ratio {{ color: var(--ahead); }}
  tr.behind td.ratio {{ color: var(--behind); }}
  h3 {{ font-size: 0.78rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-3); margin: 18px 0 4px; font-weight: 600; }}
  table.how col.c-row {{ width: 18%; }} table.how col.c-arc {{ width: 41%; }} table.how col.c-cmp {{ width: 41%; }}
  code {{ font-family: "IBM Plex Mono", Menlo, monospace; font-size: 0.8rem; background: var(--note-bg); padding: 1px 4px; border-radius: 3px; overflow-wrap: anywhere; }}
  td.how {{ font-size: 0.86rem; }}
  .note {{ background: var(--note-bg); border-left: 3px solid var(--accent); padding: 10px 14px; margin: 14px 0 0; max-width: 80ch; }}
  .note strong {{ color: var(--accent); }}
  footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule); color: var(--ink-3); font-size: 0.85rem; max-width: 80ch; }}
  @media (max-width: 900px) {{ main {{ max-width: 92vw; }} body {{ font-size: 14px; }} table {{ font-size: 0.84rem; }} }}
  @media (max-width: 600px) {{ main {{ max-width: 94vw; padding-top: 24px; }} h1 {{ font-size: 1.5rem; }} table {{ font-size: 0.78rem; min-width: 560px; }} th, td {{ padding: 6px 7px; }} }}
</style>
<main>
  <header>
    <p class="meta">ArcadeDB, engine build {pin}, one machine, September 2026</p>
    <h1>Where ArcadeDB wins and where it loses, by data model</h1>
    <p class="lede">Every number below is read from the project page's published data: a median of five runs on the same host, every engine in the same container envelope, one job at a time. Ratios are ArcadeDB against the best other engine on that row; on vector rows the best engine is the fastest one whose recall is at least ArcadeDB's. Latencies are p50 over 1,000 queries per pass for search rows, 1,000 transactions or writes for the transactional rows, and 100 runs per rep for analytical queries. Causes are marked as our reading: we measured the engine, we did not profile it.</p>
  </header>

  <h2>One record, one path, one transaction {strong_tag}</h2>
  <div class="tablewrap"><table>
    <colgroup><col class="c-model"><col class="c-op"><col class="c-size"><col class="c-a"><col class="c-b"><col class="c-r"></colgroup>
    <thead><tr><th>Model</th><th>Operation</th><th>Size</th><th class="num">ArcadeDB</th><th class="num">Best other engine</th><th>Ratio</th></tr></thead>
    <tbody>
{strong}
    </tbody>
  </table></div>
  <h3>How it was run</h3>
  <div class="tablewrap"><table class="how">
    <colgroup><col class="c-row"><col class="c-arc"><col class="c-cmp"></colgroup>
    <thead><tr><th>Row</th><th>ArcadeDB</th><th>Comparators</th></tr></thead>
    <tbody>
      <tr><td class="model">TPC-C new-order</td><td class="how">One transaction: <code>SELECT p_retailprice, stock FROM Part WHERE p_partkey = :k</code> (unique index), <code>INSERT INTO OrderNew SET okey=:o, pkey=:p, qty=1</code>, <code>UPDATE Part SET stock = stock - 1 WHERE p_partkey = :k</code>, <code>commit()</code>. 1,000 transactions.</td><td class="how">Same three statements inside BEGIN/COMMIT on PostgreSQL (image defaults, and a tuned row with buffers fitted to the container), DuckDB, and SQLite (WAL, synchronous=NORMAL), primary key on <code>p_partkey</code>.</td></tr>
      <tr><td class="model">Graph write, traversals</td><td class="how">openCypher via <code>db.command("opencypher", ...)</code> and <code>db.query("opencypher", ...)</code>. Write: <code>MATCH (p:Person) WHERE p.id = $id CREATE (q:Person {{...}}) CREATE (p)-[:KNOWS {{since: 2026}}]-&gt;(q)</code>, 1,000 timed writes. Point: <code>MATCH (p:Person) WHERE p.id = $id RETURN p.name, p.age</code>. 1-hop: <code>MATCH (p:Person)-[:KNOWS]-&gt;(f:Person) WHERE p.id = $id RETURN count(f), avg(f.age)</code>. 2-hop: <code>MATCH (p)-[:KNOWS]-&gt;()-[:KNOWS]-&gt;(fof) WHERE p.id = $id RETURN count(DISTINCT fof)</code>. Reads run twice, first pass and repeat pass. Unique index on <code>Person.id</code>; graph loaded through the Java API (<code>newVertex</code>, <code>newEdge</code>) in 5,000-record transactions.</td><td class="how">The identical Cypher text on Neo4j (bolt driver, UNWIND batches to load) and LadybugDB (its Python API, COPY to load). Neo4j runs with heap and page cache set to the same envelope.</td></tr>
      <tr><td class="model">Cross-model transaction</td><td class="how">One SQL transaction: <code>SELECT pid FROM (SELECT expand(vectorNeighbors('Product[embedding]', :q, 10, 100)))</code> on an <code>LSM_VECTOR</code> index, then <code>SELECT expand(out('RELATED')) FROM Product WHERE pid = ...</code>, then <code>UPDATE Product SET views = views + 1 WHERE pid = ...</code> for the six touched products, <code>commit()</code>. For the atomicity test an exception is raised before commit and the transaction rolls back.</td><td class="how">SurrealDB: the same three steps in one SurrealQL transaction through its Python SDK (the published row is still the in-memory store; the on-disk and served re-runs are queued). Composed stack: Qdrant search (gRPC) then Neo4j UNWIND update, two engines, no shared transaction.</td></tr>
      <tr><td class="model">Native time-series ingest</td><td class="how"><code>CREATE TIMESERIES TYPE Point TIMESTAMP ts TAGS (host STRING) FIELDS (uu DOUBLE, us DOUBLE, ui DOUBLE) SHARDS n</code>, then the async executor's <code>append_samples("Point", ts[], host[], uu[], us[], ui[])</code> with primitive NumPy columns in chunks, <code>wait_completion()</code>.</td><td class="how">DuckDB: an Arrow table registered and <code>INSERT INTO p SELECT * FROM src</code>. QuestDB: InfluxDB line protocol over TCP port 9009. SQLite: executemany in 50,000-point transactions.</td></tr>
    </tbody>
  </table></div>

  <p class="note"><strong>Read the write rows with one caveat.</strong> Durability is at each engine's default, and the defaults differ: ArcadeDB does not flush its write-ahead log at commit (<code>txWalFlush=0</code>), PostgreSQL and Neo4j fsync at every commit, SQLite runs in WAL mode with <code>synchronous=NORMAL</code>. On a laptop the same mixed workload on ArcadeDB embedded runs about 10x slower with fsync at commit (insert p50 0.3 ms to 6.4 ms). So the new-order and graph-write leads over the servers are largely this default plus the absence of a network hop, not the engine: the lead over PostgreSQL on new-order is {pg_new_order} today, and in-process SQLite, which pays no network hop either, does {sqlite_vs_us} the transactions per second on the same workload. The reads, traversals, and the cross-model transaction do not depend on it. The next campaign runs every timed write with fsync at commit.</p>

  <h2>Weakness 1: any query that reads most of a table {w1_tag}</h2>
  <div class="tablewrap"><table>
    <colgroup><col class="c-model"><col class="c-op"><col class="c-size"><col class="c-a"><col class="c-b"><col class="c-r"></colgroup>
    <thead><tr><th>Model</th><th>Operation</th><th>Size</th><th class="num">ArcadeDB</th><th class="num">Best other engine</th><th>Ratio</th></tr></thead>
    <tbody>
{w1}
    </tbody>
  </table></div>
  <h3>How it was run</h3>
  <div class="tablewrap"><table class="how">
    <colgroup><col class="c-row"><col class="c-arc"><col class="c-cmp"></colgroup>
    <thead><tr><th>Row</th><th>ArcadeDB</th><th>Comparators</th></tr></thead>
    <tbody>
      <tr><td class="model">TPC-H Q1, Q6</td><td class="how">Standard query text over a DOCUMENT TYPE <code>LineItem</code> with a NOTUNIQUE index on <code>l_shipdate</code>: <code>db.query("sql", q).to_list()</code>. 100 runs per rep, first run recorded as cold, median of the rest as warm.</td><td class="how">Same query text. DuckDB: native tables created from the same frames. PostgreSQL: tables loaded with COPY. SQLite: the same index on <code>l_shipdate</code>.</td></tr>
      <tr><td class="model">Graph analytics</td><td class="how">openCypher: <code>MATCH (p:Person)-[:KNOWS]-&gt;(:Person) RETURN p.id, count(*) AS d ORDER BY d DESC LIMIT 10</code>; <code>MATCH (a)-[:KNOWS]-&gt;(b) WHERE a.city = b.city RETURN a.city, count(*)</code>; <code>MATCH (p)-[:KNOWS]-&gt;(f) RETURN p.city, avg(f.age), count(*)</code>. Run once with <code>CREATE GRAPH ANALYTICAL VIEW ... VERTEX TYPES (Person) EDGE TYPES (KNOWS) ... UPDATE MODE OFF</code> built beforehand (its build time is on the page) and once without it. 100 runs per rep.</td><td class="how">The identical Cypher on Neo4j and LadybugDB, no view or projection on either.</td></tr>
      <tr><td class="model">Time-series 12h aggregate</td><td class="how"><code>SELECT ts.timeBucket('1h', ts) AS h, avg(uu) AS v FROM Point WHERE ts &gt;= a AND ts &lt; b GROUP BY h ORDER BY h</code> on the native TIMESERIES type. 100 runs per rep. (Until 2026-09-12 the embedded arm wrote <code>BETWEEN a AND b-1</code>, which the engine answers about 3x slower; the row is re-run with the half-open form.)</td><td class="how">QuestDB: the same window with <code>SAMPLE BY 1h</code>. DuckDB and SQLite: an hourly bucket over the same rows.</td></tr>
    </tbody>
  </table></div>
  <p class="note"><strong>Our reading.</strong> One thread walks the records, materialises each document, and evaluates the expression per record: no column pruning, no batching, no parallel scan. PostgreSQL is also a row store on page-at-a-time storage and is {pg_scan_ratio} faster on the same two scans, so this is the executor, not the page layout.</p>

  <h2>Weakness 2: bulk ingest {w2_tag}</h2>
  <div class="tablewrap"><table>
    <colgroup><col class="c-model"><col class="c-op"><col class="c-size"><col class="c-a"><col class="c-b"><col class="c-r"></colgroup>
    <thead><tr><th>Model</th><th>Operation</th><th>Size</th><th class="num">ArcadeDB</th><th class="num">Best other engine</th><th>Ratio</th></tr></thead>
    <tbody>
{w2}
    </tbody>
  </table></div>
  <h3>How it was run</h3>
  <div class="tablewrap"><table class="how">
    <colgroup><col class="c-row"><col class="c-arc"><col class="c-cmp"></colgroup>
    <thead><tr><th>Row</th><th>ArcadeDB</th><th>Comparators</th></tr></thead>
    <tbody>
      <tr><td class="model">Document ingest</td><td class="how">Batches of <code>INSERT INTO LineItem (...) VALUES (...)</code> statements joined into one <code>sqlscript</code> command, each batch inside <code>with db.transaction():</code>. Indexes exist before the load.</td><td class="how">PostgreSQL: <code>COPY FROM STDIN</code>, indexes created after. DuckDB: frames of rows, <code>INSERT INTO ... SELECT * FROM df</code>, indexes after. SQLite: executemany in one transaction per batch.</td></tr>
      <tr><td class="model">Time series as documents</td><td class="how"><code>INSERT INTO Point SET host=:h, ts=:t, uu=:a, us=:b, ui=:c</code> per point through <code>db.command</code>, committed in batches, UNIQUE index on <code>(host, ts)</code>.</td><td class="how">Same engines and paths as the native-type row above.</td></tr>
      <tr><td class="model">Dense index build</td><td class="how"><code>INSERT INTO Article SET vid = :v, embedding = :e</code> in 10,000-row transactions, then <code>CREATE INDEX ON Article (embedding) LSM_VECTOR METADATA {{dimensions: 96, similarity: EUCLIDEAN, maxConnections: 32, beamWidth: 100, quantization: ..., storeVectorsInGraph: false, addHierarchy: true}}</code>; ingest and build are one timer on every engine. maxConnections 32 is the per-layer bound equal to the comparators' M = 16.</td><td class="how">Qdrant: upsert in batches, HNSW m = 16, ef_construct = 100. LanceDB: IVF_HNSW_SQ (int8). Chroma, DuckDB VSS, Milvus: HNSW at the same M and ef_construction.</td></tr>
    </tbody>
  </table></div>
  <p class="note"><strong>Our reading.</strong> Single writes are fast (the graph edge row above), so this is throughput under a stream, not per-record cost. The native time-series type shows the engine can fill pages in batches, {native_vs_doc} the rate of the document path on the same points; the document path does not. A bulk document loader that batched page fills the same way would close most of the gap.</p>

  <h2>Weakness 3: the server wire on ingest <span class="tag behind">costs on every lane</span></h2>
  <div class="tablewrap"><table class="wire">
    <colgroup><col class="c-model"><col class="c-op"><col class="c-a"><col class="c-b"><col class="c-r"></colgroup>
    <thead><tr><th>Model</th><th>Operation</th><th class="num">Embedded</th><th class="num">Served</th><th>Cost</th></tr></thead>
    <tbody>
{w3}
    </tbody>
  </table></div>
  <h3>How it was run</h3>
  <div class="tablewrap"><table class="how">
    <colgroup><col class="c-row"><col class="c-arc"><col class="c-cmp"></colgroup>
    <thead><tr><th>Row</th><th>ArcadeDB</th><th>Comparators</th></tr></thead>
    <tbody>
      <tr><td class="model">Served ingest, every lane</td><td class="how"><code>POST /api/v1/command/{{db}}</code> with <code>language: sqlscript</code> and a batch of INSERT or CREATE VERTEX statements as text, values spelled out (a sparse document is about 254 numbers as text). The native time-series server arm is the exception: <code>POST /api/v1/ts/{{db}}/write?precision=s</code> with InfluxDB line protocol in chunks.</td><td class="how">Embedded arm: the same statements through the in-process Python package, or the Java API where the lane uses it, with no serialisation.</td></tr>
    </tbody>
  </table></div>
  <p class="note"><strong>Our reading.</strong> Every value goes in as text inside an INSERT statement and is parsed back. A binary bulk endpoint would fix this without touching the engine.</p>

  <h2>Vectors, the part already in progress {v_tag}</h2>
  <div class="tablewrap"><table>
    <colgroup><col class="c-model"><col class="c-op"><col class="c-size"><col class="c-a"><col class="c-b"><col class="c-r"></colgroup>
    <thead><tr><th>Model</th><th>Operation</th><th>Size</th><th class="num">ArcadeDB</th><th class="num">Best at equal recall</th><th>Ratio</th></tr></thead>
    <tbody>
{v}
    </tbody>
  </table></div>
  <h3>How it was run</h3>
  <div class="tablewrap"><table class="how">
    <colgroup><col class="c-row"><col class="c-arc"><col class="c-cmp"></colgroup>
    <thead><tr><th>Row</th><th>ArcadeDB</th><th>Comparators</th></tr></thead>
    <tbody>
      <tr><td class="model">Dense search</td><td class="how"><code>SELECT vid FROM (SELECT expand(vectorNeighbors('Article[embedding]', ?, 10, 100))) ORDER BY distance</code>: top 10, ef_search 100, query vector passed as a Java float array. 1,000 queries per pass; one build then five passes, pass 1 cold, passes 2 to 5 warm. Recall@10 against the published exact neighbours.</td><td class="how">Qdrant: HNSW search with hnsw_ef = 100, top 10, gRPC. Chroma, LanceDB, DuckDB VSS, Milvus, sqlite-vec: their own top-10 call at the same ef where the engine has one; sqlite-vec is an exact scan.</td></tr>
      <tr><td class="model">Sparse search</td><td class="how"><code>CREATE INDEX ON Doc (tokens, weights) LSM_SPARSE_VECTOR METADATA {{...}}</code> over <code>ARRAY_OF_INTEGERS</code> and <code>ARRAY_OF_FLOATS</code> properties, int8 posting weights by default (fp32 is the ablation row), <code>COMPACT INDEX</code> before timing. Query: <code>SELECT expand(vector.sparseNeighbors('Doc[tokens,weights]', ?, ?, 10))</code> with the query's token ids and weights as Java arrays.</td><td class="how">Qdrant: sparse vectors, upsert then search, top 10. Milvus: <code>SPARSE_INVERTED_INDEX</code>. Elasticsearch: <code>sparse_vector</code> field, refresh and force-merge to one segment before timing, index-time pruning disabled.</td></tr>
    </tbody>
  </table></div>
  <p class="note"><strong>Our reading.</strong> The dense gap is disk paging on the first pass, not the search itself: ArcadeDB pages the index in from disk while the others hold it in memory from the build. The sparse gap is real and stays after warm-up.</p>

  <footer>Each of the two core items reduces to a Java repro against the engine API: a single-threaded group-by over a few million records for the scan path, and a timed loop of document inserts for the bulk path. Full tables, per-engine versions, and image digests are on the project page; this memo is generated from the same data by <code>benchmarks/experiments/memo_bottlenecks.py</code>.</footer>
</main>
'''


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    body = build()
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"memo: {OUT} ({len(body):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
