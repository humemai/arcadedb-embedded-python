"""The Milvus arms run on the vendor's Compose standalone, pinned by digest, on Storage V2 by default (2026-10-22, Zilliz's review)."""
import importlib
import os
import re
import sys
import types

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _runner(monkeypatch, storage=None):
    if storage is None:
        monkeypatch.delenv("BENCH_MILVUS_STORAGE", raising=False)
    else:
        monkeypatch.setenv("BENCH_MILVUS_STORAGE", storage)
    import runner
    return importlib.reload(runner)


ARMS = ("milvus_dense", "milvus_dense_int8", "milvus_sparse")


def test_every_image_is_pinned_by_digest(monkeypatch):
    r = _runner(monkeypatch)
    for a in ARMS:
        be = r.BACKENDS[a]
        assert DIGEST.search(be["server_image"])
        assert {s["name"] for s in be["sidecars"]} == {"etcd", "minio"}
        for s in be["sidecars"]:
            assert DIGEST.search(s["image"]), s
            assert s["mem"], "sidecars carry their own memory cap"
    assert r.BACKENDS["milvus_dense"]["server_image"] == r.MILVUS_IMAGE


def test_storage_v2_is_the_default_and_v3_is_one_switch(monkeypatch):
    r = _runner(monkeypatch)
    be = r.BACKENDS["milvus_dense"]
    assert be["stamp"]["milvus_storage"] == "v2"
    assert not any("USELOONFFI" in x for x in be["server_env"])
    r = _runner(monkeypatch, "v3")
    be = r.BACKENDS["milvus_dense"]
    assert be["stamp"]["milvus_storage"] == "v3"
    assert "COMMON_STORAGE_USELOONFFI=true" in be["server_env"]
    with pytest.raises(SystemExit):
        _runner(monkeypatch, "v4")
    _runner(monkeypatch)


def test_seal_override_is_dense_only_and_no_yaml_is_mounted(monkeypatch):
    r = _runner(monkeypatch)
    seal = f"DATACOORD_SEGMENT_SEALPROPORTION={r.MILVUS_SEAL_PROPORTION}"
    assert seal in r.BACKENDS["milvus_dense"]["server_env"]
    assert seal in r.BACKENDS["milvus_dense_int8"]["server_env"]
    assert seal not in r.BACKENDS["milvus_sparse"]["server_env"]
    for a in ARMS:
        assert "milvus.yaml" not in " ".join(r.BACKENDS[a]["server_volumes"])
    assert not os.path.exists(os.path.join(HERE, "docker-conf", "milvus-dense.yaml"))


def test_compose_environment_matches_the_release_file(monkeypatch):
    r = _runner(monkeypatch)
    env = " ".join(r.BACKENDS["milvus_dense"]["server_env"])
    assert "ETCD_ENDPOINTS={etcd}:2379" in env and "MINIO_ADDRESS={minio}:9000" in env and "MINIO_REGION=us-east-1" in env
    assert "ETCD_USE_EMBED" not in env and "COMMON_STORAGETYPE" not in env


class _Seg:
    def __init__(self, state, n):
        self.state, self.num_rows = state, n


class _Client:
    """Growing at first, flushed on the second look; the index finishes on the third."""
    def __init__(self):
        self.polls = 0
        self.flushes = 0

    def flush(self, c):
        self.flushes += 1

    def list_persistent_segments(self, c):
        self.polls += 1
        return [_Seg("Growing" if self.polls < 2 else "Flushed", 10)]

    def describe_index(self, c, f):
        self.looks = getattr(self, "looks", 0) + 1
        done = self.looks >= 2
        return {"state": "Finished" if done else "InProgress", "pending_index_rows": 0 if done else 10,
                "indexed_rows": 10 if done else 0, "total_rows": 10}

    def list_loaded_segments(self, c):
        return [_Seg("Sealed", 10)]

    def load_collection(self, c):
        pass


def test_wait_sealed_and_indexed_waits_for_both_and_times_each(monkeypatch):
    import milvus_common as m
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    out = m.wait_sealed_and_indexed(_Client(), "c", "v", 10)
    assert {"milvus_seal_wait_s", "milvus_index_wait_s", "milvus_load_s"} <= set(out)


def test_load_check_refuses_a_partial_load(monkeypatch):
    import milvus_common as m
    with pytest.raises(RuntimeError, match="expected 11"):
        m.load_and_check(_Client(), "c", 11)


def test_search_shape_is_ids_and_distances_only():
    import milvus_common as m
    assert m.SEARCH_SHAPE["milvus_search_output_fields"] == [] and m.SEARCH_SHAPE["milvus_search_filter"] == ""
    for f in ("l3d_dense.py", "l3_sparse.py"):
        src = open(os.path.join(HERE, f), encoding="utf-8").read()
        assert 'filter="", output_fields=[]' in src


def test_client_image_carries_the_bulk_writer_extra():
    src = open(os.path.join(HERE, "build_images.sh"), encoding="utf-8").read()
    assert "pymilvus[bulk_writer]==3.0.2" in src and "minio==" in src


def _cell_caps(r):
    return [r.mem_bytes(v) for v in r.MEM_BY_SCALE.values()]


def test_server_plus_sidecars_equal_the_cell_cap_for_every_backend_with_sidecars(monkeypatch):
    """The Milvus deployment gets the cell's cap, as every other engine does, not the cap plus etcd and MinIO."""
    r = _runner(monkeypatch)
    with_sidecars = [a for a, be in r.BACKENDS.items() if be.get("sidecars")]
    assert set(ARMS) <= set(with_sidecars)
    for a in with_sidecars:
        for cap in _cell_caps(r):
            server, caps = r.split_server_budget(cap, r.BACKENDS[a]["sidecars"])
            assert server + sum(caps.values()) == cap, (a, cap)
            assert server > 0 and set(caps) == {s["name"] for s in r.BACKENDS[a]["sidecars"]}
            assert all(caps[s["name"]] == r.mem_bytes(s["mem"]) for s in r.BACKENDS[a]["sidecars"]), "sidecars keep their caps"


def test_a_budget_the_sidecars_would_swallow_is_refused(monkeypatch):
    r = _runner(monkeypatch)
    with pytest.raises(SystemExit):
        r.split_server_budget(r.mem_bytes("1g"), r.BACKENDS["milvus_dense"]["sidecars"])


def test_run_cell_applies_the_split_before_it_sizes_the_server():
    src = open(os.path.join(HERE, "runner.py"), encoding="utf-8").read()
    i = src.index("split_server_budget(_budget, be[\"sidecars\"])")
    assert i < src.index("srv_gb = max(1, server_mem"), "the server's heap and caps derive from the reduced budget"
    assert i < src.index('"--memory", str(server_mem)')


def test_server_side_figures_fold_the_sidecars_in(monkeypatch):
    r = _runner(monkeypatch)

    class S:
        def __init__(self, peak):
            self.peak = self.peak_anon = peak * 2**20
            self.peak_shmem = self.peak_file = 0
            self.end_anon = self.end_file = 0
            self.io, self.cpu = {"rbytes": 0, "wbytes": 0}, {"usage_usec": 10}
        def finish(self):
            pass

    row = {"server_peak_mib": 100.0, "server_peak_anon_mib": 100.0, "server_cpu_usec": 5, "peak_mib_sum": 150.0,
           "peak_anon_mib_sum": 150.0, "peak_shmem_mib_sum": 0.0, "peak_owned_mib_sum": 150.0, "end_anon_mib_sum": 0.0,
           "io_write_mib_sum": 0.0, "io_read_mib_sum": 0.0, "cpu_usec_sum": 7}
    r._fold_sidecars(row, [("etcd", S(20)), ("minio", S(30))])
    assert row["server_peak_mib"] == 150.0 and row["server_container_peak_mib"] == 100.0
    assert row["sidecar_etcd_peak_mib"] == 20.0 and row["sidecar_minio_peak_mib"] == 30.0
    assert row["peak_mib_sum"] == 200.0 and row["server_cpu_usec"] == 25 and row["cpu_usec_sum"] == 27
