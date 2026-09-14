#!/usr/bin/env python3
"""Shared metrics helpers for the benchmark lanes.

Stdlib-only (so every backend image can import it): latency summary stats,
on-disk size, a raw-latency sidecar dump, and a small timing context manager.
"""
import contextlib
import datetime as _dt
import decimal as _decimal
import hashlib
import json
import os
import socket
import statistics as st
import sys
import time

# THE INSTRUMENT VERSION. Rows measured under different query sets, timers, or
# durability settings cannot share a table, so every row names the instrument
# it was measured with and make_paper_tables refuses to mix them within a
# table (DECISIONS #84). "2026-09" is the September campaign (rows without the
# field); "2026-10" carries the #82 query set, the #81 durability rule, the
# ingest/index timer split, and bench_host.
INSTRUMENT = "2026-10"

# DECISIONS #81: the matched durability class is "relaxed" (a commit returns
# without waiting for the disk). An engine that cannot be relaxed declares a
# `durability` string starting with this prefix and is the named exception on
# its tables; fairness_check F8 refuses anything else.
STRICT_PREFIX = "fsync at commit"

# A THIRD ANSWER, because two were not enough. SurrealDB 3.2.4 has no sync
# setting and its behaviour at commit could not be established (see the
# evidence block below), and calling that "relaxed" would be the assertion
# #81 exists to forbid. A string carrying this mark is its own class, and
# fairness_check refuses it on any backend not named as an exception.
UNVERIFIED_MARK = "not verified"


def durability_class(text):
    """'relaxed', 'strict', 'unverified', or None when the row recorded nothing."""
    if not text:
        return None
    t = str(text)
    if UNVERIFIED_MARK in t:
        return "unverified"
    return "strict" if t.startswith(STRICT_PREFIX) else "relaxed"


# HOW EVERY DEFAULT IN THE LANES' DURABILITY MAPS WAS CHECKED.
#
# DECISIONS #81 asks for the engine's own answer, not its reputation, and the
# string a lane writes onto a row is a published claim. Measured on the laptop
# on 2026-09-14 against the pinned images and wheels; a claim that could not be
# established says so in the string itself instead of asserting a class.
#
#   ArcadeDB    GlobalConfiguration.TX_WAL_FLUSH read out of the running
#               engine: default 0, current 0, "0 = no flush" (wheel 26.8.1).
#   SQLite      PRAGMA journal_mode and synchronous read back (wal, 1), and
#               strace: 50 commits -> 8 fsync, so a commit does not sync.
#   DuckDB      strace: 50 commits -> 55 fsync, one per commit; and
#               duckdb_settings() at 1.5.5 offers no commit-sync knob at all,
#               only checkpoint thresholds. Hence "not configurable".
#   LadybugDB   strace: 50 auto-commit writes -> 56 fdatasync, one per
#               commit; ladybug 0.20.4's Database() takes no sync option.
#   PostgreSQL  read per row, not asserted: each adapter runs
#   family      SHOW synchronous_commit on connect and records the answer.
#   MongoDB     server 8.2.12: getParameter journalCommitInterval = 100 ms;
#               the implicit default write concern is w:majority with
#               writeConcernMajorityJournalDefault true, which the timed
#               writes override with w=1, j=false.
#   ArangoDB    server 3.12.11 /_admin/options: database.wait-for-sync false,
#               rocksdb.use-fsync false, rocksdb.sync-interval 100 ms; a
#               freshly created collection reads back waitForSync false.
#   QuestDB     server 9.1.1 SHOW PARAMETERS: cairo.commit.mode = nosync,
#               value_source = default.
#   SurrealDB   embedded (SDK 2.0.0, core 2.3.10) strace A/B: with
#   embedded    SURREAL_SYNC_DATA unset, 6 fsync at both 50 and 250 commits;
#               with it true, 56 and 256. The default is no sync at commit.
#   SurrealDB   3.2.4 has NO sync setting: its binary holds no "SYNC_DATA"
#   served      and no "SURREAL_DATASTORE" token, and none of its 110
#               SURREAL_* variables names sync, WAL, fsync, or durability.
#               The env var this harness used to set was inert and is gone
#               (runner.py). What it does at commit is NOT verified, and
#               DURABILITY_SURREAL_SERVER says exactly that.
#   Neo4j       2026.07.1 SHOW SETTINGS: no durability or sync setting exists
#               (the tx_log settings are buffer, preallocation, and rotation
#               only), so it cannot be relaxed; that it forces the log at
#               commit is Neo4j's documented behaviour, not measured here.
#
# One string per engine, defined here, so two lanes cannot describe the same
# engine differently and a re-check lands in one place.
DURABILITY_ARCADEDB = "txWalFlush=0 (engine default): no flush at commit"
DURABILITY_SQLITE = "WAL, synchronous=NORMAL: synced at checkpoint, not at commit"
DURABILITY_DUCKDB = "fsync at commit, not configurable (DuckDB WAL)"
DURABILITY_LADYBUG = "fsync at commit, not configurable (LadybugDB WAL)"
DURABILITY_MONGODB = "write concern w=1, j=false (journal flushed every 100 ms)"
DURABILITY_QUESTDB = "cairo.commit.mode=nosync (default): no fsync at commit"
DURABILITY_SURREAL_EMBEDDED = "SurrealKV, SURREAL_SYNC_DATA unset (the default): no sync at commit"
DURABILITY_SURREAL_SERVER = ("RocksDB at the engine default; SurrealDB 3.2.4 exposes no sync "
                             "setting and the behaviour at commit is not verified")
DURABILITY_NEO4J = ("fsync at commit, not configurable (no durability setting in "
                    "SHOW SETTINGS at 2026.07.1)")
DURABILITY_PG_OFF = "synchronous_commit=off"


def _host_identity():
    """Which machine this is, read rather than assumed.

    Order matters. BENCH_HOST first, because inside a container the kernel
    hostname is a random ID and only the launcher knows it is mini. Then the
    real hostname. A containerised run with BENCH_HOST unset returns
    "container:<id> (host unknown)" rather than a machine name, so a reader
    can see that the physical host was not recorded instead of reading a
    plausible-looking name that nothing checked.
    """
    explicit = os.environ.get("BENCH_HOST")
    if explicit:
        return explicit
    try:
        name = socket.gethostname()
    except Exception:
        return "unknown"
    containerised = os.path.exists("/.dockerenv")
    if containerised:
        return f"container:{name} (host unknown)"
    return name or "unknown"


def run_conditions(**extra):
    """The conditions this process is actually running under, read not asserted.

    Every overlay feeding T4 and T5 records zero of cpuset/heap/mem_cap, while
    runs.jsonl (produced by runner.py) records all of them. The overlays are
    what the tables print, so the published cells came from artifacts carrying
    less provenance than the campaign they override.

    The cost was concrete: Table IV's 8.84M cell is stuck at N=3 because the
    two missing reps cannot be matched to the first three, nothing having
    recorded what those ran under.

    A driver cannot be trusted to be TOLD its conditions, since that is the
    same self-assertion that let fp32_dev22_driver stamp "26.8.1.dev22" onto a
    dev20 run. So read them from the container itself: cgroup v2 exposes the
    effective cpuset and the memory ceiling, and the heap is whatever we asked
    the JVM for. Anything unreadable comes back None rather than a guess.

    Merge into a result dict before writing it:

        out.update(run_conditions(lane="l3s", scale="medium", rep=rep))

    CLIENT/SERVER CAVEAT. This reads the cgroup of the process it runs in. In
    an embedded cell that is the engine. In a client/server cell it is the
    DRIVER container, and the engine under test is in a different container
    with a different cpuset, heap and memory cap. The #109 server dense run
    stamped cpuset=0-11, heap=None, mem_cap=12g, which describes the client:
    the server had 24g of heap under a 36g cap. Those fields are still worth
    recording, but a server cell must record the SERVER's conditions
    separately (see results/srv109/server_conditions.json) and a reader must
    not take the stamped values as the engine's.

    Pass role= to make which side was measured explicit rather than implied.
    """
    def _read(path):
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            return None

    mem = _read("/sys/fs/cgroup/memory.max")
    if mem and mem.isdigit():
        mem = f"{int(mem) // (1 << 30)}g"
    elif mem == "max":
        mem = None

    cpus = (_read("/sys/fs/cgroup/cpuset.cpus.effective")
            or _read("/sys/fs/cgroup/cpuset.cpus"))

    out = {
        "cpuset": cpus,
        "mem_cap": mem,
        "heap": os.environ.get("ARCADEDB_HEAP"),
        # WHICH SCRIPT PRODUCED THIS ROW. FAIRNESS.md's structural finding was
        # that both known protocol violations came from a bespoke driver rather
        # than the lane script, and states the rule "bespoke drivers
        # investigate, lane scripts publish". Nothing enforced it, because a
        # row did not say where it came from, so the rule could only be
        # remembered per row by whoever promoted it to a cell. Recording it
        # makes the rule checkable: a published cell whose producer is not its
        # lane script is detectable instead of being an act of memory.
        "producer": os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else None,
        # "engine" when this process IS the engine, "client" when it drives one
        # over the wire. Without it, a reader cannot tell whether the cgroup
        # fields above describe the thing being measured.
        "role": os.environ.get("BENCH_ROLE",
                               "client" if os.environ.get("BENCH_SERVER_HOST")
                               else "engine"),
        # WHICH MACHINE. This used to be os.environ.get("BENCH_HOST", "mini"),
        # which is the exact self-assertion this function was written to stop:
        # a laptop run with BENCH_HOST unset stamped host="mini" and the
        # artifact then said, in writing, that it came from the controlled
        # bench host. "Every paper number is measured on mini" is a constraint
        # this field is supposed to be the EVIDENCE for, so a default that
        # always satisfies it makes the evidence worthless.
        #
        # Caught by running l4_tsbs.py on the laptop and reading the row back:
        # cpuset 0-15 (the laptop's 16 threads, not mini's 0-11 cpuset) beside
        # host "mini".
        #
        # BENCH_HOST still wins when set, because a container genuinely cannot
        # discover its physical host and the queue scripts are the only thing
        # that knows. But unset now reports what is actually readable, and
        # says so when that is a container ID rather than a machine name.
        "host": _host_identity(),
        # WHICH IMAGE. The last field a published cell was missing.
        #
        # runner.py knows every backend's image and its pinned digest, and
        # stamps them onto lane rows. An overlay driver runs inside a container
        # that is never told what image it is, so it could not record one even
        # in principle -- and the overlays are what T4 and T5 print. The
        # consequence was concrete: T5's Qdrant row is produced by a file whose
        # engine_version reads "unknown (PackageNotFoundError)" and which
        # carries no image at all, while the paper states "served comparators
        # are pinned by image digest". That claim is TRUE -- runner.py pins
        # qdrant/qdrant@sha256:75eab8c4... -- but the artifact cannot show it,
        # so the reproducibility promise rests on a config file the reader
        # never sees rather than on the result they are reading.
        #
        # Same rule as host and producer above: read what is passed, and when
        # nothing is passed say so rather than omitting the key. A missing key
        # looks like an old schema; an explicit None looks like what it is.
        "image": os.environ.get("BENCH_IMAGE"),
        "server_image": os.environ.get("BENCH_SERVER_IMAGE"),
        # WHICH ENGINE COMMIT. Same rule as image above, and the same failure.
        # runner.py stamps this from ARCADEDB_ENGINE_COMMIT (runner.py:730) onto
        # every lane row, so lane rows carry it and bespoke probes do not. On
        # 2026-08-24 sparse_cliff was re-run specifically to unblock figure f3,
        # whose ONLY blocker was "sparse_cliff rows carry engine_commit"; the
        # run finished rc=0 and all 1,000 rows came back with engine_commit
        # None, because the stamping was added to the probe while the VALUE was
        # never passed into its container. Reading it here fixes every bespoke
        # driver at once instead of one at a time.
        #
        # PAGE-SPEC rule 3 is one engine commit per table, so a row that cannot
        # say which commit it came from cannot be published under it, whatever
        # else it measured correctly.
        "engine_commit": os.environ.get("ARCADEDB_ENGINE_COMMIT", "").strip() or None,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
    }
    try:
        from importlib.metadata import version as _v
        out["engine_version"] = _v("arcadedb-embedded")
    except Exception as e:
        out["engine_version"] = f"unknown ({e.__class__.__name__})"
    out.update(extra)
    return out


def _pct(sorted_a, p):
    """Linear-interpolation percentile (numpy-compatible), pure-python."""
    n = len(sorted_a)
    if n == 1:
        return sorted_a[0]
    rank = (p / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_a[lo] * (1 - frac) + sorted_a[hi] * frac


def latstats(prefix, arr_ms):
    """Full latency summary (ms) for a list of per-op latencies:
    n, mean, std, min, p50, p90, p95, p99, max."""
    if not arr_ms:
        return {}
    a = sorted(float(x) for x in arr_ms)
    n = len(a)
    return {
        f"{prefix}_n": n,
        f"{prefix}_mean_ms": round(st.mean(a), 4),
        f"{prefix}_std_ms": round(st.pstdev(a) if n > 1 else 0.0, 4),
        f"{prefix}_min_ms": round(a[0], 4),
        f"{prefix}_p50_ms": round(_pct(a, 50), 4),
        f"{prefix}_p90_ms": round(_pct(a, 90), 4),
        f"{prefix}_p95_ms": round(_pct(a, 95), 4),
        f"{prefix}_p99_ms": round(_pct(a, 99), 4),
        f"{prefix}_max_ms": round(a[-1], 4),
    }


def dir_size_mb(path):
    """On-disk size of a file or directory tree (MiB)."""
    if not path or not os.path.exists(path):
        return None
    if os.path.isfile(path):
        total = os.path.getsize(path)
    else:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return round(total / 1048576.0, 3)


def dump_latencies(run_label, lat_by_op):
    """Write raw per-op latency arrays to $LAT_DIR/<label>.json (set by run.py).
    No-op if LAT_DIR is unset. Returns the relative sidecar path or None."""
    d = os.environ.get("LAT_DIR")
    if not d or not run_label:
        return None
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{run_label}.json"), "w") as f:
        json.dump({k: [round(float(x), 5) for x in v] for k, v in lat_by_op.items() if v}, f)
    return f"lat/{run_label}.json"


class timed:
    """`with timed() as t: ...` then read t.s (elapsed seconds)."""
    def __enter__(self):
        self._t0 = time.time()
        self.s = 0.0
        return self

    def __exit__(self, *exc):
        self.s = time.time() - self._t0
        return False

class PhaseBeat:
    """Say which phase a cell is in, and keep saying it while it lasts.

    A cell that dies used to leave nothing behind unless its engine happened
    to be chatty. SurrealDB's embedded dense cells burned a 4 hour and an
    8 hour budget at 1M and DEEP-10M and printed not one line, so the runner's
    timeout hint came back empty, no client log was written at all, and the
    phase the budget expired in could only be guessed at from a live container
    (2026-09-14, user: "just fix that now"). Markers plus a heartbeat mean any
    cell that dies, for any reason, names the phase it was in and how long it
    had been there.

    Stdlib only, stderr, one line per marker and one per heartbeat interval, so
    a timed loop is never touched: phases are entered and left around the timed
    work, never inside it.
    """

    def __init__(self, every_s=120.0, data_dir=None, out=None):
        self.every_s = float(every_s)
        self.data_dir = data_dir
        self.out = out or sys.stderr
        self._stop = None
        self._thread = None

    def _rss_mib(self):
        try:
            with open("/proc/self/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return round(int(line.split()[1]) / 1024.0, 1)
        except Exception:  # noqa: BLE001
            pass
        return None

    def _extra(self):
        bits = []
        rss = self._rss_mib()
        if rss is not None:
            bits.append(f"rss={rss}MiB")
        if self.data_dir:
            try:
                bits.append(f"data={dir_size_mb(self.data_dir)}MB")
            except Exception:  # noqa: BLE001
                pass
        return (" " + " ".join(bits)) if bits else ""

    def mark(self, name, **fields):
        kv = "".join(f" {k}={v}" for k, v in fields.items())
        print(f"PHASE {name}{kv}{self._extra()}", file=self.out, flush=True)

    @contextlib.contextmanager
    def phase(self, name, **fields):
        self.mark(f"{name}-start", **fields)
        t0 = time.perf_counter()
        import threading
        self._stop = threading.Event()

        def beat():
            while not self._stop.wait(self.every_s):
                el = round(time.perf_counter() - t0, 1)
                print(f"PHASE {name}-running t={el}s{self._extra()}",
                      file=self.out, flush=True)

        self._thread = threading.Thread(target=beat, daemon=True)
        self._thread.start()
        try:
            yield self
        finally:
            self._stop.set()
            self._thread.join(timeout=1.0)
            self.mark(f"{name}-done", t=f"{round(time.perf_counter() - t0, 2)}s")


class SelfMemorySampler:
    """Peak anonymous working set of the process's OWN cgroup, sampled.

    WHY THIS EXISTS. runner.py samples each container's cgroup from the host,
    which is why every lane row carries peak_anon_mib_sum. The overlay drivers
    are not launched that way: they run inside a container the runner did not
    start, so nothing samples them, and their records carry only mem_cap, the
    ceiling we set. That is why five of the eleven project-page tables have no
    memory column while the underlying question was measured everywhere else.

    A peak cannot be read after the fact. memory.stat's `anon` is an instant,
    and memory.peak (which would be a kernel-maintained maximum) is absent in
    this cgroup layout, so the only way to a peak is to sample. Same loop the
    runner uses, running on the measured side instead of the host side.

    Usage mirrors the runner's:

        s = SelfMemorySampler(); s.start()
        ... build and query ...
        out.update(s.finish())          # peak_anon_mib_sum, end_anon_mib_sum

    The field names deliberately match the lane rows, so a page table or a
    claim can read one field for both sources instead of branching.

    Returns None values rather than zeros when the cgroup files are absent (a
    non-Linux host, or cgroup v1), because a zero here would read as "measured,
    used nothing" and this project has already shipped one green result built
    on a measurement that silently returned nothing.

    SCOPE, and it is not a detail. This reads the CGROUP, not the process. In
    a benchmark container that is the same thing: one cgroup, one engine, and
    the number is the engine's. Run it anywhere else and it reports whatever
    else shares the cgroup. Tested on the laptop it returned 15.8 GiB while
    the process under test had allocated 300 MiB, because the laptop's shell
    session is one cgroup. So: valid inside the bench containers, meaningless
    outside them, and run_conditions()'s `host` field is what tells a reader
    which of the two they are looking at.
    """

    INTERVAL = 0.5

    def __init__(self, interval=None):
        import threading
        self.interval = interval or self.INTERVAL
        self._stop = threading.Event()
        self._thread = None
        self.peak_anon = 0
        self.end_anon = None
        self._read_ok = False

    def _anon(self):
        try:
            with open("/sys/fs/cgroup/memory.stat") as fh:
                for line in fh:
                    if line.startswith("anon "):
                        return int(line.split()[1])
        except (OSError, ValueError):
            return None
        return None

    def _loop(self):
        while not self._stop.is_set():
            v = self._anon()
            if v is not None:
                self._read_ok = True
                self.peak_anon = max(self.peak_anon, v)
                self.end_anon = v
            self._stop.wait(self.interval)

    def start(self):
        import threading
        if self._anon() is None:
            return self          # nothing to sample; finish() reports None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def finish(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2 * self.interval)
        if not self._read_ok:
            return {"peak_anon_mib_sum": None, "end_anon_mib_sum": None}
        return {
            "peak_anon_mib_sum": round(self.peak_anon / (1 << 20), 1),
            "end_anon_mib_sum": round((self.end_anon or 0) / (1 << 20), 1),
        }


# ---------------------------------------------------------------------------
# RESULT EQUIVALENCE (DECISIONS #88).
#
# A benchmark that never checks the answer measures how fast an engine can be
# wrong. Until 2026-09-14 the only cross-engine correctness in this harness was
# recall against ground truth on the vector lanes and the torn-state comparison
# in the cross-model trial: every other lane recorded latency, throughput, and
# for a few queries a row count. An adapter that silently dropped a filter, a
# group, or a join condition would have shown up as a lead rather than as a bug.
#
# So every timed query whose answer is deterministic records a canonical digest
# of that answer on its row, plus a short readable sample so a disagreement can
# be READ rather than only detected, and equivalence_check.py refuses a table
# whose engines disagree at the same scale.
#
# Three rules that are not negotiable, because each of them is a way to make
# the check pass while proving nothing:
#
#   1. The digest is computed from the object the TIMED call returned, outside
#      the timed section. Re-running the query to digest it would digest a
#      second execution -- a different transaction, a different cache state,
#      and on a lane with writes a different database.
#   2. An engine that cannot express a query records
#      "unexpressible: <reason>", never a blank. Silence is indistinguishable
#      from agreement, and that is exactly the failure #88 was written after.
#   3. Normalisation is identical for every engine. Anything that varies with
#      the driver -- tuple versus dict, int versus double, a trailing space, a
#      timezone-aware datetime -- is normalised away BEFORE hashing, so a
#      digest mismatch means the ANSWERS differ and nothing else.

DIGEST_VERSION = "rd1"
NULL_TOKEN = "<null>"
MISSING_TOKEN = "<missing>"
UNEXPRESSIBLE_PREFIX = "unexpressible: "
SAMPLE_MAX_CHARS = 240
SAMPLE_ROWS = 3


class _Missing:
    __slots__ = ()

    def __repr__(self):
        return MISSING_TOKEN


_MISSING = _Missing()


def _fmt_number(v, float_digits):
    """One number, one string, whatever driver produced it.

    An int is printed EXACTLY, because a count is exact and rounding one to
    six significant digits would let 1,234,567 and 1,234,568 collide. A float
    is printed to `float_digits` SIGNIFICANT digits, not decimal places: two
    correct engines summing 60,000 doubles in different orders differ in the
    last bits, which on a sum of 1e8 is an absolute difference of ~1e-8 * 1e8,
    and absolute decimal rounding cannot reconcile that while significant-digit
    rounding can. Below 10**float_digits the two spellings coincide (str(60175)
    and "%.6g" % 60175.0 are both "60175"), which is where counts live.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    x = float(v)
    if x != x:
        return "nan"
    if x == float("inf"):
        return "inf"
    if x == float("-inf"):
        return "-inf"
    s = f"{x:.{float_digits}g}"
    return "0" if s in ("-0", "-0.0") else s


def _fmt_value(v, float_digits):
    """One cell of one row, canonical."""
    if v is None or v is _MISSING:
        return MISSING_TOKEN if v is _MISSING else NULL_TOKEN
    if isinstance(v, (bool, int, float)):
        return _fmt_number(v, float_digits)
    if isinstance(v, _decimal.Decimal):
        return _fmt_number(float(v), float_digits)
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, bytes):
        return v.hex()
    if isinstance(v, _dt.datetime):
        # Aware datetimes land in UTC and lose the offset, so a driver that
        # returns UTC+00:00 and one that returns naive UTC agree.
        if v.tzinfo is not None:
            v = v.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        s = v.isoformat(sep="T")
        return s[:-7] if s.endswith(".000000") else s
    if isinstance(v, _dt.date):
        return v.isoformat()
    if isinstance(v, _dt.timedelta):
        return _fmt_number(v.total_seconds(), float_digits)
    # numpy scalars and anything else that knows how to become a Python scalar
    item = getattr(v, "item", None)
    if callable(item):
        try:
            return _fmt_value(item(), float_digits)
        except Exception:  # noqa: BLE001  (not a scalar after all)
            pass
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}={_fmt_value(v[k], float_digits)}"
                              for k in sorted(v, key=str)) + "}"
    if isinstance(v, (list, tuple, set, frozenset)):
        items = [_fmt_value(x, float_digits) for x in v]
        if isinstance(v, (set, frozenset)):
            items.sort()
        return "[" + "|".join(items) + "]"
    return str(v).strip()


def _to_epoch_s(v):
    """An instant, as integer seconds, however the engine spells it.

    One lane, one question, six spellings: the ArcadeDB document arm buckets on
    epoch SECONDS, its native arm on epoch MILLISECONDS (timeBucket takes ms),
    TimescaleDB and MongoDB return datetimes, QuestDB a timestamp, and DuckDB
    and SQLite integers. Those are the same instant in different units, and a
    digest that called them different answers would report six disagreements
    per query and hide any real one among them.

    The seconds/milliseconds split is decided by magnitude: epoch seconds do
    not reach 1e12 until the year 33658, so a value at or above it is
    milliseconds. Stated rather than inferred, because it is the one rule here
    that could in principle be wrong.
    """
    if isinstance(v, _dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=_dt.timezone.utc)
        return int(v.timestamp())
    if isinstance(v, _dt.date):
        return int(_dt.datetime(v.year, v.month, v.day, tzinfo=_dt.timezone.utc).timestamp())
    if isinstance(v, str):
        s = v.strip().replace("Z", "+00:00")
        try:
            return _to_epoch_s(_dt.datetime.fromisoformat(s))
        except ValueError:
            return v.strip()
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float, _decimal.Decimal)):
        x = float(v)
        return int(x / 1000.0) if abs(x) >= 1e12 else int(x)
    return v


def _to_month(v):
    """A month key, "YYYY-MM", whether the engine grouped on a truncated date
    (date_trunc returns 1994-01-01) or on a substring of an ISO string."""
    if isinstance(v, (_dt.datetime, _dt.date)):
        return f"{v.year:04d}-{v.month:02d}"
    if isinstance(v, str):
        return v.strip()[:7]
    return v


COERCIONS = {
    "epoch_s": _to_epoch_s,
    "month": _to_month,
    "text": lambda v: v if v is None else str(v).strip(),
    "num": lambda v: v if v is None else float(v),
}


def _coerce(v, how):
    if v is None or v is _MISSING or how is None:
        return v
    fn = COERCIONS[how] if isinstance(how, str) else how
    try:
        return fn(v)
    except Exception:  # noqa: BLE001  (a coercion never turns a value into a failure)
        return v


def _is_mapping(row):
    return hasattr(row, "keys") and hasattr(row, "__getitem__")


def _lookup(row, spec):
    """One declared column out of one row.

    `spec` is a column name, or a tuple of alternative names, because the same
    question is answered under different names by different drivers: a Mongo
    $group calls the key "_id", an AQL COLLECT calls it whatever the RETURN
    names it, and a SQL driver hands back a positional tuple. Dotted names
    reach into a sub-document ("_id.f"), which is how Mongo's composite group
    keys are read without a per-engine digest.
    """
    for cand in (spec if isinstance(spec, (tuple, list)) else (spec,)):
        cur = row
        ok = True
        for part in str(cand).split("."):
            if _is_mapping(cur):
                try:
                    if part in cur.keys():
                        cur = cur[part]
                        continue
                except Exception:  # noqa: BLE001  (driver row types vary)
                    pass
                ok = False
                break
            if isinstance(cur, (list, tuple)) and part.isdigit():
                idx = int(part)
                if idx < len(cur):
                    cur = cur[idx]
                    continue
            ok = False
            break
        if ok:
            return cur
    return _MISSING


def canonical_rows(rows, columns=None, float_digits=6, coerce=None):
    """The engine's answer as a list of tuples of strings, driver removed.

    `columns` is the query's DECLARED column order and is what makes a dict
    row comparable with a tuple row. Without it a mapping row falls back to
    its own keys sorted, which is deterministic but only comparable against
    another engine that happened to use the same names; every caller in this
    harness declares its columns.

    `coerce` declares what a COLUMN IS, by name or position: {"h": "epoch_s"}
    says the column holds an instant, so an engine returning a datetime and one
    returning epoch milliseconds agree. It is declared once per query in the
    lane, never per engine, so it cannot be used to make one engine's answer
    match another's.
    """
    if rows is None:
        return []
    if _is_mapping(rows) or not hasattr(rows, "__iter__") or isinstance(rows, (str, bytes)):
        rows = [rows]
    out = []
    for row in rows:
        if columns and _is_mapping(row):
            vals = [_lookup(row, c) for c in columns]
        elif columns and isinstance(row, (list, tuple)):
            # A POSITIONAL ROW ALREADY IS THE DECLARED ORDER. A SQL driver
            # hands back a tuple whose order is the SELECT list's, which is
            # what `columns` names; looking those names up in a tuple would
            # find nothing and silently digest a row of sentinels.
            vals = list(row)
        elif columns:
            vals = [row] + [_MISSING] * (len(columns) - 1)
        elif _is_mapping(row):
            vals = [row[k] for k in sorted(row.keys(), key=str)]
        elif isinstance(row, (list, tuple)):
            vals = list(row)
        else:
            vals = [row]
        if coerce:
            names = [c[0] if isinstance(c, (tuple, list)) else str(c) for c in (columns or ())]
            for i in range(len(vals)):
                how = coerce.get(i)
                if how is None and i < len(names):
                    how = coerce.get(names[i])
                if how is not None:
                    vals[i] = _coerce(vals[i], how)
        out.append(tuple(_fmt_value(v, float_digits) for v in vals))
    return out


def _key_positions(columns, key):
    if key is None:
        return None
    keys = key if isinstance(key, (tuple, list)) else (key,)
    pos = []
    for k in keys:
        if isinstance(k, int):
            pos.append(k)
        elif columns:
            names = [c[0] if isinstance(c, (tuple, list)) else c for c in columns]
            pos.append(names.index(k))
        else:
            raise ValueError(f"order_key {k!r} needs `columns` to resolve to a position")
    return tuple(pos)


def result_digest(rows, columns=None, order_matters=False, float_digits=6,
                  order_key=None, id_key=None, sample_rows=SAMPLE_ROWS,
                  coerce=None):
    """Canonical digest of one query's answer: {"digest", "sample", "n"}.

    `digest` is a short stable hash (16 hex characters of SHA-256 over the
    canonical form, the declared column names, and the ordering flags), `n` is
    the row count, and `sample` is the first few canonical rows as one short
    CSV-safe line, so a gate can print both sides of a disagreement instead of
    only announcing one.

    ORDER. Sorted unless `order_matters`, because a query without an ORDER BY
    does not define one and two engines returning the same set in different
    orders agree. When the query DOES define an order, the canonical form is a
    stable sort on the declared key with `id_key` as tie-break: engines break
    ties arbitrarily and identically-ranked rows in a different order are not a
    disagreement, while the membership of an ORDER BY ... LIMIT still is,
    because a wrong order returns a different SET of rows. The sort is applied
    to every engine identically, so it is a canonicalisation, not a relaxation.
    """
    canon = canonical_rows(rows, columns=columns, float_digits=float_digits, coerce=coerce)
    if order_matters:
        pos = _key_positions(columns, order_key)
        idp = _key_positions(columns, id_key)
        if pos is not None:
            def _k(r):
                head = tuple(r[i] for i in pos if i < len(r))
                tail = tuple(r[i] for i in idp if i < len(r)) if idp else r
                return (head, tail)
            canon = sorted(canon, key=_k)
        # order_key not declared: the engine's own order is the canonical one.
    else:
        canon = sorted(canon)
    names = [c[0] if isinstance(c, (tuple, list)) else str(c) for c in (columns or ())]
    marks = ",".join(f"{k}:{v if isinstance(v, str) else 'fn'}"
                     for k, v in sorted((coerce or {}).items(), key=lambda kv: str(kv[0])))
    blob = "\x1d".join([DIGEST_VERSION, ",".join(names), marks,
                        "ordered" if order_matters else "unordered",
                        str(float_digits), str(len(canon))]
                       + ["\x1f".join(r) for r in canon])
    h = hashlib.sha256(blob.encode("utf-8", "replace")).hexdigest()[:16]
    shown = " ; ".join("(" + ",".join(r) + ")" for r in canon[:sample_rows])
    if len(shown) > SAMPLE_MAX_CHARS:
        shown = shown[:SAMPLE_MAX_CHARS - 1] + "…"
    return {"digest": h, "sample": shown, "n": len(canon)}


def record_result(out, name, rows, **kw):
    """Stamp res_<name>_digest / _sample / _n onto a lane's output dict.

    Call it OUTSIDE the timed section with the object the timed call returned.
    Returns the digest dict so a caller can assert on it.
    """
    d = result_digest(rows, **kw)
    out[f"res_{name}_digest"] = d["digest"]
    out[f"res_{name}_sample"] = d["sample"]
    out[f"res_{name}_n"] = d["n"]
    return d


def record_unexpressible(out, name, reason):
    """This engine cannot ask this question, and the row says so.

    DECISIONS #88: "Queries that an engine cannot express are declared absent
    in its adapter, never silently skipped, and the gate names them." A blank
    is indistinguishable from agreement; this string is not.
    """
    text = UNEXPRESSIBLE_PREFIX + str(reason)
    out[f"res_{name}_digest"] = text
    out[f"res_{name}_sample"] = text
    out[f"res_{name}_n"] = None
    return text


def is_unexpressible(value):
    return isinstance(value, str) and value.startswith(UNEXPRESSIBLE_PREFIX)


# WHERE A MEASUREMENT DOES NOT APPLY, THE ROW SAYS SO (DECISIONS #89). "A
# table that omits one of these carries a stated reason, which page_check
# enforces the way it enforces the other page invariants." A blank cell is
# read as "not measured"; these strings say which of the two it is, and they
# live here so two lanes cannot phrase the same exemption differently.
NA_COLD_WARM_TXN = ("no cold/warm split: each operation runs against an "
                    "already-built, already-warm database by construction "
                    "(DECISIONS #89)")
NA_COLD_WARM_LIFECYCLE = ("no cold/warm split: this lane IS the cold "
                          "measurement -- it times opening a database "
                          "(DECISIONS #89)")
NA_COLD_WARM_INGEST = ("no cold/warm split: the timed work is a single "
                       "ingest, which happens once (DECISIONS #89)")
NA_INDEX_SPLIT_NONE = ("ingest and index are one timer: this engine indexes "
                       "while it ingests and has no boundary to split "
                       "(DECISIONS #66, #74 item 2)")
NA_COLD_WARM_DENSE_LANE = ("no cold/warm split on this row: the lane warms on a "
                           "held-out query slice before it times anything, so "
                           "every timed query here is warm. The dense table's "
                           "cold and warm columns come from the multipass "
                           "driver, whose pass 0 is the cold pass and whose "
                           "passes 1 to 5 are the warm ones (DECISIONS #89)")
NA_COLD_WARM_SPARSE_LANE = ("no cold/warm split on this row: the lane warms "
                            "before it times, so every timed query here is "
                            "warm. The sparse table's cold and warm columns "
                            "come from the multipass driver (DECISIONS #89)")


def record_cold_warm(out, name, warm_ms, cold_ms=None, digits=3):
    """COLD AND WARM, on every timed query (DECISIONS #89).

    "The first iteration after the database is opened is the cold number and
    the remaining iterations are the warm number, which costs nothing because
    those iterations already run, and it answers the question a reader actually
    has, which is what the first query of a session costs against the
    hundredth."

    Two call shapes, because the lanes differ in whether the cold pass is
    already separate:

        record_cold_warm(out, "q1", times)               # times[0] is cold
        record_cold_warm(out, "top_degree", warm, cold)  # cold measured apart

    One naming convention for all of them, so a table reads one field per lane
    instead of six spellings: cold_<q>_ms, warm_<q>_p50_ms, warm_<q>_p99_ms,
    warm_<q>_n. A lane keeps whatever pooled field it published before; these
    say what that pooled number is made of.
    """
    if cold_ms is None:
        if not warm_ms:
            return
        cold_ms, warm = warm_ms[0], list(warm_ms[1:])
    else:
        warm = list(warm_ms)
    out[f"cold_{name}_ms"] = round(float(cold_ms), digits)
    if warm:
        w = sorted(float(x) for x in warm)
        out[f"warm_{name}_p50_ms"] = round(_pct(w, 50), digits)
        out[f"warm_{name}_p99_ms"] = round(_pct(w, 99), digits)
        out[f"warm_{name}_n"] = len(w)
