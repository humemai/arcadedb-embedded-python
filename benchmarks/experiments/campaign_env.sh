#!/usr/bin/env bash
# The environment every ICDE campaign run needs. Source this; do not retype it.
#
# WHY THIS FILE EXISTS. It was scattered across ~113 ad-hoc launcher scripts in
# mini's home directory, and on 2026-08-15 a new campaign script omitted all of
# it. The l2 lane happened to validate its scale name and died in argparse,
# which was the lucky outcome: the lanes that do NOT validate would have run
# green for 41 hours on synthetic corpora instead of LDBC-SNB, Big-ANN and
# DEEP, and nothing downstream would have caught it, because a row records the
# scale it was ASKED for and not the corpus it actually read.
#
# Config that lives only in a shell script in someone's home directory is
# config that a future run will forget. This is in the repo, beside the runner
# it configures, so a campaign script is one `source` away from correct and a
# reviewer can see what the numbers were measured against.
#
#   source "$(dirname "$0")/campaign_env.sh"   # or an absolute path
#
# Override any of these by exporting before sourcing; each uses :=.

: "${BENCH_HOST:=mini}"                       # never defaulted inside the harness
: "${BENCH_DATA:=$HOME/bench-data}"           # host dir bind-mounted to /data:ro
: "${BENCH_CPUSET:=0-11}"                     # the P-core threads, both containers

# Real corpora. Each SOURCE switch flips a lane off its synthetic generator;
# each DATA path is the mount point INSIDE the container, not the host path.
: "${BENCH_GRAPH_SOURCE:=ldbc}"     ; : "${BENCH_GRAPH_DATA:=/data/ldbc}"
: "${BENCH_SPARSE_SOURCE:=bigann}"  ; : "${BENCH_SPARSE_DATA:=/data/bigann}"
: "${BENCH_DENSE_DATA:=/data/dense}"
: "${BENCH_TPC_DATA:=/data/tpch}"

# Operating points that are matched by EFFECT rather than by parameter name.
# maxConnections is a Vamana per-layer degree, not hnswlib's M; matching the
# names would compare a half-degree graph against a full-degree one.
: "${BENCH_DENSE_M:=32}"

# TPC-H scale factor. tpch1 is SF1; the tpch10 tier needs BENCH_TPC_SF=10 and a
# streaming loader that does not yet exist (see task #143).
: "${BENCH_TPC_SF:=1}"

export BENCH_HOST BENCH_DATA BENCH_CPUSET \
       BENCH_GRAPH_SOURCE BENCH_GRAPH_DATA \
       BENCH_SPARSE_SOURCE BENCH_SPARSE_DATA \
       BENCH_DENSE_DATA BENCH_DENSE_M \
       BENCH_TPC_DATA BENCH_TPC_SF

# Setting a path is not the same claim as the data being there. A campaign that
# discovers a missing corpus in hour three has already wasted hours one and two.
campaign_env_check() {
    local missing=""
    for d in ldbc bigann dense tpch; do
        [ -d "$BENCH_DATA/$d" ] || missing="$missing $BENCH_DATA/$d"
    done
    if [ -n "$missing" ]; then
        echo "campaign_env: MISSING CORPORA:$missing" >&2
        echo "campaign_env: lanes would silently fall back to synthetic data" >&2
        return 1
    fi
    return 0
}
