#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

INPUT_DIR="${INPUT_DIR:-$EXAMPLES_DIR/my_test_databases}"

if [[ $# -gt 0 ]]; then
    echo "This script does not accept command-line arguments." >&2
    echo "Use env vars instead: INPUT_DIR=/path ./scripts/cleanup_dirs_without_results.sh" >&2
    exit 1
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo "Input directory not found: $INPUT_DIR" >&2
    exit 1
fi

echo "Scanning: $INPUT_DIR"
echo "Mode: APPLY (will delete)"
echo

mapfile -t candidate_dirs < <(find "$INPUT_DIR" -mindepth 1 -maxdepth 1 -type d | sort)

if [[ ${#candidate_dirs[@]} -eq 0 ]]; then
    echo "No directories found under $INPUT_DIR"
    exit 0
fi

to_remove=()
keep_count=0

for dir in "${candidate_dirs[@]}"; do
    has_results=0

    if compgen -G "$dir/results_*.json" > /dev/null; then
        has_results=1
    elif compgen -G "$dir/search_results_*.json" > /dev/null; then
        has_results=1
    fi

    if [[ $has_results -eq 1 ]]; then
        keep_count=$((keep_count + 1))
        continue
    fi

    to_remove+=("$dir")
done

echo "Total dirs scanned : ${#candidate_dirs[@]}"
echo "Dirs with results  : $keep_count"
echo "Dirs to remove     : ${#to_remove[@]}"
echo

if [[ ${#to_remove[@]} -eq 0 ]]; then
    echo "Nothing to remove."
    exit 0
fi

printf '%s\n' "${to_remove[@]}"
echo

for dir in "${to_remove[@]}"; do
    rm -rf "$dir"
done
echo "Removed ${#to_remove[@]} directories without results."
