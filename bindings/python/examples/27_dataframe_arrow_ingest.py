#!/usr/bin/env python3
"""Example 27: DataFrames and Arrow tables in, Polars out.

A pandas or Polars DataFrame, or an Arrow table, loads straight into a type with
Database.insert_dataframe / Database.insert_arrow, the way DuckDB scans a DataFrame
in place: no loop over rows and no CSV in between. A result set comes back out as a
Polars DataFrame with ResultSet.to_polars().

Workflow covered:
- a pandas DataFrame into a DOCUMENT type (timestamps, nulls, a list column)
- a Polars DataFrame into a VERTEX type, then edges between those vertices
- an Arrow table into a type that declares some of its properties, so the int64 column
  converts to the declared INTEGER and DATETIME_MICROS properties
- a column that would lose data in a declared property (a float into an INTEGER)
  refused before a row is written
- the same data out again through to_polars()

Requirements:
- pandas, polars and pyarrow
  (pip install 'arcadedb-embedded[pandas,polars]')
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import arcadedb_embedded as arcadedb
import pandas as pd
import polars as pl
import pyarrow as pa


def documents_from_pandas(db, rows: int) -> None:
    print(f"\n=== pandas DataFrame into a document type: {rows:,} rows ===")
    db.command("sql", "CREATE DOCUMENT TYPE Trip")
    df = pd.DataFrame(
        {
            "id": range(rows),
            # NaN is pandas' missing value: it loads as a null
            "fare": [None if i % 10 == 0 else 2.5 + i % 40 for i in range(rows)],
            "picked_up": pd.Timestamp("2026-01-01")
            + pd.to_timedelta(range(rows), "min"),
            "stops": [[i % 7, i % 11] for i in range(rows)],
        }
    )
    written = db.insert_dataframe("Trip", df, batch_size=10_000)
    stats = db.query(
        "sql", "SELECT count(*) AS n, count(fare) AS with_fare FROM Trip"
    ).to_list()[0]
    print(
        f"written={written:,} stored={stats['n']:,} with a fare={stats['with_fare']:,}"
    )


def vertices_from_polars(db) -> None:
    print("\n=== Polars DataFrame into a vertex type, then edges ===")
    db.command("sql", "CREATE VERTEX TYPE Station")
    db.command("sql", "CREATE EDGE TYPE Line")
    stations = pl.DataFrame(
        {"name": ["Central", "North", "Harbour"], "opened": [1998, 2004, 2011]}
    )
    print(f"stations written={db.insert_dataframe('Station', stations)}")
    rids = {
        row["name"]: str(row["rid"])
        for row in db.query("sql", "SELECT name, @rid AS rid FROM Station").to_list()
    }
    # An edge needs the RIDs of both ends, so edges go through graph_batch().new_edges()
    with db.graph_batch() as batch:
        batch.new_edges(
            [rids["Central"], rids["North"]], "Line", [rids["North"], rids["Harbour"]]
        )
    print("edges:", db.query("sql", "SELECT count(*) AS n FROM Line").to_list()[0]["n"])


def arrow_into_declared_types(db) -> None:
    print("\n=== Arrow table into declared properties ===")
    db.command("sql", "CREATE DOCUMENT TYPE Reading")
    db.command("sql", "CREATE PROPERTY Reading.sensor INTEGER")
    db.command("sql", "CREATE PROPERTY Reading.at DATETIME_MICROS")
    table = pa.table(
        {
            "sensor": pa.array([1, 2, 3], pa.int64()),  # converts to INTEGER
            "at": pa.array(
                [datetime(2026, 5, 1, 12, 0, 0, 123456)] * 3, pa.timestamp("us")
            ),
            "value": pa.array([0.5, None, 2.5], pa.float32()),  # undeclared: DOUBLE
        }
    )
    print(f"written={db.insert_arrow('Reading', table)}")
    try:
        db.insert_arrow("Reading", pa.table({"sensor": [1.5]}))
    except TypeError as exc:
        print(f"refused before anything was written: {exc}")


def polars_out(db) -> None:
    print("\n=== to_polars() ===")
    frame = db.query(
        "sql", "SELECT sensor, at, value FROM Reading ORDER BY sensor"
    ).to_polars()
    print(frame)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--db-path", default="./my_test_databases/dataframe_ingest_db")
    args = parser.parse_args()

    path = Path(args.db_path)
    shutil.rmtree(path, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with arcadedb.create_database(str(path)) as db:
        documents_from_pandas(db, args.rows)
        vertices_from_polars(db)
        arrow_into_declared_types(db)
        polars_out(db)


if __name__ == "__main__":
    main()
