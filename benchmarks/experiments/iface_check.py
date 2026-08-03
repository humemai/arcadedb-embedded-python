"""Interface contract check for the probes. No data needed: verifies that
every name the probes reach for actually exists, which is what three earlier
wrong guesses in this lane failed on."""
import os
import sys

os.environ["BENCH_GRAPH_SOURCE"] = "ldbc"
os.environ.setdefault("BENCH_GRAPH_DATA", "/data/ldbc")
os.environ.setdefault("BENCH_SPARSE_SOURCE", "bigann")

fails = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL") + " " + msg)
    if not cond:
        fails.append(msg)


print("== l2_graph / ldbc_snb ==")
try:
    import l2_graph
    import ldbc_snb as L
    check(l2_graph._GRAPH_SOURCE == "ldbc",
          f"l2_graph._GRAPH_SOURCE == 'ldbc' (got {l2_graph._GRAPH_SOURCE!r})")
    check(hasattr(l2_graph, "ADAPTERS"), "l2_graph.ADAPTERS exists")
    check("arcadedb_graph_embedded" in getattr(l2_graph, "ADAPTERS", {}),
          "ADAPTERS has arcadedb_graph_embedded")
    check("neo4j_graph" in getattr(l2_graph, "ADAPTERS", {}),
          "ADAPTERS has neo4j_graph")
    for attr in ("gen_persons", "gen_edges"):
        check(hasattr(l2_graph, attr), f"l2_graph.{attr} is rebindable (exists)")
    check(hasattr(L, "pick_query_ids"), "ldbc_snb.pick_query_ids exists")
    check(set(getattr(L, "SCALE_PERSONS", {})) >= {"sf1", "sf10"},
          f"ldbc_snb.SCALE_PERSONS keyed by sf1/sf10 (got "
          f"{sorted(getattr(L, 'SCALE_PERSONS', {}))})")
    for m in ("gen_persons", "gen_edges"):
        check(hasattr(L, m), f"ldbc_snb.{m} exists")
    A = l2_graph.ADAPTERS["arcadedb_graph_embedded"]
    for m in ("connect", "build", "post_build", "run_cypher", "close"):
        check(callable(getattr(A, m, None)), f"arcadedb adapter has .{m}()")
except Exception as e:
    fails.append(f"l2_graph import: {e!r}")
    print(f"  FAIL import: {e!r}")

print("== l3_sparse / bigann_sparse ==")
try:
    import bigann_sparse as S
    from l3_sparse import BACKENDS
    check("arcadedb_sparse_embedded" in BACKENDS,
          "BACKENDS has arcadedb_sparse_embedded")
    for m in ("SCALE_DOCS", "SCALE_QUERIES", "K", "gen_queries"):
        check(hasattr(S, m), f"bigann_sparse.{m} exists")
    check(set(getattr(S, "SCALE_DOCS", {})) >= {"small", "medium"},
          f"SCALE_DOCS keys {sorted(getattr(S, 'SCALE_DOCS', {}))}")
    B = BACKENDS["arcadedb_sparse_embedded"]
    for m in ("connect", "build", "post_build", "search"):
        check(callable(getattr(B, m, None)), f"sparse backend has .{m}()")
    # Deliberately NOT checking .close(): it does not exist on these backends.
    # l3_sparse.main() tears down with os._exit() instead. Probes must not call
    # it -- doing so fails at the last line, after all the work is done.
    check(not hasattr(B, "close"),
          "sparse backend has NO close() (probes must not call it)")
    # .idx_name is assigned in connect(), so it is only observable on a
    # connected instance; nothing to assert here without a live database.
except Exception as e:
    fails.append(f"l3_sparse import: {e!r}")
    print(f"  FAIL import: {e!r}")

print("== GlobalConfiguration knob ==")
try:
    import arcadedb_embedded  # noqa: F401  (starts the JVM)
    import jpype
    GC = jpype.JClass("com.arcadedb.GlobalConfiguration")
    check(hasattr(GC, "SPARSE_VECTOR_SCORING_MAX_PARTITIONS"),
          "GlobalConfiguration.SPARSE_VECTOR_SCORING_MAX_PARTITIONS exists")
except Exception as e:
    print(f"  note: JVM/knob check skipped or failed: {e!r}")

print()
if fails:
    print(f"IFACE-CHECK FAILED ({len(fails)})")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("IFACE-CHECK OK")
