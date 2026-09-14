#!/usr/bin/env python3
"""The reconnect path's own unit tests (DECISIONS #91).

The failure this guards against cannot be reproduced on a laptop: it took a
ten-million-vector index and eighty minutes of queries on the bench host for
the client's keepalive to hang up on a busy server. What CAN be checked here,
in a second and with no container, is the machinery that answers it:

  * a dropped connection is recognised from the exception the SDK raises,
  * it is retried exactly once, on a connection that was rebuilt,
  * anything that is not a dropped connection is raised, not retried,
  * close() never reconnects, because a reconnect made to close is a reconnect
    that would count itself on the row,
  * the retried call's LATENCY is not counted (sample_kept), and
  * `reconnects` lands on the row whether or not anything happened.

Run directly, or as part of a smoke:

    python3 test_surreal_reconnect.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import surreal_common  # noqa: E402


class FakeClient:
    """One SDK connection: fails a given number of calls, then answers."""

    def __init__(self, fail_first=0, tag=0):
        self.fail_first = fail_first
        self.calls = 0
        self.closed = False
        self.tag = tag

    def query(self, text):
        self.calls += 1
        if self.calls <= self.fail_first:
            raise ConnectionResetError("no close frame received or sent")
        return f"rows-from-{self.tag}"

    def boom(self):
        raise ValueError("a real error, not a dropped socket")

    def close(self):
        self.closed = True
        raise ConnectionResetError("connection closed while closing")


def _client_factory(plan):
    """Hands out the clients in `plan`, one per open, newest last."""
    made = []

    def open_fn():
        c = plan[len(made)] if len(made) < len(plan) else plan[-1]
        made.append(c)
        return c

    open_fn.made = made
    return open_fn


def check(name, cond):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}")
    return 0 if cond else 1


def main():
    bad = 0
    print("=== the dropped-connection test ===")
    bad += check("recognises the SDK's own wording",
                 surreal_common.is_dropped_connection(
                     ConnectionResetError("no close frame received or sent")))
    bad += check("recognises a closed websocket by class name",
                 surreal_common.is_dropped_connection(
                     type("ConnectionClosedError", (Exception,), {})("sent 1006")))
    bad += check("does not call a value error a dropped connection",
                 not surreal_common.is_dropped_connection(ValueError("bad query")))

    print("\n=== retry once, on a rebuilt connection ===")
    first, second = FakeClient(fail_first=1, tag=1), FakeClient(tag=2)
    c = surreal_common.ReconnectingClient(_client_factory([first, second]))
    bad += check("the call returns the retry's answer", c.query("SELECT 1") == "rows-from-2")
    bad += check("one reconnect counted", c.reconnects == 1)
    bad += check("the epoch moved", c.reconnect_epoch == 1)
    bad += check("the dead connection was closed", first.closed)

    print("\n=== a second drop on a fresh connection is not retried again ===")
    always = FakeClient(fail_first=99, tag=3)
    c2 = surreal_common.ReconnectingClient(_client_factory([always, always]))
    try:
        c2.query("SELECT 1")
        bad += check("raises rather than retrying forever", False)
    except ConnectionResetError:
        bad += check("raises rather than retrying forever", True)

    print("\n=== everything that is not a dropped connection ===")
    plain = FakeClient(tag=4)
    c3 = surreal_common.ReconnectingClient(_client_factory([plain]))
    try:
        c3.boom()
        bad += check("a real error is raised, not retried", False)
    except ValueError:
        bad += check("a real error is raised, not retried", c3.reconnects == 0)

    print("\n=== close never reconnects ===")
    closing = FakeClient(tag=5)
    c4 = surreal_common.ReconnectingClient(_client_factory([closing]))
    try:
        c4.close()
    except ConnectionResetError:
        pass
    bad += check("no reconnect counted for a close", c4.reconnects == 0)

    print("\n=== the retried sample is not counted ===")
    a, b = FakeClient(fail_first=1, tag=6), FakeClient(tag=7)

    class Adapter:
        name = "surrealdb_tpc_server"

    ad = Adapter()
    ad.db = surreal_common.ReconnectingClient(_client_factory([a, b]))
    samples = []
    surreal_common.keep(ad, samples, 1.0)          # clean
    ad.db.query("SELECT 1")                        # drops, reconnects
    surreal_common.keep(ad, samples, 999.0)        # the reconnect's cost
    surreal_common.keep(ad, samples, 2.0)          # clean again
    bad += check("the sample across the reconnect is dropped", samples == [1.0, 2.0])

    print("\n=== the row records it either way ===")
    out = {}
    surreal_common.stamp_reconnects(out, ad)
    bad += check("a served row carries the count", out.get("reconnects") == 1)

    class Embedded:
        name = "surrealdb_tpc"

    emb = Embedded()
    emb.db = FakeClient(tag=8)
    out2 = {}
    surreal_common.stamp_reconnects(out2, emb)
    bad += check("an embedded row carries a zero", out2.get("reconnects") == 0)

    class Other:
        name = "duckdb"

    out3 = {}
    surreal_common.stamp_reconnects(out3, Other())
    bad += check("a non-SurrealDB row carries nothing", "reconnects" not in out3)

    print(f"\n{bad} failure(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
