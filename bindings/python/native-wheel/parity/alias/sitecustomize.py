"""Parity-run helper: make `import arcadedb_embedded[.x]` return the installed `arcadedb_native[.x]` modules, so the bindings' own tests run
unchanged against the wheel. (Users switch with `import arcadedb_native as arcadedb`.)
"""

import importlib
import importlib.abc
import importlib.util
import sys


class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        if name == "arcadedb_embedded" or name.startswith("arcadedb_embedded."):
            return importlib.util.spec_from_loader(name, self)
        return None

    def create_module(self, spec):
        return importlib.import_module(
            "arcadedb_native" + spec.name[len("arcadedb_embedded") :]
        )

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, _Alias())
