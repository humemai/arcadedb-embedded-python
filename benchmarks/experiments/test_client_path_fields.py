"""Issue #261: the comparator client-path stamps read what the arm loaded, and nothing else."""
import sys
import types

import bench_common


def _fake(monkeypatch, name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def test_absent_when_no_driver_loaded(monkeypatch):
    monkeypatch.delitem(sys.modules, "neo4j", raising=False)
    monkeypatch.delitem(sys.modules, "redis", raising=False)
    assert bench_common.client_path_fields() == {}


def test_reads_the_drivers_own_flags(monkeypatch):
    _fake(monkeypatch, "neo4j")
    _fake(monkeypatch, "neo4j._codec")
    _fake(monkeypatch, "neo4j._codec.packstream", RUST_AVAILABLE=True)
    _fake(monkeypatch, "redis")
    monkeypatch.setattr(sys.modules["redis"], "utils",
                        _fake(monkeypatch, "redis.utils", HIREDIS_AVAILABLE=False), raising=False)
    assert bench_common.client_path_fields() == {"neo4j_rust_ext": True, "redis_hiredis": False}


def test_es_serializer_is_the_class_in_use():
    class OrjsonSerializer:
        pass

    class Serializers:
        def get_serializer(self, mimetype):
            assert mimetype == "application/json"
            return OrjsonSerializer()

    es = types.SimpleNamespace(transport=types.SimpleNamespace(serializers=Serializers()))
    assert bench_common.es_json_serializer(es) == "OrjsonSerializer"
    assert bench_common.es_json_serializer(object()) is None
