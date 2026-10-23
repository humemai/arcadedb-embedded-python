"""Redis 8.10.2 on the documents (`redis_tpc`) and time-series (`redis_ts`) lanes, 2026-10-23.

Offline: a dict-backed fake of the few Redis commands the adapters send, so the transaction, single-record and read-back paths,
the registrations and the query commands are held without a server. The live check (answer digests against the other engines,
durability read back from CONFIG GET) is the PR's smoke.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench_common  # noqa: E402
import fairness_check  # noqa: E402
import l1_tpc as T  # noqa: E402
import l4_tsbs as L  # noqa: E402
import make_2611_stages as G  # noqa: E402
import runner  # noqa: E402


class FakePipe:
    def __init__(self, r, transaction):
        # redis-py: a transactional pipeline runs commands at once between WATCH and MULTI; a plain one only queues
        self.r, self.q, self.multi_on, self.tx = r, [], False, transaction

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def watch(self, *k):
        pass

    def multi(self):
        self.multi_on = True

    def execute_command(self, *a):
        if self.multi_on or not self.tx:
            self.q.append(a)
            return self
        return self.r.execute_command(*a)

    def execute(self):
        out = [self.r.execute_command(*a) for a in self.q]
        self.q = []
        return out


class FakeRedis:
    def __init__(self):
        self.d = {}
        self.log = []

    def pipeline(self, transaction=True):
        return FakePipe(self, transaction)

    def execute_command(self, *a):
        self.log.append(a)
        c = a[0]
        if c == "JSON.SET":
            key, path, val = a[1], a[2], a[3]
            if path == "$":
                self.d[key] = json.loads(val)
            else:
                self.d[key][path[2:]] = json.loads(val)
            return b"OK"
        if c == "JSON.GET":
            doc = self.d.get(a[1])
            if doc is None:
                return None
            return json.dumps({p: [doc[p[2:]]] for p in a[2:]})
        if c == "JSON.NUMINCRBY":
            self.d[a[1]][a[2][2:]] += a[3]
            return b"[0]"
        raise AssertionError(a)

    def delete(self, *k):
        for x in k:
            self.d.pop(x, None)

    def scan_iter(self, match, count=0):
        pre = match.rstrip("*")
        return iter([k for k in list(self.d) if k.startswith(pre)])


def _arm():
    b = T.RedisTPC()
    b.r = FakeRedis()
    b._pay_seq = 0
    for k in (1, 2, 3):
        b.r.d[f"part:{k}"] = {"p_partkey": k, "p_retailprice": 1.0, "stock": T.STOCK_START}
    return b


def test_new_order_inserts_the_order_and_decrements_the_stock():
    b = _arm()
    b.new_order(7, 2)
    b.new_order(8, 2)
    assert b.oltp_scan() == [(7, 2, 1, 0), (8, 2, 1, 0)]
    assert b.stock_scan() == [(2, T.STOCK_START - 2)]


def test_payment_marks_the_order_paid_and_inserts_one_payment_per_call():
    b = _arm()
    b.new_order(7, 3)
    b.payment(7)
    b.payment(7)                       # a repeated order key is a second payment, as on the document arms
    assert b.oltp_scan() == [(7, 3, 1, 1)]
    assert b.payments_n() == 2


def test_the_four_single_record_operations_leave_the_digests_the_lane_expects():
    b = _arm()
    b.crud_insert(5, 3)
    assert b.crud_scan() == [(5, 3, 1)]
    assert b.crud_read(5) == [(5, 3, 1)]
    b.crud_update(5)
    assert b.crud_scan() == [(5, 3, T.CRUD_QTY_AFTER_UPDATE)]
    b.crud_delete(5)
    assert b.crud_scan() == [] and b.crud_read(5) == []


def test_every_aggregate_carries_timeout_zero_and_the_analytics_cover_all_five_queries():
    b = T.RedisTPC()
    seen = []

    class R:
        def execute_command(self, *a):
            seen.append(a)
            return [0]
    b.r = R()
    for q in T.OLAP_QUERIES:
        b.olap(q)
    assert len(seen) == len(T.OLAP_QUERIES) == 5
    for a in seen:
        assert a[0] == "FT.AGGREGATE" and a[a.index("TIMEOUT") + 1] == "0"
    q6 = next(a for a in seen if "@disc:[0.05 0.07]" in a[2])
    assert "@ship:[19940101 19941231]" in q6[2] and "@qty:[-inf (24]" in q6[2]


def test_the_ship_date_key_is_yyyymmdd():
    assert T.RedisTPC._date_n("1998-09-02") == 19980902


def test_registered_on_both_lanes_and_in_the_stage_generator():
    assert "redis_tpc" in runner.LANES["l1tpc"][1] and "redis_ts" in runner.LANES["l4"][1]
    assert "redis_tpc" in T.BACKENDS and "redis_ts" in L.BACKENDS
    assert G.engine_of("redis_tpc") == G.engine_of("redis_ts") == G.engine_of("redis_dense") == "redis"
    assert "redis_tpc" in fairness_check.INDEX_DECISIONS["l1tpc"] and "redis_ts" in fairness_check.INDEX_DECISIONS["l4"]
    assert "redis_ts" in L._CLIENT_SERVER


def test_the_three_redis_arms_share_one_image_and_the_memory_and_thread_rules():
    cfg = [runner.BACKENDS[n] for n in ("redis_dense", "redis_tpc", "redis_ts")]
    assert len({c["server_image"] for c in cfg}) == 1
    for c in cfg:
        cmd = " ".join(c["server_cmd"])
        assert "--maxmemory {mem90_mib}mb" in cmd and "--maxmemory-policy noeviction" in cmd and "--io-threads {io_threads}" in cmd
    assert "--search-on-timeout fail" in " ".join(runner.BACKENDS["redis_tpc"]["server_cmd"])
    assert "--search-workers" not in " ".join(runner.BACKENDS["redis_ts"]["server_cmd"])


def test_strict_class_flags_reach_the_redis_documents_and_time_series_servers():
    for n in ("redis_tpc", "redis_ts"):
        patched, note = runner.durability_server_patch(runner.BACKENDS[n], "strict")
        assert "--appendfsync" in patched["server_cmd"] and "always" in patched["server_cmd"], n
        assert "appendonly=yes" in note


def test_time_series_commands_are_the_documented_forms():
    seen = []

    class R:
        def execute_command(self, *a):
            seen.append(a)
            return [[b"k:h1:uu", [], [[1, b"2"]]]] if a[0].startswith("TS.M") else [[1, b"2"]]
    b = L.RedisTS()
    b.r = R()
    b.q_range(); b.q_global(); b.q_groupby(); b.q_high(); b.q_orderlimit()
    rng, glob, grp, high, ol = seen
    assert rng[0] == "TS.RANGE" and rng[3] == (L.T0 + 3600) * 1000 - 1 and rng[-1] == 60_000
    assert glob[0] == "TS.MRANGE" and "REDUCE" in glob and glob[glob.index("REDUCE") + 1] == "avg"
    assert "GROUPBY" not in grp and grp[grp.index("AGGREGATION") + 1] == "avg"
    lo = float(high[high.index("FILTER_BY_VALUE") + 1])
    assert lo > L.HIGH and math.nextafter(L.HIGH, -math.inf) < L.HIGH and lo == math.nextafter(L.HIGH, math.inf)
    assert ol[0] == "TS.MREVRANGE" and ol[ol.index("COUNT") + 1] == L.ORDERLIMIT_N


def test_durability_strings_are_the_ones_the_dense_arm_reads_back():
    assert bench_common.STRICT_OF[bench_common.DURABILITY_REDIS] == bench_common.DURABILITY_REDIS_STRICT
    assert L.DURABILITY["redis_ts"] == bench_common.DURABILITY_REDIS
