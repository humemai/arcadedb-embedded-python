"""ArcadeDB's strict durability class is txWalFlush=1 (CAMPAIGN section 7 row 5, the user's decision of 2026-10-04).

Run with `python -m pytest test_strict_durability.py -q -rs` from this directory.

`txWalFlush=2` is FileChannel.force(true): the log's data and metadata at every commit, one fsync. SQLite's FULL in WAL mode is one
fdatasync, which is `1` (force(false)); upstream's transactions documentation recommends 1 for production and says 2 adds no recovery
value over it, with no measurable performance difference. Matching SQLite by effect, the strict class moves to 1 at the re-pin and
the page says so beside the rows measured at 2. Every route by which the flag reaches the engine is held here: the embedded JVM
argument, the async executor's own spelling, the served container's JAVA_OPTS, the read-back, and the classification of both strings.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common as B  # noqa: E402


def test_the_embedded_jvm_argument_follows_the_class():
    assert B.arcade_jvm_args("-Xms1g", cls="strict") == "-Xms1g -Darcadedb.txWalFlush=1"
    assert B.arcade_jvm_args("-Xms1g", cls="relaxed") == "-Xms1g -Darcadedb.txWalFlush=0"
    assert B.ARCADE_STRICT_TX_WAL_FLUSH == 1


def test_the_async_executors_own_spelling_is_the_one_that_matches():
    """The executor's writers ignore txWalFlush and stamp their own flush, so a load through it is told separately."""
    assert B.arcade_async_sync("strict") == "yes_nometadata" and B.arcade_async_sync("relaxed") == "no"


def test_the_served_container_gets_the_same_flag():
    import runner
    cfg = {"server_env": ["JAVA_OPTS=-Xmx2g"], "server_cmd": []}
    patched, note = runner.durability_server_patch(cfg, "strict")
    env = " ".join(str(x) for x in patched["server_env"])
    assert "-Darcadedb.txWalFlush=1" in env and "txWalFlush=2" not in env and "txWalFlush=1" in note
    relaxed, _ = runner.durability_server_patch(cfg, "relaxed")
    assert relaxed["server_env"] == ["JAVA_OPTS=-Xmx2g"]


def test_the_strings_classify_and_the_october_one_is_still_strict():
    assert B.durability_class(B.DURABILITY_ARCADEDB_STRICT) == "strict"
    assert B.durability_class(B.DURABILITY_ARCADEDB_STRICT_FULL_SYNC) == "strict"      # the October rows
    assert B.durability_class(B.DURABILITY_ARCADEDB) == "relaxed"
    assert B.DURABILITY_ARCADEDB_STRICT.startswith("txWalFlush=1:")
    assert B.DURABILITY_ARCADEDB_STRICT_FULL_SYNC == "txWalFlush=2: the WAL is flushed and synced at every commit"
    assert B.at_class(B.DURABILITY_ARCADEDB, "strict") == B.DURABILITY_ARCADEDB_STRICT


def test_the_page_sentence_about_the_change_is_keyed_on_the_october_text_not_the_new_one():
    """It must stand for as long as a row measured at 2 stands behind a table, and go when the last one does."""
    import re
    ew = (HERE / "export_web.py").read_text()
    assert re.search(r'^_ARCADEDB_FULL_SYNC = "%s"$' % re.escape(B.DURABILITY_ARCADEDB_STRICT_FULL_SYNC), ew, re.M)
    assert not B.DURABILITY_ARCADEDB_STRICT.startswith(B.DURABILITY_ARCADEDB_STRICT_FULL_SYNC)
    assert re.search(r"^_ARCADEDB_STRICT_NEXT = %d\b" % B.ARCADE_STRICT_TX_WAL_FLUSH, ew, re.M)


class _GC:
    def __init__(self, v):
        self.TX_WAL_FLUSH = type("V", (), {"getValue": staticmethod(lambda: v)})()


@pytest.mark.parametrize("value,want", [(0, B.DURABILITY_ARCADEDB), (1, B.DURABILITY_ARCADEDB_STRICT),
                                        (2, B.DURABILITY_ARCADEDB_STRICT_FULL_SYNC)])
def test_the_readback_reports_the_value_the_engine_answers_with(monkeypatch, value, want):
    import types
    fake = types.SimpleNamespace(JClass=lambda name: _GC(value))
    monkeypatch.setitem(sys.modules, "jpype", fake)
    assert B.arcade_durability_readback() == want


def test_the_readback_names_a_value_that_is_neither_class(monkeypatch):
    import types
    monkeypatch.setitem(sys.modules, "jpype", types.SimpleNamespace(JClass=lambda name: _GC(7)))
    assert "neither class" in B.arcade_durability_readback()


def test_no_lane_still_asks_for_the_full_sync():
    """e3_recovery characterizes BOTH contracts' loss windows on purpose; every other source file speaks of the class through bench_common."""
    for f in sorted(HERE.glob("*.py")):
        if f.name.startswith("test_") or f.name in ("e3_recovery.py", "bench_common.py", "export_web.py"):
            continue
        assert "txWalFlush=2" not in f.read_text().replace("txWalFlush=2 is", "").replace("YES_FULL was 2", ""), f.name
