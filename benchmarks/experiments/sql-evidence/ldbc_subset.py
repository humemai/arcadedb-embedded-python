"""The LDBC SNB sf1 subset the experiment queries (README, section "Dataset").

Reads the pre-generated CsvCompositeMergeForeign / LongDateFormatter corpus the campaign uses
(benchmarks/experiments/ldbc_snb.py documents it; on the laptop it is ~/bench-data/ldbc/sf1) and returns plain
Python rows. Nothing here is timed.

Year conversions follow ldbc_snb._birth_year: the corpus writes epoch milliseconds.
`person_limit` keeps the first N persons in file order and drops every row that references a dropped person
(the campaign's BENCH_GRAPH_PERSON_LIMIT idea); 0 keeps all.
"""
import csv
import datetime
import glob
import os


def _year(ms):
    return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).year


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="|")
        header = next(r)
        cols = {name: i for i, name in enumerate(header)}
        for row in r:
            yield row, cols


def find_roots(data_dir):
    hits = glob.glob(os.path.join(data_dir, "social_network-*", "dynamic"))
    if not hits:
        raise SystemExit(f"ldbc_subset: no social_network-*/dynamic under {data_dir}")
    dyn = hits[0]
    return dyn, os.path.join(os.path.dirname(dyn), "static")


def load(data_dir, person_limit=0):
    dyn, sta = find_roots(data_dir)
    persons = []
    for n, (row, c) in enumerate(_rows(os.path.join(dyn, "person_0_0.csv"))):
        if person_limit and n >= person_limit:
            break
        persons.append((int(row[c["id"]]), row[c["firstName"]], row[c["lastName"]], row[c["gender"]],
                        _year(row[c["birthday"]]), _year(row[c["creationDate"]]), int(row[c["place"]])))
    keep = {p[0] for p in persons}

    cities, countries = [], []
    for row, c in _rows(os.path.join(sta, "place_0_0.csv")):
        if row[c["type"]] == "city":
            cities.append((int(row[c["id"]]), row[c["name"]], int(row[c["isPartOf"]])))
        elif row[c["type"]] == "country":
            countries.append((int(row[c["id"]]), row[c["name"]]))

    forums = []
    for row, c in _rows(os.path.join(dyn, "forum_0_0.csv")):
        mod = int(row[c["moderator"]])
        if mod in keep:
            forums.append((int(row[c["id"]]), row[c["title"]], mod))

    tags, tagclasses = [], []
    for row, c in _rows(os.path.join(sta, "tag_0_0.csv")):
        tags.append((int(row[c["id"]]), row[c["name"]], int(row[c["hasType"]])))
    for row, c in _rows(os.path.join(sta, "tagclass_0_0.csv")):
        tagclasses.append((int(row[c["id"]]), row[c["name"]]))

    knows = []
    with open(os.path.join(dyn, "person_knows_person_0_0.csv"), newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="|")
        next(r)  # header has two columns both named Person.id
        for row in r:
            a, b = int(row[0]), int(row[1])
            if a in keep and b in keep:
                knows.append((min(a, b), max(a, b), _year(row[2])))

    interests = []
    for row, c in _rows(os.path.join(dyn, "person_hasInterest_tag_0_0.csv")):
        pid = int(row[c["Person.id"]])
        if pid in keep:
            interests.append((pid, int(row[c["Tag.id"]])))

    return {"person": persons, "city": cities, "country": countries, "forum": forums, "tag": tags,
            "tagclass": tagclasses, "knows": knows, "hasinterest": interests}


def counts(data):
    return {k: len(v) for k, v in data.items()}
