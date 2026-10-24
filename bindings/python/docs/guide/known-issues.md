# Known Engine Issues

This page lists the known bugs that can return a wrong answer, store a wrong value, change the
wrong rows, or refuse a read or a write. The first entry is an engine bug that is fixed on
upstream's main and not yet in a release. The next two, about
Ctrl-C and about memory held by results, are not engine bugs: they are in JPype, the library that connects
Python to the engine. The last one covers running on a free-threaded CPython: two bugs in the bindings that are fixed, and the open JPype issues and one hang that you may meet there. Each entry names the versions it was measured on, what you see, a workaround that was
checked on the same reproduction, and the release that fixes it once there is one. Entries leave
this page when the fix ships in a release these bindings package.
An entry with a `Tests:` line has a test of its workaround. An entry for a bug that is fixed on upstream's main but not yet in a release says so, with the release that will carry the fix.

## SQL `=` on a list or map misses a list written from Python (fixed in 26.11.1)

ArcadeDB 26.10.2 (the wheel) and earlier. Reported as
[ArcadeData/arcadedb#10448](https://github.com/ArcadeData/arcadedb/issues/10448), fixed by
[#10457](https://github.com/ArcadeData/arcadedb/pull/10457) on upstream's main on 2026-10-20 and
in 26.11.1, which is not released yet. On 26.11.1 (and on a snapshot built after that change) the
query below is right and you need none of the workarounds; on 26.10.2 and earlier it is not.

`Document.set`, `Vertex.set` and `GraphBatch.create_vertices` store a Python `int` as a Java
`Long`. A SQL literal such as `[1, 2]` parses to `Integer` elements, and SQL `=` compared the
elements of two lists, or the values of two maps, with Java `equals()`, which keeps a `Long` 1
and an `Integer` 1 apart. So `SELECT FROM V WHERE li = [1, 2]` missed a vertex whose `li` was
written from Python as `[1, 2]`, `li <> [1, 2]` returned it, and `mp = {"a": 1}` missed a map
the same way. `insert_many` stores `Integer` elements (the engine reads its rows as JSON), so
the literal matched a list written there and missed the same list written with `Document.set`.
`CONTAINS`, `CONTAINSALL`, `GROUP BY` and openCypher's `=` treated the two lists as equal.
From 26.11.1, `=` and `<>` on a list or a map compare the elements numerically, as those do, and
so do `IN` and `CONTAINS` with a list or map value. A `BY ITEM` index is no longer used to answer
a whole-list `=`: the query scans, so the answer is right and no longer depends on the index.

On 26.10.2 and earlier, use openCypher's `=` (`MATCH (n:V) WHERE n.li = [1, 2]`), or bind the
list as a named SQL parameter, `db.query("sql", "SELECT FROM V WHERE li = :p", {"p": [1, 2]})`:
it crosses with `Long` elements, so it matches lists written with `Document.set`,
`Vertex.set` and `GraphBatch` (and misses lists written with `insert_many`). The parameter does
not help when the list has a `BY ITEM` index: SQL `=` is then answered from the index and
matches nothing, literal or parameter. openCypher's `=` matches with or without the index.

Tests: `tests/test_collection_equality_known_issues.py` asserts the fixed answer for the SQL
literals, `<>` and the parameter through a `BY ITEM` index, and keeps the two workarounds
passing on every engine. An engine from before the fix has the same version string as one with it (the engine source of this
repository until upstream's fix is merged into it, or upstream's snapshot image), so the test file probes the
behavior and asserts the old answer on such an engine.

## Ctrl-C and `kill -TERM` with the JVM started (fixed in the next release of these bindings)

Measured on release 26.10.2.post1 with JPype 1.7.1 (the newest, and the one a fresh install gets; the package declares `jpype1>=1.5.0`). JPype's two bugs behind it, [jpype-project/jpype#1496](https://github.com/jpype-project/jpype/issues/1496) and [jpype-project/jpype#1497](https://github.com/jpype-project/jpype/issues/1497), are still open. The bindings no longer depend on JPype's handlers: after the JVM starts, `start_jvm()` gives SIGINT and SIGTERM back to Python.

With the default `interrupt=False`, JPype installs its own Java handlers for SIGINT and SIGTERM, which replace Python's at the operating-system level. Three things went wrong on the JVM wheel (the native wheel has no such handler):

- A script blocked in one long call in the main thread (`time.sleep(60)`, `Lock.acquire()`, `queue.get()`, `Thread.join()`) did not stop on Ctrl-C, with or without an open transaction. The signal reaches the JVM, which tells Python from its own signal thread. That sets the "interrupt pending" flag but wakes nobody, so the `KeyboardInterrupt` waited until the call ended, and it arrived at once if any other signal woke the thread. A busy Python loop did not stop either.
- A Java call that waits in an interruptible way (`Thread.sleep()`, `Object.wait()`) could raise `java.lang.InterruptedException` or `RuntimeError: Fatal error occurred` instead of `KeyboardInterrupt` (JPype interrupts the Java thread before it tells Python).
- `kill -TERM` with no Python handler for SIGTERM, the normal state of a script, crashed the process in `PyErr_SetInterruptEx` (exit status -6).

Now SIGINT and SIGTERM behave as in a script without a JVM. Ctrl-C raises `KeyboardInterrupt` in the main thread at once, and the rollback of a `with db.transaction():` block, `finally` blocks, and `atexit` hooks run. A Java call in progress is not interrupted: the `KeyboardInterrupt` arrives when it returns. `kill -TERM` ends the process with status -15 and runs no Python cleanup, and the next open of the database replays the log (`was not closed properly last time`); committed data is intact. To clean up on SIGTERM, register a handler yourself, for example `signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))`.

On a release without the fix, restore the handlers yourself right after the JVM starts (the first `create_database()` or `open_database()` call), from the main thread:

```python
import signal

db = arcadedb.create_database("./mydb")
signal.signal(signal.SIGINT, signal.default_int_handler)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
```

Tests: `tests/test_sigint.py` covers a Python loop, one long `time.sleep()` with a transaction open, a Java call that Ctrl-C cannot wake, and SIGTERM.


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

Read a large result with `to_list()` (the default), `iter_dicts()`, `to_columns()`, or `to_json_list()` (when you want JSON-native values)
rather than a `get()` per value, or upgrade JPype to the release that carries the fix when it ships. Count the live Python
objects with `sys.getallocatedblocks()` before and after a read to see whether your path is
affected.

## Free-threaded Python (3.13t, 3.14t)

The bindings install and run on a free-threaded CPython (no GIL), measured on 3.14t with JPype 1.7.1, which publishes `cp313t` and `cp314t` wheels and keeps the GIL off after `import jpype` and after the JVM starts. 3.13t was not measured. `tests/test_free_threading.py` runs many threads against one database and against one database each (inserts, numpy vector rows, queries, vector searches, Python functions and record events) and compares the result with a sequential run. It passes with the GIL as well. What it found:

- Fixed, with the GIL too: threads whose first call was `create_database()` or `open_database()` raced into `start_jvm()`, and all but one failed with `Failed to start JVM`. `start_jvm()` now holds a lock, and the threads that lose the race join the running JVM.
- Fixed: the first `register_function()` or `on()` defines a JPype proxy class. Threads that did it together each defined one, which is the leak the cache exists to avoid. The definition now happens once, under a lock.
- Open, in JPype: when many threads make their first Java calls at the same moment, JPype 1.7.1 can crash the process with a SIGSEGV in `JPHintsConversion::matches`, which belongs to its lazy type-conversion setup. It was seen on 3.14t and not with the GIL, and it is rare: 2 of 30 first-start runs on 3.14t, 0 of 27 with the GIL. The fault is in JPype's native code. As a precaution, make the first Java call from one thread, for example open a database and run one statement, before you start the worker threads. This is untested: it is the obvious step, not a checked workaround.
- Open, cause not found: on 3.14t the Python heap grows by about 520 to 610 bytes with every `register_function()`, `on()` and `remove()` cycle. It stays flat with the GIL. `test_registering_again_and_again_does_not_grow_the_python_heap` is marked `xfail` (not strict) on a free-threaded build for this reason. The proxy objects are suspected not to be freed there, which resembles [jpype#1506](https://github.com/jpype-project/jpype/issues/1506), but this is not shown. If you register functions or handlers in a long loop on 3.14t, watch the memory of the process.
- Not specific to free threading: a process in which a thread other than the main thread called Java does not exit. It hangs at exit in JPype's JVM shutdown, with or without the GIL ([jpype#1169](https://github.com/jpype-project/jpype/issues/1169)). The bindings keep JPype's default. There are two workarounds, both checked on a thread that creates a database. End such a thread with `jpype.java.lang.Thread.detach()`, and the process exits. Or set `jpype.config.destroy_jvm = False` before the exit: the process exits too, but JPype then skips the JVM shutdown, so the engine's JVM shutdown hooks do not run (databases that are still open are closed by the bindings as before). `attachAsDaemon()` did not help.

Tests: `tests/test_free_threading.py` covers the two fixes, the start race and the single proxy class. The crash, the heap growth and the exit hang have no test in the suite.

## Fixed in 26.10.2

These entries left the page when 26.10.2 shipped. On 26.10.1, upgrade: `pip install -U arcadedb-embedded`.

- An openCypher one-hop `count(*)` answered 0 for edges loaded with `light_edges=True` into a type that is not `LIGHTWEIGHT`: [#9378](https://github.com/ArcadeData/arcadedb/issues/9378), fixed by [#9383](https://github.com/ArcadeData/arcadedb/pull/9383). The batch now refuses that load.
- An openCypher count with a pattern predicate over an edge type that a Graph Analytical View does not list was wrong: [#9377](https://github.com/ArcadeData/arcadedb/issues/9377), fixed by [#9383](https://github.com/ArcadeData/arcadedb/pull/9383).
- An openCypher count with a negated pattern in a chain was wrong when the far end had another label or the pattern had a property map: [#9277](https://github.com/ArcadeData/arcadedb/issues/9277) and [#9278](https://github.com/ArcadeData/arcadedb/issues/9278), fixed by [#9288](https://github.com/ArcadeData/arcadedb/pull/9288).
- An openCypher count with a negated pattern was wrong for other shapes of the chain: [#9290](https://github.com/ArcadeData/arcadedb/issues/9290), fixed by [#9299](https://github.com/ArcadeData/arcadedb/pull/9299).
- `sum()` and `avg()` over a `BYTE` property raised `IllegalArgumentException`: [#9281](https://github.com/ArcadeData/arcadedb/issues/9281), fixed by [#9288](https://github.com/ArcadeData/arcadedb/pull/9288).
- An async executor batch could run out of retries and be rolled back at parallel level 4 on a one-bucket type: [#9694](https://github.com/ArcadeData/arcadedb/issues/9694), fixed by [#9703](https://github.com/ArcadeData/arcadedb/pull/9703).
