"""Read a captured ArcadeDB server log and say whether the build cache fit.

Decides between the two explanations for a slow served build:
  cache did not fit  -> `vector accesses` climbs much faster than progress
  GC / other         -> accesses tracks progress, heap pegged near max
"""
import re, sys, pathlib

PROG = re.compile(r"Graph build building: (\d+)/(\d+) \(vector accesses=(\d+), heap=([\d.]+)/([\d.]+)MB")
CHOSE = re.compile(r"Building graph with (\d+) vectors.*?cache enabled: size=(\d+)")

for path in sys.argv[1:]:
    p = pathlib.Path(path)
    if not p.exists():
        print(f"{p.name}: absent"); continue
    txt = p.read_text(errors="replace")
    print(f"=== {p.name} ===")
    m = CHOSE.search(txt)
    if m:
        vecs, cap = int(m.group(1)), int(m.group(2))
        pct = 100.0 * cap / vecs if vecs else 0
        verdict = "WHOLE CORPUS" if cap >= vecs else f"BOUNDED to {pct:.1f}% of corpus"
        print(f"  chosen build cache : size={cap:,} for {vecs:,} vectors  -> {verdict}")
    else:
        print("  chosen build cache : (line not captured)")
    rows = [(int(a), int(b), int(c), float(d), float(e)) for a, b, c, d, e in PROG.findall(txt)]
    if not rows:
        print("  no progress lines (still ingesting, or build not reached)"); continue
    f, l = rows[0], rows[-1]
    built = l[0] - f[0]
    acc = l[2] - f[2]
    ratio = acc / built if built else 0
    print(f"  progress           : {f[0]:,} -> {l[0]:,} of {l[1]:,}")
    print(f"  vector accesses    : {acc:,} for {built:,} built  -> {ratio:.2f}x per vector")
    print(f"  heap               : {f[3]:,.0f} -> {l[3]:,.0f} of {l[4]:,.0f} MB")
    if ratio > 1.5:
        print("  VERDICT: accesses far exceed progress -> the build cache is MISSING and re-reading")
    elif l[3] / l[4] > 0.92:
        print("  VERDICT: accesses track progress but heap is pegged -> GC pressure, not cache misses")
    else:
        print("  VERDICT: accesses track progress and heap has room -> healthy build")
