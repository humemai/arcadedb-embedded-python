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
    """Find all necessary ArcadeDB JAR files using custom filtering."""
    # Get variant type from environment variable (for logging purposes)
    variant = os.environ.get("ARCADEDB_VARIANT", "base").lower()

    if variant not in ["base", "jre"]:
        print(f"⚠️  Warning: Invalid variant '{variant}', using 'base'")
        variant = "base"

    print(f"📦 Building variant: {variant}")
    print("📦 Including all JARs except gRPC wire protocol (optimal balance)")

    # Look for JAR files copied from the ArcadeDB Docker image
    # The Dockerfile copies JARs from the full distribution image to these locations
    quick_paths = [
        Path("/build/jars"),  # Docker build location
        Path("/home/arcadedb/lib"),  # Direct from ArcadeDB image
    ]

    all_jars = []

    # Check for jars from Docker image
    for quick in quick_paths:
        if quick.exists():
            jars = list(map(str, quick.glob("*.jar")))
            if jars:
                print("✅ Found {} JAR files in: {}".format(len(jars), quick))
                all_jars.extend(jars)
                break

    # Simple filtering: exclude only gRPC wire protocol (too big, not needed)
    if all_jars:
        included_jars = []
        excluded_jars = []

        for jar in all_jars:
            jar_name = Path(jar).name
            # Only exclude gRPC wire protocol
            if "arcadedb-grpcw-" in jar_name:
                excluded_jars.append(jar)
            else:
                included_jars.append(jar)

        print("\n📊 JAR Filtering Results:")
        print(f"   Total found: {len(all_jars)}")
        print(f"   Included: {len(included_jars)}")
        print(f"   Excluded: {len(excluded_jars)}")

        if excluded_jars:
            print("\n❌ Excluded JARs (gRPC protocol not needed):")
            for jar in excluded_jars:
                jar_name = Path(jar).name
                size_mb = Path(jar).stat().st_size / 1024 / 1024
                print(f"   - {jar_name} ({size_mb:.1f}MB)")

        print("\n✅ Included JARs:")
        for jar in included_jars:
            jar_name = Path(jar).name
            size_mb = Path(jar).stat().st_size / 1024 / 1024
            print(f"   - {jar_name} ({size_mb:.1f}MB)")

        return included_jars

    return []


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
