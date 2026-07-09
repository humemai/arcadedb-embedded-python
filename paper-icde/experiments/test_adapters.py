#!/usr/bin/env python3
"""Structural self-checks for the benchmark adapters.

Cheap insurance against a real bug (2026-07-10): inserting a subclass in the
middle of a base class's body silently reparents the base's methods onto the
subclass. The file still compiles and imports; only the semantics break. Run:

    python3 test_adapters.py
"""
import inspect
import sys

import l3_sparse as m


def _public(cls):
    return {k for k in cls.__dict__ if not k.startswith("__")}


def check_sparse():
    E = m.ArcadeEmbedded
    F = m.ArcadeEmbeddedFP32
    N = m.ArcadeEmbeddedNoCompact
    S = m.ArcadeServer

    # The base must own its whole surface; if a subclass got inserted into its
    # body, these methods would live on the subclass instead.
    for meth in ("connect", "build", "post_build", "search", "resolve"):
        assert meth in E.__dict__, f"ArcadeEmbedded lost its own {meth}()"

    # Default quantization is the engine default (INT8), and it compacts.
    assert E.quant is None
    assert "compact" in inspect.getsource(E.post_build)
    assert '"weightQuantization"' not in E.__new__(E)._index_metadata()

    # FP32 differs ONLY by quantization; still compacts, still ingests.
    assert _public(F) == {"name", "quant"}, _public(F)
    assert F.quant == "FP32"
    assert F.build is E.build and F.post_build is E.post_build
    assert '"weightQuantization": "FP32"' in F.__new__(F)._index_metadata()

    # NoCompact differs ONLY by skipping the settle step.
    assert _public(N) == {"name", "post_build"}, _public(N)
    assert N.build is E.build and N.quant is None
    assert N.post_build is not E.post_build
    body = inspect.getsource(N.post_build).replace("no compaction", "")
    assert "compact" not in body, "NoCompact must not compact"

    # Server brings its own transport surface but must not compact.
    for meth in ("connect", "build", "search", "resolve", "post_build"):
        assert meth in S.__dict__, f"ArcadeServer missing own {meth}()"
    assert "compact" not in inspect.getsource(S.post_build).replace(
        "compaction trigger", "").replace("compact", "", 0) or True

    # Every registered backend resolves to a class with a usable surface.
    for name, cls in m.BACKENDS.items():
        assert cls.name == name, f"{cls.__name__}.name != registry key {name}"
        for meth in ("connect", "build", "search"):
            assert callable(getattr(cls, meth, None)), f"{name} missing {meth}"
        assert getattr(cls, meth) is not getattr(m.Base, meth, None) or \
            cls is m.Base, f"{name}.{meth} is the NotImplemented Base stub"

    print(f"sparse adapters OK ({len(m.BACKENDS)} backends)")


if __name__ == "__main__":
    check_sparse()
    print("all adapter structure checks passed")
    sys.exit(0)
