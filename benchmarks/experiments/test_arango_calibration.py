"""ArangoDB's calibration fails fast, and every ArangoDB arm runs one image (CAMPAIGN section 7, row 66).

Run with `python -m pytest test_arango_calibration.py -q -rs` from this directory.

On 3.12.11 an IVF index with 10,000 or more lists answered every multithreaded query from ONE list, so
recall was 0.0 even with nProbe = nLists; the calibration escalated to the exhaustive probe, the row
finished "ok", and each repetition spent 1.5 h probing every list. `calibrate_nprobe` now reads recall at
nProbe = nLists first, on a few held-out queries, and raises below a fixed floor of 0.5, so a broken index
ends the cell in minutes. These tests run it against stand-in search functions, with no server.
"""
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arango_common as A  # noqa: E402

K = 10
NLISTS = 12_643


def _queries(n):
    return [[float(i)] for i in range(n)], [list(range(100 * i, 100 * i + K)) for i in range(n)]


def _fixed_list_search():
    """An index that answers every query from the same list: the same ids, whatever the query or nProbe."""
    calls = []

    def search(q, k, nprobe):
        calls.append((q, nprobe))
        return list(range(900_000, 900_000 + k))
    return search, calls


def _healthy_search(gt, needed):
    """An index whose answer is complete once nProbe reaches `needed`, and empty-handed below it."""
    calls = []

    def search(q, k, nprobe):
        calls.append((q, nprobe))
        return list(gt[int(q[0])][:k]) if nprobe >= needed else []
    return search, calls


def test_a_search_answering_from_one_fixed_list_raises_before_the_search():
    queries, gt = _queries(200)
    search, calls = _fixed_list_search()
    with pytest.raises(A.IndexNotAnswering) as e:
        A.calibrate_nprobe(search, queries, gt, 0.9886, NLISTS, k=K)
    assert "does not answer" in str(e.value) and str(NLISTS) in str(e.value)
    # the cell stops at the first exhaustive probe: 20 queries at nProbe = nLists, nothing else
    assert len(calls) == A.EXHAUSTIVE_CHECK_QUERIES
    assert {n for _q, n in calls} == {NLISTS}


def test_the_error_is_a_runtime_error_so_the_cell_ends_as_a_failure():
    assert issubclass(A.IndexNotAnswering, RuntimeError)


def test_a_healthy_index_calibrates_to_the_smallest_sufficient_nprobe():
    queries, gt = _queries(200)
    search, calls = _healthy_search(gt, needed=167)
    nprobe, recall = A.calibrate_nprobe(search, queries, gt, 0.9886, NLISTS, k=K)
    assert (nprobe, recall) == (167, 1.0)
    # the exhaustive check ran first and cost only its 20 queries
    assert [n for _q, n in calls[:A.EXHAUSTIVE_CHECK_QUERIES]] == [NLISTS] * A.EXHAUSTIVE_CHECK_QUERIES


def test_an_exhaustive_probe_under_the_target_but_over_the_floor_is_not_stopped():
    """A healthy exhaustive probe reads 0.995 against a 0.9886 target; the floor is not the target."""
    queries, gt = _queries(200)

    def search(q, k, nprobe):          # 8 of 10 correct whatever the nProbe: recall 0.8, above 0.5, under the target
        return list(gt[int(q[0])][:8]) + [-1, -2]
    nprobe, recall = A.calibrate_nprobe(search, queries, gt, 0.9886, 600, k=K)
    assert nprobe == 600 and recall == pytest.approx(0.8)


def test_the_floor_is_strictly_below_half():
    queries, gt = _queries(40)

    def half(q, k, nprobe):            # exactly 0.5: not below the floor
        return list(gt[int(q[0])][:5]) + [-1] * 5

    def under(q, k, nprobe):           # 0.4: below it
        return list(gt[int(q[0])][:4]) + [-1] * 6
    assert A.calibrate_nprobe(half, queries, gt, 0.4, 100, k=K) == (1, pytest.approx(0.5))
    with pytest.raises(A.IndexNotAnswering):
        A.calibrate_nprobe(under, queries, gt, 0.4, 100, k=K)


def test_the_floor_is_the_decided_constant():
    assert A.EXHAUSTIVE_RECALL_FLOOR == 0.5 and A.EXHAUSTIVE_CHECK_QUERIES == 20


def test_fewer_queries_than_the_check_size_still_check():
    queries, gt = _queries(5)
    search, calls = _fixed_list_search()
    with pytest.raises(A.IndexNotAnswering):
        A.calibrate_nprobe(search, queries, gt, 0.9, 1000, k=K)
    assert len(calls) == 5


def test_the_dense_arm_calibrates_through_this_function():
    """A reimplementation in the lane would bypass the check; the arm must call arango_common's."""
    src = (HERE / "l3d_dense.py").read_text()
    body = src[src.index("class ArangoDense(Base):"):src.index("class ArangoDenseInt8")]
    assert "arango_common.calibrate_nprobe(" in body


# One image for every ArangoDB arm. A split pin would put two ArangoDB versions on one page.
_ARANGO_DIGEST = re.compile(r'"server_image": "arangodb@sha256:([0-9a-f]{64})",\s*#\s*(\S+)')
_OLD_DIGEST = "563cb2c07af0aead37fd688b58f51d6eb534a3da6163621e130e67d7a55176c4"


def test_every_arangodb_arm_runs_one_image_and_it_is_not_the_broken_release():
    runner = (HERE / "runner.py").read_text()
    pins = _ARANGO_DIGEST.findall(runner)
    assert len(pins) == 6, "six ArangoDB arms (tpc, graph, dense, e2, l4, restart) each name their image"
    assert len({d for d, _v in pins}) == 1, "the arms must share one image digest"
    digest, version = pins[0]
    assert digest != _OLD_DIGEST and not version.startswith("3.12.11")
    release = tuple(int(x) for x in version.split("."))
    assert release >= (3, 12, 12), "row 66: ArangoDB 3.12.12 or newer"


def test_the_comparator_table_names_the_same_digest():
    runner = (HERE / "runner.py").read_text()
    digest = _ARANGO_DIGEST.findall(runner)[0][0]
    doc = (HERE / "COMPARATORS.md").read_text()
    row = doc.split("| ArangoDB |")[1].splitlines()[0]
    assert row.lstrip().startswith(f"`arangodb@sha256:{digest[:8]}")   # the current pin leads; the old one may follow as history
