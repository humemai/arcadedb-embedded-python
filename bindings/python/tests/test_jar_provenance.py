"""The wheel can say which engine it carries, not just which version it is.

`__version__` is the package version. It is baked from the pom and says
nothing about the JARs that ended up in the wheel, so a build from a locally
patched Java tree reports the released version while shipping a different
engine. That happened: a local build shipped 59 JARs instead of 64 with a
bt-server-patched engine, and only a packaging test that counted JAR names
noticed. Benchmarks against such a wheel record the released version string
beside numbers the release cannot reproduce.

`jar_fingerprint()` hashes what is actually in the JARs: every entry's name
and content. These tests check the hash covers what it claims rather than
merely returning a string, because a fingerprint nobody can trust is worse
than none: it invites exactly the assumption it was added to prevent.

It hashes entries, not files, since 2026-10-04. A CI build of the official
26.9.1 release commit matched `arcadedata/arcadedb:26.9.1` in all 75,699
ArcadeDB classes, yet every ArcadeDB jar differed as a file: the zip
timestamps differ, and `com/arcadedb/arcadedb.properties` records the
buildNumber, timestamp, and branch of the checkout it was built from. A file
hash called those two the same code under two names. The tests at the end
build real jars in a temporary directory to pin what the content fingerprint
ignores (exactly those zip timestamps and those three lines) and what it does
not (any other byte).
"""

import hashlib
import os
import zipfile

import arcadedb_embedded as adb


def test_fingerprint_is_deterministic():
    """Same install, same answer. Otherwise it cannot compare two installs."""
    a = adb.jar_fingerprint()
    b = adb.jar_fingerprint()
    assert a["sha256"] == b["sha256"]
    assert a["count"] == b["count"]
    assert len(a["sha256"]) == 64, "expected a hex sha256"


def test_fingerprint_matches_what_is_on_disk():
    """count and bytes are read from the filesystem, not asserted."""
    fp = adb.jar_fingerprint()
    names = [n for n in os.listdir(fp["jar_dir"]) if n.endswith(".jar")]
    assert fp["count"] == len(
        names
    ), f"fingerprint claims {fp['count']} JARs, directory has {len(names)}"
    total = sum(os.path.getsize(os.path.join(fp["jar_dir"], n)) for n in names)
    assert fp["bytes"] == total
    assert fp["count"] > 0, "a wheel with no JARs is not a working install"


def test_hash_actually_covers_every_jar_name_and_content():
    """Recompute the combined hash from the per-JAR digests.

    This is the test that makes the fingerprint worth trusting. Without it,
    sha256 could be a hash of the count, or of one JAR, or of nothing, and
    every other assertion here would still pass.
    """
    fp = adb.jar_fingerprint(per_jar=True)
    combined = hashlib.sha256()
    for entry in fp["jars"]:
        combined.update(entry["name"].encode())
        combined.update(bytes.fromhex(entry["sha256"]))
    assert combined.hexdigest() == fp["sha256"], (
        "combined hash is not the hash of the per-JAR (name, digest) pairs, so "
        "it does not mean what the docstring says it means"
    )


def test_per_jar_digests_are_the_real_digests():
    """Spot-check against the JAR on disk, so the per-JAR list is evidence.

    ``file_sha256`` is the file's bytes; ``sha256`` is the content digest,
    recomputed here independently from the zip's entries.
    """
    fp = adb.jar_fingerprint(per_jar=True)
    # The largest JAR: most likely to catch a truncated or streamed-wrong read.
    biggest = max(fp["jars"], key=lambda e: e["bytes"])
    path = os.path.join(fp["jar_dir"], biggest["name"])
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    assert (
        h.hexdigest() == biggest["file_sha256"]
    ), f"file digest wrong for {biggest['name']}"
    assert os.path.getsize(path) == biggest["bytes"]
    assert (
        _content_digest(path) == biggest["sha256"]
    ), f"content digest wrong for {biggest['name']}"


def test_renaming_a_jar_would_change_the_fingerprint():
    """Name is hashed, not only content.

    Two JARs swapping filenames leaves the multiset of contents identical. If
    only contents were hashed, that swap would be invisible, and it is exactly
    what a mis-staged JAR_LIB_DIR can produce.
    """
    fp = adb.jar_fingerprint(per_jar=True)
    jars = fp["jars"]
    if len(jars) < 2:
        # Not a skip in disguise: with one JAR the property is vacuous, and
        # test_fingerprint_matches_what_is_on_disk already asserts count > 0.
        return
    swapped = hashlib.sha256()
    order = [jars[1], jars[0]] + jars[2:]
    for name_entry, digest_entry in zip(jars, order):
        swapped.update(name_entry["name"].encode())
        swapped.update(bytes.fromhex(digest_entry["sha256"]))
    assert (
        swapped.hexdigest() != fp["sha256"]
    ), "swapping two JARs' contents does not change the fingerprint"


def test_engine_hash_excludes_our_own_jar():
    """engine_sha256 answers "same ArcadeDB?", sha256 answers "same build?".

    Measured 2026-08-04: the PyPI 26.8.1 wheel and a local build of the same
    version have identical size, identical JAR count, identical total JAR
    bytes, and different sha256. 63 of 64 JARs are byte-identical; the only
    difference is arcadedb-python-bridge.jar, at the same 10907 bytes, because
    it is compiled during the build and carries timestamps.

    So the two hashes must actually differ in coverage, or engine_sha256 is
    decoration and someone will compare the wrong one.
    """
    fp = adb.jar_fingerprint(per_jar=True)
    ours = [j for j in fp["jars"] if not j["engine"]]
    assert ours, "no JAR is marked as ours; _OUR_JARS is stale against the wheel"
    assert fp["engine_count"] == fp["count"] - len(ours)
    assert (
        fp["engine_sha256"] != fp["sha256"]
    ), "engine hash equals the full hash, so it is not excluding anything"

    combined = hashlib.sha256()
    for entry in fp["jars"]:
        if entry["engine"]:
            combined.update(entry["name"].encode())
            combined.update(bytes.fromhex(entry["sha256"]))
    assert (
        combined.hexdigest() == fp["engine_sha256"]
    ), "engine_sha256 is not the hash of exactly the engine JARs"


def test_our_jar_list_still_matches_the_wheel():
    """_OUR_JARS names a JAR that exists.

    If the bridge JAR is ever renamed, every engine comparison silently starts
    including a non-reproducible JAR again and stops meaning what it says.
    """
    from arcadedb_embedded.jvm import _OUR_JARS

    names = {j["name"] for j in adb.jar_fingerprint(per_jar=True)["jars"]}
    missing = _OUR_JARS - names
    assert not missing, (
        f"_OUR_JARS lists {sorted(missing)}, absent from the wheel. Renamed? "
        f"engine_sha256 is now hashing a JAR we build."
    )


def test_exported_from_the_package_root():
    """Harnesses record this next to engine_version, so it must be public."""
    assert "jar_fingerprint" in adb.__all__
    assert callable(adb.jar_fingerprint)


# ---------------------------------------------------------------------------
# The content fingerprint, on real jars built in a temporary directory.
# ---------------------------------------------------------------------------

_PROPERTIES = "com/arcadedb/arcadedb.properties"
_STAMP_KEYS = ("buildNumber", "timestamp", "branch")


def _content_digest(path):
    """The documented per-JAR content digest, written out independently.

    SHA-256 over every entry in name order: the name's UTF-8 length (4 bytes,
    big-endian), the name, and the SHA-256 of the entry's content. In
    ``com/arcadedb/arcadedb.properties`` the buildNumber, timestamp, and
    branch lines are dropped first.
    """
    h = hashlib.sha256()
    with zipfile.ZipFile(path) as z:
        for info in sorted(z.infolist(), key=lambda i: i.filename):
            data = z.read(info)
            if info.filename == _PROPERTIES:
                data = b"".join(
                    line
                    for line in data.splitlines(keepends=True)
                    if line.split(b"=", 1)[0].strip().decode("latin-1")
                    not in _STAMP_KEYS
                )
            name = info.filename.encode("utf-8")
            h.update(len(name).to_bytes(4, "big"))
            h.update(name)
            h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def _properties(build_number, timestamp, branch, version="26.9.1"):
    return (
        "#\n# Copyright 2021-present Arcade Data Ltd\n#\n\n"
        f"version = {version}\n"
        "groupId = com.arcadedb\n"
        "artifactId = arcadedb-engine\n"
        f"buildNumber = {build_number}\n"
        f"timestamp =  {timestamp}\n"
        f"branch = {branch}\n"
    ).encode()


_CLASS = b"\xca\xfe\xba\xbe\x00\x00\x00\x41" + bytes(range(256)) * 8
_MANIFEST = b"Manifest-Version: 1.0\r\nCreated-By: Maven JAR Plugin 3.5.1\r\n\r\n"


def _write_jar(path, entries, date_time, compression):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.compress_type = compression
            z.writestr(info, data)


def _lib(
    tmp_path,
    label,
    *,
    build_number="9cea8e848fa57d275b8d614328245508cd76614a",
    timestamp="1788462493960",
    branch="main",
    version="26.9.1",
    engine_class=_CLASS,
    date_time=(2026, 9, 3, 19, 9, 0),
    compression=zipfile.ZIP_DEFLATED,
):
    """A two-jar lib dir shaped like the image's: one ArcadeDB jar, one third-party jar."""
    lib = tmp_path / label
    lib.mkdir()
    _write_jar(
        lib / "arcadedb-engine-26.9.1.jar",
        [
            ("META-INF/MANIFEST.MF", _MANIFEST),
            ("com/arcadedb/", b""),
            ("com/arcadedb/Engine.class", engine_class),
            (_PROPERTIES, _properties(build_number, timestamp, branch, version)),
        ],
        date_time,
        compression,
    )
    _write_jar(
        lib / "lz4-java-1.11.3.jar",
        [("META-INF/MANIFEST.MF", _MANIFEST), ("net/jpountz/Lz4.class", _CLASS[::-1])],
        date_time,
        compression,
    )
    return lib


def _fingerprint(lib):
    return adb.jar_fingerprint(per_jar=True, jar_dir=str(lib))


def test_a_rebuild_of_the_same_code_has_the_same_fingerprint(tmp_path):
    """Official jars and a source build of the same commit: one fingerprint.

    The second set differs exactly as a CI source build of 26.9.1 differed
    from the image: zip timestamps, the buildNumber, timestamp, and branch
    lines, and (here) the compression too, so every file's bytes differ.
    """
    official = _fingerprint(_lib(tmp_path, "official"))
    ours = _fingerprint(
        _lib(
            tmp_path,
            "ours",
            build_number="b6a92623554bb332d7564de19fbd9fdbc2d1d45e",
            timestamp="1791113419878",
            branch="UNKNOWN",
            date_time=(2026, 10, 4, 11, 31, 6),
            compression=zipfile.ZIP_STORED,
        )
    )
    # Not vacuous: as files, the two sets share no bytes worth a digest.
    for a, b in zip(official["jars"], ours["jars"]):
        assert a["name"] == b["name"]
        assert a["file_sha256"] != b["file_sha256"], a["name"]
        assert a["sha256"] == b["sha256"], f"{a['name']}: same entries, new digest"
    assert official["sha256"] == ours["sha256"]
    assert official["engine_sha256"] == ours["engine_sha256"]
    # The build stamp is reported, not hashed: it tells the two builds apart.
    assert official["build_number"] == "9cea8e848fa57d275b8d614328245508cd76614a"
    assert ours["build_number"] == "b6a92623554bb332d7564de19fbd9fdbc2d1d45e"


def test_one_changed_class_changes_the_fingerprint(tmp_path):
    """A single byte of one class is a different engine."""
    base = _fingerprint(_lib(tmp_path, "base"))
    patched_class = bytearray(_CLASS)
    patched_class[100] ^= 0x01
    patched = _fingerprint(_lib(tmp_path, "patched", engine_class=bytes(patched_class)))
    assert patched["sha256"] != base["sha256"]
    assert patched["engine_sha256"] != base["engine_sha256"]
    by_name = {j["name"]: j["sha256"] for j in base["jars"]}
    changed = [j["name"] for j in patched["jars"] if by_name[j["name"]] != j["sha256"]]
    assert changed == ["arcadedb-engine-26.9.1.jar"]


def test_only_the_three_build_lines_are_ignored(tmp_path):
    """Every other line of arcadedb.properties still counts.

    The engine reports ``version`` at run time, so a jar that says 26.9.2 is
    not the 26.9.1 engine whatever its classes are.
    """
    base = _fingerprint(_lib(tmp_path, "base"))
    other = _fingerprint(_lib(tmp_path, "other", version="26.9.2"))
    assert other["engine_sha256"] != base["engine_sha256"]


def test_build_number_is_the_engine_jars(tmp_path):
    """build_number is read from the engine jar on disk, and None without one."""
    fp = adb.jar_fingerprint()
    assert isinstance(fp["build_number"], str) and fp["build_number"]
    engine = [n for n in os.listdir(fp["jar_dir"]) if n.startswith("arcadedb-engine-")]
    assert len(engine) == 1, engine
    with zipfile.ZipFile(os.path.join(fp["jar_dir"], engine[0])) as z:
        lines = z.read(_PROPERTIES).decode("latin-1").splitlines()
    stamped = [
        line.split("=", 1)[1].strip()
        for line in lines
        if line.split("=", 1)[0].strip() == "buildNumber"
    ]
    assert stamped == [fp["build_number"]]

    no_engine = tmp_path / "no-engine"
    no_engine.mkdir()
    _write_jar(
        no_engine / "lz4-java-1.11.3.jar",
        [("net/jpountz/Lz4.class", _CLASS)],
        (2026, 9, 3, 19, 9, 0),
        zipfile.ZIP_DEFLATED,
    )
    assert adb.jar_fingerprint(jar_dir=str(no_engine))["build_number"] is None
