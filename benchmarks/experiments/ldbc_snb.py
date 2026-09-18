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

# Person counts of the OFFICIAL datasets. Kept for the scale names and as a
# progress hint; the streams read whatever the files actually contain.
#
# NOT A CORPUS FINGERPRINT. Our generated sf1 holds 9,892 persons against the
# official 10,995, so a shortfall guard comparing ingest against THIS refuses a
# perfectly good run -- which it did, failing every l2 cell of qBI. Use
# persons_in_corpus() for anything that must describe the corpus on disk.
SCALE_PERSONS = {"sf1": 10_995, "sf10": 72_949,
                 # The FULL SF1 network for the analytics workload (DECISIONS
                 # #103b): the same sf1/ directory, persons+KNOWS plus the
                 # message half below. A tier name of its own so its rows never
                 # share a canonical key with the projection rows they replace
                 # on the analytics table, and so the runner can give it the
                 # envelope 17M records need without moving the sf1 tier.
                 "sf1full": 10_995}
# Which corpus directory a tier reads. sf1full is not a download; it is sf1
# read whole.
SCALE_DIR = {"sf1full": "sf1"}
# What the analytics loader must stream from the uncapped sf1 network, from
# the corpus README (~/bench-data/ldbc-sf1-full/README.md, per-file counts,
# 2026-09-17; mini's ldbc/sf1 matches it file for file). The message half is
# the query-driven subset MessageCorpus loads, not every file in the tarball:
# 7 vertex labels (3,163,871 ids) and 14 edge streams (13,581,644 pairs). The
# lane refuses a shortfall the same way it refuses a short person load.
FULL_NETWORK_COUNTS = {"sf1full": {"msg_vertices": 3_163_871, "msg_edges": 13_581_644,
                                   "persons": 9_892, "knows": 180_623}}

_CORPUS_PERSONS = {}


def persons_in_corpus(scale):
    """How many persons the corpus ON DISK actually holds, counted once.

    The shortfall guard exists to catch a truncated LOAD -- ingesting fewer rows
    than the file offers. Comparing against a published constant instead makes
    it fire on a corpus that is merely a different generation, which is the
    "fingerprinting a constant" failure the guard was written to fix, one level
    up. Counted from the same file gen_persons() streams.

    Returns None when the file cannot be read, so the caller can skip the check
    rather than refuse on a count it does not have.
    """
    if scale in _CORPUS_PERSONS:
        return _CORPUS_PERSONS[scale]
    try:
        path = _root(scale) / "person_0_0.csv"
        with open(path, "rb") as fh:
            n = max(0, sum(1 for _ in fh) - 1)     # minus the header
        # Under a smoke cap the corpus the run loads IS the capped one, so the
        # shortfall guard compares against that, not the whole file.
        if PERSON_LIMIT:
            n = min(n, PERSON_LIMIT)
        _CORPUS_PERSONS[scale] = n or None
    except Exception:                              # noqa: BLE001
        _CORPUS_PERSONS[scale] = None
    return _CORPUS_PERSONS[scale]
SCALE_OLTP_QUERIES = {"sf1": 500, "sf10": 200, "sf1full": 500}
OLAP_ITERATIONS = OLAP_ITERATIONS  # re-export unchanged

PICK_SEED = 777


def _root(scale):
    base = Path(os.environ.get("BENCH_GRAPH_DATA", "/data/ldbc")) / SCALE_DIR.get(scale, scale)
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


def _static(scale):
    """The static/ dir that sits beside dynamic/ (tags, tag classes, places)."""
    return _root(scale).parent / "static"


# BENCH_GRAPH_PERSON_LIMIT caps the persons+KNOWS projection to the first N
# persons IN FILE ORDER, and drops every KNOWS whose endpoints are not both
# loaded. It exists ONLY for a laptop smoke of the analytics message half: the
# full SF1 network is 17M records, which a laptop cannot load for a smoke.
# Default 0 = the whole projection, so the interactive oltp workload and every
# bench-host run are UNCHANGED; only a smoke that exports it is capped, and
# every engine it compares sees the identical capped graph.
PERSON_LIMIT = int(os.environ.get("BENCH_GRAPH_PERSON_LIMIT") or 0)
_LOADED_PERSONS = {}


def _loaded_persons(scale):
    """The set of person ids under the cap, or None when uncapped (=all)."""
    if not PERSON_LIMIT:
        return None
    if scale not in _LOADED_PERSONS:
        s = set()
        rows = _csv_rows(_root(scale) / "person_0_0.csv")
        i_id = next(rows).index("id")
        for n, row in enumerate(rows):
            if n >= PERSON_LIMIT:
                break
            s.add(int(row[i_id]))
        _LOADED_PERSONS[scale] = s
    return _LOADED_PERSONS[scale]


def gen_persons(scale):
    """Yield (id, name, age, city) from person_0_0.csv (capped by PERSON_LIMIT)."""
    rows = _csv_rows(_root(scale) / "person_0_0.csv")
    header = next(rows)
    col = {name: i for i, name in enumerate(header)}
    i_id, i_fn, i_ln = col["id"], col["firstName"], col["lastName"]
    i_bd = col["birthday"]
    # CsvCompositeMergeForeign appends the place FK as the last column
    i_place = col.get("place", len(header) - 1)
    for n, row in enumerate(rows):
        if PERSON_LIMIT and n >= PERSON_LIMIT:
            break
        birth_year = int(row[i_bd][:4]) if row[i_bd][:4].isdigit() else 1980
        yield (int(row[i_id]), f"{row[i_fn]} {row[i_ln]}",
               max(0, _REF_YEAR - birth_year), f"city_{row[i_place]}")


def gen_edges(scale):
    """Yield (src_id, dst_id, since_year) from person_knows_person_0_0.csv.

    Under PERSON_LIMIT only the friendships whose BOTH ends were loaded are
    kept, so the capped KNOWS graph is self-consistent."""
    keep = _loaded_persons(scale)
    rows = _csv_rows(_root(scale) / "person_knows_person_0_0.csv")
    header = next(rows)
    for row in rows:
        src, dst = int(row[0]), int(row[1])
        if keep is not None and (src not in keep or dst not in keep):
            continue
        # creationDate is epoch millis with the LongDateFormatter serializer
        try:
            since = 1970 + int(row[2]) // 31_557_600_000
        except (ValueError, IndexError):
            since = 2012
        yield src, dst, since


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


# ===========================================================================
# MESSAGE HALF -- the full social network for the ANALYTICS workload only
# (DECISIONS #103b: graph analytics moves to the full SF1 network). Loaded
# ONLY at the sf1full tier, for the olap workload, keyed off
# BENCH_GRAPH_SOURCE=ldbc the same way the persons+KNOWS projection is; the
# interactive (oltp) workload keeps loading persons+KNOWS alone at sf1 and
# sf10 and never sees any of this.
#
# WHAT IS LOADED, and only this (the query-driven subset the October
# instrument's LSQB queries need, so the two pages measure one corpus):
#   vertices   Forum, Post, Comment, Tag, TagClass, Country, City
#   edges      IS_LOCATED_IN (Person->City), IS_PART_OF (City->Country),
#              HAS_MEMBER (Forum->Person), CONTAINER_OF (Forum->Post),
#              REPLY_OF (Comment->Post, Comment->Comment),
#              HAS_TAG (Post->Tag, Comment->Tag), HAS_TYPE (Tag->TagClass),
#              HAS_CREATOR (Post->Person, Comment->Person),
#              LIKES (Person->Post, Person->Comment),
#              HAS_INTEREST (Person->Tag)
# Persons and KNOWS are already loaded by gen_persons/gen_edges above; the
# message half is layered on top of them. September's three analytics
# questions read persons and KNOWS only, so with the message half loaded they
# answer the same; what the raise changes is the corpus under the table and
# the ingest column (DECISIONS #103b).
#
# MESSAGE is the SNB supertype of Post and Comment. It is not a file: each
# engine expresses it as type inheritance (ArcadeDB EXTENDS) or as a second
# label on every Post and Comment (Neo4j/Memgraph/FalkorDB). The sub-labels
# are named in MSG_MESSAGE_SUBLABELS.
#
# EVERY vertex carries only its id and every edge is a (src_id, dst_id) pair:
# the analytics table asks structural questions of this half, so nothing else
# is loaded.
#
# BENCH_GRAPH_MSG_LIMIT=N caps the three big dynamic vertex files (Forum, Post,
# Comment) to their first N rows and filters every edge to endpoints that were
# actually loaded, so the sliced subgraph is self-consistent AND identical on
# every engine. 0 = the whole corpus. Persons, tags, tag classes and places are
# always loaded whole (all small), so those endpoints are never dangling and
# need no filtering. A laptop smoke sets it; the campaign never does.
MSG_LIMIT = int(os.environ.get("BENCH_GRAPH_MSG_LIMIT") or 0)

# Load order: vertices before the edges that reference them.
MSG_VERTEX_LABELS = ["Country", "City", "Forum", "Post", "Comment", "Tag", "TagClass"]
MSG_MESSAGE_SUBLABELS = ["Post", "Comment"]
_CAPPED = {"Forum", "Post", "Comment"}

# label -> (subdir, filename, id column)
_VFILE = {
    "Forum":    ("dynamic", "forum_0_0.csv", "id"),
    "Post":     ("dynamic", "post_0_0.csv", "id"),
    "Comment":  ("dynamic", "comment_0_0.csv", "id"),
    "Tag":      ("static",  "tag_0_0.csv", "id"),
    "TagClass": ("static",  "tagclass_0_0.csv", "id"),
}


def loads_messages(scale):
    """Whether this tier carries the message half (the full-network tiers)."""
    return scale in FULL_NETWORK_COUNTS


def _file(scale, subdir, fname):
    return (_root(scale) if subdir == "dynamic" else _static(scale)) / fname


def _rows_with_cols(path):
    """Yield (row, {col: index}); the col map is the same object every row."""
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="|")
        cols = {name: i for i, name in enumerate(next(r))}
        for row in r:
            yield row, cols


class MessageCorpus:
    """The message half of the full LDBC network at one scale (see the section
    banner above). Construct once per build; its generators can be re-streamed."""

    def __init__(self, scale):
        self.scale = scale
        self._loaded = {}   # label -> set(ids) when capped; absent = load all
        if MSG_LIMIT:
            for label in _CAPPED:
                self._loaded[label] = set(self._first_ids(label, MSG_LIMIT))
        # Under a persons smoke cap, message-half edges to/from a person that
        # was not loaded are dropped too, so the whole slice stays consistent.
        lp = _loaded_persons(scale)
        if lp is not None:
            self._loaded["Person"] = lp

    @property
    def capped(self):
        return bool(MSG_LIMIT or PERSON_LIMIT)

    # -- vertices ----------------------------------------------------------
    def _first_ids(self, label, limit):
        subdir, fname, idcol = _VFILE[label]
        n = 0
        for row, cols in _rows_with_cols(_file(self.scale, subdir, fname)):
            yield int(row[cols[idcol]])
            n += 1
            if n >= limit:
                return

    def vertex_ids(self, label):
        """Bare ids for one message-half vertex label, honouring the cap."""
        if label in ("Country", "City"):
            want = label.lower()
            for row, cols in _rows_with_cols(_file(self.scale, "static", "place_0_0.csv")):
                if row[cols["type"]] == want:
                    yield int(row[cols["id"]])
            return
        cap = self._loaded.get(label)
        subdir, fname, idcol = _VFILE[label]
        for row, cols in _rows_with_cols(_file(self.scale, subdir, fname)):
            vid = int(row[cols[idcol]])
            if cap is None or vid in cap:
                yield vid

    def vertex_spec(self):
        """[(label, id_generator), ...] in load order."""
        return [(label, self.vertex_ids(label)) for label in MSG_VERTEX_LABELS]

    def _keep(self, label, vid):
        s = self._loaded.get(label)
        return s is None or vid in s

    # -- edge streams (each yields (src_id, dst_id)) -----------------------
    def _fk_edge(self, subdir, fname, src_col, dst_col, src_label, dst_label):
        for row, cols in _rows_with_cols(_file(self.scale, subdir, fname)):
            sv = row[cols[src_col]]
            dv = row[cols[dst_col]]
            if sv == "" or dv == "":
                continue
            s, d = int(sv), int(dv)
            if self._keep(src_label, s) and self._keep(dst_label, d):
                yield s, d

    def e_person_islocatedin_city(self):
        # person.place is the person's City (merged FK column)
        return self._fk_edge("dynamic", "person_0_0.csv", "id", "place",
                             "Person", "City")

    def e_city_ispartof_country(self):
        for row, cols in _rows_with_cols(_file(self.scale, "static", "place_0_0.csv")):
            if row[cols["type"]] == "city" and row[cols["isPartOf"]] != "":
                yield int(row[cols["id"]]), int(row[cols["isPartOf"]])

    def e_forum_hasmember_person(self):
        return self._fk_edge("dynamic", "forum_hasMember_person_0_0.csv",
                             "Forum.id", "Person.id", "Forum", "Person")

    def e_forum_containerof_post(self):
        # post.Forum.id names the containing forum: Forum -CONTAINER_OF-> Post
        for row, cols in _rows_with_cols(_file(self.scale, "dynamic", "post_0_0.csv")):
            pid = int(row[cols["id"]])
            fid = int(row[cols["Forum.id"]])
            if self._keep("Post", pid) and self._keep("Forum", fid):
                yield fid, pid

    def e_comment_replyof_post(self):
        return self._fk_edge("dynamic", "comment_0_0.csv", "id", "replyOfPost",
                             "Comment", "Post")

    def e_comment_replyof_comment(self):
        return self._fk_edge("dynamic", "comment_0_0.csv", "id", "replyOfComment",
                             "Comment", "Comment")

    def e_post_hastag_tag(self):
        return self._fk_edge("dynamic", "post_hasTag_tag_0_0.csv",
                             "Post.id", "Tag.id", "Post", "Tag")

    def e_comment_hastag_tag(self):
        return self._fk_edge("dynamic", "comment_hasTag_tag_0_0.csv",
                             "Comment.id", "Tag.id", "Comment", "Tag")

    def e_tag_hastype_tagclass(self):
        return self._fk_edge("static", "tag_0_0.csv", "id", "hasType",
                             "Tag", "TagClass")

    def e_post_hascreator_person(self):
        return self._fk_edge("dynamic", "post_0_0.csv", "id", "creator",
                             "Post", "Person")

    def e_comment_hascreator_person(self):
        return self._fk_edge("dynamic", "comment_0_0.csv", "id", "creator",
                             "Comment", "Person")

    def e_person_likes_post(self):
        return self._fk_edge("dynamic", "person_likes_post_0_0.csv",
                             "Person.id", "Post.id", "Person", "Post")

    def e_person_likes_comment(self):
        return self._fk_edge("dynamic", "person_likes_comment_0_0.csv",
                             "Person.id", "Comment.id", "Person", "Comment")

    def e_person_hasinterest_tag(self):
        return self._fk_edge("dynamic", "person_hasInterest_tag_0_0.csv",
                             "Person.id", "Tag.id", "Person", "Tag")

    def edge_spec(self):
        """[(rel_type, src_label, dst_label, pair_generator_fn), ...].

        REPLY_OF, HAS_TAG, HAS_CREATOR and LIKES each appear twice (a Post and a
        Comment side) because Message is Post union Comment; they are one edge
        type on each engine, loaded from two streams."""
        return [
            ("IS_LOCATED_IN", "Person", "City",     self.e_person_islocatedin_city),
            ("IS_PART_OF",    "City",   "Country",  self.e_city_ispartof_country),
            ("HAS_MEMBER",    "Forum",  "Person",   self.e_forum_hasmember_person),
            ("CONTAINER_OF",  "Forum",  "Post",     self.e_forum_containerof_post),
            ("REPLY_OF",      "Comment","Post",     self.e_comment_replyof_post),
            ("REPLY_OF",      "Comment","Comment",  self.e_comment_replyof_comment),
            ("HAS_TAG",       "Post",   "Tag",      self.e_post_hastag_tag),
            ("HAS_TAG",       "Comment","Tag",      self.e_comment_hastag_tag),
            ("HAS_TYPE",      "Tag",    "TagClass", self.e_tag_hastype_tagclass),
            ("HAS_CREATOR",   "Post",   "Person",   self.e_post_hascreator_person),
            ("HAS_CREATOR",   "Comment","Person",   self.e_comment_hascreator_person),
            ("LIKES",         "Person", "Post",     self.e_person_likes_post),
            ("LIKES",         "Person", "Comment",  self.e_person_likes_comment),
            ("HAS_INTEREST",  "Person", "Tag",      self.e_person_hasinterest_tag),
        ]
