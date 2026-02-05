# Dataset Downloader

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/download_data.py){ .md-button }

Use `download_data.py` to fetch and prepare datasets for the examples. Run it from the `examples/` directory so paths resolve correctly.

## Quick Start

```bash
cd bindings/python/examples
python download_data.py movielens-small
```

All datasets are stored under `bindings/python/examples/data/`.

## Supported Datasets

- **MovieLens**: `movielens-small`, `movielens-large`
- **Stack Exchange**: `stackoverflow-small`, `stackoverflow-medium`, `stackoverflow-large`
- **TPC-H**: `tpch-sf1`, `tpch-sf10`, `tpch-sf100`
- **LDBC SNB Interactive v1**: `ldbc-snb-sf1`, `ldbc-snb-sf10`, `ldbc-snb-sf100`
- **MSMARCO v2.1**: `msmarco-1m`, `msmarco-5m`, `msmarco-10m`

## Usage

```bash
python download_data.py movielens-large
python download_data.py stackoverflow-small
python download_data.py tpch-sf1
python download_data.py ldbc-snb-sf1
python download_data.py msmarco-1m
```

## Notes

- **MovieLens NULL injection** is enabled by default (use `--no-nulls` to skip).
- **TPC-H** uses `dbgen` to generate `.tbl` files (pipe-delimited text, not SQL) via Docker (gcc image).
    - Converted CSVs are written to `examples/data/tpch-sf<scale>/csv/`.
    - A schema file is written to `examples/data/tpch-sf<scale>/schema.json`.
- **LDBC SNB** is generated locally via Docker (ldbc/datagen).
    - CSVs are stored under `examples/data/ldbc-snb-sf<scale>/`.
    - A schema file is written to `examples/data/ldbc-snb-sf<scale>/schema.json` (inferred from CSV headers and samples).
- **MSMARCO** downloads parquet shards and converts them to vector shards with a ground-truth file.

## Dependencies

Install only what you need for the datasets you plan to download:

- Stack Exchange: `py7zr`
- MSMARCO: `huggingface_hub`, `numpy`, `pyarrow`
- TPC-H: Docker (gcc image for `dbgen`)
- LDBC SNB: Docker (ldbc/datagen image)

## Output Locations

- MovieLens: `examples/data/movielens-<size>/`
- Stack Exchange: `examples/data/stackoverflow-<size>/`
- TPC-H: `examples/data/tpch-sf<scale>/`
- LDBC SNB: `examples/data/ldbc-snb-sf<scale>/`
- MSMARCO: `examples/data/MSMARCO-<size>/`

## Formats & Schemas

- **MovieLens**: CSV files, no schema file generated.
- **Stack Exchange**: XML files, no schema file generated.
- **TPC-H**: `.tbl` plus derived CSVs (pipe-delimited); schema in `schema.json`.
- **LDBC SNB**: CSVs; schema in `schema.json` (inferred).
- **MSMARCO**: binary vector shards (`.f32`) plus `.meta.json` and `.gt.jsonl`.
