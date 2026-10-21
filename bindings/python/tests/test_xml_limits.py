"""The JDK's XML entity limits stay on unless the caller lifts them."""

import inspect

import arcadedb_embedded as arcadedb
import jpype
import pytest
from arcadedb_embedded import jvm
from arcadedb_embedded.exceptions import ArcadeDBError
from arcadedb_embedded.jvm import _build_jvm_args

LIMIT_PROPERTIES = (
    "jdk.xml.maxGeneralEntitySizeLimit",
    "jdk.xml.entityExpansionLimit",
    "jdk.xml.totalEntitySizeLimit",
)


@pytest.fixture
def db(tmp_path):
    database = arcadedb.create_database(str(tmp_path / "xml_limits_db"))
    database.command("sql", "CREATE DOCUMENT TYPE Item")
    yield database
    if database.is_transaction_active():
        database.rollback()
    database.drop()


@pytest.fixture
def big_xml(tmp_path):
    """One text node of 1,000,000 characters (200,000 entity references)."""
    path = tmp_path / "big.xml"
    path.write_text(
        "<root><item id='0'><t>" + "&amp;" * 200_000 + "</t></item>"
        "<item id='1'><t>small</t></item></root>"
    )
    return path


def _system_property(name):
    value = jpype.JClass("java.lang.System").getProperty(name)
    return None if value is None else str(value)


def test_start_jvm_default_keeps_the_limits():
    assert (
        inspect.signature(jvm.start_jvm).parameters["disable_xml_limits"].default
        is False
    )
    args = _build_jvm_args(heap_size="4g", disable_xml_limits=False, jvm_args=None)
    assert not any(a.startswith("-Djdk.xml.") for a in args)
    lifted = _build_jvm_args(heap_size="4g", disable_xml_limits=True, jvm_args=None)
    for name in LIMIT_PROPERTIES:
        assert f"-D{name}=0" in lifted


def test_import_hitting_a_limit_names_the_option(db, big_xml):
    # The session JVM must have been started with the default (limits on).
    assert [_system_property(n) for n in LIMIT_PROPERTIES] == [None] * 3
    with pytest.raises(ArcadeDBError) as excinfo:
        db.import_documents(big_xml, document_type="Item", file_type="xml")
    assert "JAXP0001000" in str(excinfo.value)
    assert "disable_xml_limits=True" in str(excinfo.value)


def test_per_call_option_lifts_the_limits_for_that_call_only(db, big_xml):
    assert [_system_property(n) for n in LIMIT_PROPERTIES] == [None] * 3
    result = db.import_documents(
        big_xml, document_type="Item", file_type="xml", disable_xml_limits=True
    )
    assert result.result == "OK"
    assert result.get("parsedRecords") == 2
    assert [_system_property(n) for n in LIMIT_PROPERTIES] == [None] * 3


def test_per_call_option_restores_a_value_that_was_already_set():
    from arcadedb_embedded.importer import _xml_limits_lifted

    System = jpype.JClass("java.lang.System")
    name = LIMIT_PROPERTIES[0]
    System.setProperty(name, "12345")
    try:
        with _xml_limits_lifted(True):
            assert _system_property(name) == "0"
        assert _system_property(name) == "12345"
    finally:
        System.clearProperty(name)


def test_limits_are_restored_when_the_import_fails(db, tmp_path):
    missing = tmp_path / "missing.xml"
    with pytest.raises(ArcadeDBError) as excinfo:
        db.import_documents(
            missing, document_type="Item", file_type="xml", disable_xml_limits=True
        )
    assert "disable_xml_limits=True" not in str(excinfo.value)
    assert [_system_property(n) for n in LIMIT_PROPERTIES] == [None] * 3
