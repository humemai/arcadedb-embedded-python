#!/bin/bash
# Script to sync upstream changes while preserving fork-specific customizations
#
# This fork maintains a small set of fork-owned files that should never be
# overwritten by upstream during sync. Everything else, including
# bindings/python/, is merged normally from upstream-main into main.
#
# Usage: ./sync-upstream.sh [--help|--status|--dry-run]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

FORK_OWNED_PATHS=(
    "README.md"
    "CLAUDE.md"
)

# Upstream-owned files that may conflict because equivalent upstream commits were
# previously imported into the fork with different commit ancestry. In these
# cases we want the exact upstream version during sync.
UPSTREAM_PREFERRED_PATHS=(
    "engine/src/main/java/com/arcadedb/utility/RidHashSet.java"
)

PROTECTED_SOURCE_REV=""

try_auto_resolve() {
    local conflicts resolved path handled
    conflicts=$(git diff --name-only --diff-filter=U)
    if [ -z "$conflicts" ]; then
        return 1
    fi
    resolved=0
    for path in $conflicts; do
        handled=0
        for protected_path in "${FORK_OWNED_PATHS[@]}"; do
            if [[ "$path" == "$protected_path" ]]; then
                git checkout --ours -- "$path"
                git add "$path"
                resolved=1
                handled=1
                break
            fi
        done

        if [ "$handled" -eq 1 ]; then
            continue
        fi

        for upstream_path in "${UPSTREAM_PREFERRED_PATHS[@]}"; do
            if [[ "$path" == "$upstream_path" ]]; then
                echo -e "${CYAN}ℹ️  Auto-resolving upstream-preferred conflict: $path${NC}"
                git checkout --theirs -- "$path"
                git add "$path"
                resolved=1
                handled=1
                break
            fi
        done
    done
    if [ "$resolved" -eq 1 ]; then
        return 0
    fi
    return 1
}

capture_protected_source_rev() {
    PROTECTED_SOURCE_REV=$(git rev-parse HEAD)
}

restore_protected_paths() {
    local path tracked_entry

    for path in "${FORK_OWNED_PATHS[@]}"; do
        while IFS= read -r tracked_entry; do
            [ -n "$tracked_entry" ] || continue
            if ! git cat-file -e "$PROTECTED_SOURCE_REV:$tracked_entry" >/dev/null 2>&1; then
                git rm -r --cached --ignore-unmatch --quiet -- "$tracked_entry" >/dev/null 2>&1 || true
                rm -rf -- "$tracked_entry"
            fi
        done < <(git ls-files -- "$path")

        if git cat-file -e "$PROTECTED_SOURCE_REV:$path" >/dev/null 2>&1; then
            git restore --source="$PROTECTED_SOURCE_REV" --staged --worktree -- "$path"
        fi
    done
}

# Show help
show_help() {
    cat << EOF
${BLUE}🔄 Upstream Sync Script${NC}

Syncs this fork with upstream ArcadeData/arcadedb while keeping:
    - upstream-main: clean mirror of upstream/main
    - main: fork changes merged with upstream-main

${YELLOW}Usage:${NC}
  ./sync-upstream.sh            Sync with upstream (interactive)
  ./sync-upstream.sh --dry-run  Show what would be synced (no changes)
  ./sync-upstream.sh --status   Check sync status only
  ./sync-upstream.sh --help     Show this help

${YELLOW}Fork-Owned Files (restored after merge):${NC}
    • README.md
    • CLAUDE.md

${YELLOW}Normal Merge Paths:${NC}
    • bindings/python/      - Merges normally from upstream-main into main

${YELLOW}After Sync:${NC}
1. Test: cd bindings/python && ./build.sh linux/amd64 && pytest tests/
        (or on Windows: ./build.sh windows/amd64; on macOS: ./build.sh darwin/arm64)
2. Push: git push origin main

${YELLOW}Troubleshooting:${NC}
    Abort merge:      git merge --abort
    View changes:     git log main..upstream-main --oneline
    Check divergence: git log upstream-main..main --oneline

${CYAN}Learn more: https://github.com/humemai/arcadedb-embedded-python${NC}
EOF
    exit 0
}

# Check sync status
check_status() {
    echo -e "${BLUE}📊 Fork Sync Status${NC}"
    echo ""

    git fetch upstream --no-tags --quiet

    if ! git show-ref --verify --quiet refs/heads/upstream-main; then
        echo -e "${YELLOW}⚠️  upstream-main branch not found. Run './sync-upstream.sh' to create it.${NC}"
        exit 0
    fi

    AHEAD=$(git rev-list --count upstream-main..main 2>/dev/null || echo 0)
    BEHIND=$(git rev-list --count main..upstream-main 2>/dev/null || echo 0)
    MIRROR_PENDING=$(git rev-list --count upstream-main..upstream/main 2>/dev/null || echo 0)

    echo -e "${YELLOW}Branch:${NC} main (fork)"
    echo -e "${YELLOW}Upstream mirror:${NC} upstream-main"
    echo -e "${YELLOW}Remote:${NC} origin (humemai/arcadedb-embedded-python)"
    echo -e "${YELLOW}Upstream:${NC} upstream (ArcadeData/arcadedb)"
    echo ""

    if [ "$MIRROR_PENDING" -eq 0 ]; then
        echo -e "${GREEN}✅ upstream-main already matches upstream/main${NC}"
    else
        echo -e "${YELLOW}⚠️  upstream-main is behind upstream/main by $MIRROR_PENDING commit(s)${NC}"
    fi

    if [ "$BEHIND" -eq 0 ]; then
        echo -e "${GREEN}✅ main already contains upstream-main${NC}"
    else
        echo -e "${YELLOW}⚠️  main is behind upstream-main by $BEHIND commit(s)${NC}"
        echo ""
        echo -e "${CYAN}Recent upstream changes:${NC}"
        git log main..upstream-main --oneline --max-count=5
        echo ""
        echo -e "${BLUE}💡 Run './sync-upstream.sh' to sync${NC}"
    fi

    if [ "$AHEAD" -gt 0 ]; then
        echo -e "${CYAN}📝 Fork-specific commits: $AHEAD${NC}"
    fi

    exit 0
}

# Parse arguments
DRY_RUN=false
case "${1:-}" in
    --help|-h)
        show_help
        ;;
    --status|-s)
        check_status
        ;;
    --dry-run|-n)
        DRY_RUN=true
        ;;
    "")
        # Continue with sync
        ;;
    *)
        echo -e "${RED}❌ Unknown option: $1${NC}"
        echo -e "${YELLOW}💡 Use --help for usage information${NC}"
        exit 1
        ;;
esac

echo -e "${BLUE}🔄 Syncing with upstream ArcadeData/arcadedb...${NC}"
echo ""

# 1. Fetch latest upstream changes
echo -e "${YELLOW}📥 Fetching upstream changes...${NC}"
git fetch upstream --no-tags

# 2. Check current status
echo -e "${YELLOW}📊 Checking current branch...${NC}"
CURRENT_BRANCH=$(git branch --show-current)
START_BRANCH="$CURRENT_BRANCH"

# 3. Ensure upstream-main exists
if ! git show-ref --verify --quiet refs/heads/upstream-main; then
    echo -e "${YELLOW}➕ Creating upstream-main from upstream/main${NC}"
    git branch upstream-main upstream/main
fi

# 4. Show what will be synced
echo ""
UPSTREAM_COMMITS=$(git rev-list --count upstream-main..upstream/main)
PENDING_MERGE_COMMITS=$(git rev-list --count main..upstream-main)
if [ "$UPSTREAM_COMMITS" -eq 0 ]; then
    echo -e "${GREEN}✅ upstream-main already matches upstream/main${NC}"
else
    echo -e "${BLUE}📋 Changes in upstream/main ($UPSTREAM_COMMITS new commit(s)):${NC}"
    git log upstream-main..upstream/main --oneline
fi

echo ""
if [ "$PENDING_MERGE_COMMITS" -eq 0 ]; then
    echo -e "${GREEN}✅ main already contains upstream-main${NC}"
else
    echo -e "${BLUE}📋 Changes that will be merged into main ($PENDING_MERGE_COMMITS commit(s)):${NC}"
    git log main..upstream-main --oneline --max-count=10
fi

# 5. Dry run mode
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${CYAN}🔍 Dry run mode - no changes will be made${NC}"
    echo -e "${GREEN}✅ Dry run complete${NC}"
    exit 0
fi

# 6. Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ You have uncommitted changes${NC}"
    echo -e "${YELLOW}💡 Please commit or stash your changes first${NC}"
    git status --short
    exit 1
fi

# 6b. Capture the exact tracked fork state for fork-owned files before merge
capture_protected_source_rev

# 7. Ask for confirmation
echo ""
read -p "$(echo -e ${YELLOW}Continue with merge? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Sync cancelled${NC}"
    exit 1
fi

# 8. Update upstream-main mirror
echo ""
echo -e "${YELLOW}🔄 Updating upstream-main...${NC}"
git checkout upstream-main
git reset --hard upstream/main

# 9. Merge upstream-main into main
echo -e "${YELLOW}🔄 Merging upstream-main into main...${NC}"
git checkout main
if git merge-base --is-ancestor upstream-main main; then
    echo -e "${GREEN}✅ No merge needed - main already contains upstream-main${NC}"
elif git merge --no-edit upstream-main; then
    echo -e "${GREEN}✅ Merge successful!${NC}"
else
    while try_auto_resolve; do
        if git merge --continue; then
            echo -e "${GREEN}✅ Merge successful!${NC}"
            break
        fi
    done
    if [ -f .git/MERGE_HEAD ]; then
        echo -e "${RED}❌ Merge failed with conflicts${NC}"
        echo ""
        echo -e "${YELLOW}🔧 Conflict resolution steps:${NC}"
        echo -e "   1. Resolve conflicts in the listed files"
        echo -e "   2. Stage resolved files: ${BLUE}git add <file>${NC}"
        echo -e "   3. Continue merge: ${BLUE}git merge --continue${NC}"
        echo -e "   4. Or abort: ${BLUE}git merge --abort${NC}"
        echo ""
        echo -e "${CYAN}Run './sync-upstream.sh --help' for more troubleshooting tips${NC}"
        exit 1
    fi
fi

# 9b. Restore fork-owned files exactly as they were before the rebase
restore_protected_paths

# Commit fork-specific preservation changes only when needed
if ! git diff --cached --quiet; then
    git commit -m "chore(sync): preserve fork custom files"
fi

# 10. Return to original branch if needed
if [ "$START_BRANCH" != "main" ] && [ "$START_BRANCH" != "upstream-main" ]; then
    git checkout "$START_BRANCH" >/dev/null 2>&1 || true
fi

# 11. Show summary
echo ""
echo -e "${GREEN}🎉 Sync complete!${NC}"
echo ""
echo -e "${BLUE}📊 Next steps (IMPORTANT):${NC}"
echo ""
echo -e "   ${CYAN}1. Review changes:${NC}"
echo -e "      ${YELLOW}git log --oneline -10${NC}"
echo ""
echo -e "   ${CYAN}2. Test locally (REQUIRED):${NC}"
echo -e "      ${YELLOW}cd bindings/python && ./build.sh linux/amd64${NC}"
echo -e "      ${YELLOW}pytest tests/ -v${NC}"
echo -e "      ${YELLOW}(or ./build.sh windows/amd64 on Windows; ./build.sh darwin/arm64 on macOS)${NC}"
echo ""
echo -e "   ${CYAN}3. Push to your fork:${NC}"
echo -e "      ${YELLOW}git push origin main${NC}"
echo ""
echo -e "${YELLOW}⚠️  Always test before pushing!${NC}"
echo ""
