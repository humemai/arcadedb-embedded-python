# The harness's DuckDB image (sql and pgq arms): DuckDB 2.0.0 with the DuckPGQ community extension baked in.
#
#   docker build -t sqlev:duckdb-2.0.0 -f docker/duckdb.Dockerfile docker
#
# Mirrors the campaign's `dbbench:duckdb` (benchmarks/experiments/build_images.sh and Dockerfile.bench: python:3.12-slim, the
# engine pin plus HARNESS_PKGS), with two differences. The campaign holds DuckDB at 1.5.6 because its DuckPGQ build did not
# parse on 2.0.0 (build_images.sh, 2026-10-23); this harness uses 2.0.0 and proves at build time that it does (the build
# fails when `CREATE PROPERTY GRAPH` and `GRAPH_TABLE` do not parse). And DuckPGQ is installed here, at build time, into a
# directory every user can read (SQLEV_DUCKDB_EXT_DIR), so a cell only runs `LOAD duckpgq` and downloads nothing. The campaign
# image is not touched.
FROM python:3.12-slim

ARG DUCKDB_VERSION=2.0.0
# Same pins as HARNESS_PKGS in build_images.sh (2026-09-19).
ARG HARNESS_PKGS="numpy==2.5.3 pandas==3.0.6 pyarrow==25.0.1"

ENV SQLEV_DUCKDB_EXT_DIR=/opt/duckdb_extensions
COPY build_check.py /tmp/build_check.py
RUN set -e; \
    pip install --no-cache-dir "duckdb==${DUCKDB_VERSION}" ${HARNESS_PKGS}; \
    mkdir -p "${SQLEV_DUCKDB_EXT_DIR}"; \
    python /tmp/build_check.py "${DUCKDB_VERSION}" "${SQLEV_DUCKDB_EXT_DIR}"; \
    chmod -R a+rX "${SQLEV_DUCKDB_EXT_DIR}"; \
    rm -f /tmp/build_check.py

WORKDIR /work
CMD ["python", "--version"]
