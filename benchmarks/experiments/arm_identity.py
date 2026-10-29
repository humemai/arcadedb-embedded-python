"""What an ArcadeDB arm is, for every script that reads rows.

Since 26.11.1 one release is measured on two builds of the same Python package API: `arcadedb` (native) and `arcadedb-jvm` (Java engine
through JPype). Both stamp the same `engine_version` and the same `backend` arm name (`arcadedb_sparse_embedded`, ...); only the row
field `engine_backend` ("native" or "jvm") tells them apart. A consumer that groups or dedupes on `engine_version` alone would pool or
overwrite the two builds, so the identity of an in-process ArcadeDB arm is (engine_version, build), and this module is the one
definition of `build`:

  * `engine_backend` is "native" or "jvm": that value.
  * a row of an ArcadeDB in-process arm WITHOUT the field (every row before 26.11.1): "jvm", because that is what it ran.
  * a served arm, the HTTP client container and every comparator: None. The served engine is a JVM server whichever Python package
    drives it, and the field is null there on purpose, so it never selects or splits them.

`select_build(rows, want)` is the one place a freeze picks a build: with BENCH_ENGINE_BACKEND=native|jvm the other build's in-process
ArcadeDB rows leave the freeze (they stay in runs.jsonl); without it, a cell that holds BOTH builds is refused by name, not pooled.
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
    if in_process(r) and "engine_backend" not in r:
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


def mixed_cells(rows):
    """{(lane, scale, n_docs, backend): builds} for the cells whose in-process ArcadeDB rows come from more than one build."""
    seen = {}
    for r in rows:
        if in_process(r) and build_of(r):
            seen.setdefault((r.get("lane"), r.get("scale"), r.get("n_docs"), r.get("backend")), set()).add(build_of(r))
    return {k: sorted(v) for k, v in seen.items() if len(v) > 1}


def select_build(rows, want=None):
    """The rows a freeze may publish: one build of the in-process ArcadeDB arms, or a refusal that says why not.

    `want` None reads BENCH_ENGINE_BACKEND. With a build, rows of the other build are dropped (served arms and comparators carry no
    build and stay). Without one, any cell holding both builds stops the freeze: a median over native and JVM rows names neither.
    """
    want = wanted_build() if want is None else want
    if want:
        return [r for r in rows if not (in_process(r) and build_of(r) not in (None, want))]
    mixed = mixed_cells(rows)
    if mixed:
        sample = ", ".join("/".join(str(x) for x in k) for k in sorted(mixed, key=str)[:3])
        raise SystemExit(
            f"REFUSING: {len(mixed)} cell(s) hold rows of both ArcadeDB builds (native and jvm), e.g. {sample}. A table cell is one "
            f"build; set {ENV}=native or {ENV}=jvm to freeze that build (the other build's rows stay in the log).")
    return rows


def refuse_pooled_builds(rs, where):
    """SystemExit when one entry's rows span two builds of ArcadeDB (the exporter's check, beside _one_version's)."""
    ids = identities(rs)
    if len({b for _v, b in ids}) > 1:
        raise SystemExit(f"REFUSING: {where} pools ArcadeDB rows of different builds {sorted(ids, key=str)}; its median would "
                         f"belong to neither. Freeze one build ({ENV}) or split the arms.")
    return rs
