#!/usr/bin/env bash
# Build a MATCHED (server image, embedded wheel) pair from one upstream commit,
# and PROVE they match by reading the commit out of the artifacts themselves.
#
# WHY THIS EXISTS. The campaign pins ArcadeDB by commit, because a local build
# reports version "26.9.1.dev0" whichever commit produced it. Until now the
# pairing was asserted by a launcher comment ("wheel AND server image both from
# <sha>") and enforced only by runner.py refusing one env var without the other,
# which proves they were PASSED together and nothing about what is inside them.
#
# That gap was not theoretical. On 2026-08-21 the image tagged
# `arcadedb-local:3ec4f07e0` was found to contain jars stamped
# 26556a16c336cbe04704632f666b443308986ed7 -- 24 commits away from its own tag.
# Every row of that campaign carried engine_commit=3ec4f07e0. The tag lied and
# nothing could have caught it, because nothing read the artifact.
#
# THE FIX IS THAT THE COMMIT IS IN THE BYTES. Every arcadedb-*.jar carries
# `com/arcadedb/arcadedb.properties` holding the full 40-char sha, written by
# buildnumber-maven-plugin (engine/pom.xml:89-101) from the git checkout at
# build time. It works on upstream's published images too. So the check is not
# "did we tag it right" but "what does the artifact say it is", asked in three
# places and required to agree.
#
# Docker LABELS are deliberately not the check. A label is written by whoever
# ran the build and would have reproduced the exact lie above.
#
# Usage:
#   ./build_engine_pair.sh <commit-ish>     build the pair and verify
#   ./build_engine_pair.sh --verify <sha>   re-verify existing artifacts only
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BUILD_IMAGE="arcadedb-build:maven25-git"

die() { echo "ERROR: $*" >&2; exit 1; }
say() { echo ">>> $*"; }

# Read the engine commit out of a jar's own bytes. One implementation, three
# call sites, because a verification that reads the artifact differently in
# each place is not one verification.
#
# python3 -m zipfile, NOT unzip. mini has no unzip, and the first version of
# this script used it: the read failed, the error went to /dev/null, and the
# check reported "no buildNumber -- the build lost git" for a build that was
# perfectly fine. A missing tool must not be able to impersonate a finding, so
# this uses the interpreter the harness already depends on everywhere.
read_jar_props() {   # <path to a jar>
  python3 - "$1" <<'PY'
import sys, zipfile
try:
    with zipfile.ZipFile(sys.argv[1]) as z:
        sys.stdout.write(z.read("com/arcadedb/arcadedb.properties").decode())
except Exception as e:
    print("READ_FAILED: %s" % e, file=sys.stderr)
    sys.exit(3)
PY
}

props_from_jar_dir() {   # <dir containing arcadedb-engine-*.jar>
  local jar; jar=$(ls "$1"/arcadedb-engine-*.jar 2>/dev/null | head -1)
  [ -n "$jar" ] || { echo "NO_JAR_IN: $1" >&2; return 1; }
  read_jar_props "$jar"
}

sha_from_props() { sed -n 's/^buildNumber *= *//p' | tr -d '[:space:]'; }

# Copy a jar OUT of an image and read it on the host: the image is a pinned
# upstream artifact and may contain neither unzip nor python3, and installing
# into it to inspect it would change the thing being inspected.
props_from_image() {   # <image>
  local out; out=$(mktemp)
  docker run --rm --entrypoint sh "$1" \
    -c 'cat /home/arcadedb/lib/arcadedb-engine-*.jar' > "$out" 2>/dev/null \
    || { rm -f "$out"; echo "IMAGE_READ_FAILED: $1" >&2; return 1; }
  read_jar_props "$out"; local rc=$?
  rm -f "$out"; return $rc
}

# THE SHA THE JARS WILL ACTUALLY CARRY. buildnumber-maven-plugin runs
#   git log -1 --no-merges --format=format:%H
# so on a MERGE commit it reports the last non-merge ancestor, never the merge
# itself. Our sync-upstream.sh produces a merge commit every time it runs, so
# pinning a campaign to a freshly synced HEAD made verification impossible: the
# tree was correct, the jars were correct, and the comparison could not succeed.
#
# Resolve the requested commit the same way the plugin will, and compare against
# THAT. This weakens nothing: the point of the check is that the artifact matches
# the tree it was built from, and --no-merges is how the tree reports itself.
stamp_sha_for() {  # <commit-ish> -> the sha buildnumber-maven-plugin will write
  git -C "$REPO" log -1 --no-merges --format=format:%H "$1"
}

verify_sha() {  # <label> <40-char sha found> <expected>
  local what="$1" got="$2" want="$3"
  [ -n "$got" ] || die "$what: no buildNumber in arcadedb.properties. The build lost git, and a jar that cannot say what it is must not be published."
  [[ "$got" =~ ^[0-9a-f]{40}$ ]] || die "$what: buildNumber '$got' is not a 40-char sha"
  [ "$got" = "$want" ] || die "$what: contains $got but expected $want. This is the failure that shipped arcadedb-local:3ec4f07e0 holding 26556a16c jars."
  echo "    OK  $what -> ${got:0:9}"
}

# ---------------------------------------------------------------- verify only
if [ "${1:-}" = "--verify" ]; then
  SHA_SHORT="${2:?usage: --verify <sha>}"
  SHA=$(stamp_sha_for "$SHA_SHORT")
  IMG="arcadedb-local:${SHA:0:9}"
  say "verifying pair at $SHA"
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

  props_from_image "$IMG" > "$tmp/img.props" || die "cannot read $IMG"
  verify_sha "server image $IMG" "$(sha_from_props < "$tmp/img.props")" "$SHA"

  W=$(ls -t "$REPO"/bindings/python/dist/*.whl 2>/dev/null | head -1)
  [ -n "$W" ] || die "no wheel in bindings/python/dist"
  # Read the engine jar straight out of the wheel: a wheel is a zip holding a
  # zip, and unpacking 67 MiB to disk to look at one file inside one jar is
  # both slower and one more place for a stale extraction to be read by
  # mistake.
  verify_sha "wheel $(basename "$W")" "$(python3 - "$W" <<'PY' | sha_from_props
import sys, io, zipfile
z = zipfile.ZipFile(sys.argv[1])
jn = [n for n in z.namelist() if "arcadedb-engine-" in n and n.endswith(".jar")]
if not jn:
    print("READ_FAILED: no engine jar in wheel", file=sys.stderr); sys.exit(3)
inner = zipfile.ZipFile(io.BytesIO(z.read(jn[0])))
sys.stdout.write(inner.read("com/arcadedb/arcadedb.properties").decode())
PY
)" "$SHA"

  # The embedded arm does NOT run $ARCADEDB_WHEEL. It runs whatever wheel was
  # baked into dbbench:arcadedb the last time build_images.sh ran, so a stale
  # bench image passes every other check while measuring a different engine
  # from the server arm beside it. That is the exact F5 failure the pairing
  # exists to prevent, so it is checked here rather than assumed.
  if docker image inspect dbbench:arcadedb >/dev/null 2>&1; then
    # The bench image DOES ship python3 (it runs the drivers), so ask it for
    # the jar bytes and read them here.
    if docker run --rm --entrypoint sh dbbench:arcadedb -c \
         'cat $(python3 -c "import arcadedb_embedded,os;print(os.path.dirname(arcadedb_embedded.__file__))")/jars/arcadedb-engine-*.jar' \
         > "$tmp/bench.jar" 2>/dev/null && [ -s "$tmp/bench.jar" ]; then
      verify_sha "bench image dbbench:arcadedb" \
        "$(read_jar_props "$tmp/bench.jar" | sha_from_props)" "$SHA"
    else
      echo "    WARN dbbench:arcadedb unreadable; rebuild it before running"
    fi
  else
    echo "    WARN dbbench:arcadedb absent; build_images.sh must run before the campaign"
  fi
  say "PAIR VERIFIED at $SHA"
  exit 0
fi

# ---------------------------------------------------------------------- build
SHA_IN="${1:?usage: build_engine_pair.sh <commit-ish>}"
git -C "$REPO" rev-parse --verify "$SHA_IN" >/dev/null 2>&1 || die "unknown commit $SHA_IN"
SHA=$(stamp_sha_for "$SHA_IN")
[ -n "$SHA" ] || die "no non-merge commit reachable from $SHA_IN"

# THE TREE TO BUILD IS NOT THE SHA THE JARS WILL CARRY, and conflating them
# builds the wrong code. $SHA above answers "what will the plugin stamp"; it is
# the last non-merge ANCESTOR, whose tree is not the merge's tree whenever the
# merge actually combined anything. Checking $SHA out therefore silently builds
# the merged-in branch tip instead of the merge result.
#
# Caught building 1b04483bf (the #6743 merge, what upstream shipped): it resolved
# to 78e63b047 (the PR tip) whose tree differs across ALL FIVE files of the
# sparse query hot path -- the exact code the build existed to re-measure. That
# would have reproduced the provenance error the re-measure was correcting.
#
# So: build the tree that was ASKED FOR, and keep $SHA only as the expected
# stamp. For a non-merge argument the two are identical and nothing changes,
# which is every campaign build to date.
SHA_TREE=$(git -C "$REPO" rev-parse --verify "${SHA_IN}^{commit}")
SHORT="${SHA_TREE:0:9}"
IMG="arcadedb-local:$SHORT"
DEST="${BUILD_DEST:-$HOME/engine-builds/$SHORT}"

say "commit  $SHA_TREE"
[ "$SHA_TREE" = "$SHA" ] || say "stamp   $SHA (merge: jars carry the last non-merge ancestor)"
say "image   $IMG"
say "workdir $DEST"

# The build container needs git, or buildnumber-maven-plugin fails the build
# outright: engine/pom.xml configures no revisionOnScmFailure. Bake it once
# rather than installing on every build, so the toolchain is a pinned artifact
# too. NOTE: `yum install` in this image exits 0 without installing, so an
# `A || B` fallback silently keeps the broken half. Use dnf.
if ! docker image inspect "$BUILD_IMAGE" >/dev/null 2>&1; then
  say "baking $BUILD_IMAGE (maven + git)"
  printf 'FROM maven:3.9-amazoncorretto-25\nRUN dnf install -y git && dnf clean all\n' \
    | docker build -q -t "$BUILD_IMAGE" - >/dev/null
fi

mkdir -p "$DEST/home"
WT="$DEST/src"
if [ ! -d "$WT/.git" ]; then
  say "cloning at $SHORT"
  rm -rf "$WT"
  # A CLONE, not `git worktree add`. In a worktree, .git is a FILE holding an
  # absolute host path into the parent repo's .git/worktrees/, which is not
  # mounted into the container: git inside sees a dangling gitdir, the SCM
  # lookup fails, and the build dies (or worse, stamps a junk revision and
  # destroys the only provenance field we have). --local hardlinks the object
  # store, so this costs almost nothing.
  git clone --local --no-checkout "$REPO" "$WT" >/dev/null 2>&1
  git -C "$WT" checkout --detach "$SHA_TREE" >/dev/null 2>&1
fi
[ "$(git -C "$WT" rev-parse HEAD)" = "$SHA_TREE" ] || die "clone is not at $SHA_TREE"
# The tree, not just the commit id: this is the assertion that would have caught
# the merge-resolution bug above, since the wrong commit had the wrong tree.
[ "$(git -C "$WT" rev-parse HEAD^{tree})" = "$(git -C "$REPO" rev-parse "${SHA_IN}^{tree}")" ] \
  || die "clone tree does not match $SHA_IN"
[ -z "$(git -C "$WT" status --porcelain)" ] || die "clone is dirty; a build from a dirty tree cannot be identified by its commit"

# Skip maven when the assembly already carries this exact commit. The check is
# the same one V0 uses -- the jar's own buildNumber -- so "already built" means
# the same thing here as "verified" does below, rather than being a timestamp
# heuristic that could skip a stale tree.
# `|| true` is load-bearing under `set -euo pipefail`. On a FRESH workdir there is
# no package/target yet, so `ls -d` exits non-zero; `2>/dev/null` hides its message
# but not its status, pipefail promotes it to the pipeline's status, and the
# assignment then kills the script BEFORE the build it was about to do. The script
# therefore only ever worked on a tree some earlier build had already populated,
# which is exactly not the case for a newly pinned commit. Found when qW aborted
# on mini four seconds in, with no error text, on a commit it had never built.
CTX_PRE=$(ls -d "$WT"/package/target/arcadedb-*.dir 2>/dev/null | grep -v -- '-base\|-headless\|-minimal' | head -1 || true)
if [ -n "$CTX_PRE" ] && [ "$(props_from_jar_dir "$(ls -d "$CTX_PRE"/arcadedb-*/lib 2>/dev/null | head -1)" 2>/dev/null | sha_from_props)" = "$SHA" ]; then
  say "assembly already at $SHORT, skipping maven (BUILD_FORCE=1 to rebuild)"
  [ -z "${BUILD_FORCE:-}" ] || { say "BUILD_FORCE set, rebuilding"; NEED_MVN=1; }
else
  NEED_MVN=1
fi

if [ -n "${NEED_MVN:-}" ]; then
say "maven package (skipping tests)"
# -u so output is owned by the caller; HOME must be writable and NOT /root,
# which is mode 0750 root:root in this image, so a non-root uid cannot even
# traverse it. studio's frontend-maven-plugin also needs a writable HOME for
# its npm cache.
docker run --rm -u "$(id -u):$(id -g)" \
  -e HOME=/var/maven -e MAVEN_CONFIG=/var/maven/.m2 \
  -e MAVEN_OPTS=-Duser.home=/var/maven \
  -v "$DEST/home":/var/maven \
  -v "$WT":/src -w /src \
  --cpuset-cpus "${BUILD_CPUSET:-0-11}" \
  "$BUILD_IMAGE" \
  mvn -B -DskipTests -Dmaven.javadoc.skip=true clean package -pl package -am \
  > "$DEST/maven.log" 2>&1 || { tail -30 "$DEST/maven.log"; die "maven failed, see $DEST/maven.log"; }
fi

CTX=$(ls -d "$WT"/package/target/arcadedb-*.dir 2>/dev/null | grep -v -- '-base\|-headless\|-minimal' | head -1)
[ -n "$CTX" ] || die "no assembly directory under package/target"
LIB=$(ls -d "$CTX"/arcadedb-*/lib | head -1)
say "assembly $CTX ($(ls "$LIB"/*.jar | wc -l) jars)"

# V0 FIRST, on the build tree, before anything is tagged. If the jars cannot
# name their own commit there is nothing worth building an image from.
verify_sha "build tree" "$(props_from_jar_dir "$LIB" | sha_from_props)" "$SHA"

say "docker build $IMG"
# The assembly directory holds only arcadedb-<version>/; the Dockerfile is
# copied in by a maven docker profile that a plain `package` does not run, so
# point at the source one and keep the assembly as the context. The Dockerfile
# COPYs ./arcadedb-* relative to the context, so this is the same build the
# profile would have produced.
DF="$CTX/Dockerfile"
[ -f "$DF" ] || DF="$WT/package/src/main/docker/Dockerfile"
[ -f "$DF" ] || die "no Dockerfile in $CTX nor at package/src/main/docker/"
docker build -q -t "$IMG" -f "$DF" \
  --label "org.opencontainers.image.revision=$SHA" \
  "$CTX" >/dev/null

say "wheel with jar dir $LIB"
# JAR_LIB_DIR IS THE THIRD POSITIONAL ARGUMENT, NOT AN ENVIRONMENT VARIABLE.
# build.sh:37-39 reads PLATFORM=$1, PYTHON_VERSION=$2, JAR_LIB_DIR=$3. Exporting
# it as an env var is silently ignored and the build falls through to "Using
# JARs from ArcadeDB image", producing a wheel from a moving upstream tag while
# every log line still says the build succeeded. That is precisely how a wheel
# and a server image drift apart, and V0 caught it here: the wheel came out
# holding 9d154222c against an image holding 472e5bddf.
#
# Absolute path required as well: build.sh cd's into bindings/python before
# parsing args, so a relative path resolves against the wrong directory.
bash "$REPO/bindings/python/scripts/build.sh" "" "3.12" "$LIB" > "$DEST/wheel.log" 2>&1 \
  || { tail -30 "$DEST/wheel.log"; die "wheel build failed, see $DEST/wheel.log"; }
grep -q "Using provided JAR directory\|pre-staged" "$DEST/wheel.log" \
  || die "build.sh did not take the local jars (see $DEST/wheel.log). It printed: $(grep -m1 'JARs from' "$DEST/wheel.log")"

say "verifying"
"$0" --verify "$SHA"

cat > "$DEST/manifest.json" <<JSON
{
  "engine_commit": "$SHA",
  "engine_commit_short": "$SHORT",
  "server_image": "$IMG",
  "jar_count": $(ls "$LIB"/*.jar | wc -l),
  "assembly": "$CTX"
}
JSON
say "manifest at $DEST/manifest.json"
say "stamp rows with ARCADEDB_ENGINE_COMMIT=$SHORT"
