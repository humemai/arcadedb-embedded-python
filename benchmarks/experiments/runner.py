#!/usr/bin/env python3
"""Benchmark runner — implements experiments/PROTOCOL.md.

Descended from the binding-suite orchestrator
(benchmarks/python-bindings/run.py) with the protocol extensions:

  * TOPOLOGIES: "embedded" (one container does engine+workload) and
    "client_server" (a long-lived server container + a client container).
    Per PROTOCOL: both containers share the SAME cpuset (CPU competition is
    natural/work-conserving); MEMORY is split explicitly (default 75/25) and
    the reported numbers are the SUM of both cgroups.
  * TIERS: tier2 (default) runs cells strictly serially with the full cpuset —
    every paper number comes from this tier. tier1 (--parallel N) is the
    exploration sweep: N workers on disjoint cpuset shards, shuffled job order,
    never two jobs of the same backend at once. Manifests record the tier.
  * MANIFESTS: results/manifest-<ts>.json records image digests, cpuset,
    memory caps, tier, repeats; every row in runs.jsonl carries run metadata.

Usage (smoke):    python3 runner.py --lanes l1 --scale tiny --reps 1
Paper (serial):   python3 runner.py --lanes l1,l2,l3s,l3d,l4 --scale medium --reps 5
Sweep (parallel): python3 runner.py --parallel 3 --tier sweep ...
"""
import argparse
import csv
import fcntl
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.abspath(os.environ.get("BENCH_DATA", os.path.join(HERE, "data")))
RESULTS = os.path.join(HERE, "results")
RAW = os.path.join(RESULTS, "raw")
SAMPLE_INTERVAL = 0.25

# P-core threads on the i9-12900HK bench host; override for other hosts.
CPUSET = os.environ.get("BENCH_CPUSET", "0-11")
MEM_BY_SCALE = {"micro": "8g", "tiny": "8g", "small": "16g", "medium": "32g",
                "large": "48g",
                # LDBC-SNB tiers (l2 lane, BENCH_GRAPH_SOURCE=ldbc)
                "sf1": "8g", "sf10": "24g",
                # DEEP-10M dense tier (l3d); 36g since the degree-matched
                # ablation (maxConnections=32, #5352) peaks ~19GB build heap
                "deep10m": "36g",
                "e2": "12g", "tpch1": "16g",
                # TPC-H SF10 (~10 GB). SF1 is 1 GB, which reads as a toy
                # scale at a DB venue where comparable papers run 700 GB+.
                "tpch10": "32g"}
# Per-cell watchdog: a cell exceeding this is killed and recorded as a timeout.
# Generous by design (ingest included); real hangs run to infinity without it.
TIMEOUT_BY_SCALE = {"micro": 900, "tiny": 1800, "small": 7200,
                    "medium": 6 * 3600, "large": 24 * 3600,
                    "sf1": 3600, "sf10": 6 * 3600, "deep10m": 6 * 3600,
                    "e2": 3600, "tpch1": 3 * 3600,
                    "tpch10": 8 * 3600}
HEAP_BY_SCALE = {"micro": "4g", "tiny": "4g", "small": "8g", "medium": "16g",
                 "large": "24g",
                 # THE HEAP LIVES INSIDE THE CAP. cgroup v2 bounds the whole
                 # container (anon + page cache), so a heap that approaches
                 # MEM_BY_SCALE does not raise OutOfMemoryError -- the kernel
                 # OOM-kills the container, silently, which is how thirty SF10
                 # cells exited 137 with no output. Heap must therefore fit the
                 # 75% SERVER-CONTAINER share with room left for metaspace,
                 # code cache, thread stacks, GC structures, direct buffers and
                 # the page cache of the engine's own files. JVMs here pin
                 # -Xms=-Xmx, so the heap is committed up front and the
                 # headroom is real, not notional.
                 #
                 # Every tier is heap = 50% of cap. deep10m is the exception
                 # at 67% (24g in 36g), which is where the degree-matched
                 # build actually peaks.
                 #
                 # This comment used to justify that with "the build peaks
                 # near 19 GB, and 16g OOMed". That claim was WITHDRAWN after
                 # #5412 made the build cache auto-size; the paper now states
                 # twice that both quantizations build inside 16 GiB. Left as
                 # a record because the number outlived its evidence in three
                 # places at once, here, in the Fig. 6 annotation, and in the
                 # lessons section.
                 #
                 # The served arm's headroom is no longer 3g: it now gets the
                 # full 36g cap rather than 0.75 of it, so 12g against a 24g
                 # heap.
                 "sf1": "4g", "sf10": "12g", "deep10m": "24g", "e2": "6g", "tpch1": "8g",
                    "tpch10": "16g"}
# THE SERVED ENGINE GETS THE FULL TIER CAP, and the driver gets its own budget
# on top. It used to take 0.75 of the cap while the embedded arm took all of
# it, so at medium an embedded engine ran in 32g and a served one in 24g, with
# both given the same heap. The headline ArcadeDB number in every table is the
# EMBEDDED arm, which is the one arm that never paid that split, and the
# deployment-axis claim attributed the resulting delta to serialisation.
#
# Cost is host RAM: a served cell now needs cap + CLIENT_MEM rather than cap.
# The largest published tier is deep10m at 36g, so 44g against mini's 61g.
CLIENT_MEM = os.environ.get("BENCH_CLIENT_MEM", "8g")
# Kept for the sweep tier and for anyone reproducing an older run; unused by
# the paper tier now. Setting it forces the old behaviour back.
SERVER_MEM_FRACTION = float(os.environ.get("BENCH_SERVER_MEM_FRACTION", "0")) or None

# ---------------------------------------------------------------- backends
# Each backend: image (bench image for the workload driver), topology, and for
# client_server: the server image + readiness probe + env.
BACKENDS = {
    "arcadedb_embedded": {
        "topology": "embedded",
        "image": "dbbench:arcadedb",
    },
    "arcadedb_server": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "arcadedata/arcadedb:26.8.1@sha256:49036720b1678b9c7a6dbf22fc34a812c8d7bed15508c22cbb02c0dddc0ca16a",  # RELEASED 26.8.1, matches the 26.8.1 wheel (F5: one engine line per table)
        # Heap parity with the embedded deployment (protocol: same JVM-heap
        # policy per scale tier) — the image's own default is -Xmx2G, which
        # starved the server vs embedded's per-scale heap. Setting JAVA_OPTS
        # also drops the image's ZGC default: both deployments run the same
        # default GC (G1) so the embedded-vs-server axis isolates transport,
        # not GC choice.
        "server_env": ["-e", "ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}",
                       "-e", "JAVA_OPTS=-Darcadedb.server.rootPassword=dbbenchpass "
                             "-Darcadedb.server.defaultDatabases=bench[root] "
                             "-Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000"],
        "server_port": 2480,
        "ready_regex": r"HTTP Server started",
    },
    "duckdb": {
        "topology": "embedded",
        "image": "dbbench:duckdb",
    },
    "postgres": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "postgres@sha256:de1e13ca94377fa5a27aafd0e9fc200df9692b15152f0090fdf074074ea5e397",  # 17.10
        "server_env": ["-e", "POSTGRES_PASSWORD=dbbenchpass", "-e", "POSTGRES_DB=bench"],
        "server_port": 5432,
        # the image prints "ready to accept connections" TWICE (initdb's
        # temporary server, then the real one); anchor on the init-complete
        # marker so we only match the second — matching the first raced the
        # restart window (2 intermittent connection-refused cells, 2026-07-08)
        "ready_regex": r"(?s)PostgreSQL init process complete.*"
                       r"database system is ready to accept connections",
    },
    # PostgreSQL with its memory settings tuned for the container it is in,
    # as an ABLATION against the default arm above.
    #
    # WHY THIS ARM EXISTS. We set ArcadeDB's heap per scale tier (16g at
    # medium) and left PostgreSQL at the image's defaults, which are 128 MB
    # shared_buffers and 4 MB work_mem: numbers chosen so PostgreSQL starts on
    # any machine, not numbers anyone deploys. Our fairness policy says to
    # equalize a default that makes the comparison apples-to-oranges, and we
    # had never tested whether this one does.
    #
    # It is NOT here to fix the memory column. Verified directly: a container
    # given shared_buffers=2GB still reports 5 MiB anon, because the buffer
    # pool is POSIX shared memory that cgroup v2 files under shmem. This arm
    # answers the LATENCY half of the question and nothing else.
    #
    # Sized by PostgreSQL's own guidance against the 24g this container gets
    # (0.75 of the medium tier's 32g): shared_buffers a quarter,
    # effective_cache_size three quarters, work_mem and maintenance_work_mem
    # raised off the floor, max_wal_size raised so a bulk load does not
    # checkpoint-storm.
    #
    # DURABILITY IS UNTOUCHED, deliberately. fsync and synchronous_commit stay
    # on, because the tables disclose that PostgreSQL fsyncs per commit while
    # ArcadeDB groups commits, and an arm that quietly relaxed that would be
    # answering a different question while wearing this one's name.
    "postgres_tuned": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "postgres@sha256:de1e13ca94377fa5a27aafd0e9fc200df9692b15152f0090fdf074074ea5e397",  # 17.10, same digest as the default arm
        "server_env": ["-e", "POSTGRES_PASSWORD=dbbenchpass", "-e", "POSTGRES_DB=bench"],
        # Sized from the container, not written as a constant. The two lanes
        # that run PostgreSQL get different envelopes (24g at medium, 12g at
        # tpch1), so a literal 6GB would be a quarter of one and a half of the
        # other. {sb} and {ecs} are filled in below from the memory this
        # container is actually given.
        "server_cmd": ["-c", "shared_buffers={sb}",
                       "-c", "effective_cache_size={ecs}",
                       "-c", "work_mem=64MB",
                       "-c", "maintenance_work_mem=1GB",
                       "-c", "max_wal_size=4GB"],
        "server_port": 5432,
        "ready_regex": r"(?s)PostgreSQL init process complete.*"
                       r"database system is ready to accept connections",
    },
    # ---- L3 sparse lane ----
    "arcadedb_graph_embedded": {
        "topology": "embedded",
        "image": "dbbench:arcadedb",
    },
    "arcadedb_graph_server": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "arcadedata/arcadedb:26.8.1@sha256:49036720b1678b9c7a6dbf22fc34a812c8d7bed15508c22cbb02c0dddc0ca16a",  # RELEASED 26.8.1, matches the 26.8.1 wheel (F5: one engine line per table)
        "server_env": ["-e", "ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}",
                       "-e", "JAVA_OPTS=-Darcadedb.server.rootPassword=dbbenchpass "
                             "-Darcadedb.server.defaultDatabases=bench[root] "
                             "-Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000"],
        "server_port": 2480,
        "ready_regex": r"HTTP Server started",
    },
    "neo4j_graph": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "neo4j@sha256:4bae36aff76271e27fd6a6ed0835413f86a284cd179cfb1cb7d188f5f7533aca",  # 5-community
        # heap parity with the ArcadeDB deployments (same per-scale heap)
        "server_env": ["-e", "NEO4J_AUTH=neo4j/dbbenchpass",
                       "-e", "NEO4J_server_memory_heap_initial__size={heap}",
                       "-e", "NEO4J_server_memory_heap_max__size={heap}",
                       # PAGE CACHE, which for Neo4j is the load-bearing
                       # setting and was never set. The image entrypoint
                       # hard-codes 512M (docker-entrypoint.sh), and it does
                       # NOT derive from the container: measured on the pinned
                       # digest at 3g, 4g, 6g and 20g caps, Neo4j reads the
                       # cgroup correctly and reports 512.00MiB every time.
                       #
                       # So our headline graph comparator ran a 512 MiB store
                       # cache at every tier, micro through SF10, in a table
                       # ArcadeDB wins on 1-hop by 9.5x. Same pathology as
                       # PostgreSQL's 128 MB shared_buffers, which we answered
                       # with the postgres_tuned arm; this one had no arm and
                       # no disclosure.
                       #
                       # {pagecache} is the container's memory minus the heap,
                       # minus a fixed reserve for the JVM's non-heap needs.
                       "-e", "NEO4J_server_memory_pagecache_size={pagecache}"],
        "server_port": 7687,
        "ready_regex": r"Started\.",
    },
    "ladybug_graph": {
        # embedded engine, runs in-process in the client image
        "topology": "embedded",
        "image": "dbbench:client",
    },
    # ---- E2 hybrid-ACID lane ----
    "arcadedb_e2": {
        "topology": "embedded",
        "image": "dbbench:arcadedb",
    },
    "surrealdb_e2": {
        "topology": "embedded",
        "image": "dbbench:client",
    },
    "composed_qdrant_neo4j": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "neo4j@sha256:4bae36aff76271e27fd6a6ed0835413f86a284cd179cfb1cb7d188f5f7533aca",
        "server_env": ["-e", "NEO4J_AUTH=neo4j/dbbenchpass",
                       "-e", "NEO4J_server_memory_heap_initial__size={heap}",
                       "-e", "NEO4J_server_memory_heap_max__size={heap}",
                       # PAGE CACHE, which for Neo4j is the load-bearing
                       # setting and was never set. The image entrypoint
                       # hard-codes 512M (docker-entrypoint.sh), and it does
                       # NOT derive from the container: measured on the pinned
                       # digest at 3g, 4g, 6g and 20g caps, Neo4j reads the
                       # cgroup correctly and reports 512.00MiB every time.
                       #
                       # So our headline graph comparator ran a 512 MiB store
                       # cache at every tier, micro through SF10, in a table
                       # ArcadeDB wins on 1-hop by 9.5x. Same pathology as
                       # PostgreSQL's 128 MB shared_buffers, which we answered
                       # with the postgres_tuned arm; this one had no arm and
                       # no disclosure.
                       #
                       # {pagecache} is the container's memory minus the heap,
                       # minus a fixed reserve for the JVM's non-heap needs.
                       "-e", "NEO4J_server_memory_pagecache_size={pagecache}"],
        "server_port": 7687,
        "ready_regex": r"Started\.",
    },
    "arcadedb_sparse_embedded": {
        "topology": "embedded",
        "image": "dbbench:arcadedb",
    },
    "arcadedb_sparse_embedded_fp32": {
        "topology": "embedded",
        "image": "dbbench:arcadedb",
    },
    "arcadedb_sparse_embedded_nocompact": {
        "topology": "embedded",
        "image": "dbbench:arcadedb",
    },
    "arcadedb_sparse_server": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "arcadedata/arcadedb:26.8.1@sha256:49036720b1678b9c7a6dbf22fc34a812c8d7bed15508c22cbb02c0dddc0ca16a",  # RELEASED 26.8.1, matches the 26.8.1 wheel (F5: one engine line per table)
        # Heap parity with the embedded deployment (protocol: same JVM-heap
        # policy per scale tier) — the image's own default is -Xmx2G, which
        # starved the server vs embedded's per-scale heap. Setting JAVA_OPTS
        # also drops the image's ZGC default: both deployments run the same
        # default GC (G1) so the embedded-vs-server axis isolates transport,
        # not GC choice.
        "server_env": ["-e", "ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}",
                       "-e", "JAVA_OPTS=-Darcadedb.server.rootPassword=dbbenchpass "
                             "-Darcadedb.server.defaultDatabases=bench[root] "
                             "-Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000"],
        "server_port": 2480,
        "ready_regex": r"HTTP Server started",
    },
    "qdrant_sparse": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c",  # v1.18.2
        "server_port": 6333,
        "ready_regex": r"Qdrant (HTTP|gRPC) listening|Actix runtime found",
    },
    "milvus_sparse": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "milvusdb/milvus@sha256:0ea40276f8111f0183e72c8ee3144f3b9aafcd30571bd947de1ed0d22ee9dd56",
        "server_env": ["-e", "DEPLOY_MODE=STANDALONE",
                       "-e", "ETCD_USE_EMBED=true",
                       "-e", "ETCD_DATA_DIR=/var/lib/milvus/etcd",
                       "-e", "ETCD_CONFIG_PATH=/milvus/configs/embedEtcd.yaml",
                       "-e", "COMMON_STORAGETYPE=local"],
        "server_volumes": ["-v", f"{HERE}/docker-conf/embedEtcd.yaml:/milvus/configs/embedEtcd.yaml"],
        "server_cmd": ["milvus", "run", "standalone"],
        "server_port": 19530,
        "ready_regex": r"Proxy successfully started|successfully started",
    },
    "elasticsearch_sparse": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "docker.elastic.co/elasticsearch/elasticsearch@sha256:268f65f1b32ea367e49c9be2acab144011b8c66c462c890f6190707743199050",  # 9.4.1, matches the 9.4.1 client
        "server_env": ["-e", "discovery.type=single-node",
                       "-e", "xpack.security.enabled=false",
                       # F3. This was hardcoded "-Xms2g -Xmx4g", the only
                       # served backend not templated on {heap}, so
                       # Elasticsearch ran a 4g heap at EVERY tier while its
                       # comparators scaled 4g -> 8g -> 16g. At medium that is
                       # a quarter of the memory, and the rows still recorded
                       # heap=16g because the row stamps what was REQUESTED.
                       # An artifact claiming a heap the engine never had is
                       # worse than one that admits it does not know.
                       # It also broke the -Xms=-Xmx pinning the rest of this
                       # lane relies on (see l3_sparse.py:82), so ES alone grew
                       # its heap under load while everyone else committed up
                       # front. observe_server() is what surfaced it: it
                       # compares the container's real -Xmx against the request
                       # and now fails the cell instead of publishing it.
                       "-e", "ES_JAVA_OPTS=-Xms{heap} -Xmx{heap}"],
        "server_port": 9200,
        "ready_regex": r'"message":"started|current.health=\"GREEN\"',
    },
    # --- l3d dense (SIFT1M) ---
    "arcadedb_dense_embedded": {"topology": "embedded",
                                "image": "dbbench:arcadedb"},
    "arcadedb_dense_server": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "arcadedata/arcadedb:26.8.1@sha256:49036720b1678b9c7a6dbf22fc34a812c8d7bed15508c22cbb02c0dddc0ca16a",  # RELEASED 26.8.1, matches the 26.8.1 wheel (F5: one engine line per table)
        "server_env": ["-e", "ARCADEDB_OPTS_MEMORY=-Xms{heap} -Xmx{heap}",
                       "-e", "JAVA_OPTS=-Darcadedb.server.rootPassword=dbbenchpass "
                             "-Darcadedb.server.defaultDatabases=bench[root] "
                             "-Darcadedb.queryMaxHeapElementsAllowedPerOp=5000000"],
        "server_port": 2480,
        "ready_regex": r"HTTP Server started",
    },
    # PRECISION ARMS. Same topology and image as their fp32 siblings, because
    # the only variable is the index precision; anything else would make the
    # pair two configurations rather than an ablation.
    "arcadedb_dense_embedded_int8": {"topology": "embedded",
                                     "image": "dbbench:arcadedb"},
    "chroma_dense": {"topology": "embedded", "image": "dbbench:dense"},
    "lancedb_dense": {"topology": "embedded", "image": "dbbench:dense"},
    "sqlite_vec_dense": {"topology": "embedded", "image": "dbbench:dense"},
    "duckdb_vss_dense": {"topology": "embedded", "image": "dbbench:dense"},
    "qdrant_dense": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c",  # v1.18.2
        "server_port": 6333,
        "ready_regex": r"Qdrant (HTTP|gRPC) listening|Actix runtime found",
    },
    # The int8 arm of qdrant_dense: identical image digest, port and
    # readiness probe, because only the INDEX precision differs. Cloned
    # rather than referenced so a future digest bump cannot move one arm
    # of an ablation without the other.
    "qdrant_dense_int8": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c",  # v1.18.2
        "server_port": 6333,
        "ready_regex": r"Qdrant (HTTP|gRPC) listening|Actix runtime found",
    },
    "milvus_dense": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "milvusdb/milvus@sha256:0ea40276f8111f0183e72c8ee3144f3b9aafcd30571bd947de1ed0d22ee9dd56",
        "server_env": ["-e", "DEPLOY_MODE=STANDALONE",
                       "-e", "ETCD_USE_EMBED=true",
                       "-e", "ETCD_DATA_DIR=/var/lib/milvus/etcd",
                       "-e", "ETCD_CONFIG_PATH=/milvus/configs/embedEtcd.yaml",
                       "-e", "COMMON_STORAGETYPE=local"],
        "server_volumes": ["-v", f"{HERE}/docker-conf/embedEtcd.yaml:/milvus/configs/embedEtcd.yaml"],
        "server_cmd": ["milvus", "run", "standalone"],
        "server_port": 19530,
        "ready_regex": r"Proxy successfully started|successfully started",
    },
    # The int8 arm of milvus_dense: identical image digest, port and
    # readiness probe, because only the INDEX precision differs. Cloned
    # rather than referenced so a future digest bump cannot move one arm
    # of an ablation without the other.
    "milvus_dense_int8": {
        "topology": "client_server",
        "image": "dbbench:client",
        "server_image": "milvusdb/milvus@sha256:0ea40276f8111f0183e72c8ee3144f3b9aafcd30571bd947de1ed0d22ee9dd56",
        "server_env": ["-e", "DEPLOY_MODE=STANDALONE",
                       "-e", "ETCD_USE_EMBED=true",
                       "-e", "ETCD_DATA_DIR=/var/lib/milvus/etcd",
                       "-e", "ETCD_CONFIG_PATH=/milvus/configs/embedEtcd.yaml",
                       "-e", "COMMON_STORAGETYPE=local"],
        "server_volumes": ["-v", f"{HERE}/docker-conf/embedEtcd.yaml:/milvus/configs/embedEtcd.yaml"],
        "server_cmd": ["milvus", "run", "standalone"],
        "server_port": 19530,
        "ready_regex": r"Proxy successfully started|successfully started",
    },
}

# Which backends run on a JVM, and therefore have a heap worth recording and
# checking. Substring match against the backend name.
JVM_BACKENDS = ("arcadedb", "neo4j", "elasticsearch", "questdb")

LANES = {
    # lane -> (bench script, backends, workloads)
    "l1": ("l1_tabular.py",
           ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres",
            "postgres_tuned"],
           ["oltp", "olap"]),
    "l2": ("l2_graph.py",
           ["arcadedb_graph_embedded", "arcadedb_graph_server",
            "neo4j_graph", "ladybug_graph"],
           ["oltp", "olap"]),
    "l1tpc": ("l1_tpc.py",
              ["arcadedb_embedded", "arcadedb_server", "duckdb", "postgres",
               "postgres_tuned"],
              ["oltp", "olap"]),
    "e2": ("e2_hybrid.py",
           ["arcadedb_e2", "surrealdb_e2", "composed_qdrant_neo4j"],
           ["hybrid", "atomicity"]),
    "l3s": ("l3_sparse.py",
            ["arcadedb_sparse_embedded", "arcadedb_sparse_embedded_fp32",
             "arcadedb_sparse_embedded_nocompact", "arcadedb_sparse_server",
             "qdrant_sparse", "milvus_sparse", "elasticsearch_sparse"],
            ["search"]),
    "l3d": ("l3d_dense.py",
            ["arcadedb_dense_embedded", "arcadedb_dense_server", "chroma_dense", "lancedb_dense",
             "sqlite_vec_dense", "duckdb_vss_dense", "qdrant_dense",
             "milvus_dense",
             # int8 arms for every dense engine that ships a quantized index.
             # Chroma, DuckDB-VSS and sqlite-vec have none; LanceDB is int8
             # already (IVF_HNSW_SQ is its only HNSW offering).
             "arcadedb_dense_embedded_int8", "qdrant_dense_int8",
             "milvus_dense_int8"],
            ["search"]),
    # l4 timeseries: added as adapters land.
}


def _pagecache_for(server_mem_bytes, heap):
    """What is left for an off-heap page cache once the heap is taken out.

    Neo4j's own guidance is heap + page cache + about 1g of JVM overhead
    (metaspace, code cache, thread stacks, direct buffers) inside the
    container. Anything we do not hand it, its entrypoint pins at 512M
    regardless of container size, which is what made the graph comparison
    unfair rather than merely untuned.

    Floors at 512m so a small tier can never end up BELOW the image default:
    the point is to stop under-provisioning it, not to introduce a new way to
    do so.
    """
    # An explicit override exists for ONE purpose: re-running the starved
    # configuration on demand, to separate "we never disclosed cache state"
    # from "we starved the comparator". Unset, this returns the computed size
    # and behaviour is exactly as before.
    forced = os.environ.get("BENCH_NEO4J_PAGECACHE")
    if forced:
        return forced
    reserve = 1 << 30
    left = server_mem_bytes - mem_bytes(heap) - reserve
    gib = left / float(1 << 30)
    return f"{gib:.1f}g" if gib >= 0.5 else "512m"


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw).stdout.strip()


def cgroup_dir(cid):
    p = f"/sys/fs/cgroup/system.slice/docker-{cid}.scope"
    if os.path.isdir(p):
        return p
    return sh(["bash", "-c",
               f"find /sys/fs/cgroup -name '*{cid}*' -type d 2>/dev/null | head -1"]) or None


def read_int(path):
    try:
        return int(open(path).read().strip())
    except Exception:
        return None


def read_cpu_stat(cg):
    out = {}
    try:
        for line in open(os.path.join(cg, "cpu.stat")):
            parts = line.split()
            if len(parts) == 2 and parts[0] in ("usage_usec", "user_usec", "system_usec"):
                out[parts[0]] = int(parts[1])
    except Exception:
        pass
    return out


def read_io_stat(cg):
    """Bytes actually read from and written to disk by a container, summed
    over devices, from cgroup v2 io.stat.

    Pairs with the writable-layer size: that says how big the data ENDED UP,
    this says how much IO it took to get there. The gap between them is write
    amplification, which for an LSM engine is the interesting half and is a
    thing we assert about compaction without ever having measured it.

    Free to collect: two reads of one file per cell.
    """
    out = {"rbytes": 0, "wbytes": 0}
    try:
        for line in open(os.path.join(cg, "io.stat")):
            for tok in line.split()[1:]:
                k, _, v = tok.partition("=")
                if k in out:
                    out[k] += int(v)
    except (OSError, ValueError):
        return {}
    return out


def read_memory_stat(cg):
    """anon = anonymous working set (heaps/buffers); file = reclaimable page
    cache. anon is the honest memory metric; file is the confound to exclude."""
    out = {}
    try:
        for line in open(os.path.join(cg, "memory.stat")):
            parts = line.split()
            # shmem added 2026-08-14. anon+file answered "how much"; without
            # shmem we could not answer "where", and that is what made a
            # PostgreSQL cell unreadable: its buffer pool is POSIX shared
            # memory, which lands in shmem and is ALSO counted inside file, so
            # a reader with only these two cannot tell a page the engine
            # deliberately holds from one the kernel happens to be caching.
            if len(parts) == 2 and parts[0] in ("anon", "file", "shmem"):
                out[parts[0]] = int(parts[1])
    except Exception:
        pass
    return out


class CgroupSampler(threading.Thread):
    """Samples one container's cgroup: memory series, kernel peak, cpu totals.

    Memory is reported two ways. `peak`/series come from memory.current /
    memory.peak, which include reclaimable FILE page cache (a container that
    touches a lot of file data pegs near its cap; ES read 20.1+-0.0 GB this
    way, which is page cache, not engine need). `peak_anon` / `end_anon` come
    from memory.stat `anon` = the true anonymous working set (heaps, buffers),
    which is what the paper reports. `end_file` records the page cache at exit
    for transparency. Steady-state = the last sample (post-load serving state).
    """

    def __init__(self, cid):
        super().__init__(daemon=True)
        self.cid, self.stop_evt = cid, threading.Event()
        self.series, self.peak, self.cpu = [], 0, {}
        self.peak_anon = 0
        self.end_anon = None
        self.peak_shmem = 0
        self.end_shmem = None
        self.peak_file = 0
        self.io = {}
        self.end_file = None

    def run(self):
        cg, t0 = None, time.time()
        while not self.stop_evt.is_set():
            cg = cg or cgroup_dir(self.cid)
            if cg:
                cur = read_int(os.path.join(cg, "memory.current"))
                pk = read_int(os.path.join(cg, "memory.peak"))
                if cur is not None:
                    self.series.append((round(time.time() - t0, 3), cur))
                if pk is not None:
                    self.peak = max(self.peak, pk)
                stat = read_memory_stat(cg)
                if stat.get("anon") is not None:
                    self.peak_anon = max(self.peak_anon, stat["anon"])
                    self.end_anon = stat["anon"]
                if stat.get("shmem") is not None:
                    self.peak_shmem = max(self.peak_shmem, stat["shmem"])
                    self.end_shmem = stat["shmem"]
                if stat.get("file") is not None:
                    self.peak_file = max(self.peak_file, stat["file"])
                # io.stat counters are cumulative, so the LAST read is the
                # total for the cell; no max() needed and none wanted.
                io = read_io_stat(cg)
                if io:
                    self.io = io
                if stat.get("file") is not None:
                    self.end_file = stat["file"]
                cpu = read_cpu_stat(cg)
                if cpu:
                    self.cpu = cpu
            time.sleep(SAMPLE_INTERVAL)

    def finish(self):
        self.stop_evt.set()
        self.join(timeout=5)


def mem_bytes(spec):
    m = re.fullmatch(r"(\d+)([gm])", spec)
    n, u = int(m.group(1)), m.group(2)
    return n * (1024 ** 3 if u == "g" else 1024 ** 2)


def image_digest(image):
    return sh(["docker", "inspect", "--format", "{{.Id}}", image])


def wait_ready(cid, regex, timeout_s=120):
    pat, t0 = re.compile(regex), time.time()
    while time.time() - t0 < timeout_s:
        logs = subprocess.run(["docker", "logs", cid], capture_output=True, text=True)
        if pat.search(logs.stdout + logs.stderr):
            return True
        time.sleep(1.0)
    return False


def docker_rm(cid):
    """Remove a container AND the anonymous volumes it created.

    The -v is not optional. Without it, every container built from an image
    that declares VOLUME (postgres, neo4j, arcadedb, elasticsearch) leaves its
    anonymous volume behind on removal, and nothing ever collects them.
    Measured on the bench host 2026-08-15: 2891 orphaned volumes holding
    891.3 GB, every byte reclaimable, accumulated across every campaign this
    project has ever run.

    That is also why disk kept looking fine while quietly not being: docker
    system df reports volumes separately from images, and nobody was reading
    that line.
    """
    subprocess.run(["docker", "rm", "-fv", cid], capture_output=True)


def _docker(cmd_args):
    """Run a docker command, returning (stdout, stderr, rc) rather than just
    stdout. The disk instrument needs the failure reason, not a silent None."""
    r = subprocess.run(["docker"] + cmd_args, capture_output=True, text=True)
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def container_disk(cid, settle_s=3.0, tries=3):
    """On-disk bytes a container is responsible for, and whether it settled.

    ON-DISK SIZE was in the campaign plan from the start, beside latency,
    recall and peak RSS, and no lane ever recorded it. Index size is half of
    what makes an index choice a tradeoff, and it is the axis where sparse
    int8 quantization should show a win the paper gives it no credit for: we
    print the recall quantization COSTS and never measured the bytes it SAVES.

    WHERE THE BYTES ARE. Two places, and an engine may use either.

      - The container's writable layer, which `docker inspect --size` reports
        as SizeRw. That is where an embedded engine writing to /tmp puts data.
      - A VOLUME. The first version of this measured only SizeRw and was wrong
        for exactly the engines that matter. Verified directly: a PostgreSQL
        container loaded with 2M rows reported SizeRw = 20480 bytes, unchanged
        from empty, while the data sat in its volume at 1017.5 MiB. ArcadeDB,
        Neo4j and PostgreSQL all declare volumes.

    Volume destinations are read FROM THE DAEMON, not from a per-backend path
    table. A table of guessed paths is eight assertions that fail silently;
    docker inspect already knows where each volume is mounted. BIND mounts are
    excluded deliberately: /data is the read-only corpus and /work is the
    repo, and neither is the engine's storage.

    SETTLING, which is the part that makes this hard. On-disk size is not
    fixed at the moment a database closes. It drifts:
      - writeback: du counts ALLOCATED blocks and ext4 delays allocation, so
        an immediate reading under-counts whatever is still dirty. Hence sync.
      - background compaction: every LSM engine here does it, ours included,
        and obsolete segments live until a merge retires them. Drifts DOWN,
        sometimes minutes later.
      - deferred cleanup, and WAL truncation after checkpoint.

    So this samples repeatedly and requires two consecutive readings to agree
    within 1%. If they never agree it returns settled=False WITH both
    readings, because a number that silently depended on when we looked is the
    same class of defect as the memory column withdrawn this week.

    Returns a dict, never a bare number, so a caller cannot mistake an
    unsettled or failed reading for a measured one.
    """
    out = {"disk_mb": None, "disk_rw_mb": None, "disk_vol_mb": None,
           "disk_settled": None, "disk_note": None}

    def sizerw():
        so, se, rc = _docker(["inspect", "--size", "-f", "{{.SizeRw}}", cid])
        if rc != 0:
            return None, se[:120]
        try:
            return int(so) / 1048576.0, None
        except ValueError:
            return None, f"unparseable SizeRw {so!r}"

    running, _, _ = _docker(["inspect", "-f", "{{.State.Running}}", cid])
    vol_dests = []
    if running == "true":
        so, _, rc = _docker(["inspect", "-f",
                             '{{range .Mounts}}{{if eq .Type "volume"}}{{.Destination}}'
                             + chr(10) + '{{end}}{{end}}', cid])
        if rc == 0:
            vol_dests = [d for d in so.splitlines() if d.strip()]

    def volumes_mb():
        if not vol_dests:
            return 0.0, None
        total = 0.0
        for d in vol_dests:
            so, se, rc = _docker(["exec", cid, "du", "-sb", d])
            if rc != 0:
                return None, f"du {d}: {se[:80]}"
            try:
                total += int(so.split()[0]) / 1048576.0
            except (ValueError, IndexError):
                return None, f"du {d}: unparseable {so[:60]!r}"
        return total, None

    def sample():
        rw, e1 = sizerw()
        vol, e2 = volumes_mb()
        if rw is None or vol is None:
            return None, None, None, (e1 or e2)
        return rw + vol, rw, vol, None

    # Flush before the first reading, or it under-counts whatever is dirty.
    if running == "true":
        _docker(["exec", cid, "sync"])

    prev, note = None, None
    for i in range(tries):
        total, rw, vol, err = sample()
        if total is None:
            out["disk_note"] = f"sample failed: {err}"
            return out
        out["disk_mb"], out["disk_rw_mb"], out["disk_vol_mb"] = (
            round(total, 1), round(rw, 1), round(vol, 1))
        if prev is not None:
            spread = abs(total - prev) / max(total, prev, 1e-9)
            if spread <= 0.01:
                out["disk_settled"] = True
                return out
            note = f"still moving after {i + 1} samples: {prev:.1f} -> {total:.1f} MiB"
        prev = total
        if i < tries - 1:
            time.sleep(settle_s)
    out["disk_settled"] = False
    out["disk_note"] = note or "did not converge"
    return out


def observe_server(cid):
    """The server container's real cpuset, cap, heap and image, from docker.

    Returns server_-prefixed keys so a row carries both what the cell asked
    for and what the engine got, and the two can be compared afterwards
    instead of assumed equal. Anything unreadable comes back absent rather
    than guessed.

    The heap is parsed out of the container's Env because that is where it was
    actually set (ARCADEDB_OPTS_MEMORY, or JAVA_OPTS for images configured that
    way); the LAST -Xmx wins, which is what the JVM itself does. Non-JVM
    servers have none and simply omit the key.
    """
    out = {}
    for key, fmt in (("server_cpuset", "{{.HostConfig.CpusetCpus}}"),
                     ("server_image", "{{.Image}}"),
                     ("server_image_ref", "{{.Config.Image}}")):
        v = sh(["docker", "inspect", "-f", fmt, cid])
        if v and v != "<no value>":
            out[key] = v
    mem = sh(["docker", "inspect", "-f", "{{.HostConfig.Memory}}", cid])
    if mem.isdigit() and int(mem):
        out["server_mem_cap"] = f"{int(mem) // (1 << 30)}g"
    env = sh(["docker", "inspect", "-f", "{{json .Config.Env}}", cid])
    try:
        envs = " ".join(json.loads(env))
    except Exception:
        envs = ""
    # TWO SPELLINGS, because -Xmx is not how every JVM image takes its heap.
    # This used to match -Xmx only, so ArcadeDB and Elasticsearch (ES_JAVA_OPTS
    # carries -Xmx) had a witness and NEO4J DID NOT: it takes
    # NEO4J_server_memory_heap_max__size=12g, which the old pattern could not
    # see. Neo4j is the comparator in the one table we win on traversal, and
    # the missing witness is exactly the failure mode that let Elasticsearch
    # run a hardcoded 4g for three tiers while its row claimed 16g.
    #
    # Found by the campaign monitor on live rows, independently of the heap
    # audit that predicted it.
    hits = re.findall(r"-Xmx(\d+)([gGmM])", envs)
    if not hits:
        hits = re.findall(r"heap[_.]max_?_?size=(\d+)([gGmM])", envs, re.I)
    if hits:
        val, unit = hits[-1]
        out["server_heap"] = (f"{val}g" if unit in "gG"
                              else f"{int(val) // 1024}g")
    # The other half of Neo4j's memory contract, and the setting the audit
    # found pinned at the image default of 512M on every tier. Recorded so a
    # future reader can see it was sized rather than inherited.
    pc = re.findall(r"pagecache[_.]size=([\d.]+)([gGmM])", envs, re.I)
    if pc:
        out["server_pagecache"] = f"{pc[-1][0]}{pc[-1][1].lower()}"
    return out


def run_cell(job, rep, scale, cpuset, tier, net_name):
    """Run one cell (backend x workload x scale, one repeat). Returns row dict."""
    be = BACKENDS[job["backend"]]
    # scale in run_id: out-file names must never collide across campaigns
    # (a stale same-name out file once resurfaced a previous campaign's
    # metrics into a killed cell's row)
    run_id = f"{job['run_id']}_{scale}_r{rep}"
    stale = os.path.join(RAW, f"{run_id}.json")
    if os.path.exists(stale):
        os.unlink(stale)  # belt-and-braces vs stale out-file reads
    total_mem = mem_bytes(MEM_BY_SCALE[scale])
    heap = HEAP_BY_SCALE[scale]
    row = {"run_id": run_id, "lane": job["lane"], "backend": job["backend"],
           "workload": job["workload"], "scale": scale, "rep": rep, "tier": tier,
           "cpuset": cpuset, "topology": be["topology"],
           # HEAP ONLY WHERE THERE IS A JVM. This used to be recorded for
           # every backend, so a Rust or C engine's row carried ArcadeDB's
           # tier heap. fairness_check's heap axis is built on the premise
           # that non-JVM engines report heap=None, so the premise was false
           # and its "engines that have a heap" carve-out never fired.
           #
           # Deliberately keyed on the backend NAME rather than a flag, so
           # adding a JVM comparator without listing it here fails loudly as a
           # missing heap rather than quietly as an unchecked one.
           **({"heap": heap} if any(t in job["backend"] for t in JVM_BACKENDS)
              else {}),
           "mem_cap": MEM_BY_SCALE[scale],
           "ts_utc": datetime.now(timezone.utc).isoformat()}

    # cli_cid initialised HERE, not at its assignment 90 lines down: the
    # finally block reads it, and a server that fails to start returns
    # before the client is ever created. Leaving it unbound turns a
    # recorded server_not_ready row into a NameError that loses the cell.
    server_cid, cli_cid, samplers = None, None, []
    try:
        if be["topology"] == "client_server":
            if SERVER_MEM_FRACTION:
                server_mem = int(total_mem * SERVER_MEM_FRACTION)
                client_mem = total_mem - server_mem
                row["mem_split"] = f"{SERVER_MEM_FRACTION:.2f}"
            else:
                # Full cap to the engine, so it sees exactly what an embedded
                # engine of the same tier sees. The driver is additional.
                server_mem = total_mem
                client_mem = mem_bytes(CLIENT_MEM)
                row["mem_split"] = "full+client"
                row["client_mem_cap"] = CLIENT_MEM
            row["server_mem_cap_g"] = round(server_mem / 2**30, 1)
            # Buffer-pool sizing derived from this container's own budget, on
            # PostgreSQL's own guidance (a quarter resident, three quarters
            # assumed cached). Only the tuned arm uses these; every other
            # backend's server_cmd has no placeholders and formats to itself.
            srv_gb = max(1, server_mem // (1 << 30))
            server_cmd = [c.format(sb=f"{max(1, srv_gb // 4)}GB",
                                   ecs=f"{max(1, srv_gb * 3 // 4)}GB")
                          for c in be.get("server_cmd", [])]
            # What it was actually launched with, so a reader of the row does
            # not have to re-derive it from the scale.
            if server_cmd:
                row["server_cmd"] = " ".join(server_cmd)
            server_cid = sh(["docker", "run", "-d", "--network", net_name,
                             "--label", "dbbench=1",
                             "--name", f"srv-{run_id}",
                             "--cpuset-cpus", cpuset,
                             "--memory", str(server_mem), "--memory-swap", str(server_mem)]
                            + [s.format(heap=heap, pagecache=_pagecache_for(server_mem, heap))
                               for s in be.get("server_env", [])]
                            + be.get("server_volumes", [])
                            + [be["server_image"]]
                            + server_cmd)
            if len(server_cid) < 12 or not wait_ready(server_cid, be["ready_regex"]):
                row["error"] = "server_not_ready"
                return row
            # WHAT THE ENGINE ACTUALLY GOT, not what this row asked for.
            # `heap` and `mem_cap` above describe the CELL's budget, and
            # bench_common.run_conditions inside the driver reads the CLIENT
            # container's cgroup, so for a served cell neither describes the
            # engine. That is why the dense server row records heap=None and
            # mem_cap=9g (the client's quarter of 36g), and why F3 could not
            # verify its envelope and F7 could not verify its degree.
            #
            # Read from the daemon rather than restated from our own
            # variables: a value we assert cannot catch the case where the
            # container was created with something else, which is the failure
            # mode behind "server:latest" and the dev22-stamped dev20 run.
            row.update(observe_server(server_cid))
            if row.get("server_heap") and row["server_heap"] != heap:
                row["error"] = (f"server heap {row['server_heap']} != requested "
                                f"{heap}; the cell is not the one we specified")
                return row
            # Before any of our data exists: the engine's own startup cost.
            # No settle loop here, the engine is idle and just booted.
            row["server_disk_baseline_mb"] = container_disk(
                server_cid, tries=1)["disk_mb"]
            s_srv = CgroupSampler(server_cid)
            s_srv.start()
            samplers.append(("server", s_srv))
            client_caps = ["--memory", str(client_mem), "--memory-swap", str(client_mem)]
            bench_env = ["-e", f"BENCH_SERVER_HOST=srv-{run_id}",
                         "-e", f"BENCH_SERVER_PORT={be['server_port']}"]
        else:
            client_caps = ["--memory", str(total_mem), "--memory-swap", str(total_mem)]
            bench_env = []

        # forward data-source selection into the container (sparse + graph + dense)
        # This list is an ALLOWLIST, so a BENCH_* the host exports and this
        # tuple omits is silently dropped at the container boundary and the
        # lane runs its default. BENCH_GAV was missing: exporting BENCH_GAV=0
        # to ablate the Graph Analytical View would have built the view anyway
        # and written rows labelled as the ablation, rc=0, indistinguishable
        # from a real one. Same shape as the BENCH_SPARSE_SOURCE omission that
        # cost this campaign 94 rows on the wrong corpus.
        #
        # "0" is a non-empty string and therefore truthy below, so the value
        # that turns the view OFF does survive the `if`.
        for _k in ("BENCH_SPARSE_SOURCE", "BENCH_SPARSE_DATA",
                   "BENCH_GRAPH_SOURCE", "BENCH_GRAPH_DATA",
                   "BENCH_DENSE_DATA", "BENCH_DENSE_M",
                   "BENCH_TPC_DATA", "BENCH_TPC_SF", "BENCH_GAV",
                   "BENCH_NEO4J_PAGECACHE"):
            if os.environ.get(_k):
                bench_env += ["-e", f"{_k}={os.environ[_k]}"]

        # TELL THE CONTAINER WHAT IT IS RUNNING. Only this process knows the
        # backend's image and pinned server digest; inside the container that
        # is unknowable. Without it a driver cannot record its own provenance
        # even in principle, which is why every overlay artifact carries no
        # image while the paper claims served comparators are pinned by digest.
        # run_conditions() in bench_common.py reads these two.
        bench_env += ["-e", f"BENCH_IMAGE={be['image']}"]
        if be.get("server_image"):
            bench_env += ["-e", f"BENCH_SERVER_IMAGE={be['server_image']}"]

        cmd = (["docker", "run", "-d", "--network", net_name,
                "--label", "dbbench=1",
                "--name", f"cli-{run_id}", "--cpuset-cpus", cpuset]
               + client_caps + bench_env
               # ARCADEDB_HEAP ONLY WHERE IT MEANS SOMETHING. It used to be
               # exported into every client container, so a Rust or C engine's
               # row carried a JVM heap it never had. fairness_check's whole
               # heap design rests on non-JVM engines reporting heap=None, and
               # they were reporting ArcadeDB's tier heap instead, so its
               # "engines that have a heap" carve-out never fired and the JVM
               # count it prints was not a count of anything.
               + (["-e", f"ARCADEDB_HEAP={heap}"]
                  if "arcadedb" in job["backend"] else [])
               + ["-e", f"RUN_LABEL={run_id}",
                  "-v", f"{HERE}:/work", "-w", "/work", "-v", f"{DATA}:/data:ro",
                  be["image"], "python", job["script"],
                  "--backend", job["backend"], "--workload", job["workload"],
                  "--scale", scale, "--out", f"/work/results/raw/{run_id}.json"])
        cli_cid = sh(cmd)
        if len(cli_cid) < 12:
            row["error"] = "client_failed_to_start"
            return row
        row["client_disk_baseline_mb"] = container_disk(cli_cid, tries=1)["disk_mb"]
        s_cli = CgroupSampler(cli_cid)
        s_cli.start()
        samplers.append(("client", s_cli))

        timeout_s = TIMEOUT_BY_SCALE[scale]
        try:
            wait = subprocess.run(["docker", "wait", cli_cid], capture_output=True,
                                  text=True, timeout=timeout_s)
            rc = int(wait.stdout.strip() or "1")
        except subprocess.TimeoutExpired:
            rc = -1
            row["error"] = f"timeout_after_{timeout_s}s"
            # phase-at-timeout evidence (cypherglot audit standard): the bench's
            # last progress lines identify WHERE the budget expired (ingest /
            # index build / warmup / query iter) without log archaeology later.
            tail = subprocess.run(["docker", "logs", "--tail", "8", cli_cid],
                                  capture_output=True, text=True)
            last = [l.strip() for l in (tail.stdout + tail.stderr).splitlines()
                    if l.strip()][-3:]
            row["timeout_phase_hint"] = " | ".join(last)[-400:]
        logs = subprocess.run(["docker", "logs", cli_cid], capture_output=True, text=True)
        # Interrogate the container BEFORE removing it. A cgroup OOM kill leaves
        # NO stdout and NO stderr, so the log is empty and docker's own State is
        # the only witness. On 2026-08-05 thirty consecutive TPC-H SF10 cells
        # were OOM-killed, each got error="" from the empty log, an empty string
        # printed as a blank status, and the lane exited 0. A green run with
        # zero results is the worst failure mode this harness has.
        insp = subprocess.run(
            ["docker", "inspect", "-f",
             "{{.State.OOMKilled}} {{.State.ExitCode}}", cli_cid],
            capture_output=True, text=True)
        oom, exit_code = "false", str(rc)
        _parts = insp.stdout.split()
        if len(_parts) == 2:
            oom, exit_code = _parts
        # DISK BEFORE REMOVAL. This is the only moment the client's writable
        # layer still exists: docker_rm below deletes it, and the finally
        # block runs afterwards. Measuring there returned "no such object" for
        # every embedded cell, which the old instrument recorded as a bare
        # None and this one recorded as a reason.
        #
        # The container has EXITED but not been removed, which is fine:
        # inspect --size works on a stopped container (verified), and an
        # embedded engine writes to /tmp, which IS the writable layer. Its
        # only mounts are binds we own, so there are no volumes to miss.
        _cd = container_disk(cli_cid, tries=1)
        row["client_disk_mb"] = _cd["disk_mb"]
        if _cd["disk_note"]:
            row["client_disk_note"] = _cd["disk_note"]
        docker_rm(cli_cid)
        row["rc"] = rc
        row["oom_killed"] = (oom == "true")
        if rc != 0 and "error" not in row:
            detail = (logs.stderr or logs.stdout)[-800:].strip()
            if not detail:
                detail = f"container exited {exit_code} with no output"
                detail += (" (cgroup OOM kill: raise the envelope or bound the "
                           "harness's peak memory)" if oom == "true"
                           else " (killed, or died before writing anything)")
            row["error"] = detail

        out_path = os.path.join(RAW, f"{run_id}.json")
        # merge bench output ONLY on clean exit: a stale or partial out file
        # must never masquerade as results for a failed/killed cell
        if rc == 0 and os.path.exists(out_path):
            row.update(json.load(open(out_path)))
    finally:
        mib = lambda b: round((b or 0) / 2**20, 1)
        # Disk BEFORE the samplers are torn down and the containers removed:
        # the writable layer disappears with the container, so a measurement
        # taken after cleanup is not late, it is impossible.
        # The SERVER is still running here, which is what makes its volumes
        # measurable at all: docker exec needs a live container, and the
        # engines that keep data in a volume are exactly the ones SizeRw
        # cannot see. The settle loop runs on this side only, since this is
        # where compaction and writeback are still in flight.
        if server_cid:
            d = container_disk(server_cid)
            row["server_disk_mb"] = d["disk_mb"]
            row["server_disk_rw_mb"] = d["disk_rw_mb"]
            row["server_disk_vol_mb"] = d["disk_vol_mb"]
            row["server_disk_settled"] = d["disk_settled"]
            if d["disk_note"]:
                row["server_disk_note"] = d["disk_note"]
        # No client measurement here: it is taken above, just before
        # docker_rm, because this block runs after the container is gone.
        _d = [row.get(k) for k in ("server_disk_mb", "client_disk_mb")
              if row.get(k) is not None]
        _b = [row.get(k) for k in ("server_disk_baseline_mb", "client_disk_baseline_mb")
              if row.get(k) is not None]
        if _d:
            row["disk_mb_sum"] = round(sum(_d), 1)
            # What the WORKLOAD wrote, with the engine's startup footprint
            # (initdb, empty catalogs, logs) taken off. This is the number a
            # storage comparison wants; the raw ones stay beside it so the
            # subtraction is visible rather than baked in.
            row["disk_data_mb"] = round(sum(_d) - sum(_b), 1) if _b else None

        for name, s in samplers:
            s.finish()
            row[f"{name}_peak_mib"] = mib(s.peak)          # incl. page cache
            row[f"{name}_peak_anon_mib"] = mib(s.peak_anon)  # working set
            row[f"{name}_end_anon_mib"] = mib(s.end_anon)    # steady-state
            row[f"{name}_peak_shmem_mib"] = mib(s.peak_shmem)  # deliberate: buffer pools
            row[f"{name}_peak_file_mib"] = mib(s.peak_file)    # incidental: kernel cache
            row[f"{name}_io_read_mib"] = mib(s.io.get("rbytes"))
            row[f"{name}_io_write_mib"] = mib(s.io.get("wbytes"))
            row[f"{name}_end_file_mib"] = mib(s.end_file)    # page cache at exit
            row[f"{name}_cpu_usec"] = s.cpu.get("usage_usec")
        if len(samplers) == 2:
            row["peak_mib_sum"] = mib(sum(s.peak for _, s in samplers))
            row["peak_anon_mib_sum"] = mib(sum(s.peak_anon for _, s in samplers))
            row["peak_shmem_mib_sum"] = mib(sum(s.peak_shmem for _, s in samplers))
            # anon + shmem = memory the engines chose to hold, which is the
            # cross-architecture comparable an anon-only column is not.
            row["peak_owned_mib_sum"] = mib(sum(s.peak_anon + s.peak_shmem
                                                for _, s in samplers))
            row["io_write_mib_sum"] = mib(sum((s.io.get("wbytes") or 0)
                                              for _, s in samplers))
            row["io_read_mib_sum"] = mib(sum((s.io.get("rbytes") or 0)
                                             for _, s in samplers))
            row["end_anon_mib_sum"] = mib(sum((s.end_anon or 0) for _, s in samplers))
            row["cpu_usec_sum"] = sum((s.cpu.get("usage_usec") or 0) for _, s in samplers)
        elif samplers:
            row["peak_mib_sum"] = row.get("client_peak_mib")
            row["peak_anon_mib_sum"] = row.get("client_peak_anon_mib")
            row["peak_shmem_mib_sum"] = row.get("client_peak_shmem_mib")
            row["peak_owned_mib_sum"] = mib(samplers[0][1].peak_anon
                                            + samplers[0][1].peak_shmem)
            row["io_write_mib_sum"] = mib(samplers[0][1].io.get("wbytes"))
            row["io_read_mib_sum"] = mib(samplers[0][1].io.get("rbytes"))
            row["end_anon_mib_sum"] = row.get("client_end_anon_mib")
            row["cpu_usec_sum"] = row.get("client_cpu_usec")
        if server_cid:
            docker_rm(server_cid)
    return row


def acquire_host_lock():
    """Enforce one-runner-per-host. Returns the held lock file object.

    sweep_orphans() force-removes every dbbench container, so a second
    runner would destroy a live campaign's in-flight cells (this happened
    2026-07-10: a micro smoke wiped an L1 medium cell mid-run). The lock is
    advisory but process-wide; it dies with the process, so a crashed runner
    leaves no stale lock.
    """
    lock_path = os.path.join(RESULTS, ".runner.lock")
    os.makedirs(RESULTS, exist_ok=True)
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(
            f"another runner already holds {lock_path} on this host. "
            "The protocol allows exactly one runner per bench host: a second "
            "one would sweep the first's containers. Wait for it, or kill it."
        )
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    return fh


def sweep_orphans():
    """Reap containers left by a previous crashed/killed runner. Only safe to
    call while holding the host lock (see acquire_host_lock)."""
    ids = sh(["docker", "ps", "-aq", "--filter", "label=dbbench=1"]).split()
    if ids:
        print(f"sweeping {len(ids)} orphaned bench container(s): "
              + sh(["docker", "ps", "-a", "--filter", "label=dbbench=1",
                    "--format", "{{.Names}}"]).replace("\n", " "))
        subprocess.run(["docker", "rm", "-f"] + ids, capture_output=True)


def split_cpuset(cpuset, n):
    """Split a 'a-b' cpuset into n disjoint contiguous shards ('a-m', ...)."""
    lo, hi = (int(x) for x in cpuset.split("-"))
    cpus = list(range(lo, hi + 1))
    if n > len(cpus):
        raise ValueError(f"{n} workers > {len(cpus)} cpus in {cpuset}")
    size = len(cpus) // n
    shards = []
    for w in range(n):
        chunk = cpus[w * size:(w + 1) * size] if w < n - 1 else cpus[(n - 1) * size:]
        shards.append(f"{chunk[0]}-{chunk[-1]}")
    return shards


def build_jobs(lanes, workloads_arg):
    """Jobs for these lanes, optionally narrowed to some workloads.

    THE ARGUMENT USED TO BE IGNORED. The parameter was spelled
    `_workloads_arg` and the loop iterated the LANE's workload list instead, so
    `--workloads olap` silently ran oltp as well. A flag that parses, is passed
    down, and does nothing is worse than no flag: the caller reads the command
    line back and believes it.

    The reason it was ignored is real, though, and the fix has to respect it.
    The default was "oltp,olap", which are l1/l1tpc's workloads; l3s uses
    "search", e2 uses "hybrid"/"atomicity". Filtering on that default would
    have emptied every vector and cross-model lane. So the default is now
    EMPTY, meaning "whatever the lane defines", and filtering happens only
    when the caller names workloads explicitly. Every existing invocation
    keeps its exact behaviour.
    """
    want = {w.strip() for w in workloads_arg if w and w.strip()}
    jobs = []
    for lane in lanes:
        script, backends, workloads = LANES[lane]
        for be in backends:
            for wl in workloads:
                if want and wl not in want:
                    continue
                jobs.append({"lane": lane, "backend": be, "workload": wl,
                             "script": script,
                             "run_id": f"{lane}_{be}_{wl}"})
    if want:
        missing = want - {j["workload"] for j in jobs}
        if missing:
            sys.exit(f"--workloads named {sorted(missing)}, which no selected "
                     f"lane defines. Lanes {lanes} offer "
                     f"{sorted({w for l in lanes for w in LANES[l][2]})}.")
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", default="l1")
    ap.add_argument("--backends", default="",
                    help="comma list to restrict backends (default: all in lane)")
    ap.add_argument("--workloads", default="",
                    help="comma list; empty (default) runs every workload the "
                         "lane defines, which is the only safe default since "
                         "lanes disagree on workload names")
    ap.add_argument("--scale", default="tiny", choices=list(MEM_BY_SCALE))
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--only-reps", default="",
                    help="comma-separated rep numbers to run (e.g. '5' or '2,4'); "
                         "empty = all 1..reps")
    ap.add_argument("--tier", default="paper", choices=["paper", "sweep"])
    ap.add_argument("--workers", type=int, default=0,
                    help="parallel workers on disjoint cpuset shards "
                         "(sweep tier only; 0 = 1 for paper, 2 for sweep)")
    ap.add_argument("--timeout", type=int, default=0,
                    help="per-cell timeout override in seconds (0 = scale default)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--results-file", default="runs.jsonl",
                    help="where rows are appended, relative to results/. Use a "
                         "scratch file for smoke runs: the canonical rule takes "
                         "the LATEST row per (lane, scale, workload, backend, "
                         "rep), so an N=1 smoke at a paper scale silently "
                         "supersedes rep 1 of a finished cell and the table "
                         "then prints one smoke row beside four real ones.")
    args = ap.parse_args()
    if os.sep in args.results_file or args.results_file.startswith("."):
        ap.error("--results-file is a bare filename under results/")

    if args.timeout:
        for k in TIMEOUT_BY_SCALE:
            TIMEOUT_BY_SCALE[k] = args.timeout

    workers = args.workers or (1 if args.tier == "paper" else 2)
    if args.tier == "paper" and workers != 1:
        ap.error("paper tier is strictly serial: one cell at a time, full cpuset")
    if workers > 1:
        host_ram = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        need = workers * mem_bytes(MEM_BY_SCALE[args.scale])
        if need > host_ram * 0.85:
            ap.error(f"{workers} workers x {MEM_BY_SCALE[args.scale]} = "
                     f"{need/2**30:.0f}g exceeds 85% of host RAM "
                     f"({host_ram/2**30:.0f}g) — this scale runs serially")
    shards = split_cpuset(CPUSET, workers)

    lanes = args.lanes.split(",")
    workloads = args.workloads.split(",")
    os.makedirs(RAW, exist_ok=True)

    # one runner per bench host; must hold before sweeping containers
    _host_lock = acquire_host_lock()  # noqa: F841 (held for process lifetime)

    net_name = "dbbench"
    subprocess.run(["docker", "network", "create", net_name], capture_output=True)
    sweep_orphans()

    jobs = build_jobs(lanes, workloads)
    if args.backends:
        keep = set(args.backends.split(","))
        jobs = [j for j in jobs if j["backend"] in keep]
    only = {int(x) for x in args.only_reps.split(",") if x.strip()}
    cells = [(j, r) for j in jobs for r in range(1, args.reps + 1)
             if not only or r in only]
    random.Random(args.seed).shuffle(cells)  # shuffled order even in serial tier

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {"ts": ts, "tier": args.tier, "scale": args.scale, "cpuset": CPUSET,
                "workers": workers, "shards": shards,
                "reps": args.reps, "seed": args.seed,
                "mem": MEM_BY_SCALE[args.scale], "heap": HEAP_BY_SCALE[args.scale],
                "server_mem_fraction": SERVER_MEM_FRACTION,
                "images": {}}
    for j in jobs:
        be = BACKENDS[j["backend"]]
        for img in filter(None, [be.get("image"), be.get("server_image")]):
            manifest["images"].setdefault(img, image_digest(img))
    json.dump(manifest, open(os.path.join(RESULTS, f"manifest-{ts}.json"), "w"), indent=2)

    rows = []
    jsonl = open(os.path.join(RESULTS, args.results_file), "a")
    total = len(cells)
    print(f"{total} cell-runs (tier={args.tier}, scale={args.scale}, "
          f"workers={workers}, shards={shards})")

    pending = list(cells)
    active_backends = set()
    cv = threading.Condition()
    done = [0]

    def worker(shard):
        while True:
            with cv:
                idx = next((i for i, (j, _) in enumerate(pending)
                            if j["backend"] not in active_backends), None)
                if idx is None:
                    if not pending:
                        return
                    cv.wait(5)  # all queued backends busy elsewhere; re-check
                    continue
                job, rep = pending.pop(idx)
                active_backends.add(job["backend"])
            t0 = time.time()
            try:
                row = run_cell(job, rep, args.scale, shard, args.tier, net_name)
            finally:
                with cv:
                    active_backends.discard(job["backend"])
                    cv.notify_all()
            row["manifest"] = ts
            # `or` rather than a dict default: an EMPTY error string is what
            # made thirty OOM kills look like blank successes.
            status = (row.get("error")
                      or ("ok" if row.get("rc") == 0 else "FAILED (no detail)"))[:60]
            with cv:
                rows.append(row)
                jsonl.write(json.dumps(row) + "\n")
                jsonl.flush()
                done[0] += 1
                print(f"  [{done[0]}/{total}] {row['run_id']} "
                      f"{time.time()-t0:.1f}s ({shard}) -> {status}")

    threads = [threading.Thread(target=worker, args=(s,)) for s in shards]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if rows:
        cols = sorted({k for r in rows for k in r})
        path = os.path.join(RESULTS, f"runs-{ts}.csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {len(rows)} rows -> {path}")

    # A queue script reads the exit code, so a lane that produced no usable
    # cells must not report success. "wrote 30 rows" was true and meaningless
    # when all thirty were OOM-killed shells.
    failed = [r for r in rows if r.get("error")]
    if failed:
        print(f"\n{len(failed)} of {len(rows)} cell-runs FAILED:")
        for r in failed[:10]:
            print(f"  {r.get('run_id')}: {str(r.get('error'))[:120]}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")
        sys.exit(1)


if __name__ == "__main__":
    main()
