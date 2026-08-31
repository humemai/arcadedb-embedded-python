"""The deep10m ArcadeDB matrix: 2 quantizations x 2 deployments x 2 cache policies.

Every arm runs at heap 24g, cpuset 0-11 and a 36g engine container cap, so the
only intended variables are the three in the title. Prints what each cell ASKED
the engine for, what the engine CHOSE, and what it cost.

WHY `chosen` IS THE COLUMN THAT MATTERS. computeGraphBuildCacheCapacity:

    if (configured > 0)     return configured;           // the crossed rows
    if (inlineQuantization) return DEFAULT_CACHE_SIZE;   // INT8 -> 100,000, RETURNS
    ... budgetBytes(pct) = availableHeapBytes()/100*pct  // fp32 only
        availableHeapBytes() = max - live                // NOT max

So int8 picks a constant and fp32 picks a value that depends on how much heap
happens to be live when CREATE INDEX runs. Observed: int8 served 100,000 twice
with builds 1.8% apart; fp32 served 3,674,697 with builds spanning 3.4x.

READING THE MEMORY COLUMNS. peak_mib_sum SUMS containers -- a served cell is
engine(36g cap) + driver(8g cap), an embedded cell is ONE container holding both
the engine and the ~5.4 GiB numpy corpus -- so served rows read higher for a
container-count reason, not an engine one. The comparable number is peak ANON,
which excludes page cache and is the figure that has produced bogus cross-engine
ratios when people used the total instead.

Peak memory is FLAT across the 3.4x build spread (28.2-28.5 GiB anon on every
arm), so it cannot distinguish a fast rep from a slow one. The cache is 1.53 GiB
against a 28 GiB anon peak, well inside this column's noise.
"""
import json, pathlib, re
R = pathlib.Path("/home/tk/repos/humemai/arcadedb-embedded-python/benchmarks/experiments/results")
RAW = R / "raw"
def rows_from(fn):
    p = R / fn
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
main = [r for r in rows_from("runs_page_8d6af9475.jsonl")
        if r.get("scale")=="deep10m" and "arcadedb" in str(r.get("backend"))]
abl  = [r for r in rows_from("ablation_cache_8d6af9475.jsonl") if r.get("scale")=="deep10m"]
def chosen(be, rep):
    for suf in ("serverlog","clientlog"):
        for t in (f".{suf}.live", f".{suf}"):
            f = RAW/f"l3d_{be}_search_deep10m_r{rep}{t}"
            if f.exists():
                m = re.search(r"cache enabled: size=(\d+)", f.read_text(errors="replace"))
                if m: return int(m.group(1))
    return None
def rng(vals, fmt="{:.0f}"):
    v=[x for x in vals if isinstance(x,(int,float))]
    if not v: return "-"
    return fmt.format(min(v)) if len(set(v))==1 or len(v)==1 else f"{fmt.format(min(v))}-{fmt.format(max(v))}"
ARMS=[("fp32","emb","arcadedb_dense_embedded"),("fp32","srv","arcadedb_dense_server"),
      ("INT8","emb","arcadedb_dense_embedded_int8"),("INT8","srv","arcadedb_dense_server_int8")]
print("  deep10m, heap 24g, cpuset 0-11, engine container cap 36g")
print()
print(f"  {'#':>2} {'q':4} {'dep':4} {'asked':>8} {'chosen':>10} {'n':>4} {'build min':>11} "
      f"{'peak tot GiB':>12} {'peak anon GiB':>13} {'anon%':>6}")
n=0
for src,pool in (("main",main),("abl",abl)):
    for q,dep,be in ARMS:
        n+=1
        rs=[r for r in pool if r.get("backend")==be and not r.get("error")]
        asked = "0 (auto)" if src=="main" else ("100000" if q=="fp32" else "3674697")
        chs=sorted({c for c in (chosen(be,r.get("rep")) for r in rs) if c})
        tot=[r.get("peak_mib_sum") for r in rs]
        anon=[r.get("peak_anon_mib_sum") for r in rs]
        pct=[100*a/t for a,t in zip(anon,tot) if isinstance(a,(int,float)) and isinstance(t,(int,float)) and t]
        tgt = 5 if src=="main" else 2
        print(f"  {n:>2} {q:4} {dep:4} {asked:>8} {(','.join(f'{c:,}' for c in chs) or '-'):>10} "
              f"{len(rs)}/{tgt:<2} {rng([x/60 for x in [r.get('build_s') for r in rs] if x]):>11} "
              f"{rng([x/1024 for x in tot if x],'{:.1f}'):>12} "
              f"{rng([x/1024 for x in anon if x],'{:.1f}'):>13} {rng(pct,'{:.0f}'):>6}")
print()
print("  NOTE peak_mib_sum SUMS the containers. For a served cell that is engine(36g cap)")
print("  + driver(8g cap); for an embedded cell it is ONE container holding both.")
