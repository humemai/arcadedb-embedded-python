# Example 09: Stack Overflow Graph (OLTP)

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/09_stackoverflow_graph_oltp.py){ .md-button }

This example builds a Stack Overflow property graph and runs a mixed OLTP workload.

## Overview

Example 09 is the graph-oriented OLTP benchmark in the Python examples set.

- Builds the Stack Overflow graph with the repository's directed schema conventions
- Runs mixed graph CRUD operations against the selected backend
- Supports ArcadeDB embedded and Neo4j client/server execution paths alongside the in-process backends
- Measures throughput, latency, disk usage, and peak RSS
- Supports deterministic single-thread verification for repeatability checks

## Table-To-Graph Projection

The graph benchmark projects six XML sources into a directed property graph.

### Source Files Used

Required inputs for the graph build:

- `Users.xml`
- `Posts.xml`
- `Comments.xml`
- `Badges.xml`
- `Tags.xml`
- `PostLinks.xml`

Not used by this graph projection:

- `Votes.xml`
- `PostHistory.xml`

## Graph Model

The example uses six vertex types and nine directed edge types.

### Vertices

- `User`
- `Question`
- `Answer`
- `Tag`
- `Badge`
- `Comment`

### Edges

- `ASKED`
- `ANSWERED`
- `HAS_ANSWER`
- `ACCEPTED_ANSWER`
- `TAGGED_WITH`
- `COMMENTED_ON`
- `COMMENTED_ON_ANSWER`
- `EARNED`
- `LINKED_TO`

Each vertex type gets a unique `Id` index.

### Vertex Mapping

| Vertex type | Source | Required key | Properties carried into the graph |
| --- | --- | --- | --- |
| `User` | `Users.xml` | `Id` | `Id`, `DisplayName`, `Reputation`, `CreationDate`, `Views`, `UpVotes`, `DownVotes` |
| `Question` | `Posts.xml` where `PostTypeId = 1` | `Id` | `Id`, `Title`, `Body`, `Score`, `ViewCount`, `CreationDate`, `AnswerCount`, `CommentCount`, `FavoriteCount` |
| `Answer` | `Posts.xml` where `PostTypeId = 2` | `Id` | `Id`, `Body`, `Score`, `CreationDate`, `CommentCount` |
| `Tag` | `Tags.xml` | `Id` | `Id`, `TagName`, `Count` |
| `Badge` | `Badges.xml` | `Id` | `Id`, `Name`, `Date`, `Class` |
| `Comment` | `Comments.xml` | `Id` | `Id`, `Text`, `Score`, `CreationDate` |

### Edge Mapping

| Edge type | From | To | Source rule | Edge properties |
| --- | --- | --- | --- | --- |
| `ASKED` | `User` | `Question` | question owner from `Posts.xml` | `CreationDate` |
| `ANSWERED` | `User` | `Answer` | answer owner from `Posts.xml` | `CreationDate` |
| `HAS_ANSWER` | `Question` | `Answer` | `ParentId` on answer row | none |
| `ACCEPTED_ANSWER` | `Question` | `Answer` | `AcceptedAnswerId` on question row | none |
| `TAGGED_WITH` | `Question` | `Tag` | parsed question tags from `Posts.xml` | none |
| `COMMENTED_ON` | `Comment` | `Question` | comment target is a question | `CreationDate`, `Score` |
| `COMMENTED_ON_ANSWER` | `Comment` | `Answer` | comment target is an answer | `CreationDate`, `Score` |
| `EARNED` | `User` | `Badge` | badge owner from `Badges.xml` | `Date`, `Class` |
| `LINKED_TO` | `Question` | `Question` | `PostLinks.xml` question-to-question links | `LinkTypeId`, `CreationDate` |

## Projection Rules

### Source Mapping

| Source file | Output |
| --- | --- |
| `Users.xml` | `User` vertices |
| `Posts.xml` | `Question` and `Answer` vertices, plus `ASKED`, `ANSWERED`, `HAS_ANSWER`, `ACCEPTED_ANSWER`, `TAGGED_WITH` |
| `Comments.xml` | `Comment` vertices, plus `COMMENTED_ON` and `COMMENTED_ON_ANSWER` |
| `Badges.xml` | `Badge` vertices, plus `EARNED` |
| `Tags.xml` | `Tag` vertices |
| `PostLinks.xml` | `LINKED_TO` |

### Vertex Projection Rules

- `Posts.xml` with `PostTypeId = 1` becomes `Question`
- `Posts.xml` with `PostTypeId = 2` becomes `Answer`
- there is no generic `Post` vertex type in the graph model

### Edge Derivation Rules

| Edge | Rule |
| --- | --- |
| `ASKED` | `User.OwnerUserId -> Question.Id`, carries `CreationDate` |
| `ANSWERED` | `User.OwnerUserId -> Answer.Id`, carries `CreationDate` |
| `HAS_ANSWER` | `Question.ParentId -> Answer.Id` |
| `ACCEPTED_ANSWER` | `Question.Id -> Answer.AcceptedAnswerId` |
| `TAGGED_WITH` | parse question `Tags`, resolve by `TagName -> Id`, create `Question -> Tag` |
| `COMMENTED_ON` | comment `PostId` resolves to a question |
| `COMMENTED_ON_ANSWER` | comment `PostId` resolves to an answer |
| `EARNED` | `User.UserId -> Badge.Id`, carries `Date`, `Class` |
| `LINKED_TO` | `Question.PostId -> Question.RelatedPostId`, carries `LinkTypeId`, `CreationDate` |

Tag parsing rule:

1. replace `><` with a separator
1. strip `<` and `>`
1. split into tag names

### Recommended Load Order

1. `Tag`
1. `User`
1. `Question`
1. `Answer`
1. `Badge`
1. `Comment`
1. build `Id` indexes
1. build endpoint lookups
1. `ASKED`
1. `ANSWERED`
1. `HAS_ANSWER`
1. `ACCEPTED_ANSWER`
1. `TAGGED_WITH`
1. `COMMENTED_ON`
1. `COMMENTED_ON_ANSWER`
1. `EARNED`
1. `LINKED_TO`

## Exact OLTP Workload

### Operation Mix

The source fixes the workload to:

- `read`: 60%
- `update`: 20%
- `insert`: 10%
- `delete`: 10%

### Read Targets

Each read chooses one of these target kinds:

- `user`
- `question`
- `answer`
- `badge`
- `tag`
- `comment`
- `edge_sample`

#### ArcadeDB SQL Mode Reads

1. SQL-R1: edge sample

```sql
SELECT FROM {edge_type} LIMIT 1
```

1. SQL-R2: user by `Id`

```sql
SELECT Id FROM User WHERE Id = :id LIMIT 1
```

1. SQL-R3: question by `Id`

```sql
SELECT Id FROM Question WHERE Id = :id LIMIT 1
```

1. SQL-R4: answer by `Id`

```sql
SELECT Id FROM Answer WHERE Id = :id LIMIT 1
```

1. SQL-R5: tag by `Id`

```sql
SELECT Id FROM Tag WHERE Id = :id LIMIT 1
```

1. SQL-R6: comment by `Id`

```sql
SELECT Id FROM Comment WHERE Id = :id LIMIT 1
```

1. SQL-R7: badge by `Id`

```sql
SELECT Id FROM Badge WHERE Id = :id LIMIT 1
```

#### ArcadeDB Cypher Mode Reads

1. CYP-R1: user outbound activity

```cypher
MATCH (u:User {Id: %d})-[:ASKED|ANSWERED]->(p)
RETURN p.Id
LIMIT 1
```

1. CYP-R2: question tags

```cypher
MATCH (q:Question {Id: %d})-[:TAGGED_WITH]->(t:Tag)
RETURN t.Id
LIMIT 1
```

1. CYP-R3: answer comments

```cypher
MATCH (a:Answer {Id: %d})<-[:COMMENTED_ON_ANSWER]-(c:Comment)
RETURN c.Id
LIMIT 1
```

1. CYP-R4: questions for a tag

```cypher
MATCH (q:Question)-[:TAGGED_WITH]->(t:Tag {Id: %d})
RETURN q.Id
LIMIT 1
```

1. CYP-R5: comment target

```cypher
MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON|COMMENTED_ON_ANSWER]->(p)
RETURN p.Id
LIMIT 1
```

1. CYP-R6: badge owner

```cypher
MATCH (u:User)-[:EARNED]->(b:Badge {Id: %d})
RETURN u.Id
LIMIT 1
```

1. CYP-R7: edge sample

```cypher
MATCH ()-[r:ASKED|ANSWERED|HAS_ANSWER|ACCEPTED_ANSWER|TAGGED_WITH|COMMENTED_ON|COMMENTED_ON_ANSWER|EARNED|LINKED_TO]->()
RETURN r
LIMIT 1
```

### Updates

#### ArcadeDB SQL Mode Updates

1. SQL-U1: question score

```sql
UPDATE Question SET Score = coalesce(Score, 0) + 1 WHERE Id = :id
```

1. SQL-U2: answer score

```sql
UPDATE Answer SET Score = coalesce(Score, 0) + 1 WHERE Id = :id
```

1. SQL-U3: comment score

```sql
UPDATE Comment SET Score = coalesce(Score, 0) + 1 WHERE Id = :id
```

1. SQL-U4: tag count

```sql
UPDATE Tag SET Count = coalesce(Count, 0) + 1 WHERE Id = :id
```

1. SQL-U5: user reputation

```sql
UPDATE User SET Reputation = coalesce(Reputation, 0) + 1 WHERE Id = :id
```

The SQL OLTP path does not update edges.

#### ArcadeDB Cypher Mode Updates

1. CYP-U1: question score

```cypher
MATCH (q:Question {Id: %d})
SET q.Score = coalesce(q.Score, 0) + 1
```

1. CYP-U2: answer score

```cypher
MATCH (a:Answer {Id: %d})
SET a.Score = coalesce(a.Score, 0) + 1
```

1. CYP-U3: comment score

```cypher
MATCH (c:Comment {Id: %d})
SET c.Score = coalesce(c.Score, 0) + 1
```

1. CYP-U4: tag count

```cypher
MATCH (t:Tag {Id: %d})
SET t.Count = coalesce(t.Count, 0) + 1
```

1. CYP-U5: user reputation

```cypher
MATCH (u:User {Id: %d})
SET u.Reputation = coalesce(u.Reputation, 0) + 1
```

1. CYP-U6: `ASKED` edge

```cypher
MATCH (u:User {Id: %d})-[r:ASKED]->(q:Question {Id: %d})
SET r.CreationDate = coalesce(r.CreationDate, 0) + 1
```

1. CYP-U7: `ANSWERED` edge

```cypher
MATCH (u:User {Id: %d})-[r:ANSWERED]->(a:Answer {Id: %d})
SET r.CreationDate = coalesce(r.CreationDate, 0) + 1
```

1. CYP-U8: `COMMENTED_ON` edge

```cypher
MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON]->(q:Question {Id: %d})
SET r.Score = coalesce(r.Score, 0) + 1
```

1. CYP-U9: `COMMENTED_ON_ANSWER` edge

```cypher
MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON_ANSWER]->(a:Answer {Id: %d})
SET r.Score = coalesce(r.Score, 0) + 1
```

1. CYP-U10: `EARNED` edge

```cypher
MATCH (u:User {Id: %d})-[r:EARNED]->(b:Badge {Id: %d})
SET r.Class = coalesce(r.Class, 0) + 1
```

1. CYP-U11: `LINKED_TO` edge

```cypher
MATCH (q1:Question {Id: %d})-[r:LINKED_TO]->(q2:Question {Id: %d})
SET r.LinkTypeId = coalesce(r.LinkTypeId, 0) + 1
```

### Inserts

#### ArcadeDB SQL Mode Inserts

1. SQL-I1: synthetic user

```sql
INSERT INTO User SET Id = :id, DisplayName = 'Synthetic', Reputation = 0, CreationDate = :ts
```

1. SQL-I2: synthetic question

```sql
INSERT INTO Question SET Id = :id, Title = 'Synthetic', Body = 'Synthetic body', Score = 0, CreationDate = :ts
```

1. SQL-I3: `ASKED` edge

```sql
CREATE EDGE ASKED FROM (SELECT FROM User WHERE Id = :uid LIMIT 1) TO (SELECT FROM Question WHERE Id = :qid LIMIT 1) SET CreationDate = :ts
```

1. SQL-I4: synthetic answer

```sql
INSERT INTO Answer SET Id = :id, Body = 'Synthetic answer', Score = 0, CreationDate = :ts, CommentCount = 0
```

1. SQL-I5: `ANSWERED` edge

```sql
CREATE EDGE ANSWERED FROM (SELECT FROM User WHERE Id = :uid LIMIT 1) TO (SELECT FROM Answer WHERE Id = :aid LIMIT 1) SET CreationDate = :ts
```

1. SQL-I6: `HAS_ANSWER` edge

```sql
CREATE EDGE HAS_ANSWER FROM (SELECT FROM Question WHERE Id = :qid LIMIT 1) TO (SELECT FROM Answer WHERE Id = :aid LIMIT 1)
```

1. SQL-I7: synthetic comment

```sql
INSERT INTO Comment SET Id = :id, Text = 'Synthetic comment', Score = 0, CreationDate = :ts
```

1. SQL-I8: `COMMENTED_ON` edge

```sql
CREATE EDGE COMMENTED_ON FROM (SELECT FROM Comment WHERE Id = :cid LIMIT 1) TO (SELECT FROM Question WHERE Id = :qid LIMIT 1) SET CreationDate = :ts, Score = 0
```

1. SQL-I9: `COMMENTED_ON_ANSWER` edge

```sql
CREATE EDGE COMMENTED_ON_ANSWER FROM (SELECT FROM Comment WHERE Id = :cid LIMIT 1) TO (SELECT FROM Answer WHERE Id = :aid LIMIT 1) SET CreationDate = :ts, Score = 0
```

1. SQL-I10: `TAGGED_WITH` edge

```sql
CREATE EDGE TAGGED_WITH FROM (SELECT FROM Question WHERE Id = :qid LIMIT 1) TO (SELECT FROM Tag WHERE Id = :tid LIMIT 1)
```

1. SQL-I11: `LINKED_TO` edge

```sql
CREATE EDGE LINKED_TO FROM (SELECT FROM Question WHERE Id = :qid LIMIT 1) TO (SELECT FROM Question WHERE Id = :rid LIMIT 1) SET LinkTypeId = 1, CreationDate = :ts
```

1. SQL-I12: `ACCEPTED_ANSWER` edge

```sql
CREATE EDGE ACCEPTED_ANSWER FROM (SELECT FROM Question WHERE Id = :qid LIMIT 1) TO (SELECT FROM Answer WHERE Id = :aid LIMIT 1)
```

1. SQL-I13: synthetic badge

```sql
INSERT INTO Badge SET Id = :id, Name = 'SyntheticBadge', Date = :ts, Class = 1
```

1. SQL-I14: `EARNED` edge

```sql
CREATE EDGE EARNED FROM (SELECT FROM User WHERE Id = :uid LIMIT 1) TO (SELECT FROM Badge WHERE Id = :bid LIMIT 1) SET Date = :ts, Class = 1
```

#### ArcadeDB Cypher Mode Inserts

1. CYP-I1: synthetic user and question with `ASKED`

```cypher
CREATE (u:User {Id: %d, DisplayName: 'Synthetic', Reputation: 0, CreationDate: %d})
CREATE (q:Question {Id: %d, Title: 'Synthetic', Body: 'Synthetic body', Score: 0, CreationDate: %d})
CREATE (u)-[:ASKED {CreationDate: %d}]->(q)
```

1. CYP-I2: synthetic answer with `ANSWERED` and `HAS_ANSWER`

```cypher
MATCH (u:User {Id: %d}), (q:Question {Id: %d})
CREATE (a:Answer {Id: %d, Body: 'Synthetic answer', Score: 0, CreationDate: %d, CommentCount: 0})
CREATE (u)-[:ANSWERED {CreationDate: %d}]->(a)
CREATE (q)-[:HAS_ANSWER]->(a)
```

1. CYP-I3: synthetic comment on question

```cypher
MATCH (q:Question {Id: %d})
CREATE (c:Comment {Id: %d, Text: 'Synthetic comment', Score: 0, CreationDate: %d})
CREATE (c)-[:COMMENTED_ON {CreationDate: %d, Score: 0}]->(q)
```

1. CYP-I4: synthetic comment on answer

```cypher
MATCH (a:Answer {Id: %d})
CREATE (c:Comment {Id: %d, Text: 'Synthetic comment', Score: 0, CreationDate: %d})
CREATE (c)-[:COMMENTED_ON_ANSWER {CreationDate: %d, Score: 0}]->(a)
```

1. CYP-I5: `TAGGED_WITH` edge

```cypher
MATCH (q:Question {Id: %d}), (t:Tag {Id: %d})
CREATE (q)-[:TAGGED_WITH]->(t)
```

1. CYP-I6: `LINKED_TO` edge

```cypher
MATCH (q1:Question {Id: %d}), (q2:Question {Id: %d})
CREATE (q1)-[:LINKED_TO {LinkTypeId: 1, CreationDate: %d}]->(q2)
```

1. CYP-I7: `ACCEPTED_ANSWER` edge

```cypher
MATCH (q:Question {Id: %d}), (a:Answer {Id: %d})
CREATE (q)-[:ACCEPTED_ANSWER]->(a)
```

1. CYP-I8: synthetic badge with `EARNED`

```cypher
MATCH (u:User {Id: %d})
CREATE (b:Badge {Id: %d, Name: 'SyntheticBadge', Date: %d, Class: 1})
CREATE (u)-[:EARNED {Date: %d, Class: 1}]->(b)
```

### Deletes

#### ArcadeDB SQL Mode Deletes

1. SQL-D1: question

```sql
DELETE FROM Question WHERE Id = :id
```

1. SQL-D2: answer

```sql
DELETE FROM Answer WHERE Id = :id
```

1. SQL-D3: comment

```sql
DELETE FROM Comment WHERE Id = :id
```

1. SQL-D4: badge

```sql
DELETE FROM Badge WHERE Id = :id
```

1. SQL-D5: user

```sql
DELETE FROM User WHERE Id = :id
```

1. SQL-D6: tag

```sql
DELETE FROM Tag WHERE Id = :id
```

The SQL OLTP path does not delete edges.

#### ArcadeDB Cypher Mode Deletes

1. CYP-D1: node delete template used for `Question`, `Answer`, `Comment`, `Badge`, `User`, and `Tag`

```cypher
MATCH (n:%s {Id: %d})
DETACH DELETE n
```

1. CYP-D2: `ASKED`

```cypher
MATCH (u:User {Id: %d})-[r:ASKED]->(q:Question {Id: %d})
DELETE r
```

1. CYP-D3: `ANSWERED`

```cypher
MATCH (u:User {Id: %d})-[r:ANSWERED]->(a:Answer {Id: %d})
DELETE r
```

1. CYP-D4: `HAS_ANSWER`

```cypher
MATCH (q:Question {Id: %d})-[r:HAS_ANSWER]->(a:Answer {Id: %d})
DELETE r
```

1. CYP-D5: `ACCEPTED_ANSWER`

```cypher
MATCH (q:Question {Id: %d})-[r:ACCEPTED_ANSWER]->(a:Answer {Id: %d})
DELETE r
```

1. CYP-D6: `TAGGED_WITH`

```cypher
MATCH (q:Question {Id: %d})-[r:TAGGED_WITH]->(t:Tag {Id: %d})
DELETE r
```

1. CYP-D7: `COMMENTED_ON`

```cypher
MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON]->(q:Question {Id: %d})
DELETE r
```

1. CYP-D8: `COMMENTED_ON_ANSWER`

```cypher
MATCH (c:Comment {Id: %d})-[r:COMMENTED_ON_ANSWER]->(a:Answer {Id: %d})
DELETE r
```

1. CYP-D9: `EARNED`

```cypher
MATCH (u:User {Id: %d})-[r:EARNED]->(b:Badge {Id: %d})
DELETE r
```

1. CYP-D10: `LINKED_TO`

```cypher
MATCH (q1:Question {Id: %d})-[r:LINKED_TO]->(q2:Question {Id: %d})
DELETE r
```

## Current Repository Guidance

- ArcadeDB graph preload now uses `GraphBatch` for the initial node and edge load,
  driven by the configured `--threads` value
- `GraphBatch` is the repository's recommended bulk graph ingest path from Python
- Neo4j runs through a Dockerized server plus Python driver wrapper, with the benchmark
  splitting the configured global memory/CPU budget between client and server via
  `--server-fraction`
- Traversal expectations should be read as directed unless the query pattern
  explicitly traverses both directions
- For cross-database comparability, `--threads 1` is the recommended baseline
- `--verify-single-thread-series` uses DB-scoped baselines for deterministic
  repeatability, not strict cross-database equality

## Supported Backends

- `arcadedb_sql`
- `arcadedb_cypher`
- `neo4j`
- `ladybug` / `ladybugdb`
- `graphqlite`
- `duckdb`
- `sqlite`
- `python_memory`

## Run

From `bindings/python/examples`:

```bash
python 09_stackoverflow_graph_oltp.py \
  --dataset stackoverflow-tiny \
  --db arcadedb_cypher \
  --threads 1 \
  --transactions 10000 \
  --batch-size 10000 \
  --mem-limit 4g \
  --verify-single-thread-series
```

## Key Options

- `--dataset`: dataset size from `stackoverflow-tiny` through `stackoverflow-full`
- `--db`: graph backend to test
- `--threads`: worker threads for the OLTP run
- `--transactions`: number of OLTP operations
- `--batch-size`: preload XML insert batch size
- `--mem-limit`: Docker and JVM memory budget
- `--server-fraction`: for Neo4j, fraction of the total CPU/memory budget reserved for the server process
- `--sqlite-profile`: SQLite tuning profile when using SQLite-backed paths

## Result Notes

- `du_mib` is real post-run filesystem usage
- `disk_after_*` fields are benchmark-reported logical size counters
- Neo4j runs also record `client_rss_peak_*` and `server_rss_peak_*`, while `rss_peak_*`
  represents the combined observed peak
- Per-operation latency is derived from `latency_summary.ops.{50,95,99}` with values
  converted from seconds to milliseconds
- Operation totals come from `op_counts`

## Validation Checklist

After loading the graph, validate at least the following:

- every vertex type has the expected count
- every edge type has the expected count
- all vertex `Id` indexes exist
- `COMMENTED_ON` only targets `Question`
- `COMMENTED_ON_ANSWER` only targets `Answer`
- `LINKED_TO` only connects `Question -> Question`
