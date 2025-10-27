#!/usr/bin/env python3
"""Extract ArcadeDB version from parent pom.xml

ArcadeDB Python Bindings Versioning Strategy
============================================

This script implements the automated versioning system for ArcadeDB Python bindings.
It extracts versions from the main ArcadeDB pom.xml and converts them to PEP 440
compliant Python versions, supporting both development and release workflows.

## Key Principles

1. **Single Source of Truth**: Version is only defined in pom.xml - everything else
   extracts it
2. **PEP 440 Compliance**: All Python versions follow Python packaging standards
3. **Development/Release Distinction**: Different handling for -SNAPSHOT vs release
   versions
4. **Automated Conversion**: No manual version editing required in Python files

## Version Conversion Rules

| Maven Version (pom.xml) | Python Version | Use Case |
|-------------------------|----------------|----------|
| 25.10.1-SNAPSHOT        | 25.10.1.dev0   | Development builds |
| 25.9.1                  | 25.9.1         | Release builds |
| 25.9.1 (--python-patch 1) | 25.9.1.post1 | Python-specific patches |
| 25.9.1 (--python-patch 2) | 25.9.1.post2 | Additional Python patches |

## Development Mode vs Release Mode

**Development Mode** (SNAPSHOT versions):
- Triggered by: -SNAPSHOT suffix in pom.xml
- Conversion: X.Y.Z-SNAPSHOT → X.Y.Z.dev0
- Purpose: Pre-release development builds
- Example: 25.10.1-SNAPSHOT → 25.10.1.dev0

**Release Mode** (clean versions):
- Triggered by: No -SNAPSHOT suffix in pom.xml
- Conversion: X.Y.Z → X.Y.Z (or X.Y.Z.postN for Python patches)
- Purpose: Official releases to PyPI
- Example: 25.9.1 → 25.9.1 or 25.9.1.post1

## Python-Specific Patches

For Python-only bug fixes that don't require a new ArcadeDB version:

```bash
# Build with Python patch number
python extract_version.py --python-patch 1
# Results in: 25.9.1.post1 (if base ArcadeDB version is 25.9.1)

# Subsequent Python patches
python extract_version.py --python-patch 2
# Results in: 25.9.1.post2
```

## Usage Examples

```bash
# Basic usage (development mode)
python extract_version.py
# Output: 25.10.1.dev0 (from 25.10.1-SNAPSHOT in pom.xml)

# Basic usage (release mode)
python extract_version.py
# Output: 25.9.1 (from 25.9.1 in pom.xml)

# With Python patch for release
python extract_version.py --python-patch 1
# Output: 25.9.1.post1

# Docker format (raw Maven version)
python extract_version.py --format=docker
# Output: 25.10.1-SNAPSHOT (no conversion)

# Custom pom.xml path
python extract_version.py /path/to/pom.xml --format=pep440
```

## Integration Points

This script is used by:
- build-all.sh: For building Python packages
- Dockerfile.build: During Docker-based builds
- GitHub Actions: For CI/CD version extraction
- Release scripts: For PyPI publishing

## Error Handling

- Validates pom.xml file exists and is readable
- Ensures version tag is found in expected location
- Validates command-line arguments
- Provides clear error messages for debugging

Usage:
    python extract_version.py [pom_path] [--format=pep440|docker] [--python-patch=N]

    --format=pep440  : Convert to PEP 440 for Python packaging (default)
                       25.10.1-SNAPSHOT -> 25.10.1.dev0 (development)
                       25.9.1 -> 25.9.1 (first release)
    --format=docker  : Raw Maven version for Docker tags
                       25.10.1-SNAPSHOT -> 25.10.1-SNAPSHOT
    --python-patch=N : For released Java versions, add .postN suffix
                       25.9.1 + --python-patch=1 -> 25.9.1.post1
"""
import re
import sys
from pathlib import Path


def extract_raw_version_from_pom(pom_file):
    """Extract the raw version string from pom.xml (no conversion)"""
    with open(pom_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the first <version> tag after <artifactId>arcadedb-parent</artifactId>
    pattern = r"<artifactId>arcadedb-parent</artifactId>.*?<version>(.*?)</version>"
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(1).strip()

    raise ValueError("Could not find version in pom.xml")


def extract_version_from_pom(pom_file, fmt="pep440", patch_version=0):
    """Extract version from Maven pom.xml

    Args:
        pom_file: Path to pom.xml file
        fmt: 'pep440' for Python packaging, 'docker' for Docker tags
        patch_version: For released versions, add .postN suffix (0 = no suffix)
    """
    raw_version = extract_raw_version_from_pom(pom_file)

    if fmt == "docker":
        # Return raw Maven version for Docker tags
        return raw_version

    # Convert Maven version to PEP 440 compatible version
    is_snapshot = "-SNAPSHOT" in raw_version

    if is_snapshot:
        # Development mode: 25.10.1-SNAPSHOT -> 25.10.1.dev0
        base_version = raw_version.replace("-SNAPSHOT", "")
        return f"{base_version}.dev0"
    else:
        # Release mode: 25.9.1 -> 25.9.1 (or 25.9.1.post1 if patch_version > 0)
        base_version = raw_version

        # Handle other pre-release identifiers
        if "-RC" in base_version:
            base_version = base_version.replace("-RC", "rc")
        elif "-" in base_version:
            # Generic replacement for other pre-release identifiers
            base_version = base_version.replace("-", "")

        # Add Python patch version for Python-only releases
        if patch_version > 0:
            return f"{base_version}.post{patch_version}"
        else:
            return base_version


if __name__ == "__main__":
    # Default to parent pom.xml (two levels up from bindings/python)
    script_dir = Path(__file__).parent
    pom_path = script_dir / "../../pom.xml"
    output_format = "pep440"
    python_patch = 0

    # Parse arguments
    for arg in sys.argv[1:]:
        if arg.startswith("--format="):
            output_format = arg.split("=", 1)[1]
            if output_format not in ["pep440", "docker"]:
                print(
                    "Error: Invalid format. Use 'pep440' or 'docker'", file=sys.stderr
                )
                sys.exit(1)
        elif arg.startswith("--python-patch="):
            try:
                python_patch = int(arg.split("=", 1)[1])
                if python_patch < 0:
                    raise ValueError("Python patch version must be >= 0")
            except ValueError as e:
                print(f"Error: Invalid python-patch value: {e}", file=sys.stderr)
                sys.exit(1)
        elif not arg.startswith("--"):
            pom_path = Path(arg)

    try:
        extracted_version = extract_version_from_pom(
            pom_path, output_format, python_patch
        )
        print(extracted_version)
    except (ValueError, FileNotFoundError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
