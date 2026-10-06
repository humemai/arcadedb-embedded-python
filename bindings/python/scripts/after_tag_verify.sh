#!/bin/bash
# After the tag push: verify the release end to end. Read-only against GitHub and PyPI (no writes).
#
# usage: after-tag-verify.sh <version> <previous-version> [<release-workflow-run-id>] [<expected-engine-jar-sha256> <expected-engine-buildNumber>]
# example: after-tag-verify.sh 26.10.1 26.9.1 <run-id> e2e98691a6c399f439d52f441536abf551e76d6b809d2c835d5e60061a84dc2a d36b4ca3ae4c170abc73598e0dffa2bb58e06621
#
# Run it under bash (not zsh). Every step prints PASS or FAIL; the exit code is the number of FAILs.
# Set PIN=4-5 to pin the smoke runs to those cores. It downloads about 3 GB (the 20 wheels of the run and four from PyPI): TMPDIR or WORK should point at a disk, not a tmpfs. Needs: gh, curl, python3, uv.
set -uo pipefail
V="${1:?version}"
PREV="${2:?previous version}"
RUN="${3:-}"
ENG_SHA="${4:-}"
ENG_BUILD="${5:-}"
R=humemai/arcadedb-embedded-python
W="${WORK:-$(mktemp -d "${TMPDIR:-$HOME}/after-tag-XXXXXX")}"
FAILS=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() {
    printf 'FAIL  %s\n' "$*"
    FAILS=$((FAILS + 1))
}
mkdir -p "$W"
printf 'work dir: %s\n' "$W"

# (a) the release workflow, and the publish JOB's own conclusion (the job has continue-on-error: true)
if [ -n "$RUN" ]; then
    gh run view "$RUN" -R "$R" --json status,conclusion,headBranch,headSha,createdAt,updatedAt > "$W/run.json" 2>&1 || true
    python3 - "$W/run.json" "$V" << 'EOF' || FAILS=$((FAILS + 1))
import json,sys
d=json.load(open(sys.argv[1]))
ok = d.get("status")=="completed" and d.get("conclusion")=="success" and d.get("headBranch")==sys.argv[2]
print(("PASS" if ok else "FAIL"), " release run:", d.get("status"), d.get("conclusion"), "ref", d.get("headBranch"), "sha", (d.get("headSha") or "")[:12], d.get("createdAt"), "->", d.get("updatedAt"))
sys.exit(0 if ok else 1)
EOF
    gh api "repos/$R/actions/runs/$RUN/jobs" --paginate --jq '.jobs[] | select(.name|startswith("Publish")) | [.name,.status,.conclusion,(.steps|map(select(.name=="Publish to PyPI"))|.[0].conclusion)]|@tsv' > "$W/publish-job.tsv" 2>&1
    cat "$W/publish-job.tsv"
    if awk -F'\t' '$2=="completed" && $3=="success" && $4=="success"{ok=1} END{exit ok?0:1}' "$W/publish-job.tsv"; then pass "publish job and its 'Publish to PyPI' step both succeeded"; else fail "publish job or its upload step did not succeed (a green run does not mean the upload worked)"; fi
fi

# (b) PyPI file set against the previous release: exactly the same 20 files with the new version, each under 100 MB (decimal)
curl -fsS "https://pypi.org/pypi/arcadedb-embedded/$V/json" -o "$W/pypi-new.json" || fail "PyPI has no $V yet"
curl -fsS "https://pypi.org/pypi/arcadedb-embedded/$PREV/json" -o "$W/pypi-prev.json" || fail "cannot read PyPI $PREV"
python3 - "$W/pypi-new.json" "$W/pypi-prev.json" "$V" "$PREV" << 'EOF' || FAILS=$((FAILS + 1))
import json,sys
new,prev,v,pv=json.load(open(sys.argv[1])),json.load(open(sys.argv[2])),sys.argv[3],sys.argv[4]
want={u["filename"].replace(pv,v) for u in prev["urls"]}
have={u["filename"]:u for u in new["urls"]}
missing=sorted(want-set(have)); extra=sorted(set(have)-want)
print("files on PyPI for %s: %d (previous release had %d)"%(v,len(have),len(prev["urls"])))
for m in missing: print("MISSING",m)
for e in extra: print("EXTRA  ",e)
big=[f for f,u in have.items() if u["size"]>=100_000_000]
yanked=[f for f,u in have.items() if u["yanked"]]
for f,u in sorted(have.items()): print("  %-62s %9.2f MB  %s"%(f,u["size"]/1e6,u["digests"]["sha256"][:16]))
ok=not missing and not extra and not big and not yanked and new["info"]["version"]==v
print(("PASS" if ok else "FAIL"),"file set identical in shape to the previous release, all under 100 MB, none yanked")
sys.exit(0 if ok else 1)
EOF

# (c) sha256 of every file on PyPI against the artifact the workflow built
if [ -n "$RUN" ] && [ -s "$W/pypi-new.json" ]; then
    mkdir -p "$W/artifacts"
    gh run download "$RUN" -R "$R" -p 'wheel-*-py*' -D "$W/artifacts" > /dev/null 2>&1 || fail "could not download the wheel artifacts of run $RUN (retention is 7 days)"
    python3 - "$W/pypi-new.json" "$W/artifacts" << 'EOF' || FAILS=$((FAILS + 1))
import json,sys,hashlib,pathlib
d=json.load(open(sys.argv[1])); art={}
for p in pathlib.Path(sys.argv[2]).rglob("*.whl"):
    art[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
bad=0
for u in d["urls"]:
    a=art.get(u["filename"])
    if a is None: print("NO ARTIFACT for",u["filename"]); bad+=1
    elif a!=u["digests"]["sha256"]: print("SHA MISMATCH",u["filename"]); bad+=1
print(("PASS" if not bad else "FAIL"),"%d PyPI files compared with %d workflow artifacts"%(len(d["urls"]),len(art)))
sys.exit(1 if bad else 0)
EOF
fi

# (d) every platform resolves, and a fresh venv installs and works (3.12 and 3.14)
for plat in manylinux_2_34_x86_64 manylinux_2_34_aarch64 macosx_11_0_arm64 win_amd64; do
    if uvx pip download --no-deps --only-binary=:all: --platform "$plat" --python-version 3.12 "arcadedb-embedded==$V" -d "$W/dl-$plat" > "$W/dl-$plat.log" 2>&1; then pass "pip download $plat (cp312)"; else fail "pip download $plat: $(tail -1 "$W/dl-$plat.log")"; fi
done
for py in 3.12 3.14; do
    [ -n "${SKIP_SMOKE:-}" ] && {
        printf "SKIP  smoke on Python %s (SKIP_SMOKE set)\n" "$py"
        continue
    }
    uv venv --python "$py" "$W/venv-$py" > /dev/null 2>&1 || {
        fail "uv venv $py"
        continue
    }
    uv pip install --no-cache --python "$W/venv-$py/bin/python" "arcadedb-embedded==$V" > "$W/install-$py.log" 2>&1 || {
        fail "uv pip install $V on $py: $(tail -1 "$W/install-$py.log")"
        continue
    }
    ENG_SHA="$ENG_SHA" ENG_BUILD="$ENG_BUILD" V="$V" ${PIN:+taskset -c "$PIN"} "$W/venv-$py/bin/python" - << 'EOF' > "$W/smoke-$py.log" 2>&1
import hashlib, os, pathlib, tempfile, zipfile
import arcadedb_embedded as adb
assert adb.__version__ == os.environ["V"], adb.__version__
jars = pathlib.Path(adb.__file__).parent / "jars"
eng = sorted(jars.glob("arcadedb-engine-*.jar"))
assert len(eng) == 1 and eng[0].name == "arcadedb-engine-%s.jar" % os.environ["V"], eng
sha = hashlib.sha256(eng[0].read_bytes()).hexdigest()
props = zipfile.ZipFile(eng[0]).read("com/arcadedb/arcadedb.properties").decode()
build = [l.split("=", 1)[1].strip() for l in props.splitlines() if l.startswith("buildNumber")][0]
print("engine jar", eng[0].name, sha, "buildNumber", build)
if os.environ["ENG_SHA"]: assert sha == os.environ["ENG_SHA"], "engine jar is not the official one"
if os.environ["ENG_BUILD"]: assert build == os.environ["ENG_BUILD"], "buildNumber differs"
with tempfile.TemporaryDirectory() as d:
    with adb.create_database(os.path.join(d, "smoke"), jvm_kwargs={"heap_size": "1g"}) as db:
        db.command("sql", "CREATE VERTEX TYPE P")
        with db.transaction():
            db.command("sql", "CREATE VERTEX P SET name = 'Ada'")
        assert db.query("sql", "SELECT name FROM P").to_list()[0]["name"] == "Ada"
        assert db.query("opencypher", "MATCH (n:P) RETURN n.name AS name").to_list()[0]["name"] == "Ada"
print("SMOKE OK", adb.__version__)
EOF
    if [ $? -eq 0 ] && grep -q 'SMOKE OK' "$W/smoke-$py.log"; then
        pass "fresh venv Python $py: install, import, SQL, openCypher, official engine jar"
        grep 'engine jar' "$W/smoke-$py.log"
    else
        fail "smoke on Python $py (see $W/smoke-$py.log)"
        tail -3 "$W/smoke-$py.log"
    fi
done

# (e) docs: the version selector lists $V and `latest` points at it
curl -fsS https://docs.humem.ai/arcadedb/versions.json -o "$W/versions.json" || fail "cannot read versions.json"
python3 - "$W/versions.json" "$V" << 'EOF' || FAILS=$((FAILS + 1))
import json,sys
vs=json.load(open(sys.argv[1])); v=sys.argv[2]
hit=[x for x in vs if x["version"]==v]
ok=bool(hit) and "latest" in hit[0].get("aliases",[])
print(("PASS" if ok else "FAIL"),"docs versions.json: first entries",[ (x["version"],x["aliases"]) for x in vs[:3]])
sys.exit(0 if ok else 1)
EOF
curl -fsS "https://docs.humem.ai/arcadedb/$V/" -o /dev/null && pass "docs page /$V/ answers" || fail "docs page /$V/ does not answer"
curl -fsS "https://docs.humem.ai/arcadedb/latest/guide/known-issues/" -o /dev/null && pass "docs latest known-issues page answers" || fail "docs latest known-issues page missing"

printf '\n%d FAIL(s)\n' "$FAILS"
exit "$FAILS"
