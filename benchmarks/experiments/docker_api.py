"""The few Docker Engine API calls the server-restart lane makes, over the host's socket.

The restart lane (l6_restart.py) stops and starts its OWN server container from
inside the client container, so a restart keeps everything the runner gave the
server: the same container, the same data, the same flags, cpuset, memory cap,
and network name. The runner mounts /var/run/docker.sock into that lane's client
and into no other.

Standard library only (http.client over an AF_UNIX socket): the client image
carries no Docker SDK, and adding one to every image for three calls would put a
new dependency on every lane.
"""
import http.client
import json
import socket
import urllib.parse

SOCK = "/var/run/docker.sock"


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, timeout):
        super().__init__("localhost", timeout=timeout)

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(SOCK)
        self.sock = s


def call(method, path, body=None, timeout=60):
    """(status, decoded body) for one API call; an HTTP error status raises."""
    conn = _UnixConnection(timeout)
    headers, data = {}, None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    try:
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
    finally:
        conn.close()
    if resp.status >= 400:
        raise RuntimeError(f"docker {method} {path}: HTTP {resp.status} {raw[:300]!r}")
    if raw[:1] in (b"{", b"["):
        return resp.status, json.loads(raw)
    return resp.status, raw


def inspect(name):
    return call("GET", f"/containers/{urllib.parse.quote(name)}/json")[1]


def stop(name, grace_s):
    """Stop the container the way `docker stop` does: the image's STOPSIGNAL
    (SIGTERM when it declares none), then SIGKILL after `grace_s`. Returns when
    the container has exited. The caller times it."""
    call("POST", f"/containers/{urllib.parse.quote(name)}/stop?t={int(grace_s)}",
         timeout=grace_s + 120)


def start(name):
    """Start a stopped container. Returns once its process is running, before
    the engine inside it is ready for anything."""
    call("POST", f"/containers/{urllib.parse.quote(name)}/start", timeout=120)


def create_and_start(config, name):
    """Create and start a helper container (the shutdown trace's sidecar)."""
    call("POST", f"/containers/create?name={urllib.parse.quote(name)}", body=config)
    start(name)


def wait(name, timeout):
    return call("POST", f"/containers/{urllib.parse.quote(name)}/wait", timeout=timeout)[1]


def logs(name):
    """stdout+stderr of a container, demultiplexed (non-TTY streams carry an
    8-byte header per frame)."""
    _, raw = call("GET", f"/containers/{urllib.parse.quote(name)}/logs?stdout=1&stderr=1")
    if not isinstance(raw, (bytes, bytearray)):
        return json.dumps(raw)
    out, i = [], 0
    while i + 8 <= len(raw):
        n = int.from_bytes(raw[i + 4:i + 8], "big")
        out.append(raw[i + 8:i + 8 + n])
        i += 8 + n
    return b"".join(out).decode("utf-8", "replace")


def remove(name):
    try:
        call("DELETE", f"/containers/{urllib.parse.quote(name)}?force=1")
    except RuntimeError:
        pass
