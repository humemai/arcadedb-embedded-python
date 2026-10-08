# Known Engine Issues

These are ArcadeDB engine bugs that can return a wrong answer, store a wrong value, change
the wrong rows, or refuse a read or a write. The entries about Ctrl-C and about memory held by
results are not engine bugs: they are in JPype, the library that connects Python to the engine. Each entry names the versions
it was measured on, what you see, a workaround that was checked on the same reproduction, and
the release that fixes it once there is one. Entries leave this page when the fix ships in a
release these bindings package.
An entry with a `Tests:` line has a test of its workaround. While the bug is open it also has a
strict `xfail` test of the engine behavior, which starts failing the suite when a fix reaches the
engine the suite runs on; the test is then made a plain regression test. An entry for a bug that
is fixed on upstream's main but not yet in a release says so, and its regression tests fail on the
released wheel until the next release ships.

## Ctrl-C during an interruptible Java wait can raise `InterruptedException`, not `KeyboardInterrupt`

JPype 1.7.1, the newest release and the one a fresh install gets (the package declares
`jpype1>=1.5.0`); measured through the bindings with a 26.10.1 snapshot of the engine, and again
on JPype master (874a197, 2026-10-06), where it is unchanged.
Open. This is a race in JPype, not in ArcadeDB; it is reported as
[jpype-project/jpype#1496](https://github.com/jpype-project/jpype/issues/1496).

With the default `interrupt=False`, JPype handles SIGINT in Java. Its handler first interrupts
the main thread with `Thread.interrupt()` and only then tells Python that Ctrl-C arrived. A
Java call that waits in an interruptible way wakes up between the two steps, and JPype finds
no Python interrupt yet. `Thread.sleep()` and `Object.wait()` do, and so does the engine's
`wait_completion()` on an async executor (its Java source handles `InterruptedException`;
this one was not measured). Instead of a `KeyboardInterrupt` from the call you see one of:

- `java.lang.InterruptedException` raised from the call, and the `KeyboardInterrupt` a
  moment later in whatever statement runs next: a `finally` block, an `atexit` hook such as
  the bindings' own close of open databases. The program ends with exit status 1 or by
  SIGINT, with a traceback that names `InterruptedException`.
- `RuntimeError: Fatal error occurred`, with `Fatal error in exception handling` and
  `Handling: java.lang.InterruptedException: sleep interrupted` on stderr. `finally` blocks
  and `atexit` hooks still ran.

SIGINT at a random moment of a 1.5 s `Thread.sleep()` on two pinned cores gave one of these in
14 of 400 interrupts (3.5%) with the cores idle, and in 26 of 200 (13%) with two busy loops
sharing the two cores. `Object.wait()` with the busy loops: 42 of 200 (21%). A Python loop,
and a Java call that ignores `Thread.interrupt()` (a socket `accept()` with a timeout, which
returns with its `KeyboardInterrupt` when it times out), had no failure in 150 interrupts each
with the busy loops.

Wait in Python instead, so the main thread is never inside the Java wait: run the call in a
daemon thread and poll it with `join`. Ctrl-C then raises `KeyboardInterrupt` in the main
thread within the poll interval, and 150 of 150 interrupts with the busy loops did, with a
`Thread.sleep()` in the worker:

```python
import threading

worker = threading.Thread(target=async_exec.wait_completion, daemon=True)
worker.start()
while worker.is_alive():
    worker.join(0.1)  # Ctrl-C raises KeyboardInterrupt here, never inside the Java wait
```

The worker keeps waiting after Ctrl-C and ends with the process. A Python wait loop such as
`while True: time.sleep(1)`, as in the server examples, is not affected.

The same handler has a second problem with `interrupt=False` when Python has no handler of its
own for SIGTERM, which is the normal state of a script: `kill -TERM` crashes the process with a
SIGSEGV in `PyErr_SetInterruptEx` (exit status -6 and an `hs_err_pid*.log`) instead of stopping
it ([jpype-project/jpype#1497](https://github.com/jpype-project/jpype/issues/1497); measured on
JPype 1.7.1 and master, Temurin 21 and 25, 10 of 10 attempts each, and through the bindings, 3
of 3). Register a handler after the first database is opened, which is after the JVM has
started; the process then stops at once, 3 of 3 through the bindings. A handler registered
before the JVM starts also avoids the crash, but runs only when the main thread next executes
Python code, so a blocking call such as `time.sleep(30)` delays it until the call returns:

```python
import signal
import sys

db = arcadedb.create_database("./mydb")
signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
```

Tests: `tests/test_sigint.py` covers a Python loop and a Java call that Ctrl-C cannot wake.
It has no test of the waits above, because the failure is random (humemai/arcadedb-embedded-python#179).


## `Result.get()` keeps a Python object for every number that comes back from Java

JPype 1.7.1, the newest release and the one a fresh install gets (the package declares
`jpype1>=1.5.0`; 1.6.0 leaks too, [jpype-project/jpype#1379](https://github.com/jpype-project/jpype/issues/1379));
measured through the bindings on the 26.10.1 wheel with a Python 3.12 process. Fixed on JPype
master (874a197, 2026-10-06, not in a release yet), which leaks nothing in the same runs. This is a
leak in JPype, not in ArcadeDB.

JPype 1.7.1 keeps one Python object (about 32 bytes) for every number that comes back from Java
as a boxed `Long`, `Integer`, `Short`, `Byte`, `Float`, or `Double`, and never frees it before the
process ends. Through the bindings that is about 3.9 objects per row for a scan of nine
properties read with `Result.get()` or `Result.to_dict()`, about 125 bytes per row, or 1.2 GB
for 10 million rows. Small integers and booleans are cached by Python and do not count, so
only values above 256 and floats leak. `to_list()` and `iter_dicts()` read numbers from
JSON text, as `to_json_list()` and `to_columns()` do, so plain numbers do not leak there
(only a value the transport hands over as the engine's own object, such as a `float[]`,
is a number JPype boxes). The 3.9 objects per row above were measured when `to_list()` and
`iter_dicts()` converted each value in Python.

Read a large result with `to_list()`, `iter_dicts()`, `to_json_list()`, or `to_columns()`
rather than a `get()` per value, or upgrade JPype to the release that carries the fix when it ships. Count the live Python
objects with `sys.getallocatedblocks()` before and after a read to see whether your path is
affected.

## An openCypher one-hop `count(*)` answers 0 for edges loaded with `light_edges=True` into a type that is not `LIGHTWEIGHT`

ArcadeDB [#9378](https://github.com/ArcadeData/arcadedb/issues/9378); measured through the
bindings on the 26.10.1 wheel (the official jars are upstream build d36b4ca3ae), and in Java on that
build and on upstream main 246821a605, on Temurin 21 and 25, with the same answers. Fixed upstream
for new loads by [ArcadeData/arcadedb#9383](https://github.com/ArcadeData/arcadedb/pull/9383), merged
on 2026-10-07 for ArcadeDB 26.11.1, which is not released yet. The 26.10.1 wheel still has the bug.
The fix does not repair a database that an older version already wrote.

`db.graph_batch(light_edges=True)` writes each edge that has no properties as a light edge, one
with no record of its own. When the edge type is an ordinary one (`CREATE EDGE TYPE E`, not
`CREATE EDGE TYPE E LIGHTWEIGHT`), a `MATCH` of one hop that ends in `RETURN count(*)` is answered
by the count push-down from the number of records in the type, and the type holds none. On three
vertices a, b, and c with the edges a to b and b to c, loaded that way on 26.10.1:

```python
db.command("sql", "CREATE VERTEX TYPE V")
db.command("sql", "CREATE EDGE TYPE E")
with db.graph_batch(light_edges=True) as batch:
    a, b, c = batch.create_vertices("V", 3)
    batch.new_edge(a, "E", b)
    batch.new_edge(b, "E", c)

db.query("opencypher", "MATCH (a:V)-[:E]->(b:V) RETURN count(*) AS n").first().get("n")  # 0, not 2
```

`EXPLAIN` of that query shows `CONSTANT COUNT (0: the pattern has an empty or undeclared type)`.
The edges are in the graph: the same pattern returning rows gives 2, the two-hop count gives 1, and
SQL `out('E')` finds both. The wrong count does not depend on the session: it is the same after the
database is closed and opened again. It also holds for `<-[:E]-`, for an undirected `-[:E]-`, and
for unlabelled nodes. A type declared `LIGHTWEIGHT`, a batch with `light_edges=False`, and a
batch that does not pass `light_edges` all counted 2 in the same run.

**In 26.11.1** the batch refuses the load. `new_edge` raises `ArcadeDBError`, and nothing is
written for that edge:

```
Failed to buffer batch edge 'E': java.lang.IllegalArgumentException: Edge type 'E' does not declare
LIGHTWEIGHT, so a batch built with withLightEdges(true) cannot store its property-less edges as
light edges. Declare the type with CREATE EDGE TYPE E LIGHTWEIGHT, or build the batch without
withLightEdges(true)
```

Edges with properties are not light edges and still load into an undeclared type. On the 26.11.1
snapshot, the load above with `CREATE EDGE TYPE E LIGHTWEIGHT`, with `light_edges=False`, and
without the option all counted 2.

On 26.10.1, do not pass `light_edges=True` for an edge type that is not declared `LIGHTWEIGHT`:
declare the type `LIGHTWEIGHT` before the load, or leave the option out. A `LIGHTWEIGHT` type
refuses an edge with properties (`IllegalArgumentException`).

**A database that was already loaded that way stays wrong on 26.10.1.** The 26.11.1 snapshot counts
it right since upstream #9409 (closing #9389): its count push-down now finds the light edges in an
undeclared type (checked with two light edges written by the engine's `newLightEdge`: 2 on the
snapshot, 0 on 26.10.1). On 26.10.1, count in a way that does not take the push-down: put the
variables through a `WITH`, count a node, or name the relationship and count that. All three counted
2 on the 26.10.1 wheel and on the snapshot:

```python
db.query("opencypher", "MATCH (a:V)-[:E]->(b:V) WITH a, b RETURN count(*) AS n")
db.query("opencypher", "MATCH (a:V)-[:E]->(b:V) RETURN count(b) AS n")
db.query("opencypher", "MATCH (a:V)-[r:E]->(b:V) RETURN count(r) AS n")
```

Tests: `tests/test_light_edge_and_view_known_issues.py` checks the workarounds, the refusal, and the
cases that are not affected. The refusal test is plain and passes on the engine the suite builds
against (upstream's 26.11.1 snapshot, which has the fix) and fails on the 26.10.1 wheel, and so does
the test of the count over light edges that an older version wrote (a strict `xfail` until #9409).
Remove the 26.10.1 part of this entry when the release that carries the fix ships.


## An openCypher count with a pattern predicate over an edge type that a Graph Analytical View does not list is wrong

ArcadeDB [#9377](https://github.com/ArcadeData/arcadedb/issues/9377); measured through the
bindings on the 26.10.1 wheel (the official jars are upstream build d36b4ca3ae), and in Java on that
build and on upstream main 246821a605, on Temurin 21 and 25, with the same answers. Fixed upstream by
[ArcadeData/arcadedb#9383](https://github.com/ArcadeData/arcadedb/pull/9383), merged on 2026-10-07
for ArcadeDB 26.11.1, which is not released yet: a predicate over an edge type the view does not
list now reads the record. The 26.10.1 wheel still has the bug, and the workarounds below are
still needed on it.

A Graph Analytical View copies the structure of the vertex and edge types it lists
(`CREATE GRAPH ANALYTICAL VIEW ... VERTEX TYPES (...) EDGE TYPES (...)`), and a query that the
view can serve is answered from the copy. A view that lists the edge types of the chain in a
`MATCH` but not an edge type that a pattern predicate in its `WHERE` names is still used for an
aggregate, and the predicate is then checked against the copy, where the unlisted type has no
edges. On the vertices x, y, and z of type `V` with the edges x `-E->` y, x `-F->` y, and
y `-E->` z, and a view over `V` and `E`, the pair (x, y) has an `F` edge, so the right count of each
query below is 1. The 26.10.1 view answered:

| Query over the view that lists `E` only | Counted | Right |
| --- | --- | --- |
| `MATCH (a:V)-[:E]->(b:V) WHERE NOT (a)-[:F]->(b) RETURN count(*)` | 2 | 1 |
| `MATCH (a:V)-[:E]->(b:V) WHERE (a)-[:F]->(b) RETURN count(*)` | 0 | 1 |
| `MATCH (a:V)-[:E]->(b:V) WHERE NOT (a)-[:F]->(b) RETURN count(a)` | 2 | 1 |

`EXPLAIN` of the first shows `GAV ONE-HOP SCAN` with the predicate as its filter. The same
predicates counted right with no view, with a view that lists `F` as well as `E`, behind a `WITH`,
and in a query that returns rows instead of an aggregate. The query returns no error and no
warning, only the wrong number. On the 26.11.1 snapshot all three counted 1, with the view still in
the plan.

On 26.10.1, put the variables through a `WITH` before the `WHERE`, as for the count push-down
entries below. That keeps the query off the view, and counted 1 for both forms above. It gives up
the view's speed for that query. Or list every edge type that your pattern predicates name when you
create the view (`EDGE TYPES (E, F)`), which counted 1 as well:

```python
db.query(
    "opencypher",
    "MATCH (a:V)-[:E]->(b:V) WITH a, b WHERE NOT (a)-[:F]->(b) RETURN count(*) AS n",
)
```

Tests: `tests/test_light_edge_and_view_known_issues.py` checks both workarounds and the cases that
are not affected, and has plain regression tests of the right counts. They pass on the engine the
suite builds against (upstream's 26.11.1 snapshot, which has the fix) and fail on the 26.10.1
wheel. Remove this entry when the release that carries the fix ships.


## An openCypher count with a negated pattern in a chain is wrong when the far end has another label or the pattern has a property map

ArcadeDB [#9277](https://github.com/ArcadeData/arcadedb/issues/9277) and
[#9278](https://github.com/ArcadeData/arcadedb/issues/9278); measured through the bindings on
26.10.1 (the official jars are upstream build d36b4ca3ae), and in Java on that build, on 26.9.1, and on
5a90b0f52a, on Temurin 21 and 25, with the same answers. Both are fixed upstream by
[ArcadeData/arcadedb#9288](https://github.com/ArcadeData/arcadedb/pull/9288), merged on 2026-10-06 for
ArcadeDB 26.11.1, which is not released yet. The 26.10.1 wheel still has both bugs.

A `MATCH` chain of two or more hops that ends in `RETURN count(*)` and has a negated pattern
predicate between two of its nodes (`WHERE NOT (a)-[:R]-(c)`, alone or with `AND a <> c` or
`AND id(a) <> id(c)`) is answered by a count push-down; `EXPLAIN` lists `COUNT ANTI-JOIN
CHAIN`. It counts wrong in two cases:

- **Another label at the far end (#9277).** On the single path
  `(x0:Person)-[:KNOWS]-(x1:Person)-[:KNOWS]-(y0:Employee)-[:HAS_INTEREST]->(t:Tag)`, in which
  `x0` and `y0` are not connected, the chain `(p1:Person)...(p2:Person)...(p3:Employee)...(t:Tag)`
  with `WHERE NOT (p1)-[:KNOWS]-(p3)` counted 0 where the answer is 1. The same holds with
  `AND p1 <> p3`. A chain whose nodes all have the same label, and a far end that is a sub type
  of the first labels, gave the right count in every case I ran. In 26.10.1, which carries
  upstream #9271, `id(p1) <> id(p3)` takes the same push-down, so that spelling, which counted 1
  before, now counts 0.
- **A property map on the pattern's relationship (#9278).** The push-down drops it. With an edge
  `x -[:K {w: 0}]-> z`, `WHERE NOT (x)-[:K {w: 1}]->(z)` counted 0 where the answer is 1,
  because no edge with `w = 1` connects them; it was counted as `NOT (x)-[:K]->(z)`.

Put the variables through a `WITH` before the `WHERE`. That keeps the query off the push-down,
and the row pipeline counted the right number in every case above. It gives up the push-down's
speed for that query:

```python
chain = "MATCH (p1:Person)-[:KNOWS]-(p2:Person)-[:KNOWS]-(p3:Employee)-[:HAS_INTEREST]->(t:Tag) "
n = (
    db.query(
        "opencypher",
        chain + "WITH p1, p2, p3, t WHERE NOT (p1)-[:KNOWS]-(p3) RETURN count(*) AS n",
    )
    .first()
    .get("n")
)
```

Tests: `tests/test_count_pushdown_known_issues.py` checks the `WITH` workaround and the cases
that are not affected, and has plain regression tests of the right counts. They pass on the
engine the suite builds against (upstream's 26.11.1 snapshot, which has the fix) and fail on the
26.10.1 wheel. Remove this entry when the release that carries the fix ships.


## An openCypher count with a negated pattern is wrong for other shapes of the chain

ArcadeDB [#9290](https://github.com/ArcadeData/arcadedb/issues/9290); measured through the
bindings on the 26.10.1 wheel, and in Java on 26.10.1, on upstream main cbf701d66e, and on the
head of the upstream fix for the entry above (#9288, head 7d69d5f534, merged for 26.11.1), on Temurin 21
and 25, with the same answers. Fixed upstream by
[ArcadeData/arcadedb#9299](https://github.com/ArcadeData/arcadedb/pull/9299), merged on 2026-10-06
for ArcadeDB 26.11.1, which is not released yet: the push-down now applies only to the one shape
the engine verifies against the row pipeline, and every other chain takes the row pipeline. The
26.10.1 wheel still has the bug, and the `WITH` workaround below is still needed on it.

The count push-down of the entry above (`EXPLAIN` lists `COUNT ANTI-JOIN CHAIN`) is also wrong
for chains that are not the two-hop shape it is written for. On four people with `KNOWS` a-b,
b-c, c-d, and a-c, each interested in one tag, these counted more than the right number, with
the push-down in the plan:

| Chain and `WHERE` | Counted | Right |
| --- | --- | --- |
| three `KNOWS` hops, `NOT (p0)-[:KNOWS]-(p2) AND p0 <> p2` | 6 | 2 |
| two hops and a tag, `NOT (p0)-[:KNOWS]-(p2) AND p1 <> p2` (an inequality between other nodes) | 12 | 4 |
| the same chain, `NOT (p0)-[:KNOWS]-(p2)` (no inequality) | 12 | 4 |
| three `KNOWS` hops, `NOT (p1)-[:KNOWS]-(p3) AND p1 <> p3` (the pattern not at the first node) | 10 | 2 |
| an unlabelled middle node, `NOT (p2)-[:KNOWS]-(p0) AND p2 <> p0` | 18 | 4 |

The two-hop chain with a label on every node, the negated pattern between its first and third
node, and the inequality between the same two (the shape of the LSQB benchmark's Q9) counted
right (4). Put the variables through a `WITH` before the `WHERE`, as above; the row pipeline
counted the right number for every shape in the table:

```python
chain = "MATCH (p0:Person)-[:KNOWS]-(p1:Person)-[:KNOWS]-(p2:Person)-[:HAS_INTEREST]->(t:Tag) "
n = (
    db.query(
        "opencypher",
        chain + "WITH p0, p1, p2, t WHERE NOT (p0)-[:KNOWS]-(p2) RETURN count(*) AS n",
    )
    .first()
    .get("n")
)
```

Tests: `tests/test_count_pushdown_known_issues.py` checks the `WITH` workaround and the unaffected
shape, and has strict `xfail` tests of the wrong counts; they start failing the suite when the
engine fixes them, which is the cue to remove this entry.


## `sum()` and `avg()` over a `BYTE` property raise `IllegalArgumentException`

ArcadeDB [#9281](https://github.com/ArcadeData/arcadedb/issues/9281); measured through the
bindings on 26.10.1 (the official jars are upstream build d36b4ca3ae), and in Java on that build, on 26.9.1, and
on 5a90b0f52a, on Temurin 21 and 25. Fixed upstream by
[ArcadeData/arcadedb#9288](https://github.com/ArcadeData/arcadedb/pull/9288), merged on 2026-10-06 for
ArcadeDB 26.11.1, which is not released yet. The 26.10.1 wheel still has the bug.

Over a property declared `BYTE`, `SELECT sum(b) FROM T` and `SELECT avg(b) FROM T` in SQL and
`MATCH (n:V) RETURN sum(n.b)` in openCypher raise `ArcadeDBError` (`Query failed:
java.lang.IllegalArgumentException: Cannot increment value '100' (class java.lang.Byte) with
'50' (class java.lang.Byte)`) once the aggregate has two rows to add. The same values in a
`SHORT` or `INTEGER` property sum and average as expected.

Convert the value before the aggregate, `b.asInteger()` in SQL and `toInteger(n.b)` in
openCypher, or declare the property `SHORT`:

```python
total = db.query("sql", "SELECT sum(b.asInteger()) AS total FROM T").first().get("total")
average = db.query("sql", "SELECT avg(b.asInteger()) AS average FROM T").first().get("average")
```

Tests: `tests/test_count_pushdown_known_issues.py` checks the conversion workaround and has plain
regression tests of the aggregates. They pass on the engine the suite builds against (upstream's
26.11.1 snapshot, which has the fix) and fail on the 26.10.1 wheel. Remove this entry when the
release that carries the fix ships.
