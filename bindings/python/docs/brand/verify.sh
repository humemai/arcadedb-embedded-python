#!/usr/bin/env bash
# Ships inside every vendored copy. Fails if a vendored file was edited in
# place or the copy is partial: the files must hash to what VERSION.md says.
set -euo pipefail
cd "$(dirname "$0")"
claimed=$(sed -n 's/^Hash:[[:space:]]*//p' VERSION.md)
actual=$(find css logo assets export -type f | LC_ALL=C sort | xargs sha256sum | sha256sum | awk '{print $1}')
if [ "$claimed" != "$actual" ]; then
    echo "✗ brand files differ from VERSION.md ($claimed vs $actual)."
    echo "  Change them in humemai/design-system and vendor again; don't edit the copy."
    exit 1
fi
echo "✓ brand files match VERSION.md"
