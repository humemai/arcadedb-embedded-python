"""In-process server on the native backend (HTTP API, Studio, wire-protocol plugins as configured)."""

import os
from typing import Any, Dict, Optional

from ..exceptions import ArcadeDBError
from . import lib
from .database import NativeDatabase, _call


def _config_key(key: str) -> str:
    return f"arcadedb.{key.replace('_', '.')}"


class NativeServer:
    def __init__(
        self,
        root_path: str = "./databases",
        root_password: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self._config = config or {}
        self._root_path = root_path
        self._root_password = root_password
        self._h = 0
        self._started = False

    def _settings(self) -> dict:
        cfg = self._config
        settings: Dict[str, Any] = {"arcadedb.server.rootPath": self._root_path}
        if self._root_password:
            settings["arcadedb.server.rootPassword"] = self._root_password
        settings["arcadedb.server.mode"] = cfg.get("mode", "development")
        settings["arcadedb.server.httpIncomingHost"] = cfg.get("host", "localhost")
        settings["arcadedb.server.httpIncomingPort"] = cfg.get("http_port", 2480)
        for key, value in cfg.items():
            if key not in ("mode", "host", "http_port"):
                settings[_config_key(key)] = value
        return settings

    def start(self):
        import json

        if self._started:
            raise ArcadeDBError("Server is already started")
        body = json.dumps(
            {
                "settings": self._settings(),
                "host": self._config.get("host", "localhost"),
            }
        )
        try:
            self._h = _call(
                "Failed to start server", "arcadedb_n_server_start", lib.b(body)
            )["h"]
        except ArcadeDBError:
            raise
        self._started = True

    def stop(self):
        if not self._started:
            return
        _call("Failed to stop server", "arcadedb_n_server_stop", self._h)
        self._started = False

    def __del__(self):
        try:
            if self._started:
                self.stop()
        except Exception:  # nosec B110
            return

    def get_database(self, name: str) -> NativeDatabase:
        if not self._started:
            raise ArcadeDBError("Server is not started")
        return NativeDatabase(
            _call(
                f"Failed to get database '{name}'",
                "arcadedb_n_server_db",
                self._h,
                lib.b(name),
                0,
            )["h"],
            owned_by_server=True,
        )

    def create_database(self, name: str) -> NativeDatabase:
        if not self._started:
            raise ArcadeDBError("Server is not started")
        return NativeDatabase(
            _call(
                f"Failed to create database '{name}'",
                "arcadedb_n_server_db",
                self._h,
                lib.b(name),
                1,
            )["h"],
            owned_by_server=True,
        )

    def is_started(self) -> bool:
        return self._started

    def get_http_port(self) -> int:
        return self._config.get("http_port", 2480)

    def get_studio_url(self) -> str:
        host = self._config.get("host", "localhost")
        if host in ("0.0.0.0", "::"):  # nosec B104
            host = "localhost"
        return f"http://{host}:{self.get_http_port()}/"

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
