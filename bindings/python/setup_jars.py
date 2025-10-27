#!/usr/bin/env python3
"""
Setup script to copy ArcadeDB JAR files to the Python package.

This script should be run as part of the build process to ensure
all necessary JAR files are included in the wheel.

Environment Variables:
    ARCADEDB_VARIANT: Package variant (base, jre)
                     Default: base
"""

import os
import shutil
from pathlib import Path


def find_jar_files():
    """Find all necessary ArcadeDB JAR files from minimal distribution."""
    # Get variant type from environment variable (for logging purposes)
    variant = os.environ.get("ARCADEDB_VARIANT", "base").lower()

    if variant not in ["base", "jre"]:
        print(f"⚠️  Warning: Invalid variant '{variant}', using 'base'")
        variant = "base"

    print(f"📦 Building variant: {variant}")
    print("📦 Using minimal distribution JAR set")

    # Look for JAR files copied from the ArcadeDB Docker image
    # The Dockerfile copies JARs from the minimal distribution image to these locations
    quick_paths = [
        Path("/build/jars"),  # Docker build location
        Path("/home/arcadedb/lib"),  # Direct from ArcadeDB image
    ]

    found_jars = []

    # Check for jars from Docker image
    for quick in quick_paths:
        if quick.exists():
            jars = list(map(str, quick.glob("*.jar")))
            if jars:
                print("✅ Found {} JAR files in: {}".format(len(jars), quick))
                found_jars.extend(jars)
                break

    # Remove duplicates while preserving order
    seen = set()
    unique_jars = []
    for jar in found_jars:
        jar_name = Path(jar).name
        # Skip test and source JARs to reduce size
        if "-tests.jar" in jar_name or "-sources.jar" in jar_name:
            continue
        if jar not in seen:
            seen.add(jar)
            unique_jars.append(jar)

    return unique_jars


def copy_jars_to_package():
    """Copy JAR files to the Python package."""
    package_dir = Path(__file__).parent
    jar_dir = package_dir / "src" / "arcadedb_embedded" / "jars"

    # Create jars directory if it doesn't exist
    jar_dir.mkdir(parents=True, exist_ok=True)

    # Find all JAR files
    jar_files = find_jar_files()

    if not jar_files:
        print("⚠️  Warning: No JAR files found!")
        print("   This script expects to run inside a Docker build")
        print("   where JARs are copied from the ArcadeDB image.")
        return False

    print(f"📦 Found {len(jar_files)} JAR files")

    # Copy JAR files
    copied_count = 0
    for jar_file in jar_files:
        jar_path = Path(jar_file)
        if jar_path.exists() and jar_path.stat().st_size > 0:
            dest_path = jar_dir / jar_path.name
            shutil.copy2(jar_path, dest_path)
            print(f"   ✅ Copied: {jar_path.name}")
            copied_count += 1
        else:
            print(f"   ⚠️  Skipped (empty or missing): {jar_path.name}")

    print(f"✅ Successfully copied {copied_count} JAR files to {jar_dir}")

    # Calculate total size
    total_size = sum(f.stat().st_size for f in jar_dir.glob("*.jar"))
    print(f"📊 Total package size: {total_size / 1024 / 1024:.1f} MB")

    return copied_count > 0


def main():
    """Main function."""
    variant = os.environ.get("ARCADEDB_VARIANT", "base").lower()

    print("🎮 ArcadeDB Python Package Setup")
    print("=" * 40)
    print(f"📦 Variant: {variant}")
    print()

    if copy_jars_to_package():
        print("\n🎉 Setup completed successfully!")
    else:
        print("\n❌ Setup failed!")
        print("💡 Make sure to run this via build-all.sh:")
        print("   cd bindings/python")
        print("   ./build-all.sh base")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
