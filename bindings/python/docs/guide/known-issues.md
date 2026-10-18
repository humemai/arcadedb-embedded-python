# Known Engine Issues

This page lists the known bugs that can return a wrong answer, store a wrong value, change the
wrong rows, or refuse a read or a write. The two entries now on it, about Ctrl-C and about memory
held by results, are not engine bugs: they are in JPype, the library that connects Python to the
engine. Each entry names the versions it was measured on, what you see, a workaround that was
checked on the same reproduction, and the release that fixes it once there is one. Entries leave
this page when the fix ships in a release these bindings package.
An entry with a `Tests:` line has a test of its workaround.

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

Read a large result with `to_list()` (the default), `iter_dicts()`, `to_columns()`, or `to_json_list()` (when you want JSON-native values)
rather than a `get()` per value, or upgrade JPype to the release that carries the fix when it ships. Count the live Python
objects with `sys.getallocatedblocks()` before and after a read to see whether your path is
affected.

## Fixed in 26.10.2

These entries left the page when 26.10.2 shipped. On 26.10.1, upgrade: `pip install -U arcadedb-embedded`.

- An openCypher one-hop `count(*)` answered 0 for edges loaded with `light_edges=True` into a type that is not `LIGHTWEIGHT`: [#9378](https://github.com/ArcadeData/arcadedb/issues/9378), fixed by [#9383](https://github.com/ArcadeData/arcadedb/pull/9383). The batch now refuses that load.
- An openCypher count with a pattern predicate over an edge type that a Graph Analytical View does not list was wrong: [#9377](https://github.com/ArcadeData/arcadedb/issues/9377), fixed by [#9383](https://github.com/ArcadeData/arcadedb/pull/9383).
- An openCypher count with a negated pattern in a chain was wrong when the far end had another label or the pattern had a property map: [#9277](https://github.com/ArcadeData/arcadedb/issues/9277) and [#9278](https://github.com/ArcadeData/arcadedb/issues/9278), fixed by [#9288](https://github.com/ArcadeData/arcadedb/pull/9288).
- An openCypher count with a negated pattern was wrong for other shapes of the chain: [#9290](https://github.com/ArcadeData/arcadedb/issues/9290), fixed by [#9299](https://github.com/ArcadeData/arcadedb/pull/9299).
- `sum()` and `avg()` over a `BYTE` property raised `IllegalArgumentException`: [#9281](https://github.com/ArcadeData/arcadedb/issues/9281), fixed by [#9288](https://github.com/ArcadeData/arcadedb/pull/9288).
- An async executor batch could run out of retries and be rolled back at parallel level 4 on a one-bucket type: [#9694](https://github.com/ArcadeData/arcadedb/issues/9694), fixed by [#9703](https://github.com/ArcadeData/arcadedb/pull/9703).
