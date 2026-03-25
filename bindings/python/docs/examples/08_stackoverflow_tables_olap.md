# Example 08: Stack Overflow Tables (OLAP)

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/08_stackoverflow_tables_olap.py){ .md-button }

This example loads the Stack Overflow tables and runs a fixed analytical SQL suite.

## Overview

Example 08 is the table OLAP benchmark.

- It loads the same eight tables used by Example 07.
- It builds `Id` indexes after load.
- It runs one fixed list of ten SQL queries.
- It can repeat the suite with fixed or shuffled order.

## Supported Backends

- `arcadedb_sql`
- `sqlite`
- `duckdb`
- `postgresql`

## Run

From `bindings/python/examples`:

```bash
python 08_stackoverflow_tables_olap.py \
  --dataset stackoverflow-tiny \
  --db arcadedb_sql \
  --batch-size 10000 \
  --query-runs 3 \
  --query-order shuffled \
  --mem-limit 4g
```

## Query Suite Definition

The source defines the workload once in `QUERY_DEFS`. For ArcadeDB SQL, SQLite, and
DuckDB, the exact SQL below is executed as written. PostgreSQL runs the same logical
queries after applying `translate_sql_for_postgresql()`, which mechanically quotes
identifiers such as `User`, `Post`, `Id`, and `Count`.

## Exact SQL Queries

### Q1. Post Type Counts

```sql
SELECT PostTypeId, count(*) as count
FROM Post
GROUP BY PostTypeId
ORDER BY PostTypeId
```

### Q2. Top Users By Reputation

```sql
SELECT Id, DisplayName, Reputation
FROM User
WHERE Reputation IS NOT NULL
ORDER BY Reputation DESC, Id ASC
LIMIT 10
```

### Q3. Top Questions By Score

```sql
SELECT Id, Score, ViewCount
FROM Post
WHERE PostTypeId = 1
ORDER BY Score DESC, Id ASC
LIMIT 10
```

### Q4. Top Answers By Score

```sql
SELECT Id, Score
FROM Post
WHERE PostTypeId = 2
ORDER BY Score DESC, Id ASC
LIMIT 10
```

### Q5. Most Commented Posts

```sql
SELECT PostId, count(*) as comment_count
FROM Comment
GROUP BY PostId
ORDER BY comment_count DESC, PostId ASC
LIMIT 10
```

### Q6. Votes By Type

```sql
SELECT VoteTypeId, count(*) as count
FROM Vote
GROUP BY VoteTypeId
ORDER BY VoteTypeId
```

### Q7. Top Badges

```sql
SELECT Name, count(*) as count
FROM Badge
GROUP BY Name
ORDER BY count DESC, Name ASC
LIMIT 10
```

### Q8. PostLinks By Type

```sql
SELECT LinkTypeId, count(*) as count
FROM PostLink
GROUP BY LinkTypeId
ORDER BY LinkTypeId
```

### Q9. PostHistory By Type

```sql
SELECT PostHistoryTypeId, count(*) as count
FROM PostHistory
GROUP BY PostHistoryTypeId
ORDER BY PostHistoryTypeId
```

### Q10. Top Tags By Count

```sql
SELECT TagName, Count
FROM Tag
ORDER BY Count DESC, TagName ASC
LIMIT 10
```

## PostgreSQL Translation Rule

The PostgreSQL runner does not define a separate query suite. It rewrites the exact
SQL above by quoting a fixed identifier list. In source, the translation rule is:

```python
translated = re.sub(pattern, quote_ident_pg(ident), translated)
```

with the identifiers:

- `User`
- `Post`
- `Comment`
- `Badge`
- `Vote`
- `PostLink`
- `Tag`
- `PostHistory`
- `Id`
- `Reputation`
- `CreationDate`
- `DisplayName`
- `PostTypeId`
- `Score`
- `ViewCount`
- `PostId`
- `VoteTypeId`
- `Name`
- `LinkTypeId`
- `PostHistoryTypeId`
- `TagName`
- `Count`

That means the benchmark intent stays identical across engines, while PostgreSQL gets
reserved-word-safe SQL.

## Load And Index Notes

The benchmark measures query execution, but the setup path still matters for context.

- ArcadeDB loads documents through async SQL inserts.
- SQLite uses batched inserts.
- DuckDB bulk-loads CSV via `COPY`.
- PostgreSQL bulk-loads CSV via `COPY ... FROM STDIN`.
- After load, all engines build `Id` indexes for the benchmark tables.

## Result Notes

- `--query-runs` controls how many measured executions happen per query.
- `--query-order fixed` preserves the source order above.
- `--query-order shuffled` randomizes query order between runs.
- Query latency should be interpreted together with the repeated-run policy and query order.
