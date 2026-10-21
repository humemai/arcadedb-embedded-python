"""The dense lane's search-beam sweep and its matched-recall headline (instrument 2026-11 only).

One latency at one search beam says little: an engine that is fast at ef 100 may be fast
because it is answering worse. ANN-benchmarks practice is to compare engines at the SAME
recall, so under BENCH_INSTRUMENT=2026-11 the dense lane builds the index once and, after the
cold timed pass it has always run, runs one more timed pass per beam value on the same built
index. The headline cell is the lowest p50 among the beam values whose recall@10 reaches a
fixed target (0.95; 0.90 and 0.99 are secondary), with the beam that achieved it beside it.

Pure logic, no engine imports, so the selection rule is tested on synthetic rows
(test_dense_ef_sweep.py). The adapters' knobs live in l3d_dense.py (Base.set_beam).

Row fields (the flat names the CSV freeze carries):

    beam_kind                 "ef" (HNSW beam), "nprobe" (IVF lists probed) or "none" (no knob)
    beam_values               the values the sweep ran, "50,100,200,400,800"
    beam_na                   why an engine with no knob ran once
    beam_skipped              why a cell too slow for the sweep kept its cold pass as the one point
    ef100_recall_at_10        per beam value V: <kind>V_recall_at_10, <kind>V_query_p50_ms,
    ef100_query_p50_ms        <kind>V_query_p99_ms (the sweep passes; the cold pass keeps
    ef100_query_p99_ms        query_p50_ms, query_p99_ms, recall_at_10 as before)
    beam_max_recall_at_10     the best recall the sweep reached (the shortfall of a miss)
    matched_r095_status       "reached", "not reached" or "not swept" (beam_skipped), per target (r095, r090, r099)
    matched_r095_beam         the beam value of the winning pass (absent for kind "none")
    matched_r095_p50_ms       the winning pass's p50, p99 and recall (absent when not reached)
    matched_r095_p99_ms
    matched_r095_recall_at_10
"""
import os

import bench_common

# The headline target first, then the secondary columns.
HEADLINE_TARGET = 0.95
TARGETS = (0.95, 0.90, 0.99)
# HNSW-style beams (Qdrant hnsw_ef, Milvus ef, pgvector hnsw.ef_search, ArcadeDB efSearch,
# DuckDB hnsw_ef_search, Chroma ef_search, LanceDB ef, Neo4j SEARCH candidates, SurrealDB,
# MongoDB numCandidates, Elasticsearch num_candidates, LadybugDB efs). 100 is the lane's
# EF_SEARCH, the beam of the cold pass and of every published row until now.
EF_LIST = (50, 100, 200, 400, 800)
# IVF engines (ArangoDB): multiples of the calibrated nProbe, which is the cold pass's value.
NPROBE_MULTIPLES = (0.25, 0.5, 1, 2, 4)
# A cell whose worst-case sweep (sweep_bound_s) is over this many seconds of timed queries keeps its cold pass
# as the one point (BENCH_DENSE_BEAM_BUDGET_S overrides). 1800 s is under a tenth of a deep10m cell's build.
BUDGET_S = 1800.0


def enabled():
    """True when the sweep may run: instrument 2026-11 or later. Under 2026-10 nothing changes."""
    return bench_common.instrument_at_least("2026-11")


def tag(target):
    """'r095' for 0.95: the suffix of the matched_* fields."""
    return f"r{round(target * 100):03d}"


def ef_values():
    return list(EF_LIST)


def nprobe_values(calibrated, nlists):
    """The nProbe list around the calibrated value, clipped to [1, nlists], ascending, deduplicated."""
    vals = {min(max(1, int(round(m * calibrated))), int(nlists)) for m in NPROBE_MULTIPLES}
    vals.add(min(max(1, int(calibrated)), int(nlists)))
    return sorted(vals)


def select_matched(points, target):
    """The point with the lowest p50 among those whose recall reaches `target`, or None.

    Ties on p50 (the latency is rounded to a microsecond) go to the smaller beam: the same
    answer for less work, and a deterministic choice. A point whose beam is None (an engine
    with no knob) sorts as 0."""
    ok = [p for p in points if p["recall"] >= target]
    if not ok:
        return None
    return min(ok, key=lambda p: (p["p50"], p["beam"] if p["beam"] is not None else 0))


def row_fields(kind, points, na=None, skipped=None):
    """The flat row fields for a sweep: `points` is a list of {beam, recall, p50, p99} dicts.

    `kind` is "ef", "nprobe" or "none"; for "none" `points` has one entry with beam None
    (the engine's single operating point) and `na` says why."""
    out = {"beam_kind": kind}
    if skipped:
        out["beam_skipped"] = skipped
    if kind == "none":
        out["beam_na"] = na or "no search-beam setting"
    else:
        out["beam_values"] = ",".join(str(p["beam"]) for p in points)
        for p in points:
            out[f"{kind}{p['beam']}_recall_at_10"] = round(p["recall"], 4)
            out[f"{kind}{p['beam']}_query_p50_ms"] = round(p["p50"], 3)
            out[f"{kind}{p['beam']}_query_p99_ms"] = round(p["p99"], 3)
    out["beam_max_recall_at_10"] = round(max(p["recall"] for p in points), 4)
    for t in TARGETS:
        w = select_matched(points, t)
        k = tag(t)
        if w is None:
            # a skipped cell never tried a larger beam: it did not fail the target, it was not swept
            out[f"matched_{k}_status"] = "not swept" if skipped else "not reached"
            continue
        out[f"matched_{k}_status"] = "reached"
        if w["beam"] is not None:
            out[f"matched_{k}_beam"] = w["beam"]
        out[f"matched_{k}_p50_ms"] = round(w["p50"], 3)
        out[f"matched_{k}_p99_ms"] = round(w["p99"], 3)
        out[f"matched_{k}_recall_at_10"] = round(w["recall"], 4)
    return out


def timed_pass(backend, test, gt, timed_n, k, warm_n, keep, pct, mean):
    """One sweep pass: `warm_n` untimed held-out warm-ups, then `timed_n` timed queries.

    Mirrors the lane's own query loop (held-out warm-up, perf_counter around the search,
    recall against the ground truth) so the passes differ in the beam and nothing else.
    `keep` and `pct` are the lane's own helpers (surreal_common.keep, pct). Returns
    {"beam": None, "recall", "p50", "p99"}; the caller sets the beam."""
    import time
    for q in test[timed_n:timed_n + warm_n]:
        backend.search(q, k)
    lats, recalls = [], []
    for qi in range(timed_n):
        t1 = time.perf_counter()
        ids = backend.search(test[qi], k)
        keep(backend, lats, (time.perf_counter() - t1) * 1e3)
        recalls.append(len(set(ids[:k]) & set(gt[qi].tolist())) / k)
    p = pct(lats)
    return {"beam": None, "recall": mean(recalls), "p50": p["p50"], "p99": p["p99"]}


def sweep_bound_s(values, default, cold_span_s):
    """The worst-case seconds of timed queries the sweep adds, from the cold pass's own span.

    Latency grows at most linearly with the beam, so a pass at beam v costs at most v/default of
    the cold pass (which also paid for the cold caches); the bound is that sum over the list."""
    return cold_span_s * sum(values) / default


def budget_s():
    return float(os.environ.get("BENCH_DENSE_BEAM_BUDGET_S", str(BUDGET_S)))


def run_sweep(backend, test, gt, timed_n, k, warm_n, keep, pct, mean, cold, cold_span_s, beat=None):
    """Run the sweep on a built index and return (kind, points, na, skipped). Restores the default beam.

    `cold` is the cold pass as a point ({"recall", "p50", "p99"}) and `cold_span_s` its wall time.
    Two cases run no extra pass and use the cold pass as the one point, saying why on the row:
    an engine with no beam knob (backend.beam_kind None; `na` names the reason), and a cell whose
    worst-case sweep (sweep_bound_s) would exceed the budget (`skipped` names the numbers), so a
    cell that is slow per query is not made slower by 15 passes."""
    kind = backend.beam_kind
    if kind is None:
        return "none", [{**cold, "beam": None}], backend.beam_na, None
    default = backend.beam_default()
    values = backend.beam_values()
    bound = sweep_bound_s(values, default, cold_span_s)
    if bound > budget_s():
        why = (f"sweep skipped: the cold pass took {cold_span_s:.0f} s, so the {len(values)}-pass sweep could take up to "
               f"{bound:.0f} s, over the {budget_s():.0f} s budget; the cold pass at {kind} {default} is the one point")
        return kind, [{**cold, "beam": default}], None, why
    points = []
    try:
        for v in values:
            backend.set_beam(v)
            if beat is not None:
                beat.mark(f"{kind}-sweep", value=v)
            pt = timed_pass(backend, test, gt, timed_n, k, warm_n, keep, pct, mean)
            pt["beam"] = v
            points.append(pt)
    finally:
        backend.set_beam(default)
    return kind, points, None, None
