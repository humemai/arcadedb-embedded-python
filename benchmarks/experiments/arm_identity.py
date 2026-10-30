"""What an ArcadeDB arm is, for every script that reads rows.

Since 26.11.1 one release is measured on two builds of the same Python package API: `arcadedb` (native) and `arcadedb-jvm` (Java engine
through JPype). Both stamp the same `engine_version` and the same `backend` arm name (`arcadedb_sparse_embedded`, ...); only the row
field `engine_backend` ("native" or "jvm") tells them apart. A consumer that groups or dedupes on `engine_version` alone would pool or
overwrite the two builds, so the identity of an in-process ArcadeDB arm is (engine_version, build), and this module is the one
definition of `build`:

  * `engine_backend` is "native" or "jvm": that value.
  * a row of an ArcadeDB in-process arm WITHOUT the field, or with it empty (every row before 26.11.1, and those rows read back from the
    frozen CSV): "jvm", because that is what it ran.
  * a served ArcadeDB arm (`arcadedb_server`, `arcadedb_graph_server`, ...) carries the build of the SERVER it talked to since
    #222: "jvm" for the official Docker server image, "native" for the native wheel's in-process server (native_server_launcher.py).
    A served row without the field (every row before it) is "jvm", the only server there was. The image-defaults sensitivity arm
    (`arcadedb_imgdefaults_server`), the HTTP client container and every comparator carry None: they have no native counterpart.

`select_build(rows, want)` is the one place a freeze picks a build: with BENCH_ENGINE_BACKEND=native|jvm the other build's in-process
ArcadeDB rows leave the freeze (they stay in runs.jsonl); without it BOTH builds stay, and the page shows them side by side as two arms
(`splits_page`, `build_label`: "ArcadeDB (embedded, native build)" next to "ArcadeDB (embedded, JVM build)"). A table entry still never
pools the two (`refuse_pooled_builds`). `pair_problems(rows)` is the gate over a two-build freeze: one engine commit, one engine_version.
No import of ArcadeDB, no I/O: safe in every consumer, including the ones that read old rows.
"""
import os

BUILDS = ("native", "jvm")
ENV = "BENCH_ENGINE_BACKEND"

# Backend names that are ArcadeDB but not an in-process arm: the served engine and its client container.
_NOT_IN_PROCESS = ("server", "http_client", "imgdefaults")


def is_arcadedb(r):
    return str(r.get("backend") or "").startswith("arcadedb")


def in_process(r):
    b = str(r.get("backend") or "")
    return b.startswith("arcadedb") and not any(t in b for t in _NOT_IN_PROCESS)


def served(r):
    """True for a served ArcadeDB arm that stands once per build: the HTTP server arms, not the image-defaults sensitivity arm."""
    b = str(r.get("backend") or "")
    return b.startswith("arcadedb") and "server" in b and not any(t in b for t in ("http_client", "imgdefaults"))


def built(r):
    """True for an ArcadeDB arm that stands once per build: an in-process arm or a served one (#222)."""
    return in_process(r) or served(r)


def build_of(r):
    """"native", "jvm" or None for the row (see the module docstring)."""
    eb = r.get("engine_backend")
    if eb in BUILDS:
        return eb
    # No usable field: an old row, or a row read back from the frozen CSV, where a row from before 26.11.1 has the column empty.
    if built(r) and not eb:
        return "jvm"
    return None


def arm_identity(r):
    """(engine_version, build): what two rows must share to be one measurement of one engine."""
    return (str(r.get("engine_version") or ""), build_of(r))


def identities(rows):
    """The set of (engine_version, build) over the in-process ArcadeDB rows."""
    return {arm_identity(r) for r in rows if built(r)}


def wanted_build(env=None):
    """The build a freeze was asked for ("native" or "jvm"), or None. A value that is neither is an error, not None."""
    v = (os.environ.get(ENV, "") if env is None else env).strip().lower()
    if not v:
        return None
    if v not in BUILDS:
        raise SystemExit(f"{ENV}={v!r}: expected one of {BUILDS}")
    return v


def select_build(rows, want=None):
    """The rows a freeze may publish.

    `want` None reads BENCH_ENGINE_BACKEND. With a build, rows of the other build are dropped (served arms and comparators carry no
    build and stay): a deliberate one-build freeze. Without one every row stays, and the page shows the two builds as two arms
    (`splits_page`); the exporter groups on the build, so no median is taken over native and JVM rows together.
    """
    want = wanted_build() if want is None else want
    if want:
        return [r for r in rows if not (built(r) and build_of(r) not in (None, want))]
    return rows


def stamp_build(row, wheel_build):
    """Give an ArcadeDB row (in-process or served) its build when the row names none: the build of the wheel its runner was pinned to, or,
    for a served row, the server's own (`server_build`, written by the runner at launch).

    A cell killed by its cap or by the kernel writes a row from the runner, not from the engine process, so the row has no
    engine_backend of its own; without this a native timeout would read as the JVM build (the default for an unstamped row).
    Returns the row.
    """
    if built(row) and not row.get("engine_backend"):
        if served(row) and row.get("server_build") in BUILDS:
            row["engine_backend"] = row["server_build"]
        elif in_process(row) and wheel_build in BUILDS:
            row["engine_backend"] = wheel_build
    if built(row) and row.get("engine_backend") in BUILDS and not row.get("cpu_baseline"):
        row["cpu_baseline"] = cpu_baseline(row["engine_backend"], served(row))
    return row


# THE CPU BASELINE OF EACH ARTIFACT, disclosed on the page and left as built. The native wheel is compiled with `-march=compatibility`
# (runs on any x86-64 CPU); upstream's official native server image is compiled for `native.march` (native/pom.xml: x86-64-v3 on amd64, i.e.
# AVX2/BMI2/FMA, set by ArcadeData/arcadedb#10581; override with ARCADEDB_NATIVE_SERVER_MARCH if a different image is pinned); the JVM
# server and the JVM wheel compile at run time for the CPU they run on.
NATIVE_WHEEL_MARCH = "compatibility"
NATIVE_SERVER_MARCH_DEFAULT = "x86-64-v3"


def native_server_march(env=None):
    return ((os.environ if env is None else env).get("ARCADEDB_NATIVE_SERVER_MARCH", "").strip() or NATIVE_SERVER_MARCH_DEFAULT)


def cpu_baseline(build, is_server, env=None):
    """The CPU baseline sentence stamped on a row of `build` ("native" / "jvm")."""
    if build == "native":
        return (f"native server image: -march={native_server_march(env)}" if is_server
                else f"native wheel: -march={NATIVE_WHEEL_MARCH}")
    return "JVM: compiled at run time for the host CPU"


def builds_in(rows):
    """The builds the in-process ArcadeDB rows of `rows` ran on, as a set of "native" / "jvm"."""
    return {build_of(r) for r in rows if built(r)} - {None}


def splits_page(rows):
    """True when the page must name the build on every in-process ArcadeDB arm: some row ran on the native build.

    Rows from before the field are all "jvm", so a freeze of old rows is never split and renders exactly as it did. A freeze that holds
    only native rows is split too: an unlabelled arm would read as the JVM build.
    """
    return "native" in builds_in(rows)


BUILD_NAMES = {"native": "native build", "jvm": "JVM build"}


def build_label(label, build):
    """"ArcadeDB (embedded)" -> "ArcadeDB (embedded, native build)"; a label with no parenthesis gets one."""
    name = BUILD_NAMES[build]
    return f"{label[:-1]}, {name})" if label.endswith(")") else f"{label} ({name})"


def build_in_label(label):
    """The build a label names ("native" / "jvm"), or None."""
    for b, name in BUILD_NAMES.items():
        if str(label).endswith(f", {name})") or str(label).endswith(f"({name})"):
            return b
    return None


def strip_build(label):
    """The label without its build: "ArcadeDB (embedded, native build)" -> "ArcadeDB (embedded)"; a label with no build is returned as is."""
    b = build_in_label(label)
    if not b:
        return label
    name = BUILD_NAMES[b]
    label = str(label)
    return label[:-len(f", {name})")] + ")" if label.endswith(f", {name})") else label[:-len(f" ({name})")]


def pair_problems(rows):
    """What stops a two-build freeze from being published, as a list of sentences (empty: fine).

    The two builds of one release are built from ONE engine commit. A freeze whose native and JVM rows name different engine_versions
    or different engine commits compares two engines, not two builds of one, so the page must not print them side by side.
    """
    out = []
    by = {}
    for r in rows:
        if built(r) and build_of(r):
            by.setdefault(build_of(r), []).append(r)
    if len(by) < 2:
        return out
    for field in ("engine_version", "engine_commit"):
        # engine_version of a served row is the server's own build string ("server:<v> (build ...)"), not the wheel's: compare the wheels' versions
        # on the in-process rows; the commit is one value for every ArcadeDB row, served ones included.
        seen = {b: sorted({str(r.get(field) or "") for r in rs if field != "engine_version" or in_process(r)} - {""}) for b, rs in by.items()}
        flat = {v for vs in seen.values() for v in vs}
        if len(flat) > 1:
            out.append(f"the two ArcadeDB builds name different {field} values {seen}; one release is built from one engine commit")
    out += server_settings_problems(rows)
    return out


# THE SETTINGS A SERVER ARM IS HELD TO (#222 (3)). Both servers (the Docker JVM image, the native wheel's in-process server) are launched with
# the same explicit settings and the runner reads each back from the engine at start (`server_settings`, key -> value in force). The keys
# below must be present on every served ArcadeDB row and equal between the two builds of one cell (same arm, scale, durability class);
# other keys the runner requested (the HTTP body limit, the query cap) are compared when both builds list them.
SERVER_SETTING_KEYS = ("arcadedb.server.mode", "arcadedb.server.httpIncomingHost", "arcadedb.server.httpIncomingPort", "arcadedb.txWalFlush")


def server_settings_problems(rows):
    """Sentences for a served-arm settings mismatch between the builds (empty: fine). A native server row with no read-back is a problem
    too: a setting written is not a setting in force."""
    out, cells = [], {}
    for r in rows:
        if not served(r) or build_of(r) not in BUILDS:
            continue
        got = r.get("server_settings")
        if isinstance(got, str):
            try:
                import json
                got = json.loads(got)
            except ValueError:
                got = None
        if build_of(r) == "native" and not isinstance(got, dict):
            out.append(f"{r.get('backend')}: a native server row has no server_settings read-back")
            continue
        sc, pin = str(r.get("server_engine_commit") or ""), str(r.get("engine_commit") or "")
        if sc and pin and not (sc.startswith(pin[:7]) or pin.startswith(sc[:7])):
            out.append(f"{r.get('backend')}: the {build_of(r)} server reports engine commit {sc[:9]} and the row names {pin[:9]}")
        if isinstance(got, dict):
            key = (r.get("backend"), str(r.get("scale")), str(r.get("durability_class") or ""))
            cells.setdefault(key, {}).setdefault(build_of(r), []).append(got)
    for (arm, scale, cls), by in sorted(cells.items(), key=str):
        if len(by) < 2:
            continue
        a, b = (by[x][0] for x in BUILDS)
        keys = set(SERVER_SETTING_KEYS) | (set(a) & set(b))
        for k in sorted(keys):
            if str(a.get(k)) != str(b.get(k)):
                out.append(f"{arm} at {scale} ({cls or 'any class'}): server setting {k} is {a.get(k)!r} on the native server and "
                           f"{b.get(k)!r} on the JVM server")
    return out


def refuse_pooled_builds(rs, where):
    """SystemExit when one entry's rows span two builds of ArcadeDB (the exporter's check, beside _one_version's)."""
    ids = identities(rs)
    if len({b for _v, b in ids}) > 1:
        raise SystemExit(f"REFUSING: {where} pools ArcadeDB rows of different builds {sorted(ids, key=str)}; its median would "
                         f"belong to neither. Freeze one build ({ENV}) or split the arms.")
    return rs
