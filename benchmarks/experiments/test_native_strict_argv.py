"""The strict class on the native server arm: the argument list the container start receives, with no container (pure Python).

The native server image is started with its settings as command-line arguments, and each item of `server_cmd` is ONE argument. The strict
class's durability patch used to map a helper that appends the flush token to any string lacking one over every item, so the argument
list became ["-Xmx4g -Darcadedb.txWalFlush=1", "-Darcadedb.server.mode=development -Darcadedb.txWalFlush=1", ...] and the native
runtime refused the heap size ("Invalid option '-Xmx4g -Darcadedb.txWalFlush=1' does not specify a valid number", server_not_ready).
test_native_server_arm.py only counted the items that START with the token, which the damage never touched.
Run with `python -I -m pytest test_native_strict_argv.py -q` from this directory.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("BENCH_INSTRUMENT", "2026-11")

import runner as R  # noqa: E402

IMAGE = "arcadedata/arcadedb:26.11.1-native"
FLUSH = "-Darcadedb.txWalFlush="
SERVED = sorted(n for n, c in R.BACKENDS.items()
                if "arcadedb" in n and c.get("topology") == "client_server"
                and str(c.get("server_image", "")).startswith("arcadedata/arcadedb") and not c.get("jvm_defaults"))


def native_argv(name, cls, heap="4g"):
    """The argument list the runner passes after the image name for a native cell of this arm and class (the runner formats `{heap}`)."""
    cfg, _ = R.durability_server_patch(R.native_server_arm(R.BACKENDS[name], IMAGE), cls)
    return [c.format(heap=heap) for c in cfg["server_cmd"]]


def test_there_are_served_arms_to_check():
    assert {"arcadedb_server", "arcadedb_graph_server", "arcadedb_e2_server"} <= set(SERVED)


@pytest.mark.parametrize("name", SERVED)
@pytest.mark.parametrize("cls", ["relaxed", "strict"])
def test_every_item_of_a_native_command_is_one_argument(name, cls):
    argv = native_argv(name, cls)
    assert argv[0] == "-Xmx4g"
    assert all(isinstance(c, str) and c and not any(ch.isspace() for ch in c) for c in argv), argv
    assert all(c.startswith("-D") for c in argv[1:]), argv


@pytest.mark.parametrize("name", SERVED)
def test_strict_changes_only_the_flush_item_of_the_native_command(name):
    relaxed, strict = native_argv(name, "relaxed"), native_argv(name, "strict")
    assert [c for c in strict if c.startswith(FLUSH)] == [FLUSH + "1"]
    assert len(strict) == len(relaxed)
    assert [(a, b) for a, b in zip(relaxed, strict) if a != b] == [(FLUSH + "0", FLUSH + "1")]


@pytest.mark.parametrize("name", SERVED)
def test_the_jvm_arm_still_takes_the_strict_flag_as_one_token_in_java_opts(name):
    base = R.BACKENDS[name]
    cfg, note = R.durability_server_patch(base, "strict")
    opts = [e for e in cfg["server_env"] if isinstance(e, str) and e.startswith("JAVA_OPTS=")]
    assert len(opts) == 1 and opts[0].count(FLUSH) == 1 and FLUSH + "1" in opts[0].split() and "txWalFlush=1" in note
    assert cfg["server_cmd"] == list(base.get("server_cmd", []))
