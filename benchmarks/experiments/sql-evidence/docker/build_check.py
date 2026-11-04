"""Image build step for docker/duckdb.Dockerfile: install DuckPGQ from the community repository into the image and prove it works.

  python build_check.py DUCKDB_VERSION EXTENSION_DIR

Fails (the build stops) when the installed duckdb is not DUCKDB_VERSION, when `LOAD duckpgq` fails, or when the loaded
extension does not parse SQL/PGQ (`CREATE PROPERTY GRAPH`, `GRAPH_TABLE ... MATCH`). Prints the versions it read.
"""
import sys

import duckdb

want, ext_dir = sys.argv[1], sys.argv[2]
if duckdb.__version__ != want:
    sys.exit(f"duckdb {duckdb.__version__} is installed, the pin is {want}")
cx = duckdb.connect(":memory:")
cx.execute(f"SET extension_directory='{ext_dir}'")
cx.execute("INSTALL duckpgq FROM community")
cx.execute("LOAD duckpgq")
row = cx.execute("SELECT extension_version FROM duckdb_extensions() WHERE extension_name = 'duckpgq' AND loaded").fetchall()
if not row:
    sys.exit("duckpgq is not loaded after LOAD duckpgq")
cx.execute("CREATE TABLE p(id BIGINT PRIMARY KEY)")
cx.execute("CREATE TABLE k(a BIGINT, b BIGINT)")
cx.execute("INSERT INTO p VALUES (1), (2)")
cx.execute("INSERT INTO k VALUES (1, 2)")
cx.execute("CREATE PROPERTY GRAPH g VERTEX TABLES (p) EDGE TABLES (k SOURCE KEY (a) REFERENCES p (id) "
           "DESTINATION KEY (b) REFERENCES p (id))")
got = cx.execute("SELECT * FROM GRAPH_TABLE (g MATCH (x:p)-[e:k]->(y:p) COLUMNS (x.id AS xid, y.id AS yid))").fetchall()
if got != [(1, 2)]:
    sys.exit(f"GRAPH_TABLE smoke returned {got}, expected [(1, 2)]")
print(f"duckdb {duckdb.__version__}, duckpgq {row[0][0]}, extension dir {ext_dir}: LOAD and a GRAPH_TABLE match work")
