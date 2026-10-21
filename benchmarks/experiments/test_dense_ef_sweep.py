"""The dense lane's search-beam sweep and matched-recall headline (instrument 2026-11).

Run with `python -m pytest test_dense_ef_sweep.py -q` from this directory. Needs numpy (the lane and export_web import it).

Under 2026-11 the lane builds once, runs the cold pass it has always run, then one timed pass per beam value, and the
headline is the lowest p50 among the passes whose recall@10 reaches a fixed target (dense_beam.py). Under 2026-10 nothing
changes.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dense_beam as DB  # noqa: E402


def pt(beam, recall, p50, p99=None):
    return {"beam": beam, "recall": recall, "p50": p50, "p99": p99 if p99 is not None else p50 * 3}


# ------------------------------------------------------------------ gating

def _enabled(instrument):
    env = dict(os.environ)
    env.pop("BENCH_INSTRUMENT", None)
    if instrument is not None:
        env["BENCH_INSTRUMENT"] = instrument
    r = subprocess.run([sys.executable, "-c", "import dense_beam; print(dense_beam.enabled())"],
                       cwd=HERE, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_the_sweep_is_off_by_default_and_under_2026_10():
    assert _enabled(None) == "False"
    assert _enabled("2026-10") == "False"


def test_the_sweep_is_on_under_2026_11():
    assert _enabled("2026-11") == "True"


def test_the_lane_runs_the_sweep_only_behind_the_gate():
    src = (HERE / "l3d_dense.py").read_text()
    assert src.count("dense_beam.run_sweep(") == 1
    before = src.split("dense_beam.run_sweep(")[0].rsplit("\n", 4)[-3:]
    assert any("if dense_beam.enabled():" in line for line in before)


# ------------------------------------------------------------------ selection

def test_target_reached_at_ef_200_is_the_headline():
    pts = [pt(50, 0.80, 0.3), pt(100, 0.91, 0.5), pt(200, 0.96, 0.9), pt(400, 0.992, 1.7)]
    w = DB.select_matched(pts, 0.95)
    assert w["beam"] == 200 and w["p50"] == 0.9
    assert DB.select_matched(pts, 0.90)["beam"] == 100
    assert DB.select_matched(pts, 0.99)["beam"] == 400


def test_never_reached_has_no_headline():
    pts = [pt(50, 0.60, 0.3), pt(100, 0.70, 0.5), pt(800, 0.80, 3.2)]
    assert DB.select_matched(pts, 0.95) is None
    f = DB.row_fields("ef", pts)
    assert f["matched_r095_status"] == "not reached"
    assert not any(k.startswith("matched_r095_") and k != "matched_r095_status" for k in f)
    assert f["beam_max_recall_at_10"] == 0.8


def test_the_fastest_pass_wins_even_when_latency_is_not_monotone_in_the_beam():
    pts = [pt(100, 0.96, 1.2), pt(200, 0.97, 0.8)]          # a noisy or cached larger beam that ran faster
    assert DB.select_matched(pts, 0.95)["beam"] == 200


def test_ties_go_to_the_smaller_beam():
    pts = [pt(400, 0.97, 0.9), pt(200, 0.96, 0.9), pt(800, 0.98, 0.9)]
    assert DB.select_matched(pts, 0.95)["beam"] == 200


def test_recall_exactly_at_the_target_counts():
    assert DB.select_matched([pt(100, 0.95, 1.0)], 0.95)["beam"] == 100


def test_row_fields_are_named_by_the_beam():
    pts = [pt(50, 0.80, 0.3), pt(100, 0.91, 0.5), pt(200, 0.96, 0.9)]
    f = DB.row_fields("ef", pts)
    assert f["beam_kind"] == "ef" and f["beam_values"] == "50,100,200"
    assert f["ef200_recall_at_10"] == 0.96 and f["ef200_query_p50_ms"] == 0.9 and f["ef200_query_p99_ms"] == 2.7
    assert f["matched_r095_status"] == "reached" and f["matched_r095_beam"] == 200
    assert f["matched_r095_p50_ms"] == 0.9 and f["matched_r095_p99_ms"] == 2.7
    assert f["matched_r090_beam"] == 100 and f["matched_r099_status"] == "not reached"
    # the cold pass keeps its own fields: the sweep never writes them
    assert "query_p99_ms" not in f and "recall_at_10" not in f


def test_nprobe_fields_use_the_nprobe_prefix():
    f = DB.row_fields("nprobe", [pt(8, 0.9, 1.0), pt(16, 0.96, 1.8)])
    assert f["nprobe16_recall_at_10"] == 0.96 and f["matched_r095_beam"] == 16


def test_an_engine_without_a_beam_runs_once_and_says_so():
    f = DB.row_fields("none", [pt(None, 0.97, 4.0)], na="exact scan")
    assert f["beam_kind"] == "none" and f["beam_na"] == "exact scan"
    assert f["matched_r095_status"] == "reached" and "matched_r095_beam" not in f
    assert f["matched_r095_p50_ms"] == 4.0
    miss = DB.row_fields("none", [pt(None, 0.90, 4.0)], na="fixed")
    assert miss["matched_r095_status"] == "not reached" and miss["matched_r090_status"] == "reached"


def test_targets_and_tags():
    assert DB.TARGETS == (0.95, 0.90, 0.99) and DB.HEADLINE_TARGET == 0.95
    assert [DB.tag(t) for t in DB.TARGETS] == ["r095", "r090", "r099"]


def test_ef_list_contains_the_lane_default():
    import l3d_dense
    assert l3d_dense.EF_SEARCH in DB.EF_LIST and sorted(DB.EF_LIST) == list(DB.EF_LIST)


def test_nprobe_list_is_clipped_sorted_and_holds_the_calibrated_value():
    v = DB.nprobe_values(100, 1000)
    assert v == [50, 100, 200, 400]
    assert DB.nprobe_values(3, 1000) == [2, 3, 6, 12]
    assert DB.nprobe_values(400, 500)[-1] == 500 and 400 in DB.nprobe_values(400, 500)


# ------------------------------------------------------------------ the sweep driver

class FakeBackend:
    """Recall rises with the beam; records the beams it was asked to run at."""
    beam_kind = "ef"
    beam_na = None

    def __init__(self):
        self.beam = 100
        self.seen = []

    def beam_values(self):
        return DB.ef_values()

    def beam_default(self):
        return 100

    def set_beam(self, v):
        self.beam = v

    def search(self, q, k):
        self.seen.append(self.beam)
        return list(range(k)) if self.beam >= 200 else list(range(k - 3)) + [900, 901, 902]


class NoKnobBackend(FakeBackend):
    beam_kind = None
    beam_na = "fixed"


COLD = {"recall": 0.9, "p50": 5.0, "p99": 20.0}


def _run(backend):
    import numpy as np
    test = np.zeros((25, 2), dtype="float32")
    gt = np.tile(np.arange(10), (25, 1))
    return DB.run_sweep(backend, test, gt, 5, 10, 20, lambda b, lats, ms: lats.append(ms),
                        lambda v: {"p50": sorted(v)[len(v) // 2], "p99": max(v)},
                        lambda v: sum(v) / len(v), COLD)


def test_run_sweep_takes_every_beam_warms_each_pass_and_restores_the_default():
    b = FakeBackend()
    kind, points, na = _run(b)
    assert kind == "ef" and na is None
    assert [p["beam"] for p in points] == list(DB.EF_LIST)
    assert [round(p["recall"], 1) for p in points] == [0.7, 0.7, 1.0, 1.0]
    for v in DB.EF_LIST:
        assert b.seen.count(v) == 5 + 20           # 5 timed queries and 20 held-out warm-ups at each beam
    assert b.beam == 100                            # the default is back for the mutation phases
    assert DB.select_matched(points, 0.95)["beam"] in (200, 400)     # real (tiny) timings: only the recall gate is fixed


def test_run_sweep_restores_the_default_when_a_pass_fails():
    class Boom(FakeBackend):
        def search(self, q, k):
            if self.beam == 400:
                raise RuntimeError("engine fell over")
            return super().search(q, k)
    b = Boom()
    with pytest.raises(RuntimeError):
        _run(b)
    assert b.beam == 100


def test_an_engine_without_a_knob_runs_no_extra_pass_and_uses_the_cold_pass():
    b = NoKnobBackend()
    kind, points, na = _run(b)
    assert kind == "none" and na == "fixed"
    assert points == [{**COLD, "beam": None}] and b.seen == []


def test_no_cell_is_skipped():
    b = FakeBackend()
    kind, points, na = _run(b)
    assert kind == "ef" and [p["beam"] for p in points] == list(DB.EF_LIST)
    assert not hasattr(DB, "budget_s") and not hasattr(DB, "BUDGET_S")


# ------------------------------------------------------------------ the adapters

@pytest.fixture(scope="module")
def L():
    pytest.importorskip("numpy")
    import l3d_dense
    return l3d_dense


NO_KNOB = {"sqlite_vec_dense", "sqlite_vec_dense_int8", "memgraph_dense", "memgraph_dense_int8", "falkordb_dense"}
NPROBE = {"arangodb_dense", "arangodb_dense_int8"}


def test_every_adapter_declares_its_beam(L):
    for name, cls in L.BACKENDS.items():
        want = None if name in NO_KNOB else "nprobe" if name in NPROBE else "ef"
        assert cls.beam_kind == want, name
        if want is None:
            assert cls.beam_na, f"{name}: an engine with no beam must say why"


def test_the_default_set_beam_moves_the_one_global_the_searches_read(L):
    old = L.EF_SEARCH
    try:
        L.Base().set_beam(400)
        assert L.EF_SEARCH == 400
    finally:
        L.EF_SEARCH = old


def test_arangodb_turns_nprobe_around_the_calibrated_value(L):
    a = L.ArangoDense.__new__(L.ArangoDense)
    a.ivf_nprobe, a.ivf_nlists = 40, 1000
    assert a.beam_default() == 40 and a.beam_values() == [20, 40, 80, 160]
    a.set_beam(80)
    assert a.ivf_nprobe == 80


def test_the_engines_that_bake_the_beam_into_the_connection_override_set_beam(L):
    for cls in (L.Chroma, L.DuckVSS, L.PgVector):
        assert "set_beam" in vars(cls), cls.__name__


# ------------------------------------------------------------------ the export

@pytest.fixture(scope="module")
def EW():
    pytest.importorskip("numpy")
    import export_web
    return export_web


def dense_row(instrument, pts, backend="qdrant_dense", kind="ef", **extra):
    row = {"lane": "l3d", "backend": backend, "scale": "small", "instrument": instrument,
           "query_p50_ms": "1.0", "query_p99_ms": "2.0", "recall_at_10": "0.9"}
    row.update({k: str(v) for k, v in DB.row_fields(kind, pts).items()})
    row.update(extra)
    return row


SPEC = {"metrics": [("query_p50_ms", "cold p50 ms")]}


def test_export_adds_the_matched_columns_when_the_rows_carry_the_sweep(EW, monkeypatch):
    pts = [pt(100, 0.91, 0.5), pt(200, 0.96, 0.9)]
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [dense_row("2026-11", pts)])
    labels = [lab for _f, lab in EW._metrics_for("l3d", SPEC, "l3d")]
    assert labels[0] == "cold p50 ms"
    assert "p50 ms at recall 0.95" in labels and "p99 ms at recall 0.95" in labels
    assert "ef or nProbe at recall 0.95" in labels and "p50 ms at recall 0.99" in labels
    # a table whose rows carry no sweep grows nothing
    plain = dense_row("2026-11", pts)
    plain.pop("beam_kind")
    monkeypatch.setattr(EW, "_FROZEN_ROWS", [plain])
    assert not any(l.startswith("p50 ms at recall") for _f, l in EW._metrics_for("l3d", SPEC, "l3d"))


def test_export_marks_a_target_no_run_reached_and_carries_the_curve(EW):
    rows = [dense_row("2026-11", [pt(100, 0.80, 0.5), pt(200, 0.90, 0.9)]),
            dense_row("2026-11", [pt(100, 0.82, 0.6), pt(200, 0.91, 1.1)])]
    entry = {"metrics": {}}
    EW._beam_extras(entry, rows)
    assert entry["metrics"]["p50 ms at recall 0.95"]["text"].startswith("not reached")
    assert "0.910" in entry["metrics"]["p50 ms at recall 0.95"]["text"]
    assert "p50 ms at recall 0.90" not in entry["metrics"]          # 0.91 reached 0.90: a number, not a mark
    curve = entry["beam_curve"]
    assert curve["kind"] == "ef" and [p["beam"] for p in curve["points"]] == [100, 200]
    assert curve["points"][1]["recall"] == 0.905 and curve["points"][1]["p50"] == 1.0


def test_export_leaves_a_row_without_the_sweep_alone(EW):
    entry = {"metrics": {"cold p50 ms": {"median": 1.0}}}
    EW._beam_extras(entry, [{"lane": "l3d", "backend": "qdrant_dense", "instrument": "2026-11"}])
    assert entry == {"metrics": {"cold p50 ms": {"median": 1.0}}}


def test_export_says_why_an_engine_without_a_beam_ran_once(EW):
    row = dense_row("2026-11", [pt(None, 0.97, 4.0)], backend="sqlite_vec_dense", kind="none")
    row["beam_na"] = "exact scan"
    entry = {"metrics": {}}
    EW._beam_extras(entry, [row])
    assert entry["beam_curve"] == {"kind": "none", "na": "exact scan"}
