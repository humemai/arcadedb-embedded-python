"""psycopg 3 and SQLAlchemy 2 steps (run with `uv run --with psycopg[binary]==3.2.9 --with sqlalchemy==2.0.41`).

  python probe_python.py HOST PORT USER PASSWORD
psycopg: connection, information_schema queries, server-side bound parameter, join, group by.
SQLAlchemy: engine.connect, Inspector.get_table_names / get_columns (the reflection queries are SQLAlchemy's own),
Core select on the reflected table, bound parameter, join, group by.
"""
import sys

import pgsteps

host, port, user, pw = sys.argv[1:5]


def run(client, version, name, fn):
    try:
        fn()
        pgsteps.emit(client, version, name, True)
    except Exception as e:  # noqa: BLE001
        pgsteps.emit(client, version, name, False, f"{type(e).__name__}: {e}")


def need_rows(rows, what="rows"):
    if not rows:
        raise AssertionError(f"no {what} returned")


# ---- psycopg
import psycopg  # noqa: E402

PV = "psycopg " + psycopg.__version__
holder = {}


def pg_connect():
    holder["c"] = psycopg.connect(host=host, port=port, dbname="sqlev", user=user, password=pw, sslmode="disable", autocommit=True)
    holder["c"].execute("SELECT 1").fetchall()


run("psycopg", PV, "connect", pg_connect)
if "c" in holder:
    c = holder["c"]


    def pg_tables():
        names = [r[0] for r in c.execute(pgsteps.LIST_TABLES_INFO_SCHEMA).fetchall()]
        if not pgsteps.has_person(names):
            raise AssertionError(f"Person not in {names[:10]}")


    def pg_cols():
        need_rows(c.execute(pgsteps.LIST_COLUMNS_INFO_SCHEMA).fetchall(), "columns")


    run("psycopg", PV, "list_tables", pg_tables)
    run("psycopg", PV, "list_columns", pg_cols)
    run("psycopg", PV, "select", lambda: need_rows(c.execute(pgsteps.SQL["select"]).fetchall()))
    run("psycopg", PV, "select_param", lambda: need_rows(c.execute(pgsteps.PARAM_SQL.format(ph="%s"), (pgsteps.PARAM_VALUE,)).fetchall()))
    run("psycopg", PV, "join", lambda: need_rows(c.execute(pgsteps.SQL["join"]).fetchall()))
    run("psycopg", PV, "group_by", lambda: need_rows(c.execute(pgsteps.SQL["group_by"]).fetchall()))

# ---- SQLAlchemy
import sqlalchemy as sa  # noqa: E402

SV = "sqlalchemy " + sa.__version__
sh = {}


def sa_connect():
    sh["e"] = sa.create_engine(f"postgresql+psycopg://{user}:{pw}@{host}:{port}/sqlev?sslmode=disable", isolation_level="AUTOCOMMIT")
    sh["c"] = sh["e"].connect()
    sh["c"].execute(sa.text("SELECT 1")).fetchall()


run("sqlalchemy", SV, "connect", sa_connect)
if "c" in sh:
    eng, cx = sh["e"], sh["c"]


    def sa_tables():
        names = sa.inspect(eng).get_table_names()
        if not pgsteps.has_person(names):
            raise AssertionError(f"Person not in {names[:10]}")


    def sa_cols():
        need_rows(sa.inspect(eng).get_columns("Person"), "columns")


    def reflect():
        if "t" not in sh:
            md = sa.MetaData()
            sh["t"] = (sa.Table("Person", md, autoload_with=eng), sa.Table("City", md, autoload_with=eng))
        return sh["t"]


    def sa_select():
        person, _ = reflect()
        need_rows(cx.execute(sa.select(person.c.id, person.c.name).order_by(person.c.id).limit(5)).fetchall())


    def sa_param():
        need_rows(cx.execute(sa.text(pgsteps.PARAM_SQL.format(ph=":pid")), {"pid": pgsteps.PARAM_VALUE}).fetchall())


    def sa_join():
        person, city = reflect()
        q = sa.select(person.c.name, city.c.name.label("city")).select_from(person.join(city, person.c.city_id == city.c.id)).where(person.c.id < 10)
        need_rows(cx.execute(q).fetchall())


    def sa_group():
        person, _ = reflect()
        n = sa.func.count().label("n")
        need_rows(cx.execute(sa.select(person.c.city_id, n).group_by(person.c.city_id).order_by(n.desc()).limit(5)).fetchall())


    run("sqlalchemy", SV, "list_tables", sa_tables)
    run("sqlalchemy", SV, "list_columns", sa_cols)
    run("sqlalchemy", SV, "select", sa_select)
    run("sqlalchemy", SV, "select_param", sa_param)
    run("sqlalchemy", SV, "join", sa_join)
    run("sqlalchemy", SV, "group_by", sa_group)
