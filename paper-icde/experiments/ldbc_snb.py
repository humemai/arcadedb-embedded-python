"""LDBC-SNB data source for the L2 graph lane (drop-in for graph_common).

Streams the persons+KNOWS projection of the pre-generated LDBC Social
Network Benchmark Interactive v1 datasets (CsvCompositeMergeForeign,
LongDateFormatter serializer) published by the LDBC council. Activated by
BENCH_GRAPH_SOURCE=ldbc; BENCH_GRAPH_DATA must point at the directory
holding sf1/, sf10/, ... as extracted from the official tarballs.

Person attributes are projected onto the lane's existing schema so every
adapter and query template works unchanged:
    id   <- Person.id (sparse LDBC long)
    name <- firstName lastName
    age  <- years since birthday (fixed reference date, deterministic)
    city <- "city_<isLocatedIn place id>"
KNOWS edges carry since = year(creationDate). LDBC ships knows once per
undirected pair; we load it as a single directed edge (the lane's queries
traverse OUT), storage is bidirectional (engine default) in every adapter.

Deliberately unchanged vs graph_common: OLTP/OLAP Cypher templates and all
tunables, so synthetic-vs-LDBC runs differ ONLY in data.
"""
import csv
import os
import sys
from pathlib import Path

from graph_common import (OLAP_ITERATIONS, OLAP_QUERIES, OLTP_READS,
                          OLTP_WRITE, SCALE_OLTP_QUERIES as _SYN_QUERIES)

_REF_YEAR = 2026  # age reference; fixed so re-runs are identical

# person counts of the official datasets (for progress/expected counts;
# the streams read whatever the files actually contain)
SCALE_PERSONS = {"sf1": 10_995, "sf10": 72_949}
SCALE_OLTP_QUERIES = {"sf1": 500, "sf10": 200}
OLAP_ITERATIONS = OLAP_ITERATIONS  # re-export unchanged

PICK_SEED = 777


def _root(scale):
    base = Path(os.environ.get("BENCH_GRAPH_DATA", "/data/ldbc")) / scale
    hits = list(base.glob("social_network-*/dynamic"))
    if not hits:
        sys.exit(f"ldbc_snb: no dynamic/ dir under {base}")
    return hits[0]


def _csv_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="|")
        header = next(r)
        yield header
        yield from r


def gen_persons(scale):
    """Yield (id, name, age, city) from person_0_0.csv."""
    rows = _csv_rows(_root(scale) / "person_0_0.csv")
    header = next(rows)
    col = {name: i for i, name in enumerate(header)}
    i_id, i_fn, i_ln = col["id"], col["firstName"], col["lastName"]
    i_bd = col["birthday"]
    # CsvCompositeMergeForeign appends the place FK as the last column
    i_place = col.get("place", len(header) - 1)
    for row in rows:
        birth_year = int(row[i_bd][:4]) if row[i_bd][:4].isdigit() else 1980
        yield (int(row[i_id]), f"{row[i_fn]} {row[i_ln]}",
               max(0, _REF_YEAR - birth_year), f"city_{row[i_place]}")


def gen_edges(scale):
    """Yield (src_id, dst_id, since_year) from person_knows_person_0_0.csv."""
    rows = _csv_rows(_root(scale) / "person_knows_person_0_0.csv")
    header = next(rows)
    for row in rows:
        # creationDate is epoch millis with the LongDateFormatter serializer
        try:
            since = 1970 + int(row[2]) // 31_557_600_000
        except (ValueError, IndexError):
            since = 2012
        yield int(row[0]), int(row[1]), since


def person_ids(scale):
    """All real (sparse) person ids, in file order."""
    rows = _csv_rows(_root(scale) / "person_0_0.csv")
    header = next(rows)
    i_id = header.index("id")
    return [int(row[i_id]) for row in rows]


def pick_query_ids(scale, n_queries, seed=PICK_SEED):
    """Sample REAL ids: LDBC person ids are sparse, never 0..n-1."""
    import random
    ids = person_ids(scale)
    rng = random.Random(seed)
    return [ids[rng.randrange(len(ids))] for _ in range(n_queries)]


def write_id_base(scale):
    """Safe base for harness-generated new person ids (write workload)."""
    return max(person_ids(scale)) + 1_000_000
