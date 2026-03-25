# Example 07: Stack Overflow Tables (OLTP)

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/07_stackoverflow_tables_oltp.py){ .md-button }

This example loads the Stack Overflow XML tables into a relational-style layout and
runs a point-oriented CRUD workload.

## Overview

Example 07 is the table OLTP benchmark for the Stack Overflow dataset.

- It loads eight XML-derived tables.
- It uses a fixed mixed workload: 60% read, 20% update, 10% insert, 10% delete.
- Every operation picks one table and one target row at random.
- It measures preload time, index time, OLTP latency, throughput, disk usage, and RSS.

## Source Tables

The example defines these tables directly in `TABLE_DEFS`.

| Table | Source file | Columns |
| --- | --- | --- |
| `User` | `Users.xml` | `Id`, `Reputation`, `CreationDate`, `DisplayName`, `LastAccessDate`, `WebsiteUrl`, `Location`, `AboutMe`, `Views`, `UpVotes`, `DownVotes`, `AccountId` |
| `Post` | `Posts.xml` | `Id`, `PostTypeId`, `ParentId`, `AcceptedAnswerId`, `CreationDate`, `Score`, `ViewCount`, `Body`, `OwnerUserId`, `LastEditorUserId`, `LastEditorDisplayName`, `LastEditDate`, `LastActivityDate`, `Title`, `Tags`, `AnswerCount`, `CommentCount`, `FavoriteCount`, `ClosedDate`, `CommunityOwnedDate` |
| `Comment` | `Comments.xml` | `Id`, `PostId`, `Score`, `Text`, `CreationDate`, `UserId` |
| `Badge` | `Badges.xml` | `Id`, `UserId`, `Name`, `Date`, `Class`, `TagBased` |
| `Vote` | `Votes.xml` | `Id`, `PostId`, `VoteTypeId`, `CreationDate`, `UserId`, `BountyAmount` |
| `PostLink` | `PostLinks.xml` | `Id`, `CreationDate`, `PostId`, `RelatedPostId`, `LinkTypeId` |
| `Tag` | `Tags.xml` | `Id`, `TagName`, `Count`, `ExcerptPostId`, `WikiPostId` |
| `PostHistory` | `PostHistory.xml` | `Id`, `PostHistoryTypeId`, `PostId`, `RevisionGUID`, `CreationDate`, `UserId`, `UserDisplayName`, `Comment`, `Text`, `CloseReasonId` |

Each backend also creates a unique `Id` index for every table.

## Supported Backends

- `arcadedb_sql`
- `sqlite`
- `duckdb`
- `postgresql`

## Run

From `bindings/python/examples`:

```bash
python 07_stackoverflow_tables_oltp.py \
  --dataset stackoverflow-tiny \
  --db arcadedb_sql \
  --threads 1 \
  --transactions 10000 \
  --batch-size 10000 \
  --mem-limit 4g \
  --verify-single-thread-series
```

## Workload Model

The operation planner is fixed in source as:

```python
DEFAULT_OLTP_MIX = {"read": 0.60, "update": 0.20, "insert": 0.10, "delete": 0.10}
```

The selected table for each operation is random across all eight tables.

### Read Projections

Reads always filter on `Id`, but the projected columns vary by table. The source code
uses `get_read_projection()`, which chooses one of two projections per table.

| Table | Projection A | Projection B |
| --- | --- | --- |
| `User` | `Id, Reputation, CreationDate` | `Id, Reputation, DisplayName` |
| `Post` | `Id, PostTypeId, ParentId` | `Id, PostTypeId, AcceptedAnswerId` |
| `Comment` | `Id, PostId, Score` | `Id, PostId, Text` |
| `Badge` | `Id, UserId, Name` | `Id, UserId, Date` |
| `Vote` | `Id, PostId, VoteTypeId` | `Id, PostId, CreationDate` |
| `PostLink` | `Id, CreationDate, PostId` | `Id, CreationDate, RelatedPostId` |
| `Tag` | `Id, TagName, Count` | `Id, TagName, ExcerptPostId` |
| `PostHistory` | `Id, PostHistoryTypeId, PostId` | `Id, PostHistoryTypeId, RevisionGUID` |

### Update Targets

The update column is the first non-`Id` field whose declared type is `INTEGER` or
`BOOLEAN`.

| Table | Updated column |
| --- | --- |
| `User` | `Reputation` |
| `Post` | `PostTypeId` |
| `Comment` | `PostId` |
| `Badge` | `UserId` |
| `Vote` | `PostId` |
| `PostLink` | `PostId` |
| `Tag` | `Count` |
| `PostHistory` | `PostHistoryTypeId` |

### Insert Payloads

Insert rows are synthetic. The source uses `build_synthetic_row()`:

- `Id` is the next generated integer for that table.
- `INTEGER` fields get a random value in `[1, 1000]`.
- `BOOLEAN` fields get a random boolean.
- `DATETIME` fields get the current UTC timestamp.
- string fields get `synthetic_<Table>_<Field>_<Id>`.

## Query Suite

### ArcadeDB SQL

The ArcadeDB path issues SQL directly.

#### ArcadeDB Read

```sql
SELECT {projection} FROM {table_name} WHERE Id = {target_id}
```

#### ArcadeDB Update

```sql
UPDATE {table_name} SET {update_col} = coalesce({update_col}, 0) + 1 WHERE Id = {target_id}
```

#### ArcadeDB Insert

```sql
INSERT INTO {table_name} SET {col1} = ?, {col2} = ?, ...
```

The same statement shape is used both for preload batches and OLTP inserts.

#### ArcadeDB Delete

```sql
DELETE FROM {table_name} WHERE Id = {target_id}
```

### SQLite

The SQLite path uses parameterized SQL with quoted identifiers.

#### SQLite Read

```sql
SELECT {projection} FROM "{table_name}" WHERE "Id" = ?
```

#### SQLite Update

```sql
UPDATE "{table_name}" SET "{update_col}" = coalesce("{update_col}", 0) + 1 WHERE "Id" = ?
```

#### SQLite Insert

```sql
INSERT INTO "{table_name}" ("col1", "col2", ...) VALUES (?, ?, ...)
```

#### SQLite Delete

```sql
DELETE FROM "{table_name}" WHERE "Id" = ?
```

### DuckDB

The DuckDB OLTP path uses the same SQL shapes as SQLite, with explicit transactions.

#### DuckDB Read

```sql
SELECT {projection} FROM "{table_name}" WHERE "Id" = ?
```

#### DuckDB Update

```sql
UPDATE "{table_name}" SET "{update_col}" = coalesce("{update_col}", 0) + 1 WHERE "Id" = ?
```

#### DuckDB Insert

```sql
INSERT INTO "{table_name}" ("col1", "col2", ...) VALUES (?, ?, ...)
```

#### DuckDB Delete

```sql
DELETE FROM "{table_name}" WHERE "Id" = ?
```

### PostgreSQL

The PostgreSQL path uses quoted identifiers and `%s` parameters.

#### Read

```sql
SELECT {projection_sql} FROM "{table_name}" WHERE "Id" = %s
```

The `projection_sql` string is built by quoting each projected column returned by
`get_read_projection()`.

#### Update

```sql
UPDATE "{table_name}" SET "{update_col}" = coalesce("{update_col}", 0) + 1 WHERE "Id" = %s
```

#### Insert

```sql
INSERT INTO "{table_name}" ("col1", "col2", ...) VALUES (%s, %s, ...)
```

#### Delete

```sql
DELETE FROM "{table_name}" WHERE "Id" = %s
```

## Preload Paths

The benchmark does not use the same preload mechanism for every backend.

- ArcadeDB preload uses async `INSERT INTO ... SET ...` SQL.
- SQLite preload uses batched `INSERT INTO ... VALUES ...` statements.
- DuckDB preload uses per-table CSV materialization followed by:

```sql
COPY "{table_name}" FROM '{csv_path}' (AUTO_DETECT TRUE, HEADER TRUE)
```

- PostgreSQL preload writes CSV and then streams it through:

```sql
COPY "{table_name}" ("col1", "col2", ...) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
```

Those load-path differences matter for ingest timing, but they do not change the
OLTP CRUD statements listed above.

## Result Notes

- `du_mib` is real post-run filesystem usage.
- `disk_after_*` fields are benchmark-reported logical size counters.
- Per-operation latency is summarized from the recorded `read`, `update`, `insert`,
  and `delete` latency buckets.
- `--verify-single-thread-series` checks deterministic repeatability for one backend
  configuration, not strict equality across different engines.
