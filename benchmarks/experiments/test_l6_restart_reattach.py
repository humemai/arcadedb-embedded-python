"""The restart lane's documents engine reattaches PostgreSQL with autocommit on, as build() leaves it, so the batch it
writes after a restart is committed (qP24, 2026-10-18)."""
import types

import l6_restart as R


class _Cx:
    def __init__(self):
        self.autocommit = False


class _FakePostgresTPC:
    name = "postgres"

    def connect(self):
        self.cx = _Cx()   # the real adapter opens with autocommit=False; only build() turns it on


def _docs(backend, adapter_cls):
    d = object.__new__(R.Docs)
    d.backend, d.L = backend, types.SimpleNamespace(BACKENDS={backend: adapter_cls})
    return d


def test_postgres_reattach_turns_autocommit_on():
    d = _docs("postgres", _FakePostgresTPC)
    d.reattach()
    assert d.adapter.cx.autocommit is True


def test_other_backends_are_left_as_connect_made_them():
    d = _docs("sqlite_like", _FakePostgresTPC)
    d.reattach()
    assert d.adapter.cx.autocommit is False
