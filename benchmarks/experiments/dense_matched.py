#!/usr/bin/env python3
"""The matched dense comparison: every engine, one protocol, one envelope.

T5's dense block currently prints ArcadeDB's warm passes beside comparators'
single cold pass, at 36g against their 28g (#117, #121). queue61 and queue62
re-measure both sides under one protocol (one build, five timed passes, 20
untimed warmups before each) and one envelope (36g total, split 0.75/0.25 for
served backends), so cold AND warm exist for everyone.

This reads only results/dense_mp and never mixes in a published number. That
matters more than it sounds: the comparator levels moved in BOTH directions
against the published run (duckvss 16% slower, lancedb 5% faster), so the
old and new numbers are not interchangeable even where the ratio is stable.

    python3 dense_matched.py

Prints the matched table and the ranking at each operating point, and says
whether the paper's claim depends on which point is chosen.
"""
import glob
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
MP = os.path.join(HERE, "results", "dense_mp")

# Rows the paper cares about ranking against each other. Milvus (17.9 ms) and
# sqlite-vec (882 ms) are deliberately not re-measured: no cache pass reorders
# a number that far off the pace, and sqlite-vec would cost 73 minutes of pure
# query time. Their absence is stated wherever this output is used.
LABEL = {"arcade_fp32": "ArcadeDB (emb, fp32)",
         "arcade_int8": "ArcadeDB (emb, int8)",
         "chroma": "Chroma", "qdrant": "Qdrant",
         "duckvss": "DuckDB-VSS", "lancedb": "LanceDB"}


def load():
    out = {}
    for fp in sorted(glob.glob(os.path.join(MP, "mp_*.json"))):
        name = os.path.basename(fp)[3:-5]
        try:
            reps = json.load(open(fp))
        except Exception:
            continue
        cold = [r["p50"] for r in reps if r.get("rep") == 1]
        warm = [r["p50"] for r in reps if r.get("rep", 0) >= 2]
        if not (cold and warm):
            continue
        out[name] = {
            "cold": cold[0], "warm": st.median(warm),
            "cold99": [r["p99"] for r in reps if r.get("rep") == 1][0],
            "warm99": st.median([r["p99"] for r in reps if r.get("rep", 0) >= 2]),
            "recall": reps[0].get("recall_at_10"),
            "build_s": reps[0].get("build_s"),
            "mem": reps[0].get("mem_cap"),
            "lib": reps[0].get("lib_version") or reps[0].get("engine_version"),
            "n": len(reps),
        }
    return out


def main():
    d = load()
    if not d:
        raise SystemExit(f"no arms yet in {MP}")
    print(f"  DEEP-10M, one build + five passes, matched envelope "
          f"({len(d)} arm(s) measured)\n")
    print(f"  {'engine':22} {'cold p50':>9} {'warm p50':>9} {'gain':>6} "
          f"{'warm p99':>9} {'recall':>7} {'build':>7} {'mem':>5}")
    for k, v in sorted(d.items(), key=lambda x: x[1]["warm"]):
        print(f"  {LABEL.get(k, k):22} {v['cold']:9.3f} {v['warm']:9.3f} "
              f"{v['cold']/v['warm']:5.2f}x {v['warm99']:9.2f} "
              f"{(v['recall'] or 0):7.4f} {(v['build_s'] or 0):7.0f} "
              f"{str(v['mem']):>5}")

    missing = [k for k in ("arcade_fp32", "arcade_int8") if k not in d]
    if missing:
        print(f"\n  INCOMPLETE: {', '.join(missing)} not measured yet "
              f"(queue62). Rankings below are between comparators only and "
              f"must NOT be read as the paper's answer.")

    for point in ("cold", "warm"):
        board = sorted(((v[point], k) for k, v in d.items()))
        print(f"\n  ranking at {point:4} : " +
              "  ".join(f"{LABEL.get(k, k).split(' (')[0]} {t:.2f}"
                        for t, k in board))

    if "arcade_fp32" in d:
        rc = [k for _, k in sorted((v["cold"], k) for k, v in d.items())]
        rw = [k for _, k in sorted((v["warm"], k) for k, v in d.items())]
        pc, pw = rc.index("arcade_fp32") + 1, rw.index("arcade_fp32") + 1
        print(f"\n  ArcadeDB fp32 ranks {pc} cold and {pw} warm of {len(d)}.")
        if pc == pw:
            print("  Same rank either way: the operating point does not change")
            print("  the claim. Report warm, disclose cold, state that the")
            print("  comparators were re-measured under the same protocol.")
        else:
            print("  RANK DEPENDS ON THE OPERATING POINT. The table must lead")
            print("  with one point applied to every engine and say which,")
            print("  and the prose cannot claim a rank without naming it.")

    gains = {k: v["cold"] / v["warm"] for k, v in d.items()}
    flat = [k for k, g in gains.items() if g < 1.15 and not k.startswith("arcade")]
    if flat:
        print(f"\n  Comparators with no cold/warm distinction (gain < 1.15x): "
              f"{', '.join(LABEL.get(k, k).split(' (')[0] for k in flat)}.")
        print("  For those, the single number the published table prints is")
        print("  simultaneously their cold AND their warm number, which is why")
        print("  the old table was closer to a warm-vs-warm comparison than the")
        print("  protocol mismatch alone suggested.")


if __name__ == "__main__":
    main()
