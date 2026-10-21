#!/bin/bash
# Check that the wheel build tools resolve for every Python version available.
# Nothing is installed into any interpreter: `uv run --no-project --with build` puts the tools in
# a throwaway environment, the same way the CI workflows run `build.sh` and `build-native.sh`.

set -e

echo "Checking Python installations and the build tools..."

if ! command -v uv &> /dev/null; then
    echo "❌ uv not found"
    echo "💡 Install uv: https://astral.sh/uv"
    exit 1
fi

check_build_tools() {
    local python_path="$1"
    if uv run --no-project --python "$python_path" --with build --with wheel --with setuptools \
        python -m build --version &> /dev/null; then
        echo "  ✅ build tools resolve for $python_path"
    else
        echo "  ⚠️  Could not resolve the build tools for $python_path"
    fi
}

# Check system python3
if command -v python3 &> /dev/null; then
    PYTHON_PATH=$(command -v python3)
    echo "Found python3 at: $PYTHON_PATH"
    check_build_tools "$PYTHON_PATH"
fi

# Also check common Homebrew Python 3.14 location
if [[ -f "/opt/homebrew/bin/python3.14" ]]; then
    echo "Found /opt/homebrew/bin/python3.14"
    check_build_tools /opt/homebrew/bin/python3.14
fi

echo ""
echo "To build a wheel natively, run the script under the same tools:"
echo "  uv run --no-project --with build --with wheel --with setuptools bash ./scripts/build.sh <platform>"
echo "✅ Done"
