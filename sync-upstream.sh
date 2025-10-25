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

Syncs this fork with upstream ArcadeData/arcadedb while preserving fork-specific files.

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
  1. Test: cd bindings/python && ./build-all.sh headless && pytest tests/
  2. Push: git push --force-with-lease origin main

${YELLOW}Troubleshooting:${NC}
  Abort rebase:     git rebase --abort
  View changes:     git log HEAD..upstream/main --oneline
  Check divergence: git log origin/main..HEAD --oneline

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

    git fetch upstream --quiet

    AHEAD=$(git rev-list --count upstream/main..HEAD)
    BEHIND=$(git rev-list --count HEAD..upstream/main)

    echo -e "${YELLOW}Branch:${NC} main"
    echo -e "${YELLOW}Remote:${NC} origin (humemai/arcadedb-embedded-python)"
    echo -e "${YELLOW}Upstream:${NC} upstream (ArcadeData/arcadedb)"
    echo ""

    if [ "$BEHIND" -eq 0 ]; then
        echo -e "${GREEN}✅ Up to date with upstream${NC}"
    else
        echo -e "${YELLOW}⚠️  Behind upstream by $BEHIND commit(s)${NC}"
        echo ""
        echo -e "${CYAN}Recent upstream changes:${NC}"
        git log HEAD..upstream/main --oneline --max-count=5
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
git fetch upstream

# 2. Check current status
echo -e "${YELLOW}📊 Checking current branch...${NC}"
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo -e "${RED}❌ Not on main branch (currently on: $CURRENT_BRANCH)${NC}"
    echo -e "${YELLOW}💡 Please checkout main first: git checkout main${NC}"
    exit 1
fi

# 3. Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}❌ You have uncommitted changes${NC}"
    echo -e "${YELLOW}💡 Please commit or stash your changes first${NC}"
    git status --short
    exit 1
fi

# 4. Show what will be synced
echo ""
UPSTREAM_COMMITS=$(git rev-list --count HEAD..upstream/main)
if [ "$UPSTREAM_COMMITS" -eq 0 ]; then
    echo -e "${GREEN}✅ Already up to date with upstream!${NC}"
    exit 0
fi

echo -e "${BLUE}📋 Changes in upstream/main ($UPSTREAM_COMMITS new commit(s)):${NC}"
git log HEAD..upstream/main --oneline --max-count=10

# 5. Dry run mode
if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${CYAN}🔍 Dry run mode - no changes will be made${NC}"
    echo -e "${GREEN}✅ Dry run complete${NC}"
    exit 0
fi

# 6. Ask for confirmation
echo ""
read -p "$(echo -e ${YELLOW}Continue with rebase? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Sync cancelled${NC}"
    exit 1
fi

# 7. Rebase onto upstream/main
echo ""
echo -e "${YELLOW}🔄 Rebasing onto upstream/main...${NC}"
if git rebase upstream/main; then
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

# 8. Show summary
echo ""
echo -e "${GREEN}🎉 Sync complete!${NC}"
echo ""
echo -e "${BLUE}📊 Next steps (IMPORTANT):${NC}"
echo ""
echo -e "   ${CYAN}1. Review changes:${NC}"
echo -e "      ${YELLOW}git log --oneline -10${NC}"
echo ""
echo -e "   ${CYAN}2. Test locally (REQUIRED):${NC}"
echo -e "      ${YELLOW}cd bindings/python && ./build-all.sh headless${NC}"
echo -e "      ${YELLOW}pytest tests/ -v${NC}"
echo ""
echo -e "   ${CYAN}3. Push to your fork:${NC}"
echo -e "      ${YELLOW}git push --force-with-lease origin main${NC}"
echo ""
echo -e "${YELLOW}⚠️  Always test before pushing! Use --force-with-lease (safer than --force)${NC}"
echo ""
