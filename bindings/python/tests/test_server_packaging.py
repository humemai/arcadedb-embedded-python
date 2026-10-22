"""The server stack is actually IN the wheel, and the API is reachable.

This file exists because of a specific failure. On 2026-07-05 commit cfcde0c2
excluded the server JARs and deleted ``server.py`` to save ~7 MB, that shipped
in stable 26.7.2 on 2026-07-09, and nobody noticed for three weeks until a
downstream user said so on the commit itself. The other server tests were
guarded by a helper that skipped them when the JARs were missing, so they did
not fail: **they skipped, silently, and the suite stayed green.** That guard is
gone, and CI now fails any skip it does not list (scripts/check_test_skips.py),
so a wheel without the server stack fails the server tests as well as these.

These tests state the packaging requirement directly: if the server stack is
absent, they fail.

If a future build genuinely wants a slim wheel, that is a decision to make on
purpose, by deleting this file with a commit message that says why, not by
letting a packaging change quietly turn a suite green.
"""

import os
import zipfile

import pytest

# The JAR families that make server mode work. Sizes as measured on the
# 26.8.1-SNAPSHOT image (uncompressed, MB) are in docs/guide/server.md. Studio is
# deliberately NOT in this list: the wheels leave it out (test_studio_is_not_bundled).
REQUIRED_JAR_PREFIXES = [
    "arcadedb-server",  # the server itself, 0.66 MB
    "undertow-core",  # HTTP server, 2.21 MB
    "xnio-api",  # undertow's IO layer
    "xnio-nio",
    "wildfly-common",
    "jboss-logging",
    "jboss-threads",
    "micrometer-core",  # required at server startup, not optional
]


def _jar_names():
    from arcadedb_embedded.jvm import get_jar_path

    jar_dir = get_jar_path()
    assert os.path.isdir(jar_dir), f"jar directory missing: {jar_dir}"
    return sorted(os.listdir(jar_dir))


def test_server_jars_are_bundled():
    """Every JAR server mode needs is present. Fails, never skips."""
    names = _jar_names()
    missing = [
        p for p in REQUIRED_JAR_PREFIXES if not any(n.startswith(p) for n in names)
    ]
    assert not missing, (
        f"server JARs missing from the wheel: {missing}\n"
        f"This is how server mode was lost in 26.7.2. If the removal is "
        f"deliberate, delete this test explicitly rather than letting the "
        f"suite go quiet.\n"
        f"jars present: {names}"
    )


def test_server_api_is_importable_and_exported():
    """create_server / ArcadeDBServer are importable AND in __all__.

    Both halves matter: the classes existing but not being exported is the
    same breakage from a user's point of view, since the documented import is
    ``from arcadedb_embedded import create_server``.
    """
    import arcadedb_embedded as adb

    assert hasattr(adb, "ArcadeDBServer"), "ArcadeDBServer not importable"
    assert hasattr(adb, "create_server"), "create_server not importable"
    assert "ArcadeDBServer" in adb.__all__, "ArcadeDBServer missing from __all__"
    assert "create_server" in adb.__all__, "create_server missing from __all__"


def test_studio_is_not_bundled():
    """No Studio jar and no ApexCharts file in the installed package.

    Studio bundles ApexCharts, which has not been open source since 5.1.0, and this
    package is Apache-2.0 (https://github.com/ArcadeData/arcadedb/issues/10579).
    scripts/jar_exclusions.txt leaves the jar out and scripts/verify_wheel_no_studio.py
    guards the wheel; this checks what pip actually installed.
    """
    from arcadedb_embedded.jvm import get_jar_path

    jar_dir = get_jar_path()
    studio = [n for n in os.listdir(jar_dir) if n.lower().startswith("arcadedb-studio")]
    assert not studio, f"Studio jar bundled again: {studio}"

    package_dir = os.path.dirname(jar_dir)
    for root, _dirs, files in os.walk(package_dir):
        for name in files:
            path = os.path.join(root, name)
            assert (
                "apexcharts" not in name.lower()
            ), f"ApexCharts file in the wheel: {path}"
            if name.endswith(".jar"):
                with zipfile.ZipFile(path) as z:
                    hits = [n for n in z.namelist() if "apexcharts" in n.lower()]
                assert not hits, f"{name} carries ApexCharts files: {hits[:3]}"


@pytest.mark.server
def test_server_root_says_studio_is_not_bundled(temp_server_root):
    """GET / answers 200 with the server's own "Studio is not bundled" page.

    Without the Studio jar the server serves a self-contained notice at the root
    (GetDynamicContentHandler.missingResourceFallback) instead of a bare 404 that
    would look like a broken server. Other missing assets stay 404.
    """
    requests = pytest.importorskip("requests")
    from arcadedb_embedded import create_server
    from tests.conftest import TEST_PASSWORD

    with create_server(
        root_path=temp_server_root, root_password=TEST_PASSWORD
    ) as server:
        base = server.get_studio_url()
        root = requests.get(base, timeout=30)
        assert root.status_code == 200
        assert "text/html" in root.headers.get("Content-Type", "")
        assert "not bundled" in root.text
        assert "ArcadeDB Server is running" in root.text
        assert "apexcharts" not in root.text.lower()
        missing = requests.get(base + "studio-does-not-exist.js", timeout=30)
        assert missing.status_code == 404


@pytest.mark.server
def test_server_starts_and_serves_http(temp_server_root):
    """End-to-end: the bundled stack actually starts and answers.

    The packaging tests above prove the files are present. This proves they
    work together, which is the claim a user actually cares about.
    """
    requests = pytest.importorskip("requests")
    from arcadedb_embedded import create_server
    from tests.conftest import TEST_PASSWORD

    with create_server(
        root_path=temp_server_root, root_password=TEST_PASSWORD
    ) as server:
        assert server.is_started()
        port = server.get_http_port()
        r = requests.get(
            f"http://localhost:{port}/api/v1/server?mode=basic",
            auth=("root", TEST_PASSWORD),
            timeout=30,
        )
        assert r.status_code == 200, f"server returned {r.status_code}"
        assert "version" in r.json()
