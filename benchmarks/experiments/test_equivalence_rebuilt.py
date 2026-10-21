"""The server-restart lane's vector read is an approximate top 10 from an index built again every repetition, so two
reps may differ while each is right (arcadedb_dense_server at deep10m, recall 0.9 in rep 1 and 1.0
in reps 2 and 3). E2 must list that, not fail it, and must still fail an exact read that changes between reps."""
import equivalence_check as E


def _row(rep, digest, query="restart_knn", model="dense"):
    return {"lane": "restart", "scale": "deep10m", "workload": "restart", "backend": "arcadedb_dense_server",
            "rep": rep, "rc": 0, "instrument": E.REQUIRED_INSTRUMENT, "restart_model": model,
            "durability_class": "relaxed", f"res_{query}_digest": digest, f"res_{query}_n": 10}


def _report(rows):
    groups, _skipped, seen, _silent = E.collect(rows)
    lines = []
    bad, *_ = E.report(groups, seen, out=lines.append)
    return bad, "\n".join(lines)


def test_an_approximate_top_10_that_differs_between_reps_is_listed_not_failed():
    bad, text = _report([_row(1, "6d47c11cea587c61"), _row(2, "57ae75a81c90c8cc"), _row(3, "57ae75a81c90c8cc")])
    assert bad == 0
    assert "E2b" in text and "restart_read_recall_at_10" in text and "E2:" not in text


def test_an_exact_read_that_differs_between_reps_still_fails():
    bad, text = _report([_row(1, "aaaa", "restart_read", "doc"), _row(2, "bbbb", "restart_read", "doc")])
    assert bad == 1
    assert "E2: an engine must agree with itself" in text
