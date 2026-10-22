"""arcadedb-embedded-native: a pure-Python tree plus one prebuilt shared library, tagged py3-none-<platform>.

The platform tag comes from ARCADEDB_NATIVE_PLAT (build_wheel.py computes it from the library's glibc symbol versions).
"""

import os

from setuptools import setup
from setuptools.dist import Distribution

try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
except ImportError:  # pragma: no cover
    _bdist_wheel = None


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


cmdclass = {}
if _bdist_wheel is not None:

    class bdist_wheel(_bdist_wheel):
        def finalize_options(self):
            super().finalize_options()
            self.root_is_pure = False  # platlib, not purelib

        def get_tag(self):
            return "py3", "none", os.environ["ARCADEDB_NATIVE_PLAT"]

    cmdclass["bdist_wheel"] = bdist_wheel

setup(distclass=BinaryDistribution, cmdclass=cmdclass)
