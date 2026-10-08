"""The sparse warm-up and the idle-state hold (CAMPAIGN section 7 row 81, DECISIONS #177).

Run with `python -m pytest test_idle_and_warmup.py -q` from this directory.

Both switches are OFF unless the launching environment sets them, and the 26.10.1 chain pulls main at every stage start, so the first group
of tests holds that with both unset the sparse lane makes exactly the calls it made and its row has exactly the fields it had, and the runner
neither opens the device nor adds a field. No engine runs: the lane is driven against a stand-in backend that records its calls.
"""
import json
import os
import struct
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import l3_sparse as S  # noqa: E402
import overrides as OV  # noqa: E402
import runner  # noqa: E402

N_DOCS, N_QUERIES = 20, 40
QUERIES = [([i, i + 1], [1.0, 0.5]) for i in range(N_QUERIES)]


class FakeBackend:
    name = "fake_sparse"
    version = "0"
    calls = []

    def connect(self):
        FakeBackend.calls.append(("connect",))

    def build(self, n):
        FakeBackend.calls.append(("build", n))

    def post_build(self):
        FakeBackend.calls.append(("post_build",))

    def search(self, idx, vals, k):
        FakeBackend.calls.append(("search", tuple(idx)))
        return [1, 2, 3]

    def resolve(self, ids):
        return ids

    def close(self):
        FakeBackend.calls.append(("close",))


def _run_lane(monkeypatch, tmp_path):
    FakeBackend.calls = []
    monkeypatch.setitem(S.BACKENDS, "fake_sparse", FakeBackend)
    monkeypatch.setitem(S.SCALE_DOCS, "micro", N_DOCS)
    monkeypatch.setitem(S.SCALE_QUERIES, "micro", N_QUERIES)
    monkeypatch.setattr(S, "gen_queries", lambda n: QUERIES[:n])
    monkeypatch.setattr(S, "gen_docs", lambda n, *a, **k: iter(()))
    monkeypatch.setattr(S, "build_ordinals", None, raising=False)
    out = tmp_path / "row.json"
    monkeypatch.setattr(sys, "argv", ["l3_sparse.py", "--backend", "fake_sparse", "--scale", "micro", "--out", str(out)])
    S.main()
    return json.loads(out.read_text()), list(FakeBackend.calls)


TIMED = [("search", tuple(q[0])) for q in QUERIES]


def test_with_the_switch_unset_the_lane_makes_exactly_its_old_calls_and_adds_no_field(monkeypatch, tmp_path):
    monkeypatch.delenv(S.WARMUP_ENV, raising=False)
    row, calls = _run_lane(monkeypatch, tmp_path)
    assert calls == [("connect",), ("build", N_DOCS), ("post_build",)] + TIMED + [("close",)]
    assert "sparse_warmup_queries" not in row
    assert row["n_queries"] == N_QUERIES
    assert S.sparse_warmup_n() == 0


def test_the_warmup_runs_n_untimed_searches_before_the_timed_pass_and_stamps_n(monkeypatch, tmp_path):
    monkeypatch.setenv(S.WARMUP_ENV, "7")
    row, calls = _run_lane(monkeypatch, tmp_path)
    searches = [c for c in calls if c[0] == "search"]
    assert len(searches) == 7 + N_QUERIES
    warm, timed = searches[:7], searches[7:]
    assert timed == TIMED                                   # the timed pass is the timed pass, in order
    assert calls.index(("post_build",)) < calls.index(warm[0]) and calls.index(timed[0]) > calls.index(warm[-1])
    assert row["sparse_warmup_queries"] == 7
    assert row["n_queries"] == N_QUERIES and row["query_n"] == N_QUERIES - S.WARMUP      # the percentiles still cover the same queries


def test_the_warmup_draw_is_the_same_for_every_engine_and_is_not_the_first_n():
    a, b = S.warmup_indices(7, N_QUERIES), S.warmup_indices(7, N_QUERIES)
    assert a == b and len(set(a)) == 7 and a != list(range(7))
    assert S.warmup_indices(100, 5) == [0, 1, 2, 3, 4]       # never more than the set holds


@pytest.mark.parametrize("bad", ["0", "-3", "many", "1.5"])
def test_a_warmup_that_is_not_a_positive_integer_ends_the_run(monkeypatch, bad):
    monkeypatch.setenv(S.WARMUP_ENV, bad)
    with pytest.raises(SystemExit):
        S.sparse_warmup_n()


# ---------------------------------------------------------------------------
# the idle-state hold

def test_with_the_switch_unset_the_runner_opens_nothing_and_stamps_nothing(monkeypatch):
    monkeypatch.delenv(runner.CPU_DMA_LATENCY_ENV, raising=False)
    opened = []
    monkeypatch.setattr(runner.os, "open", lambda *a, **k: opened.append(a) or 99)
    assert runner.cpu_dma_latency_target() is None
    row = {"run_id": "x", "rc": 0}
    with runner.CpuDmaLatencyHold(runner.cpu_dma_latency_target()) as hold:
        assert hold.fd is None
        assert hold.stamp(row) is row
    assert row == {"run_id": "x", "rc": 0} and opened == []


def test_the_hold_writes_the_32_bit_target_keeps_the_descriptor_open_for_the_cell_and_closes_it_after(monkeypatch, tmp_path):
    dev = tmp_path / "cpu_dma_latency"
    dev.write_bytes(b"")
    monkeypatch.setattr(runner, "CPU_DMA_LATENCY_DEV", str(dev))
    monkeypatch.setenv(runner.CPU_DMA_LATENCY_ENV, "10")
    row = {}
    with runner.CpuDmaLatencyHold(runner.cpu_dma_latency_target()) as hold:
        fd = hold.fd
        assert fd is not None and runner.os.fstat(fd)          # still open while the cell runs
        assert dev.read_bytes() == struct.pack("=i", 10)
        hold.stamp(row)
    with pytest.raises(OSError):
        runner.os.fstat(fd)                                    # closed after
    assert row == {"cpu_dma_latency_us": 10, "cpu_dma_latency_held": True}


def test_a_target_of_zero_is_a_hold_and_not_unset(monkeypatch, tmp_path):
    dev = tmp_path / "cpu_dma_latency"
    dev.write_bytes(b"")
    monkeypatch.setattr(runner, "CPU_DMA_LATENCY_DEV", str(dev))
    monkeypatch.setenv(runner.CPU_DMA_LATENCY_ENV, "0")
    row = {}
    with runner.CpuDmaLatencyHold(runner.cpu_dma_latency_target()) as hold:
        hold.stamp(row)
    assert dev.read_bytes() == struct.pack("=i", 0) and row["cpu_dma_latency_us"] == 0 and row["cpu_dma_latency_held"] is True


def test_a_device_that_cannot_be_opened_or_written_never_fails_the_cell_and_the_stamp_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "CPU_DMA_LATENCY_DEV", str(tmp_path / "missing" / "cpu_dma_latency"))
    row = {}
    with runner.CpuDmaLatencyHold(10) as hold:
        hold.stamp(row)
    assert row["cpu_dma_latency_us"] == 10 and row["cpu_dma_latency_held"] is False and "cannot open" in row["cpu_dma_latency_error"]
    # opens but refuses the write
    monkeypatch.setattr(runner, "CPU_DMA_LATENCY_DEV", str(tmp_path / "ro"))
    (tmp_path / "ro").write_bytes(b"")
    real_write = runner.os.write

    def refuse(fd, data):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(runner.os, "write", refuse)
    row = {}
    with runner.CpuDmaLatencyHold(10) as hold:
        assert hold.fd is None
        hold.stamp(row)
    monkeypatch.setattr(runner.os, "write", real_write)
    assert row["cpu_dma_latency_held"] is False and "cannot write" in row["cpu_dma_latency_error"]


@pytest.mark.parametrize("bad", ["-1", "fast", "1.5", str(2 ** 31)])
def test_a_target_that_is_not_a_whole_number_of_microseconds_ends_the_run(monkeypatch, bad):
    monkeypatch.setenv(runner.CPU_DMA_LATENCY_ENV, bad)
    with pytest.raises(SystemExit):
        runner.cpu_dma_latency_target()


def test_the_runner_wraps_the_cell_in_the_hold_and_forwards_the_warmup_switch():
    src = (HERE / "runner.py").read_text()
    assert "with CpuDmaLatencyHold(cpu_dma_latency_target()) as _hold:" in src and "_hold.stamp(row)" in src
    assert '"BENCH_SPARSE_WARMUP"' in src                    # forwarded into the container, or the lane never sees it


# ---------------------------------------------------------------------------
# the registry

def test_both_switches_are_registered_judged_only_where_stamped_and_absent_from_the_manifest():
    for key in ("sparse_warmup", "cpu_dma_latency"):
        assert key in OV.BY_KEY
        assert key not in OV.keys_for_backend("qdrant_sparse")      # the default manifest is what it was
    plain = {"instrument": "2026-10", "lane": "l3s", "backend": "qdrant_sparse", "scale": "micro", "workload": "search"}
    assert [f for f in OV.stamp_findings([plain])[0] if f["key"] in ("sparse_warmup", "cpu_dma_latency")] == []
    assert not [o for o in OV.applicable("l3s", ["qdrant_sparse"], [plain]) if o.key in ("sparse_warmup", "cpu_dma_latency")]
    assert not [t for t, _v in OV.notes_for_table("t", "l3s", ["qdrant_sparse"], [plain]) if "untimed" in t or "sleep-state" in t]


def test_the_stamped_rows_are_checked_and_the_sentences_name_the_values_the_rows_carry():
    base = {"instrument": "2026-10", "lane": "l3s", "backend": "qdrant_sparse", "scale": "micro", "workload": "search"}
    ok = dict(base, sparse_warmup_queries=100, cpu_dma_latency_us=10, cpu_dma_latency_held=True)
    assert [f for f in OV.stamp_findings([ok])[0]] == []
    bad = dict(base, cpu_dma_latency_us=10, cpu_dma_latency_held=False)
    assert [f["key"] for f in OV.stamp_findings([bad])[0]] == ["cpu_dma_latency"]            # failed hold with no reason
    assert OV.stamp_findings([dict(bad, cpu_dma_latency_error="Permission denied")])[0] == []
    assert [f["key"] for f in OV.stamp_findings([dict(base, sparse_warmup_queries=0)])[0]] == ["sparse_warmup"]
    text = OV.notes_for_table("t", "l3s", ["qdrant_sparse"], [ok])
    joined = " ".join(t for t, _v in text)
    assert "100 untimed searches" in joined and "held at 10 microseconds" in joined
    refused = " ".join(t for t, _v in OV.notes_for_table("t", "l3s", ["qdrant_sparse"], [dict(bad, cpu_dma_latency_error="x")]))
    assert "refused the hold" in refused
    assert "—" not in joined and "--" not in joined


def test_the_idle_state_disclosure_is_always_on_the_page_setup_block():
    pytest.importorskip("numpy")
    mp = pytest.MonkeyPatch()
    if not os.environ.get("BENCH_ENGINE_COMMIT"):
        mp.setenv("BENCH_ENGINE_COMMIT", "417314c18")
    try:
        import export_web
    finally:
        mp.undo()
    assert "not controlled" in export_web.CPU_IDLE_NOTE and "C10" in export_web.CPU_IDLE_NOTE and "wake up" in export_web.CPU_IDLE_NOTE
    assert "setup.cpu_idle_note" in (HERE / "PAGE-SPEC.md").read_text()
