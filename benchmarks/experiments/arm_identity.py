"""What an ArcadeDB arm is, for every script that reads rows.

Since 26.11.1 one release is measured on two builds of the same Python package API: `arcadedb` (native) and `arcadedb-jvm` (Java engine
through JPype). Both stamp the same `engine_version` and the same `backend` arm name (`arcadedb_sparse_embedded`, ...); only the row
field `engine_backend` ("native" or "jvm") tells them apart. A consumer that groups or dedupes on `engine_version` alone would pool or
overwrite the two builds, so the identity of an in-process ArcadeDB arm is (engine_version, build), and this module is the one
definition of `build`:

  * `engine_backend` is "native" or "jvm": that value.
  * a row of an ArcadeDB in-process arm WITHOUT the field, or with it empty (every row before 26.11.1, and those rows read back from the
    frozen CSV): "jvm", because that is what it ran.
  * a served arm, the HTTP client container and every comparator: None. The served engine is a JVM server whichever Python package
    drives it, and the field is null there on purpose, so it never selects or splits them.

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


def build_of(r):
    """"native", "jvm" or None for the row (see the module docstring)."""
    eb = r.get("engine_backend")
    if eb in BUILDS:
        return eb
    # No usable field: an old row, or a row read back from the frozen CSV, where a row from before 26.11.1 has the column empty.
    if in_process(r) and not eb:
        return "jvm"
    return None


def arm_identity(r):
    """(engine_version, build): what two rows must share to be one measurement of one engine."""
    return (str(r.get("engine_version") or ""), build_of(r))


def identities(rows):
    """The set of (engine_version, build) over the in-process ArcadeDB rows."""
    return {arm_identity(r) for r in rows if in_process(r)}


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
        return [r for r in rows if not (in_process(r) and build_of(r) not in (None, want))]
    return rows


def builds_in(rows):
    """The builds the in-process ArcadeDB rows of `rows` ran on, as a set of "native" / "jvm"."""
    return {build_of(r) for r in rows if in_process(r)} - {None}


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
        if in_process(r) and build_of(r):
            by.setdefault(build_of(r), []).append(r)
    if len(by) < 2:
        return out
    for field in ("engine_version", "engine_commit"):
        seen = {b: sorted({str(r.get(field) or "") for r in rs} - {""}) for b, rs in by.items()}
        flat = {v for vs in seen.values() for v in vs}
        if len(flat) > 1:
            out.append(f"the two ArcadeDB builds name different {field} values {seen}; one release is built from one engine commit")
    return out


def refuse_pooled_builds(rs, where):
    """SystemExit when one entry's rows span two builds of ArcadeDB (the exporter's check, beside _one_version's)."""
    ids = identities(rs)
    if len({b for _v, b in ids}) > 1:
        raise SystemExit(f"REFUSING: {where} pools ArcadeDB rows of different builds {sorted(ids, key=str)}; its median would "
                         f"belong to neither. Freeze one build ({ENV}) or split the arms.")
    return rs
