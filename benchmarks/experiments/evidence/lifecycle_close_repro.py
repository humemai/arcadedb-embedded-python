"""Mechanism check for the lifecycle regression: what a no-op session costs
after ONE unsearched insert leaves a delta vector behind. Laptop, mechanism only;
timings are not comparable to mini's and are not reported as such."""
import os, sys, time, shutil, random, json
import arcadedb_embedded as a

N = int(sys.argv[1]); DIM = 32
DB = os.path.join(sys.argv[2], f"lc_repro_{N}")
shutil.rmtree(DB, ignore_errors=True)
HEAP = "4g"
KEYS = ("graphNodeCount", "persistedGraphNodeCount", "deltaVectorsCount",
        "stalePrefixGraphReuses", "asyncRebuildInProgress", "closeTimeRebuildPending",
        "graphRebuildCount", "unverifiedGraphReuses")


def stats(db):
    try:
        ti = db.schema.get_index_by_name("V[emb]")
        st = ti.getIndexesOnBuckets()[0].getStats()
        d = {str(k): int(st.get(k)) for k in st.keySet()}
        return {k: d.get(k) for k in KEYS}
    except Exception as e:  # noqa: BLE001
        return {"err": str(e)[:80]}


def session(label, action=None):
    t0 = time.perf_counter(); db = a.open_database(DB); t1 = time.perf_counter()
    s = stats(db)
    if action:
        action(db)
    t2 = time.perf_counter(); db.close(); t3 = time.perf_counter()
    print(f"  {label:32} open={1000*(t1-t0):7.1f} ms  close={1000*(t3-t2):7.1f} ms  {json.dumps(s)}", flush=True)


db = a.create_database(DB, jvm_kwargs={"heap_size": HEAP, "jvm_args": f"-Xms{HEAP}"})
c = db.command
c("sql", "CREATE VERTEX TYPE V"); c("sql", "CREATE PROPERTY V.id INTEGER"); c("sql", "CREATE PROPERTY V.emb ARRAY_OF_FLOATS")
rnd = random.Random(17); db.begin()
for i in range(N):
    v = ", ".join("%.6f" % rnd.random() for _ in range(DIM))
    c("sql", f"CREATE VERTEX V SET id = {i}, emb = [{v}]")
    if (i + 1) % 2000 == 0:
        db.commit(); db.begin()
db.commit()
t = time.perf_counter()
c("sql", f'CREATE INDEX ON V (emb) LSM_VECTOR METADATA {{ "dimensions": {DIM}, "similarity": "COSINE" }}')
print(f"  build {N}: {time.perf_counter()-t:.1f}s", flush=True)
t = time.perf_counter(); db.close(); print(f"  build-session close: {1000*(time.perf_counter()-t):.1f} ms", flush=True)

for k in range(3):
    session(f"clean #{k+1} (0 delta)")
v = ", ".join("0.25" for _ in range(DIM))


def one_insert(db):
    db.begin(); db.command("sql", f"INSERT INTO V SET id = {10_000_000}, emb = [{v}]"); db.commit()


def many_inserts(db):
    db.begin()
    for j in range(28):
        db.command("sql", f"INSERT INTO V SET id = {10_000_000 + j}, emb = [{v}]")
    db.commit()


def search(db):
    q = ", ".join("0.5" for _ in range(DIM))
    list(db.query("sql", f"SELECT FROM (SELECT expand(vectorNeighbors('V[emb]', [{q}], 10)))"))


session("write_own: 28 inserts, no search", many_inserts)
for k in range(2):
    session(f"clean #{k+1} (28 delta, unsearched)")
session("read: 1 search (loads graph)", search)
for k in range(3):
    session(f"clean #{k+1} (after a read)")
session("read again", search)
for k in range(2):
    session(f"clean #{k+1} (after 2nd read)")
