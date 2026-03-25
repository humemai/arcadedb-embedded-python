# Example 10: Stack Overflow Graph (OLAP)

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/examples/10_stackoverflow_graph_olap.py){ .md-button }

This example builds a Stack Overflow property graph and runs a fixed OLAP query suite
using OpenCypher.

## Overview

Example 10 is the graph-oriented OLAP benchmark in the Python examples set.

- Builds the Stack Overflow graph with directed edge types
- Runs a fixed analytical query suite across the selected backend
- Records load/index/query timings, disk usage, and peak RSS
- Supports repeated query runs and single-query filtering

## Graph Projection Assumptions

This query suite runs on the same projected graph model used by [Example 09](./09_stackoverflow_graph_oltp.md).

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
- there is no generic `Post` vertex type in this graph model

### Tag Parsing Rule

Question tags are parsed by:

1. replacing `><` with a separator
1. stripping `<` and `>`
1. splitting into tag names

## Graph Query Suite

The source defines ten fixed OpenCypher queries in `QUERY_DEFS`. The same query text
is reused across the supported backends for this example.

### Q1. Top Askers

```cypher
MATCH (u:User)-[:ASKED]->(q:Question)
RETURN u.Id AS user_id, u.DisplayName AS name, count(q) AS questions
ORDER BY questions DESC, user_id ASC
LIMIT 10
```

### Q2. Top Answerers

```cypher
MATCH (u:User)-[:ANSWERED]->(a:Answer)
RETURN u.Id AS user_id, u.DisplayName AS name, count(a) AS answers
ORDER BY answers DESC, user_id ASC
LIMIT 10
```

### Q3. Top Accepted Answerers

```cypher
MATCH (q:Question)-[:ACCEPTED_ANSWER]->(a:Answer)
MATCH (u:User)-[:ANSWERED]->(a)
WITH u, count(*) AS accepted
RETURN u.Id AS user_id, u.DisplayName AS name, accepted
ORDER BY accepted DESC, user_id ASC
LIMIT 10
```

### Q4. Top Tags By Question Count

```cypher
MATCH (q:Question)-[:TAGGED_WITH]->(t:Tag)
RETURN t.Id AS tag_id, t.TagName AS tag, count(q) AS questions
ORDER BY questions DESC, tag_id ASC
LIMIT 10
```

### Q5. Tag Co-Occurrence

```cypher
MATCH (q:Question)-[:TAGGED_WITH]->(t1:Tag)
MATCH (q)-[:TAGGED_WITH]->(t2:Tag)
WHERE t1.Id < t2.Id
RETURN t1.TagName AS tag1, t2.TagName AS tag2, count(*) AS cooccurs
ORDER BY cooccurs DESC, tag1 ASC, tag2 ASC
LIMIT 10
```

### Q6. Top Questions By Score

```cypher
MATCH (q:Question)
RETURN q.Id AS question_id, q.Score AS score
ORDER BY score DESC, question_id ASC
LIMIT 10
```

### Q7. Questions With Most Answers

```cypher
MATCH (q:Question)-[:HAS_ANSWER]->(a:Answer)
RETURN q.Id AS question_id, count(a) AS answers
ORDER BY answers DESC, question_id ASC
LIMIT 10
```

### Q8. Asker-Answerer Pairs

```cypher
MATCH (asker:User)-[:ASKED]->(q:Question)-[:HAS_ANSWER]->(a:Answer)<-[:ANSWERED]-(answerer:User)
WHERE asker.Id <> answerer.Id
WITH asker, answerer, count(*) AS interactions
RETURN asker.Id AS asker_id, answerer.Id AS answerer_id, interactions
ORDER BY interactions DESC, asker_id ASC, answerer_id ASC
LIMIT 10
```

### Q9. Top Badges

```cypher
MATCH (:User)-[:EARNED]->(b:Badge)
RETURN b.Name AS badge, count(*) AS earned
ORDER BY earned DESC, badge ASC
LIMIT 10
```

### Q10. Top Questions By Total Comments

```cypher
MATCH (q:Question)
OPTIONAL MATCH (c1:Comment)-[:COMMENTED_ON]->(q)
WITH q, count(c1) AS direct_comments
OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)
OPTIONAL MATCH (c2:Comment)-[:COMMENTED_ON_ANSWER]->(a)
WITH q, direct_comments, count(c2) AS answer_comments
RETURN q.Id AS question_id, direct_comments + answer_comments AS total_comments
ORDER BY total_comments DESC, question_id ASC
LIMIT 10
```

## Schema Used By The Query Suite

The queries assume these indexed vertex types:

- `User`
- `Question`
- `Answer`
- `Tag`
- `Badge`
- `Comment`

and these edge types:

- `ASKED`
- `ANSWERED`
- `HAS_ANSWER`
- `ACCEPTED_ANSWER`
- `TAGGED_WITH`
- `COMMENTED_ON`
- `COMMENTED_ON_ANSWER`
- `EARNED`
- `LINKED_TO`

The source creates unique `Id` indexes on all six vertex types before the query suite runs.

## Current Repository Guidance

- ArcadeDB graph preload now uses `GraphBatch` for the initial node and edge load,
  driven by the configured `--threads` value
- `GraphBatch` is the repository's recommended bulk graph ingest path from Python
- ArcadeDB query execution is cypher-only in this example path
- Traversal expectations should be interpreted as directed

## Supported Backends

- `arcadedb_sql`
- `arcadedb_cypher`
- `ladybug` / `ladybugdb`
- `graphqlite`
- `duckdb`
- `sqlite`
- `python_memory`

## Run

From `bindings/python/examples`:

```bash
python 10_stackoverflow_graph_olap.py \
  --dataset stackoverflow-tiny \
  --db arcadedb_cypher \
  --batch-size 10000 \
  --query-runs 3 \
  --query-order shuffled \
  --mem-limit 4g
```

## Key Options

- `--dataset`: dataset size from `stackoverflow-tiny` through `stackoverflow-full`
- `--db`: graph backend to test
- `--batch-size`: preload XML insert batch size
- `--query-runs`: measured executions per query
- `--query-order`: `fixed` or `shuffled`
- `--only-query`: run a single named query
- `--manual-checks`: enable additional validation queries
