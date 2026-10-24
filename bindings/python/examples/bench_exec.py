#!/usr/bin/env python3
"""Print the environment a Docker-wrapped benchmark example runs in, then run it.

The Docker wrappers of examples 07 to 12 start the measured script as

    uv run --no-project --python <python> --with <package> ... python bench_exec.py <script> <args>

This file prints one line with the interpreter and one line per installed package
(name==version, from ``importlib.metadata``, the ``pip freeze`` equivalent), then
replaces itself with ``python -u <script> <args>``. The measured process is the
same interpreter in the same environment that printed the versions, so the log of
a run records exactly what it ran with. Compare the lines of two runs to check that
two setups install the same versions.

It runs inside the container, from the examples directory, and uses only the
standard library.
"""

import importlib.metadata
import os
import platform
import sys


def installed_packages():
    versions = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if name:
            versions[name.lower().replace("_", "-")] = dist.version
    return dict(sorted(versions.items()))


def main(argv):
    if not argv:
        print("usage: bench_exec.py <script.py> [args...]", file=sys.stderr)
        return 2
    print(
        f"[bench-env] python={platform.python_version()} "
        f"implementation={platform.python_implementation()} "
        f"machine={platform.machine()} executable={sys.executable}",
        flush=True,
    )
    for name, version in installed_packages().items():
        print(f"[bench-env] {name}=={version}", flush=True)
    os.execv(sys.executable, [sys.executable, "-u", *argv])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
