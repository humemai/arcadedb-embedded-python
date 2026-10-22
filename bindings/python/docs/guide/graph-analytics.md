# Graph Analytics Guide

!!! warning "Known engine issues"
    Known bugs that can return a wrong answer or refuse a lookup, and the releases that fixed earlier ones, are listed on
    [Known Engine Issues](known-issues.md).

ArcadeDB ships two things for whole-graph questions such as "who matters most" or
"which accounts form one cluster". The first is the `algo.*` procedures, dozens of
them, which you call from openCypher. The second is the **Graph Analytical View** (GAV),
an in-memory compressed copy of the graph (a CSR, compressed sparse row) that the
procedures and some traversals read instead of walking records one at a time.

Neither one has a Python method. Both are reached with `db.command()` (the DDL) and
`db.query("opencypher", ...)` (the procedures), which is the
[DSL-first](../api-access-methods.md) path.

Every example below runs against the graph in the next section, and the test that
runs them is `tests/test_guide_graph_analytics.py`. They were measured on engine
26.10.2.

## The example graph

Six people and six `Follows` edges. `ada`, `bob`, `cy` and `dee` follow each other in a
loop; `eve` follows `fay` and is cut off from the rest.

```python
import arcadedb_embedded as arcadedb

db = arcadedb.create_database("./analytics_db")

db.command("sql", "CREATE VERTEX TYPE Person")
db.command("sql", "CREATE EDGE TYPE Follows")
db.command("sql", "CREATE PROPERTY Follows.weight DOUBLE")

edges = [
    ("ada", "bob", 1.0),
    ("bob", "cy", 1.0),
    ("ada", "cy", 5.0),
    ("cy", "dee", 1.0),
    ("dee", "ada", 1.0),
    ("eve", "fay", 1.0),
]
with db.transaction():
    for name in ["ada", "bob", "cy", "dee", "eve", "fay"]:
        db.command("sql", "CREATE VERTEX Person SET name = ?", name)
    for src, dst, weight in edges:
        db.command("sql", "CREATE EDGE Follows FROM (SELECT FROM Person WHERE name = ?) TO (SELECT FROM Person WHERE name = ?) SET weight = ?", src, dst, weight)
```

## The procedures work without a view

`algo.*` procedures run on any graph. Without a view they read the vertices and edges
from storage; with a view that covers the graph they read the CSR. The answers are the
same, so you can start without a view and add one when a call gets slow.

### PageRank

```python
rows = db.query("opencypher", "CALL algo.pagerank() YIELD node, score RETURN node.name AS name, round(score * 1000) / 1000.0 AS score ORDER BY score DESC, name").to_list()
# [{'name': 'cy', 'score': 0.259}, {'name': 'dee', 'score': 0.254},
#  {'name': 'ada', 'score': 0.25}, {'name': 'bob', 'score': 0.14},
#  {'name': 'fay', 'score': 0.063}, {'name': 'eve', 'score': 0.034}]
```

Options go in one map. `tolerance`, `weightProperty` and `direction` (`OUT`, `IN` or
`BOTH`; default `OUT`) are the other keys.

```python
db.query("opencypher", "CALL algo.pagerank({dampingFactor: 0.9, maxIterations: 50}) YIELD node, score RETURN node.name AS name ORDER BY score DESC, name LIMIT 1").to_list()
# [{'name': 'cy'}]
```

### Connected components

`algo.wcc()` ignores edge direction; `algo.scc()` respects it.

```python
db.query("opencypher", "CALL algo.wcc() YIELD node, componentId RETURN componentId, collect(node.name) AS members").to_list()
# two components: ada, bob, cy, dee  and  eve, fay
db.query("opencypher", "CALL algo.scc() YIELD node, componentId RETURN componentId, collect(node.name) AS members").to_list()
# three: ada, bob, cy, dee  and  eve  and  fay
```

The order of the `members` list and the numbering of `componentId` are not defined;
sort them in Python before you compare.

### Breadth-first search

`algo.bfs(start, relationshipTypes, direction, maxDepth)` takes a vertex, so bind it
with `MATCH` first.

```python
db.query("opencypher", "MATCH (a:Person {name: 'ada'}) CALL algo.bfs(a, 'Follows', 'OUT', 3) YIELD node, depth RETURN node.name AS name, depth ORDER BY depth, name").to_list()
# [{'name': 'bob', 'depth': 1}, {'name': 'cy', 'depth': 1}, {'name': 'dee', 'depth': 2}]
```

The start vertex is not in the output.

### Weighted shortest path

`algo.dijkstra(start, end, relationshipType, weightProperty, direction)` returns the
path and its total weight. The direct `ada -> cy` edge costs 5, the route through `bob`
costs 2, so the cheap route wins.

```python
db.query("opencypher", "MATCH (a:Person {name: 'ada'}), (d:Person {name: 'dee'}) CALL algo.dijkstra(a, d, 'Follows', 'weight', 'OUT') YIELD path, weight RETURN [n IN nodes(path) | n.name] AS names, weight").to_list()
# [{'names': ['ada', 'bob', 'cy', 'dee'], 'weight': 3.0}]
```

### Degree and triangles

```python
db.query("opencypher", "CALL algo.degree() YIELD node, inDegree, outDegree RETURN node.name AS name, inDegree, outDegree ORDER BY name").to_list()
# ada 1/2, bob 1/1, cy 2/1, dee 1/1, eve 0/1, fay 1/0  (in/out)
db.query("opencypher", "CALL algo.triangleCount() YIELD node, triangles RETURN node.name AS name, triangles ORDER BY name").to_list()
# ada 2, bob 1, cy 2, dee 1, eve 0, fay 0
```

`algo.triangleCount` counts triangles with edge direction ignored.

### Communities and centrality

```python
db.query("opencypher", "CALL algo.louvain() YIELD node, communityId RETURN communityId, collect(node.name) AS members").to_list()
# eve and fay share a community; none of the other four is in it
db.query("opencypher", "CALL algo.betweenness() YIELD node, score RETURN node.name AS name, score ORDER BY score DESC, name").to_list()
# eve and fay score 0.0; no score is above 0.15 on this graph
```

Also run on this graph: `algo.kcore()` and `algo.labelPropagation()`. The engine's
procedure list is much longer (similarity, centrality, flow, embeddings); see the
engine reference below for the names and arguments, and run an unfamiliar one on a
small graph before you rely on it.

## Graph Analytical Views

A view is a named, persisted definition plus an in-memory CSR that is built from it.

```python
db.command("sql", "CREATE GRAPH ANALYTICAL VIEW social VERTEX TYPES (Person) EDGE TYPES (Follows) PROPERTIES (name) EDGE PROPERTIES (weight) UPDATE MODE SYNCHRONOUS")
# {'operation': 'create graph analytical view', 'name': 'social', 'created': True}
```

| Clause | Meaning |
| --- | --- |
| `VERTEX TYPES (...)`, `EDGE TYPES (...)` | What the view contains. Leave a clause out to include every type. |
| `PROPERTIES (...)` | Vertex properties copied into the view. Omit to copy all, `PROPERTIES ()` to copy none. |
| `EDGE PROPERTIES (...)` | Edge properties copied in, for weighted algorithms. |
| `UPDATE MODE OFF`, `SYNCHRONOUS`, `ASYNCHRONOUS` | How the view follows later writes (below). Default `OFF`. |
| `COMPACTION THRESHOLD n` | How many pending changes the view collects before it folds them into the CSR. |
| `IF NOT EXISTS` | Returns `created: False` instead of failing when the name is taken. |

`CREATE` returns at once and the CSR is built in the background. Read the state from
`schema:graphAnalyticalViews`:

```python
import time

def wait_ready(db, name="social"):
    while True:
        row = db.query("sql", "SELECT status, nodeCount, edgeCount, updateMode FROM schema:graphAnalyticalViews WHERE name = 'social'").first()
        if row.get("status") == "READY":
            return row.to_dict()
        time.sleep(0.05)

wait_ready(db)
# {'status': 'READY', 'nodeCount': 6, 'edgeCount': 6, 'updateMode': 'SYNCHRONOUS'}
```

A view that is not `READY` does not serve a call: the `OFF` example below shows a
procedure answering correctly from the live graph while its view is `STALE`.

### Update modes

| Mode | After a commit that changes the graph |
| --- | --- |
| `SYNCHRONOUS` | The change is in the view when `commit()` returns. Slows commits. |
| `ASYNCHRONOUS` | The view folds the change in afterwards: `status` shows `BUILDING`, then `READY`. Poll for it as above. |
| `OFF` | The view is marked `STALE` and keeps its old counts. Procedures scan the live graph, so answers stay correct and the speed-up is gone until you rebuild. |

```python
db.command("sql", "ALTER GRAPH ANALYTICAL VIEW social UPDATE MODE OFF")
with db.transaction():
    db.command("sql", "CREATE VERTEX Person SET name = 'hal'")
# the view now reports status STALE and still counts the old 7 vertices
db.query("opencypher", "CALL algo.wcc() YIELD node RETURN count(node) AS n").to_list()
# [{'n': 8}]   the call scanned the live graph, so it sees 'hal'
db.command("sql", "REBUILD GRAPH ANALYTICAL VIEW social")
# status READY again, nodeCount 8
```

The `ASYNCHRONOUS` form, with the compaction setting:

```python
db.command("sql", "CREATE GRAPH ANALYTICAL VIEW social VERTEX TYPES (Person) EDGE TYPES (Follows) UPDATE MODE ASYNCHRONOUS COMPACTION THRESHOLD 500")
```

`ALTER GRAPH ANALYTICAL VIEW name COMPACTION THRESHOLD n` changes the other setting.
After a stretch in `OFF`, `REBUILD` before you rely on the speed-up again.

### What a ready view serves

Whole-graph `algo.*` calls use the view when it is `READY` and covers **every** vertex
and edge type of the database. A view that leaves a type out (say, a `City` type next
to `Person`) is not used for those calls: they scan and still count the `City`
vertices. For a call that names its edge types (`algo.bfs(a, 'Follows', ...)`) the view
only has to cover those.

The engine also has view-backed paths for some counts and traversals (the SQL
`shortestPath` and `astar` functions, for one), but this page does not rely on them:
`EXPLAIN` of a count prints `COUNT CHAIN PATHS (CSR count-push-down)` with the view and
without it, so the plan text does not show whether a view served the call. Compare
timings on your own graph instead (a laptop timing needs a quiet machine and several
repeats), and expect the same answers either way.

A view that covers only `Person` next to a `City` type:

```python
db.command("sql", "CREATE GRAPH ANALYTICAL VIEW people VERTEX TYPES (Person) EDGE TYPES (Follows)")
db.query("opencypher", "CALL algo.degree() YIELD node RETURN count(node) AS n").to_list()
# counts the City vertices too: the view is not used for this call
```

### Drop

```python
db.command("sql", "DROP GRAPH ANALYTICAL VIEW social")
# {'operation': 'drop graph analytical view', 'name': 'social', 'dropped': True}
db.command("sql", "DROP GRAPH ANALYTICAL VIEW IF EXISTS social")  # no error if missing
```

`CREATE GRAPH ANALYTICAL VIEW IF NOT EXISTS social` answers `created: False` for a name
that is taken, where plain `CREATE` raises `ArcadeDBError` ("already exists"). An
unknown mode in `ALTER ... UPDATE MODE` and a `DROP` of a missing view raise too.

## Caveats

- A view is memory. `memoryUsageBytes` in `schema:graphAnalyticalViews` shows its size;
  create one for the types you query, not for everything.
- `SYNCHRONOUS` costs write throughput on every commit; `ASYNCHRONOUS` can lag behind
  the commit, so do not read your own write through a view without polling.
- After a database reopen a view can answer `READY` with `nodeCount` 0 and `edgeCount` 0
  until the first query that uses it, so the `wait_ready` loop above can return a
  zero row. Run one query through the view (a `MATCH` or an `algo.*` call), then poll
  the row again. Seen in `examples/21_graph_analytical_view_sql.py` on the 26.11.1
  main engine; the query and the counts match the records, only the row lags.
- `OFF` is the default. A view you create without `UPDATE MODE` goes stale on the
  first write.
- Left out of this page because they were not run here: contraction hierarchies
  (`CCH (...)` and `algo.cchShortestPath`), what a view serves inside a transaction
  that has uncommitted changes, whether a weighted PageRank uses a view, and whether a
  reopened view is read from its persisted file or rebuilt.

## References

- [ArcadeDB documentation](https://docs.arcadedb.com/) for the full `algo.*` list and
  the Graph Analytical View chapter.
- The grammar of the statements:
  [`SQLParser.g4`](https://github.com/ArcadeData/arcadedb/blob/main/engine/src/main/antlr4/com/arcadedb/query/sql/grammar/SQLParser.g4)
  (search for `GRAPH ANALYTICAL VIEW`).
- [Graph Operations](graphs.md) for building the graph, and
  [Queries](core/queries.md) for the two query languages.
