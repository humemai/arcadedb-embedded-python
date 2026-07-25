"""Tests for Database.insert_many and AsyncExecutor.create_record."""

import datetime

import pytest


def _count(db, type_name):
    return int(db.query("sql", f"SELECT count(*) AS n FROM {type_name}")
               .to_list()[0]["n"])


class TestInsertMany:
    def test_basic_roundtrip(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Item")
        rows = [{"k": i, "name": f"item_{i}", "price": i * 1.5,
                 "active": i % 2 == 0, "tags": ["a", "b"], "meta": {"x": i}}
                for i in range(500)]
        n = temp_db.insert_many("Item", rows, commit_every=100)
        assert n == 500
        assert _count(temp_db, "Item") == 500
        got = temp_db.query(
            "sql", "SELECT FROM Item WHERE k = 7").to_list()[0]
        assert got["name"] == "item_7"
        assert got["price"] == pytest.approx(10.5)
        assert got["active"] is False
        assert list(got["tags"]) == ["a", "b"]

    def test_null_values(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Nul")
        n = temp_db.insert_many("Nul", [{"a": 1, "b": None}, {"a": None}])
        assert n == 2
        assert _count(temp_db, "Nul") == 2

    def test_empty(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Empty")
        assert temp_db.insert_many("Empty", []) == 0

    def test_parallel(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Par")
        rows = [{"k": i} for i in range(2000)]
        n = temp_db.insert_many("Par", rows, parallel=True)
        assert n == 2000
        assert _count(temp_db, "Par") == 2000

    def test_non_json_fallback(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Dated")
        rows = [{"k": i, "when": datetime.datetime(2026, 7, 25, 12, 0, i)}
                for i in range(3)]
        n = temp_db.insert_many("Dated", rows)
        assert n == 3
        assert _count(temp_db, "Dated") == 3

    def test_inside_open_transaction(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE Tx")
        temp_db.begin()
        temp_db.insert_many("Tx", [{"k": 1}, {"k": 2}], commit_every=0)
        temp_db.commit()
        assert _count(temp_db, "Tx") == 2


class TestAsyncCreateRecord:
    def test_create_and_wait(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE ARec")
        ex = temp_db.async_executor()
        for i in range(100):
            doc = temp_db.new_document("ARec")
            doc.set("k", i)
            ex.create_record(doc)
        ex.wait_completion()
        assert _count(temp_db, "ARec") == 100

    def test_callback(self, temp_db):
        temp_db.command("sql", "CREATE DOCUMENT TYPE CRec")
        seen = []
        ex = temp_db.async_executor()
        doc = temp_db.new_document("CRec")
        doc.set("k", 1)
        ex.create_record(doc, callback=lambda rec: seen.append(rec))
        ex.wait_completion()
        assert _count(temp_db, "CRec") == 1
        assert len(seen) == 1
