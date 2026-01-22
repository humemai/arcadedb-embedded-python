#!/bin/bash
# Script to sync upstream changes while preserving fork-specific customizations
#
# This fork maintains custom files that should never be overwritten:
#   - .github/workflows/  (Python CI/CD)
#   - bindings/python/    (Python bindings)
#   - README.md          (modified for Python)
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

# Show help
show_help() {
    cat << EOF
${BLUE}🔄 Upstream Sync Script${NC}

Syncs this fork with upstream ArcadeData/arcadedb while keeping:
    - upstream-main: clean mirror of upstream/main
    - main: fork changes rebased on top of upstream-main

${YELLOW}Usage:${NC}
  ./sync-upstream.sh            Sync with upstream (interactive)
  ./sync-upstream.sh --dry-run  Show what would be synced (no changes)
  ./sync-upstream.sh --status   Check sync status only
  ./sync-upstream.sh --help     Show this help

${YELLOW}Protected Files (never overwritten):${NC}
  • .github/workflows/    - Python CI/CD pipelines
  • bindings/python/      - Python bindings implementation
  • README.md            - Fork-specific documentation

${YELLOW}After Sync:${NC}
  1. Test: cd bindings/python && ./build.sh linux/amd64 && pytest tests/
  2. Push: git push --force-with-lease origin main

${YELLOW}Troubleshooting:${NC}
    Abort rebase:     git rebase --abort
    View changes:     git log main..upstream-main --oneline
    Check divergence: git log upstream-main..main --oneline

${YELLOW}Conflict Resolution:${NC}
  For README.md conflicts (common):
    git checkout --ours README.md    # Keep your version
    git add README.md
    git rebase --continue

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

    echo -e "${YELLOW}Branch:${NC} main (fork)"
    echo -e "${YELLOW}Upstream mirror:${NC} upstream-main"
    echo -e "${YELLOW}Remote:${NC} origin (humemai/arcadedb-embedded-python)"
    echo -e "${YELLOW}Upstream:${NC} upstream (ArcadeData/arcadedb)"
    echo ""

    if [ "$BEHIND" -eq 0 ]; then
        echo -e "${GREEN}✅ Up to date with upstream${NC}"
    else
        echo -e "${YELLOW}⚠️  Behind upstream by $BEHIND commit(s)${NC}"
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

# 3. Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ You have uncommitted changes${NC}"
    echo -e "${YELLOW}💡 Please commit or stash your changes first${NC}"
    git status --short
    exit 1
fi

# 4. Ensure upstream-main exists
if ! git show-ref --verify --quiet refs/heads/upstream-main; then
    echo -e "${YELLOW}➕ Creating upstream-main from upstream/main${NC}"
    git branch upstream-main upstream/main
fi

# 5. Show what will be synced
echo ""
UPSTREAM_COMMITS=$(git rev-list --count upstream-main..upstream/main)
if [ "$UPSTREAM_COMMITS" -eq 0 ]; then
    echo -e "${GREEN}✅ Already up to date with upstream!${NC}"
else
    echo -e "${BLUE}📋 Changes in upstream/main ($UPSTREAM_COMMITS new commit(s)):${NC}"
    git log upstream-main..upstream/main --oneline --max-count=10
fi

# 6. Dry run mode
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${CYAN}🔍 Dry run mode - no changes will be made${NC}"
    echo -e "${GREEN}✅ Dry run complete${NC}"
    exit 0
fi

# 7. Ask for confirmation
echo ""
read -p "$(echo -e ${YELLOW}Continue with rebase? [y/N]: ${NC})" -n 1 -r
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

# 9. Rebase fork main onto upstream-main
echo -e "${YELLOW}🔄 Rebasing main onto upstream-main...${NC}"
git checkout main
BAD_COMMIT_SUBJECT="Add comprehensive Python bindings for ArcadeDB"
BAD_COMMIT_HASH=$(git log --format="%H:%s" upstream-main..main | awk -F: -v subj="$BAD_COMMIT_SUBJECT" '$2==subj {print $1; exit}')
BAD_COMMIT_SHORT=""
if [ -n "$BAD_COMMIT_HASH" ]; then
    BAD_COMMIT_SHORT=$(git rev-parse --short "$BAD_COMMIT_HASH")
fi

if [ -n "$BAD_COMMIT_HASH" ]; then
    echo -e "${YELLOW}⚠️  Dropping known conflicting commit: ${BAD_COMMIT_HASH} (${BAD_COMMIT_SUBJECT})${NC}"
    TMP_EDITOR=$(mktemp)
    cat > "$TMP_EDITOR" << EOF
#!/bin/sh
sed -i -e "s/^pick ${BAD_COMMIT_SHORT} /drop ${BAD_COMMIT_SHORT} /" "\$1"
EOF
    chmod +x "$TMP_EDITOR"
    if GIT_SEQUENCE_EDITOR="$TMP_EDITOR" git rebase -i upstream-main; then
        rm -f "$TMP_EDITOR"
        echo -e "${GREEN}✅ Rebase successful!${NC}"
    else
        rm -f "$TMP_EDITOR"
        echo -e "${RED}❌ Rebase failed with conflicts${NC}"
        echo ""
        echo -e "${YELLOW}🔧 Conflict resolution steps:${NC}"
        echo -e "   1. Resolve conflicts in the listed files"
        echo -e "   2. Stage resolved files: ${BLUE}git add <file>${NC}"
        echo -e "   3. Continue rebase: ${BLUE}git rebase --continue${NC}"
        echo -e "   4. Or abort: ${BLUE}git rebase --abort${NC}"
        echo ""
        echo -e "${YELLOW}💡 Common fixes:${NC}"
        echo -e "   README.md conflict: ${BLUE}git checkout --ours README.md && git add README.md${NC}"
        echo ""
        echo -e "${CYAN}Run './sync-upstream.sh --help' for more troubleshooting tips${NC}"
        exit 1
    fi
elif git rebase upstream-main; then
    echo -e "${GREEN}✅ Rebase successful!${NC}"
else
    echo -e "${RED}❌ Rebase failed with conflicts${NC}"
    echo ""
    echo -e "${YELLOW}🔧 Conflict resolution steps:${NC}"
    echo -e "   1. Resolve conflicts in the listed files"
    echo -e "   2. Stage resolved files: ${BLUE}git add <file>${NC}"
    echo -e "   3. Continue rebase: ${BLUE}git rebase --continue${NC}"
    echo -e "   4. Or abort: ${BLUE}git rebase --abort${NC}"
    echo ""
    echo -e "${YELLOW}💡 Common fixes:${NC}"
    echo -e "   README.md conflict: ${BLUE}git checkout --ours README.md && git add README.md${NC}"
    echo ""
    echo -e "${CYAN}Run './sync-upstream.sh --help' for more troubleshooting tips${NC}"
    exit 1
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
echo ""
echo -e "   ${CYAN}3. Push to your fork:${NC}"
echo -e "      ${YELLOW}git push --force-with-lease origin main${NC}"
echo ""
echo -e "${YELLOW}⚠️  Always test before pushing! Use --force-with-lease (safer than --force)${NC}"
echo ""
