"""The DBpedia OpenAI part of examples/download_data.py.

The 26 parquet files (9.55 GB) are pinned by size and sha256, so a file that
changes upstream stops the download instead of being converted. These tests
cover the pin check, the lazy file fetch, and the conversion to the shard
layout the MSMARCO sets use, on tiny synthetic parquet files. No network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "examples" / "download_data.py"
EMBEDDING = "text-embedding-3-large-1536-embedding"
DIM = 8


@pytest.fixture(scope="module")
def dd():
    spec = importlib.util.spec_from_file_location("download_data_dbpedia", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_parquet(path: Path, first_id: int, rows: int, dim: int = DIM) -> np.ndarray:
    """Write a parquet file shaped like the upstream ones; return its vectors."""
    rng = np.random.default_rng(first_id)
    vectors = rng.normal(size=(rows, dim))
    table = pa.table(
        {
            "_id": [f"<dbpedia:E{first_id + i}>" for i in range(rows)],
            "title": [f"Entity {first_id + i}" for i in range(rows)],
            "text": ["body"] * rows,
            EMBEDDING: pa.array(vectors.tolist(), type=pa.list_(pa.float64())),
        }
    )
    pq.write_table(table, path, row_group_size=3)
    return vectors


def _pin(dd, monkeypatch, path: Path) -> None:
    monkeypatch.setattr(
        dd,
        "DBPEDIA_OPENAI3_FILES",
        {
            path.name: (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        },
    )


def test_manifest_pins_all_26_files(dd):
    files = dd.DBPEDIA_OPENAI3_FILES
    assert list(files) == [f"train-{i:05d}-of-00026.parquet" for i in range(26)]
    for size, sha256 in files.values():
        assert size > 0
        assert re.fullmatch(r"[0-9a-f]{64}", sha256)
    assert len({sha for _, sha in files.values()}) == 26
    # download_size in the dataset card
    assert sum(size for size, _ in files.values()) == 9_551_862_565


def test_check_pinned_file_accepts_matching_file(dd, tmp_path):
    path = tmp_path / "f.parquet"
    path.write_bytes(b"abc")
    dd._check_pinned_file(path, 3, hashlib.sha256(b"abc").hexdigest())


def test_check_pinned_file_rejects_changed_content(dd, tmp_path):
    path = tmp_path / "f.parquet"
    path.write_bytes(b"abd")
    with pytest.raises(RuntimeError, match="sha256"):
        dd._check_pinned_file(path, 3, hashlib.sha256(b"abc").hexdigest())


def test_check_pinned_file_rejects_wrong_size(dd, tmp_path):
    path = tmp_path / "f.parquet"
    path.write_bytes(b"abcd")
    with pytest.raises(RuntimeError, match="size"):
        dd._check_pinned_file(path, 3, hashlib.sha256(b"abc").hexdigest())


def test_verified_file_on_disk_is_not_downloaded_again(dd, tmp_path, monkeypatch):
    path = tmp_path / "train-00000-of-00026.parquet"
    path.write_bytes(b"payload")
    _pin(dd, monkeypatch, path)

    def no_download(url, destination):
        raise AssertionError("download_file must not run for a verified file")

    monkeypatch.setattr(dd, "download_file", no_download)
    assert dd.fetch_dbpedia_openai3_file(path.name, tmp_path) == path


def test_download_uses_https_and_the_pinned_revision(dd, tmp_path, monkeypatch):
    name = "train-00000-of-00026.parquet"
    monkeypatch.setattr(
        dd,
        "DBPEDIA_OPENAI3_FILES",
        {name: (7, hashlib.sha256(b"payload").hexdigest())},
    )
    seen = []

    def fake_download(url, destination):
        seen.append(url)
        destination.write_bytes(b"payload")

    monkeypatch.setattr(dd, "download_file", fake_download)
    dd.fetch_dbpedia_openai3_file(name, tmp_path)
    assert seen == [
        "https://huggingface.co/datasets/"
        "Qdrant/dbpedia-entities-openai3-text-embedding-3-large-1536-1M/resolve/"
        f"{dd.DBPEDIA_OPENAI3_REVISION}/data/{name}"
    ]


def test_corrupt_download_is_removed_and_stops_the_run(dd, tmp_path, monkeypatch):
    name = "train-00000-of-00026.parquet"
    monkeypatch.setattr(
        dd,
        "DBPEDIA_OPENAI3_FILES",
        {name: (7, hashlib.sha256(b"payload").hexdigest())},
    )
    monkeypatch.setattr(
        dd,
        "download_file",
        lambda url, destination: destination.write_bytes(b"PAYLOAD"),
    )
    with pytest.raises(RuntimeError, match="sha256"):
        dd.fetch_dbpedia_openai3_file(name, tmp_path)
    assert not (tmp_path / name).exists()


def test_conversion_writes_msmarco_layout_ids_and_exact_gt(dd, tmp_path):
    first = _write_parquet(tmp_path / "a.parquet", 0, 5)
    second = _write_parquet(tmp_path / "b.parquet", 100, 5)
    out = tmp_path / "out"

    dd.convert_dbpedia_openai3_to_shards(
        parquet_files=[tmp_path / "a.parquet", tmp_path / "b.parquet"],
        out_dir=out,
        count=7,
        dim=DIM,
        shard_size=3,
        batch_rows=2,
        q_count=4,
        topk=3,
        chunk=2,
    )

    base = "dbpedia-openai3-1536-7"
    meta = json.loads((out / f"{base}.meta.json").read_text())
    assert (meta["dim"], meta["dtype"], meta["count"], meta["shard_size"]) == (
        DIM,
        "float32",
        7,
        3,
    )
    assert [(s["path"], s["count"], s["start"]) for s in meta["shards"]] == [
        (f"{base}.shard0000.f32", 3, 0),
        (f"{base}.shard0001.f32", 3, 3),
        (f"{base}.shard0002.f32", 1, 6),
    ]

    stored = np.concatenate(
        [
            np.fromfile(out / s["path"], dtype=np.float32).reshape(-1, DIM)
            for s in meta["shards"]
        ]
    )
    source = np.concatenate([first, second])[[0, 1, 2, 3, 4, 5, 6]]
    expected = (source / np.linalg.norm(source, axis=1, keepdims=True)).astype(
        np.float32
    )
    np.testing.assert_allclose(stored, expected, atol=1e-6)

    ids = [
        json.loads(line)
        for line in (out / f"{base}.ids.jsonl").read_text().split("\n")
        if line
    ]
    assert [r["id"] for r in ids] == list(range(7))
    assert [r["dbpedia_id"] for r in ids] == [
        f"<dbpedia:E{i}>" for i in (0, 1, 2, 3, 4, 100, 101)
    ]
    assert ids[5]["title"] == "Entity 100"

    gt = [
        json.loads(line)
        for line in (out / f"{base}.gt.jsonl").read_text().split("\n")
        if line
    ]
    assert len(gt) == 4
    assert len({rec["query_id"] for rec in gt}) == 4
    for rec in gt:
        sims = stored @ stored[rec["query_id"]]
        want = np.argsort(-sims, kind="stable")[:3]
        got = [t["doc_id"] for t in rec["topk"]]
        assert got == want.tolist()
        assert got[0] == rec["query_id"]
        assert rec["topk"][0]["score"] == pytest.approx(1.0, abs=1e-5)


def test_conversion_asks_for_files_lazily(dd, tmp_path):
    _write_parquet(tmp_path / "a.parquet", 0, 5)
    asked = []

    def files():
        for name in ("a.parquet", "never.parquet"):
            asked.append(name)
            yield tmp_path / name

    dd.convert_dbpedia_openai3_to_shards(
        parquet_files=files(),
        out_dir=tmp_path / "out",
        count=5,
        dim=DIM,
        q_count=2,
        topk=2,
    )
    assert asked == ["a.parquet"]


def test_conversion_fails_when_source_is_short(dd, tmp_path):
    _write_parquet(tmp_path / "a.parquet", 0, 5)
    out = tmp_path / "out"
    with pytest.raises(RuntimeError, match="fewer than"):
        dd.convert_dbpedia_openai3_to_shards(
            parquet_files=[tmp_path / "a.parquet"], out_dir=out, count=6, dim=DIM
        )
    assert not list(out.glob("*.meta.json"))


def test_conversion_rejects_wrong_dimension(dd, tmp_path):
    _write_parquet(tmp_path / "a.parquet", 0, 5, dim=DIM + 1)
    with pytest.raises(RuntimeError, match="dimension"):
        dd.convert_dbpedia_openai3_to_shards(
            parquet_files=[tmp_path / "a.parquet"],
            out_dir=tmp_path / "out",
            count=5,
            dim=DIM,
        )
