"""psql steps, run through the official postgres image on the job's docker network (stdlib only).

  python probe_psql.py NETWORK IMAGE HOST PORT USER PASSWORD
Every step is a psql script on stdin with ON_ERROR_STOP; the client's own meta-commands (\\dt, \\d) are the
list-tables and list-columns steps. The parameterized step uses the extended protocol (\\bind).
"""
import subprocess
import sys

import pgsteps

net, image, host, port, user, pw = sys.argv[1:7]
base = ["docker", "run", "--rm", "-i", "--network", net, "-e", f"PGPASSWORD={pw}", image]
conn = f"host={host} port={port} dbname=sqlev user={user} sslmode=disable"
ver = subprocess.run(base + ["psql", "--version"], capture_output=True, text=True).stdout.strip()


def step(name, script, must_contain=None):
    r = subprocess.run(base + ["psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", conn, "-f", "-"], input=script,
                       capture_output=True, text=True, timeout=120)
    out = r.stdout.strip()
    ok = r.returncode == 0 and bool(out) and (must_contain is None or must_contain.lower() in out.lower())
    err = None if ok else (r.stderr.strip() or f"rc={r.returncode}, stdout={out[:200]!r}")
    pgsteps.emit("psql", ver, name, ok, err)


step("connect", "SELECT 1;\n")
step("list_tables", "\\dt\n", "Person")
step("list_columns", "\\d Person\n", "city_id")
step("select", pgsteps.SQL["select"] + ";\n")
step("select_param", pgsteps.PARAM_SQL.format(ph="$1") + f" \\bind {pgsteps.PARAM_VALUE} \\g\n", "Person7")
step("join", pgsteps.SQL["join"] + ";\n")
step("group_by", pgsteps.SQL["group_by"] + ";\n")
