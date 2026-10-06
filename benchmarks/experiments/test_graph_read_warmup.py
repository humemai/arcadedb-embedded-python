"""The graph interactive reads get an untimed warm-up on start persons the timed set never asks for (CAMPAIGN section 7 row 55, DECISIONS #148).

Run with `python -m pytest test_graph_read_warmup.py -q -rs` from this directory.

Through October the lane timed its reads twice over the SAME start persons and the table printed the first pass, so for an
engine on a JVM the printed column included the JIT compiling the query path (ArcadeDB embedded's SF1 point p50 was 3.59x its
second pass, every engine not on a JVM 0.89x to 1.10x). Now every engine runs an untimed warm-up of each read on persons
outside the timed set, the first query of the session is the cold column, and the rows record `read_warmup`.

The lane itself runs here, in-process, against a stand-in adapter that records every read it is asked: the warm-up ids are
disjoint from the timed ids, every warm-up read comes before every timed one, the first read of the session is the cold
number, a slow read's warm-up stops at its share of the read's budget, and the row stops saying "already warm by
construction". No engine is needed.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import graph_common as G  # noqa: E402
import l2_graph as L  # noqa: E402

ANSWER = {"point": [{"name": "p", "age": 40}], "hop1": [{"n": 3, "a": 41.0}], "hop2": [{"n": 9}], "hop3f": [{"n": 20}]}


# ---- the id choice --------------------------------------------------------------------------------------------

def test_warmup_ids_are_disjoint_distinct_deterministic_and_capped():
    universe = list(range(5_000))
    timed = G.pick_query_ids(5_000, 500)
    w1 = G.warmup_ids(universe, timed, n=300)
    assert len(w1) == 300 == len(set(w1))
    assert not set(w1) & set(timed)
    assert w1 == G.warmup_ids(universe, timed, n=300)                       # deterministic
    assert w1 != G.warmup_ids(universe, timed, n=300, seed=G.READ_WARMUP_SEED + 1)


def test_a_corpus_smaller_than_the_warmup_returns_every_other_person():
    w = G.warmup_ids(range(100), [1, 2, 3], n=1000)
    assert sorted(w) == [i for i in range(100) if i not in (1, 2, 3)]


def test_sparse_ids_work_like_ldbc_ones():
    universe = [10_995_116_277_000 + 7 * i for i in range(2_000)]
    timed = universe[::9]
    w = G.warmup_ids(universe, timed, n=500)
    assert not set(w) & set(timed) and set(w) <= set(universe)


# ---- the lane, end to end, on a stand-in adapter ------------------------------------------------------------------

class _Recorder(L.Base):
    name = "stub_graph"
    version = "stub"
    QUERY_LANGUAGE = "stub"
    CALLS = []
    SLOW = {}          # op -> seconds a read of it takes

    def connect(self):
        self.CALLS.clear()

    def build(self, n):
        for _ in L.gen_persons(n):
            pass
        for _ in L.gen_edges(n):
            pass

    def run_read(self, op, pid):
        import time
        self.CALLS.append((op, int(pid)))
        if self.SLOW.get(op):
            time.sleep(self.SLOW[op])
        return ANSWER[op]

    def run_visited(self, pid):
        return [{"n": 3}]

    def run_write(self, pid, new_id):
        pass

    def run_update(self, new_id):
        pass

    def run_delete(self, new_id):
        pass

    def person_scan(self, id_from):
        return []

    def edge_scan(self, id_from):
        return []


@pytest.fixture
def lane(monkeypatch, tmp_path):
    monkeypatch.setitem(L.ADAPTERS, "stub_graph", _Recorder)
    monkeypatch.setenv("BENCH_CRUD_OPS", "10")
    monkeypatch.setattr(L, "CRUD_OPS", 10)
    _Recorder.SLOW = {}

    def run(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, str(v))
        out = tmp_path / "row.json"
        monkeypatch.setattr(sys, "argv", ["l2_graph.py", "--backend", "stub_graph", "--workload", "oltp",
                                           "--scale", "micro", "--out", str(out)])
        L.main()
        return json.loads(out.read_text()), list(_Recorder.CALLS)
    return run


def test_every_warmup_read_is_disjoint_from_the_timed_ids_and_comes_first(lane):
    row, calls = lane()
    timed_list = G.pick_query_ids(G.SCALE_PERSONS["micro"], G.SCALE_OLTP_QUERIES["micro"])
    timed_ids = set(timed_list)
    first_timed = next(i for i, (_op, pid) in enumerate(calls) if pid in timed_ids)
    warm, timed = calls[:first_timed], calls[first_timed:]
    assert warm and all(pid not in timed_ids for _op, pid in warm)
    assert {pid for _op, pid in timed} <= timed_ids                       # nothing else asked after the warm-up
    assert len(timed) == 2 * 4 * len(timed_list)                          # two timed passes of four reads over every id
    for op in ("point", "hop1", "hop2", "hop3f"):
        n = sum(1 for o, _p in warm if o == op)
        assert n == row[f"{op}_warmup_n"] == G.READ_WARMUP_IDS, op


def test_the_first_read_of_the_session_is_the_cold_number_and_the_row_says_what_ran(lane):
    row, calls = lane()
    assert calls[0][0] == "point"
    assert row["cold_first_query_name"] == "point" and row["cold_first_query_ms"] is not None
    assert row["read_warmup"] and row["read_warmup_s"] >= 0
    assert "cold_warm_na" not in row                  # "already warm by construction" is not true of this lane any more
    assert row["knows_direction"] == "undirected"


def test_the_warmup_count_can_be_lowered_and_the_row_records_what_ran(lane, monkeypatch):
    monkeypatch.setattr(G, "READ_WARMUP_IDS", 7)           # BENCH_GRAPH_READ_WARMUP is read when graph_common is imported
    monkeypatch.setattr(L, "READ_WARMUP_IDS", 7)
    row, calls = lane()
    assert row["point_warmup_n"] == 7 and row["hop3f_warmup_n"] == 7


def test_a_slow_read_stops_its_warmup_at_its_share_of_the_budget(lane):
    _Recorder.SLOW = {"hop3f": 0.02}
    # budget 1 s per read, so the warm-up may spend at most READ_WARMUP_BUDGET_SHARE of it: 0.25 s = about 12 reads
    row, _calls = lane(BENCH_GRAPH_READ_BUDGET_S=1)
    assert 1 <= row["hop3f_warmup_n"] < 40
    assert row["point_warmup_n"] == 1000              # the fast reads are not cut


def test_the_old_cold_aliases_of_the_first_pass_are_gone(lane):
    row, _calls = lane()
    assert not any(k.startswith("cold_") and k.endswith(("_p50_ms", "_p99_ms")) for k in row)
    assert "point_p50_ms" in row and "warm_point_p50_ms" in row      # both timed passes stay, so a reader can compare them


# ---- the page's cold column -----------------------------------------------------------------------------------

def test_the_table_prints_a_cold_column_only_for_rows_that_were_warmed(monkeypatch):
    import os
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        monkeypatch.setenv("BENCH_ENGINE_COMMIT", "417314c18")      # export_web refuses to import without a pin
    import export_web as EW
    row = {"lane": "l2", "workload": "oltp", "instrument": "2026-10", "cold_first_query_ms": 4.2}
    labels = lambda: [lbl for _f, lbl in EW._metrics_for("l2", {"metrics": []})]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [dict(row)])               # an October row: the first pass is the cold one
    assert "cold first query ms" not in labels()
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [dict(row, read_warmup="up to 1000 untimed reads")])
    got = labels()
    assert "cold first query ms" in got and got.index("cold first query ms") == got.index("delete p50 ms") + 1
