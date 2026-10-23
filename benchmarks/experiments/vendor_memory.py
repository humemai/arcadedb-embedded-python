"""The memory settings of the two comparators whose vendors give a rule for them (DECISIONS #202).

Every engine runs as its vendor recommends. For two JVM comparators the vendor's rule differs from the half-cap heap the
rest of the harness uses (`runner.HEAP_BY_SCALE`), so their arms take their heap, and Neo4j its page cache, from here:

  * Neo4j: the numbers `neo4j-admin server memory-recommendation` prints for the cell's cap, run from the pinned image
    (`neo4j_memory_recommendation.json`, written by `python3 vendor_memory.py --regenerate`; the test compares the table
    below with that file). The tool sets the initial heap equal to the maximum heap, as the Neo4j manual recommends.
  * Elasticsearch: the heap is no more than 50% of the cell's cap and below the compressed-oops threshold ("26GB is safe
    on most systems"), `-Xms` = `-Xmx`.

Nothing here imports the runner, so the runner, the tests and the page generator all read one table.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NEO4J_RECOMMENDATION_FILE = os.path.join(HERE, "neo4j_memory_recommendation.json")

# The image the tool ran from: the digest every Neo4j arm in runner.BACKENDS pins (2026.10.0-community).
NEO4J_IMAGE_DIGEST = "sha256:c3903fa96db31479c2a28e5d00e05260b039ff856f8b2cca7280c78299877731"
# The command that produced the table, per cap (`{cap}` is the cell's memory cap). It runs against an empty data directory, so
# the page cache it recommends is the one for a server whose memory is the only input, as for the cells that build their store.
NEO4J_RECOMMENDATION_COMMAND = ("docker run --rm -m 2g --entrypoint neo4j-admin neo4j@" + NEO4J_IMAGE_DIGEST
                                + " server memory-recommendation --memory={cap} --docker")

# cap -> (heap, page cache), both as the tool prints them. Initial heap = maximum heap. Generated from the file above.
NEO4J_MEMORY = {
    "8g": ("3600m", "2g"),
    "12g": ("4600m", "4g"),
    "16g": ("5g", "7g"),
    "24g": ("8g", "10g"),
    "28g": ("10g", "11g"),
    "32g": ("12g", "12g"),
    "36g": ("13800m", "14g"),
    "48g": ("18g", "20g"),
}

# Elasticsearch: "Set Xms and Xmx to no more than 50% of the total memory available to each Elasticsearch node" and "to no more
# than the threshold for compressed ordinary object pointers ... 26GB is safe on most systems".
ES_HEAP_CAP_FRACTION = 0.5
ES_HEAP_OOPS_CEILING_GIB = 26


def is_neo4j(backend):
    return "neo4j" in str(backend)


def is_elasticsearch(backend):
    return str(backend).startswith("elasticsearch")


def _gib(spec):
    m = re.fullmatch(r"(\d+)([gm])", str(spec))
    n = int(m.group(1))
    return n if m.group(2) == "g" else n / 1024.0


def parse_recommendation(output):
    """(heap_initial, heap_max, pagecache) as printed, from the tool's `--docker` output."""
    def get(name):
        m = re.search(r"^NEO4J_server_memory_" + name + r"='([^']+)'", output, re.M)
        return m.group(1) if m else None
    return get("heap_initial__size"), get("heap_max__size"), get("pagecache_size")


def elasticsearch_heap(tier_heap, cap):
    """The tier's heap, brought under Elastic's two ceilings (half the cap, the compressed-oops threshold), as `<n>g`."""
    gib = min(_gib(tier_heap), _gib(cap) * ES_HEAP_CAP_FRACTION, ES_HEAP_OOPS_CEILING_GIB)
    return f"{int(gib)}g" if gib == int(gib) else f"{int(gib * 1024)}m"


def heap_for(backend, tier_heap, cap):
    """The heap this arm runs with at a tier whose half-cap heap is `tier_heap` and whose cap is `cap`."""
    if is_neo4j(backend):
        return NEO4J_MEMORY[cap][0]
    if is_elasticsearch(backend):
        return elasticsearch_heap(tier_heap, cap)
    return tier_heap


def neo4j_pagecache(cap):
    return NEO4J_MEMORY[cap][1]


def regenerate(caps):
    """Run the tool from the pinned image for each cap and write the file the test reads."""
    out = {"image": "neo4j@" + NEO4J_IMAGE_DIGEST, "command": NEO4J_RECOMMENDATION_COMMAND, "caps": {}}
    for cap in caps:
        cmd = NEO4J_RECOMMENDATION_COMMAND.format(cap=cap).split()
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        hi, hm, pc = parse_recommendation(r.stdout)
        assert hi == hm and hm and pc, (cap, hi, hm, pc)
        out["caps"][cap] = {"heap_initial": hi, "heap_max": hm, "pagecache": pc, "output": r.stdout}
    with open(NEO4J_RECOMMENDATION_FILE + ".new", "w") as f:
        json.dump(out, f, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(NEO4J_RECOMMENDATION_FILE + ".new", NEO4J_RECOMMENDATION_FILE)
    print("wrote", NEO4J_RECOMMENDATION_FILE)
    for cap, v in out["caps"].items():
        print(f'    "{cap}": ("{v["heap_max"]}", "{v["pagecache"]}"),')


if __name__ == "__main__":
    if "--regenerate" not in sys.argv:
        sys.exit(__doc__)
    sys.path.insert(0, HERE)
    import runner
    regenerate(sorted(set(runner.MEM_BY_SCALE.values()), key=_gib))
