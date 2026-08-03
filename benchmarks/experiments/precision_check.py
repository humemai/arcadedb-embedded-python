"""Does the dense SERVER adapter's %.6f text encoding change kNN results?

l3d_dense.py builds the server index by formatting each component as "%.6f"
into a SQL INSERT, and formats the query vector the same way. The embedded
adapter passes exact float32 arrays via to_java_float_array. So the two
deployments are indexing and querying DIFFERENT numbers, which is the same
class of error as #5411 (compared across corpora) and #5352 (compared a
half-degree graph against a full-degree one).

The sparse adapter got this right: it uses "%.9f" with the comment "exact
float32 round-trip, keeps ingest == GT weights". The dense one did not.

This measures the consequence on the actual generated vectors instead of
arguing from digit counts: exact top-10 by brute force on full-precision
float32 vs on %.6f-rounded vectors, same queries, and how often the returned
set differs.
"""
import numpy as np

DIMENSIONS = 128          # l3d_dense.DIM
DOC_SEED = 20260709       # dense_common
QUERY_SEED = 515151
K = 10
N_DOCS = 200_000
N_QUERIES = 500


def unit(rng, n, d):
    v = rng.standard_normal((n, d), dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


def round6(v):
    """Exactly what "%.6f" % x does, vectorised."""
    return np.round(v.astype(np.float64), 6).astype(np.float32)


def topk_euclidean(docs, queries, k):
    # EUCLIDEAN, matching the index metadata in l3d_dense
    out = np.empty((len(queries), k), dtype=np.int64)
    for i, q in enumerate(queries):
        d = np.linalg.norm(docs - q, axis=1)
        out[i] = np.argpartition(d, k)[:k][np.argsort(d[np.argpartition(d, k)[:k]])]
    return out


def main():
    docs = unit(np.random.default_rng(DOC_SEED), N_DOCS, DIMENSIONS)
    queries = unit(np.random.default_rng(QUERY_SEED), N_QUERIES, DIMENSIONS)

    docs6, queries6 = round6(docs), round6(queries)

    comp_abs = np.abs(docs - docs6)
    nz = np.abs(docs) > 0
    comp_rel = comp_abs[nz] / np.abs(docs)[nz]
    print(f"component abs error : max {comp_abs.max():.3e}  mean {comp_abs.mean():.3e}")
    print(f"component rel error : max {comp_rel.max():.3e}  mean {comp_rel.mean():.3e}")
    print(f"typical |component| : {np.abs(docs).mean():.4f} "
          f"(unit vectors in {DIMENSIONS}d)")
    print(f"significant digits kept: ~{-np.log10(comp_rel.mean()):.1f}")

    exact = topk_euclidean(docs, queries, K)
    rounded = topk_euclidean(docs6, queries6, K)

    set_diff = order_diff = 0
    swapped = 0
    for a, b in zip(exact, rounded):
        sa, sb = set(a.tolist()), set(b.tolist())
        if sa != sb:
            set_diff += 1
            swapped += len(sa - sb)
        elif a.tolist() != b.tolist():
            order_diff += 1
    print()
    print(f"queries with a DIFFERENT top-{K} set   : {set_diff}/{len(queries)} "
          f"({100.0*set_diff/len(queries):.1f}%)")
    print(f"queries same set, different order     : {order_diff}/{len(queries)}")
    print(f"total documents swapped out of top-{K}: {swapped}")
    print()
    if set_diff:
        print("VERDICT: %.6f changes the ground truth. The server and embedded "
              "dense indexes are built over different numbers, so recall is not "
              "comparable across the deployment axis and latency is measured on "
              "non-identical indexes.")
    else:
        print("VERDICT: no top-K change at this scale. Still worth fixing for "
              "consistency with the sparse adapter, but not a comparability bug.")


if __name__ == "__main__":
    main()
