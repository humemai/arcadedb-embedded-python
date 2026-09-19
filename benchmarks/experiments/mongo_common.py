"""MongoDB through pymongo, served only, shared by every lane that runs it.

MongoDB has no in-process mode, so it gets one row per table, like ArangoDB
(DECISIONS #78). Before October it ran on three tables -- documents, TPC and
the native time-series collection -- and was absent from vectors, graph and
cross-model. DECISIONS #68 recorded the vector absence as "needs the separate
mongot process, a two-container server the runner cannot start yet" and the
graph absence as "$graphLookup is not a model it claims". This module exists
because the first of those stopped being true and the second was never a
reason under #92: an engine competes in its own dialect if it can express the
query.

WHICH DEPLOYMENT, AND WHY

  documents / TPC / time series   `mongo` 8.2.12, no access control, one-node
                                  replica set (a multi-document transaction
                                  needs one). Unchanged.
  graph                           THE SAME IMAGE AND THE SAME DIGEST. The
                                  traversal is $graphLookup and chained
                                  $lookup, both core mongod, so the graph arm
                                  needs nothing mongot does.
  dense vectors / cross-model     `dbbench:mongo-search`: the same mongod
                                  digest plus mongot 1.70.4, MongoDB Search
                                  Community, in one container
                                  (Dockerfile.mongosearch). mongot requires
                                  SCRAM or x509 against its sync source, so
                                  THIS ARM RUNS WITH ACCESS CONTROL ON and
                                  the document arm does not. That is a
                                  property of the feature rather than a knob
                                  we chose, and `mongo_auth` on the row says
                                  which of the two a cell ran.

WHY NOT mongodb/mongodb-atlas-local, which would have been one line: MongoDB
documents it as "For evaluation only" and "not suitable for production use",
and its vector-capable variant is a `:preview` tag. #68 pins comparators to
the latest self-hosted RELEASE. MongoDB Search and Vector Search reached
general availability for Community Edition on 2026-06-30 and ship as the
mongot binary beside mongod; that is what the image builds, and it is what an
operator would actually deploy.
"""
from __future__ import annotations

import os
import time

import bench_common

DB = "bench"
USER = "root"
PASSWORD = "dbbenchpass"
DURABILITY = bench_common.DURABILITY_MONGODB


def uri(auth: bool) -> str:
    host = os.environ.get("BENCH_SERVER_HOST", "localhost")
    port = os.environ.get("BENCH_SERVER_PORT", "27017")
    cred = f"{USER}:{PASSWORD}@" if auth else ""
    tail = "&authSource=admin" if auth else ""
    return f"mongodb://{cred}{host}:{port}/?directConnection=true{tail}"


def connect(auth: bool = False, fresh: bool = True, wait_s: int = 120):
    """(client, bench db, "mongodb <version>") against a primary that supports
    sessions.

    THE RECONNECT IS NOT OPTIONAL and the reason is on the record (l1_tpc,
    2026-09-12 laptop smoke): the first client's topology snapshot is taken
    while the node is still starting and carries no
    logicalSessionTimeoutMinutes, so the first transaction raises "Sessions
    are not supported by this MongoDB deployment" before the next heartbeat
    refreshes it. A second client discovers the primary as such.
    """
    import pymongo

    u = uri(auth)
    cl = pymongo.MongoClient(u, serverSelectionTimeoutMS=60000)
    # Idempotent: the plain `mongo` image needs the single-node set initiated,
    # dbbench:mongo-search has already done it in its entrypoint (mongot
    # cannot sync from a standalone), and an already-initiated set answers
    # with an OperationFailure this deliberately swallows.
    try:
        # THE MEMBER HOST IS THE SERVER'S OWN VIEW OF ITSELF, not the address we
        # dialled. A replica set member name has to resolve INSIDE mongod, and
        # the client's address need not: a published port maps 37018 outside to
        # 27017 inside, and initiating with the outside address leaves a member
        # the node cannot find, which shows up later as a bare "not primary" on
        # the first write. localhost:27017 is what the node always is, and
        # directConnection=true means the client never routes through the
        # member list anyway. Same address the mongot config uses, for the same
        # reason.
        cl.admin.command("replSetInitiate",
                         {"_id": "rs0", "members": [{"_id": 0, "host": "localhost:27017"}]})
    except pymongo.errors.OperationFailure:
        pass
    for _ in range(wait_s * 2):
        try:
            if cl.admin.command("hello").get("isWritablePrimary"):
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    cl.close()
    cl = pymongo.MongoClient(u, serverSelectionTimeoutMS=60000)
    for _ in range(wait_s * 2):
        try:
            cl.admin.command("ping")
            if cl.topology_description.logical_session_timeout_minutes is not None:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    version = f"mongodb {cl.server_info()['version']}"
    if fresh:
        cl.drop_database(DB)
    return cl, cl[DB], version


def write_concern(cls=None):
    """w=1 with j from the durability class (DECISIONS #90).

    j=false at the relaxed class (the journal is flushed every 100 ms),
    j=true at the strict one, where the ack waits for the journal sync.
    """
    from pymongo import WriteConcern
    return WriteConcern(w=1, j=bench_common.journal_ack(cls))


def search_version(cl) -> str:
    """The mongot build behind $vectorSearch, READ from the deployment.

    A row that names only the mongod version describes half of the deployment:
    the vector index is built and served by a different binary on a different
    release line, and "mongodb 8.2.12" alone cannot be re-measured.

    mongod answers for its own build and knows nothing about mongot's, and
    mongot's health port is bound to localhost inside the server container, so
    the entrypoint copies the image's own VERSION.txt into `dbbench.build` at
    startup and this reads it back. When it is missing the string says so
    rather than substituting a constant: an unread version that looks like a
    read one is worse than a blank.
    """
    try:
        r = cl.admin.command({"getParameter": 1, "mongotHost": 1})
        host = r.get("mongotHost") or "unset"
    except Exception as e:  # noqa: BLE001
        host = f"unreadable ({e.__class__.__name__})"
    try:
        doc = cl["dbbench"]["build"].find_one({"_id": "mongot"}) or {}
        ver = doc.get("version") or "mongot version not recorded by the image"
    except Exception as e:  # noqa: BLE001
        ver = f"mongot version unreadable ({e.__class__.__name__})"
    return f"{ver} at {host}"


# ---------------------------------------------------------------- vector index
#
# THE OPERATING POINT IS EXPRESSIBLE, and that had to be checked rather than
# assumed. $vectorSearch takes an HNSW index whose degree and construction
# beam are `hnswOptions.maxEdges` and `hnswOptions.numEdgeCandidates`, and the
# search-time candidate list is the stage's own `numCandidates`. Verified
# accepted on this pin (Community 8.2.12 + mongot 1.70.4, laptop 2026-09-15):
# the created index reads back
#   "indexingMethod": "hnsw", "hnswOptions": {"maxEdges": 16, "numEdgeCandidates": 100}
# which is exactly the lane's matched point (COMPARATOR_M=16,
# EF_CONSTRUCTION=100, EF_SEARCH=100). MongoDB's own defaults happen to be the
# same two numbers; they are passed explicitly anyway, so the row records a
# configuration rather than a coincidence, and a future default change cannot
# move this lane's operating point without anyone noticing.
#
# maxEdges is Lucene HNSW's per-layer bound with the base layer doubled, the
# same family as hnswlib's M, which is why degree_stamp puts this arm in the
# hnswlib_m_doubled_at_base class beside Qdrant, pgvector, Neo4j and SurrealDB.
VECTOR_INDEX = "vidx"


def create_vector_index(coll, path, dim, max_edges, num_edge_candidates,
                        similarity="euclidean", filter_paths=(), name=VECTOR_INDEX):
    from pymongo.operations import SearchIndexModel
    field = {"type": "vector", "path": path, "numDimensions": int(dim),
             "similarity": similarity, "quantization": "none",
             "indexingMethod": "hnsw",
             "hnswOptions": {"maxEdges": int(max_edges),
                             "numEdgeCandidates": int(num_edge_candidates)}}
    fields = [field] + [{"type": "filter", "path": p} for p in filter_paths]
    coll.create_search_index(SearchIndexModel(definition={"fields": fields},
                                              name=name, type="vectorSearch"))
    return name


def wait_queryable(coll, name=VECTOR_INDEX, timeout_s=7200):
    """Block until mongot reports the index READY and queryable.

    THE CLOCK STOPS HERE, NOT AT create_search_index. mongot builds the index
    out of band from the oplog, so the create call returns in milliseconds
    while the index does not exist yet -- the same shape as the Milvus settle
    this harness already documents at length (BUGS F8): an engine that answers
    queries before its index is built produces a build time that is not one,
    and a recall that came from something other than the index under test.
    Both conjuncts are load-bearing: `status` goes READY before `queryable`
    flips on a fresh index.
    """
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        idx = [i for i in coll.list_search_indexes() if i.get("name") == name]
        last = idx[0] if idx else None
        if last and last.get("status") == "READY" and last.get("queryable"):
            return last
        time.sleep(0.5)
    raise RuntimeError(f"mongot index {name!r} not queryable within {timeout_s}s: {last}")


def close(cl):
    try:
        cl.close()
    except Exception:  # noqa: BLE001
        pass
