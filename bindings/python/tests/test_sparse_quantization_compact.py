"""Sparse index weight precision and the settle step, plus the dense search
beam argument: three engine features the vector guide documents and the
benchmark harness depends on (guide/vectors.md, 2026-09-07)."""

import arcadedb_embedded as arcadedb
import jpype.types as jtypes
import pytest

DIMS = 512


def _sparse_db(db, quant):
    db.command("sql", "CREATE DOCUMENT TYPE SDoc")
    db.command("sql", "CREATE PROPERTY SDoc.id INTEGER")
    db.command("sql", "CREATE PROPERTY SDoc.tokens ARRAY_OF_INTEGERS")
    db.command("sql", "CREATE PROPERTY SDoc.weights ARRAY_OF_FLOATS")
    meta = (
        f'{{"dimensions": {DIMS}'
        + (f', "weightQuantization": "{quant}"' if quant else "")
        + "}"
    )
    db.command(
        "sql",
        f"CREATE INDEX ON SDoc (tokens, weights) LSM_SPARSE_VECTOR METADATA {meta}",
    )
    with db.transaction():
        for i in range(200):
            toks = sorted({(i * 7 + j * 13) % DIMS for j in range(8)})
            wts = [round(0.1 + ((i + j) % 10) / 10.0, 3) for j in range(len(toks))]
            db.command(
                "sql",
                f"INSERT INTO SDoc SET id = {i}, tokens = {toks}, weights = {wts}",
            )


def _neighbours(db, toks, wts, k=5):
    rows = db.query(
        "sql",
        "SELECT id FROM (SELECT expand(`vector.sparseNeighbors`('SDoc[tokens,weights]', ?, ?, ?)))",
        jtypes.JArray(jtypes.JInt)(toks),
        arcadedb.to_java_float_array(wts),
        k,
    ).to_list()
    return [int(r["id"]) for r in rows]


@pytest.mark.parametrize("quant", [None, "FP32"])
def test_sparse_weight_precision_and_compact(temp_db, quant):
    _sparse_db(temp_db, quant)
    toks = sorted({(3 * 7 + j * 13) % DIMS for j in range(8)})
    wts = [1.0] * len(toks)
    before = _neighbours(temp_db, toks, wts)
    assert len(before) == 5 and 3 in before
    # The settle step: synchronous, and the answer does not change.
    temp_db.command("sql", "COMPACT INDEX `SDoc[tokens,weights]`")
    after = _neighbours(temp_db, toks, wts)
    assert len(after) == 5 and 3 in after


def test_dense_search_beam_argument(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE VDoc")
    temp_db.command("sql", "CREATE PROPERTY VDoc.id INTEGER")
    temp_db.command("sql", "CREATE PROPERTY VDoc.emb ARRAY_OF_FLOATS")
    with temp_db.transaction():
        for i in range(300):
            v = [((i * (j + 1)) % 17) / 17.0 for j in range(16)]
            temp_db.command("sql", f"INSERT INTO VDoc SET id = {i}, emb = {v}")
    temp_db.command(
        "sql",
        'CREATE INDEX ON VDoc (emb) LSM_VECTOR METADATA {"dimensions": 16, "similarity": "COSINE"}',
    )
    q = [((7 * (j + 1)) % 17) / 17.0 for j in range(16)]
    for beam in (16, 200):
        rows = temp_db.query(
            "sql",
            "SELECT id FROM (SELECT expand(vectorNeighbors('VDoc[emb]', ?, ?, ?)))",
            arcadedb.to_java_float_array(q),
            10,
            beam,
        ).to_list()
        assert len(rows) == 10, (beam, rows)
        assert 7 in [int(r["id"]) for r in rows]
