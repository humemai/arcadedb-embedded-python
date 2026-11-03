# Host helper: exact per-phase peaks where `memory.peak` is root-owned

`bench-cgroup-grant` lets the benchmark runner (not root) open one container's `memory.peak` for writing, which instrument 2026-12 needs to reset the peak at each phase. It is installed by the host's owner, with root; the harness never installs or changes it. When it is absent the harness still runs and says `mem_probe_grant` = `absent` on the row.

Docker-group membership is already root-equivalent on these hosts, so this adds no new privilege class, only a narrower path: root runs one fixed script that hands one file (`memory.peak` of one container, found by its full id) to the user who called `sudo`, and nothing else.

Replace `<REPO>` with the absolute path of the repository checkout on the host and `<user>` with the runner's user.

## Install

```bash
sudo install -o root -g root -m 0755 <REPO>/benchmarks/experiments/host/bench-cgroup-grant /usr/local/sbin/bench-cgroup-grant
echo '<user> ALL=(root) NOPASSWD: /usr/local/sbin/bench-cgroup-grant' | sudo tee /etc/sudoers.d/bench-cgroup-grant
sudo chmod 0440 /etc/sudoers.d/bench-cgroup-grant
sudo visudo -cf /etc/sudoers.d/bench-cgroup-grant || sudo rm -f /etc/sudoers.d/bench-cgroup-grant
```

The last line removes the drop-in again if `visudo` rejects it. Alternatively write the drop-in with `sudo visudo -f /etc/sudoers.d/bench-cgroup-grant`.

## Verify

Start a throwaway container, ask for the grant, then open `memory.peak` read-write as yourself, write a reset and read it back. Any local image works in place of `dbbench:client`.

```bash
id=$(docker run -d --rm --name grant-check dbbench:client sleep 60)
sudo -n /usr/local/sbin/bench-cgroup-grant "$id" && echo granted
cg=/sys/fs/cgroup/system.slice/docker-$id.scope; [ -d "$cg" ] || cg=/sys/fs/cgroup/docker/$id
uv run --no-project python - "$cg/memory.peak" <<'PY'
import os, sys
fd = os.open(sys.argv[1], os.O_RDWR)
print("before", os.pread(fd, 64, 0).decode().strip())
os.write(fd, b"reset")
print("after ", os.pread(fd, 64, 0).decode().strip())
PY
docker rm -f grant-check
```

Expected: `granted`, then two byte counts with `after` at or below `before` (the reset applies to reads through this descriptor). `Permission denied` on the open means the grant did not apply.

## Refusals

Each refusal is one line on stderr and an exit code: 64 usage, 65 not a full 64-hex id, 66 `SUDO_UID` unset, zero or not a number, 67 no cgroup directory (or more than one) for that id, 68 `memory.peak` is not a plain file at the expected path, 69 `chown` failed. The harness records the last line as `mem_probe_grant` = `refused: rc=<n>: <message>` and falls back to the cumulative-rise rule.

## Uninstall

```bash
sudo rm -f /etc/sudoers.d/bench-cgroup-grant /usr/local/sbin/bench-cgroup-grant
```
