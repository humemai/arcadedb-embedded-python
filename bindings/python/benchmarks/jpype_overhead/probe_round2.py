"""Round-2 candidate-fix probes (measure-only): pick implementations for
(a) bulk row fetch in results.py and (b) java.util.List conversion, before
changing src. Usage: uv run python probe_round2.py <docs_db_dir>"""

import sys
import timeit

import arcadedb_embedded as arcadedb
from arcadedb_embedded.type_conversion import convert_java_to_python


def t(name, fn, number=2000):
    per = timeit.timeit(fn, number=number) / number * 1e6
    print(f"PROBE,{name},{per:.2f}us", flush=True)


with arcadedb.open_database(sys.argv[1]) as db:
    import jpype

    # --- (a) row materialization strategies on a real 7-scalar-col row ---
    java_row = db.query(
        "sql", "SELECT id, score, name, category, active, created, counts FROM Doc LIMIT 1"
    )._java_result_set.next()
    names = [str(n) for n in java_row.getPropertyNames()]

    t(
        "row_current_getProperty_per_col",
        lambda: {
            n: convert_java_to_python(java_row.getProperty(n)) for n in names
        },
        5000,
    )
    t(
        "row_toMap_then_convert",
        lambda: convert_java_to_python(java_row.toMap()),
        5000,
    )

    # --- (b) List<Float> conversion strategies ---
    JList = jpype.JClass("java.util.ArrayList")()
    JFloat = jpype.JClass("java.lang.Float")
    for i in range(384):
        JList.add(JFloat(i / 384.0))

    t("list_current_convert", lambda: convert_java_to_python(JList), 500)
    t("list_direct_float_cast", lambda: [float(x) for x in JList], 500)

    def via_jarray():
        return memoryview(jpype.JArray(jpype.JFloat)(JList)).tolist()

    try:
        via_jarray()
        t("list_via_jfloatarray_memoryview", via_jarray, 500)
    except Exception as e:
        print(f"PROBE,list_via_jfloatarray_memoryview,FAILED:{type(e).__name__}")

    def via_toarray():
        return [float(x) for x in JList.toArray()]

    t("list_toArray_float_cast", via_toarray, 500)

    # --- (c) map conversion (dominates toMap strategy) ---
    JMap = jpype.JClass("java.util.LinkedHashMap")()
    for i, n in enumerate(["id", "score", "name", "category", "active", "created", "counts"]):
        JMap.put(n, JFloat(i * 1.5))
    t("map_current_convert_7keys", lambda: convert_java_to_python(JMap), 5000)
    t(
        "map_entrySet_convert_7keys",
        lambda: {
            str(e.getKey()): convert_java_to_python(e.getValue())
            for e in JMap.entrySet()
        },
        5000,
    )

    # --- (d) exact-type dict dispatch vs isinstance chain ---
    JInt = jpype.JClass("java.lang.Integer")(42)
    JDouble = jpype.JClass("java.lang.Double")(1.5)
    JStr = jpype.JClass("java.lang.String")("hello")
    print(f"PROBE_INFO,type_stability,{type(JInt) is type(jpype.JClass('java.lang.Integer')(7))}")
    _DISPATCH = {type(JInt): int, type(JDouble): float, type(JStr): str}

    def dict_dispatch(v):
        conv = _DISPATCH.get(type(v))
        return conv(v) if conv is not None else convert_java_to_python(v)

    t("scalar_current_convert_int", lambda: convert_java_to_python(JInt), 20000)
    t("scalar_dict_dispatch_int", lambda: dict_dispatch(JInt), 20000)
    t("scalar_dict_dispatch_str", lambda: dict_dispatch(JStr), 20000)
