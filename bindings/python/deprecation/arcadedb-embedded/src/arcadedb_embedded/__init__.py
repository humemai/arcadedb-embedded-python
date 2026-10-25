# Copyright © 2021-present Arcade Data Ltd (info@arcadedata.com)
# SPDX-License-Identifier: Apache-2.0
"""Deprecated: ``arcadedb-embedded`` has moved to ``arcadedb-jvm``.

This is the last release of ``arcadedb-embedded``. It is a thin shim: it warns once at import, then hands every name and submodule over to ``arcadedb-jvm``, which provides the module ``arcadedb``.
"""

# ---- per-shim constants: the shims differ only in this block ----
_OLD_DIST = "arcadedb-embedded"
_NEW_DIST = "arcadedb-jvm"
_NEW_MODULE = "arcadedb"
_NOTE = "`arcadedb-jvm` is the same JVM build as this package, so nothing changes at run time (`arcadedb` is the native build, a different runtime)."
# ---- shared body: identical in all shim modules (tests/test_deprecation_shims.py checks it) ----

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import warnings

_MESSAGE = (
    f"The {_OLD_DIST!r} package has moved and this is its last release. "
    f"Install {_NEW_DIST!r} instead (`pip install {_NEW_DIST}`). {_NOTE} "
    f"Write `import {_NEW_MODULE}` where you wrote `import {__name__}`. "
    "New home: https://github.com/ArcadeData/arcadedb-python, "
    "docs: https://docs.arcadedb.com/arcadedb-python/"
)
# FutureWarning, not DeprecationWarning: Python shows it to end users by default.
warnings.warn(_MESSAGE, FutureWarning, stacklevel=2)

_new = importlib.import_module(_NEW_MODULE)
__all__ = list(
    getattr(_new, "__all__", None) or [n for n in dir(_new) if not n.startswith("_")]
)
# the same names `from <module> import *` would bind
globals().update({_n: getattr(_new, _n) for _n in __all__})

_OLD = __name__
_NEW = _new.__name__


class _AliasLoader(importlib.abc.Loader):
    """Hand out the real ``arcadedb`` submodule under the old name, not a second copy."""

    def __init__(self, target):
        self._target = target
        self._spec = None

    def create_module(self, spec):
        module = importlib.import_module(self._target)
        self._spec = module.__spec__
        return module

    def exec_module(self, module):
        # the import machinery stamped the alias spec on the shared module: put its own back
        module.__spec__ = self._spec


class _AliasFinder(importlib.abc.MetaPathFinder):
    """Resolve ``arcadedb_embedded.x.y`` to ``arcadedb.x.y``, also for modules not yet imported."""

    alias_of = _NEW
    old = _OLD

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(_OLD + "."):
            return None
        real = _NEW + fullname[len(_OLD) :]
        try:
            found = importlib.util.find_spec(real)
        except (ImportError, ValueError):
            return None
        if found is None:
            return None
        return importlib.machinery.ModuleSpec(fullname, _AliasLoader(real))


# first in line, so a package alias is not also found on disk and loaded a second time
if not any(
    getattr(f, "alias_of", None) == _NEW and getattr(f, "old", None) == _OLD
    for f in sys.meta_path
):
    sys.meta_path.insert(0, _AliasFinder())

# submodules the new package has already imported answer to the old name right away
for _name, _module in list(sys.modules.items()):
    if _name.startswith(_NEW + ".") and _module is not None:
        sys.modules.setdefault(_OLD + _name[len(_NEW) :], _module)


def __getattr__(name):
    """Anything not star-imported (a private name, a submodule) comes from ``arcadedb``."""
    try:
        return getattr(_new, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None


def __dir__():
    return sorted(set(globals()) | set(dir(_new)))
