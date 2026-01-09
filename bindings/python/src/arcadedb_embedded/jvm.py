"""
ArcadeDB Python Bindings - JVM Management

Handles JVM initialization and JAR file management.
"""

import glob
import os
import platform
from pathlib import Path

import jpype
import jpype.imports

from .exceptions import ArcadeDBError


def get_jar_path() -> str:
    """Get the path to bundled JAR files."""
    package_dir = Path(__file__).parent
    jar_dir = package_dir / "jars"
    return str(jar_dir)


def get_bundled_jre_lib_path() -> str:
    """
    Get the path to bundled JRE's JVM library.

    Returns:
        Path to the JVM library (platform-specific: jvm.dll, libjvm.dylib,
        or libjvm.so).

    Raises:
        ArcadeDBError: If the bundled JRE or JVM library is not found.
    """
    package_dir = Path(__file__).parent
    jre_dir = package_dir / "jre"

    # Check if JRE directory exists
    if not jre_dir.exists():
        raise ArcadeDBError(
            f"Bundled JRE not found at {jre_dir}. "
            "The package may be corrupted or incomplete."
        )

    # Platform-specific JVM library paths
    system = platform.system()
    if system == "Windows":
        # Windows: bin/server/jvm.dll
        jvm_lib_path = jre_dir / "bin" / "server" / "jvm.dll"
    elif system == "Darwin":
        # macOS: lib/server/libjvm.dylib
        jvm_lib_path = jre_dir / "lib" / "server" / "libjvm.dylib"
    else:
        # Linux: lib/server/libjvm.so
        jvm_lib_path = jre_dir / "lib" / "server" / "libjvm.so"

    if not jvm_lib_path.exists():
        raise ArcadeDBError(
            f"JVM library not found at {jvm_lib_path}. "
            "The package may be corrupted or incomplete."
        )

    return str(jvm_lib_path)


def start_jvm():
    """
    Start the JVM with ArcadeDB JARs if not already started.

    JVM Memory Configuration (via environment variables):
    -----------------------------------------------------
    ARCADEDB_JVM_ARGS (optional)
        JVM arguments for memory and advanced configuration (space-separated).
        If not specified, defaults to: "-Xmx4g -Djava.awt.headless=true"

        Common memory-related options:
            -Xmx<size>
                Maximum heap memory (e.g., "-Xmx8g")
            -Xms<size>
                Initial heap size (recommended: same as -Xmx)
            -XX:MaxDirectMemorySize=<size>
                Limit off-heap direct buffer memory
            -Darcadedb.vectorIndex.locationCacheSize=<count>
                Max vector locations to cache (controls LSM vector memory)
            -Darcadedb.vectorIndex.graphBuildCacheSize=<count>
                Max vectors cached during HNSW graph build
            -Darcadedb.vectorIndex.mutationsBeforeRebuild=<count>
                Mutations threshold before rebuilding HNSW graph

        Examples:
            # Production with 8GB heap and bounded vector caches
            export ARCADEDB_JVM_ARGS="-Xmx8g -Xms8g -XX:MaxDirectMemorySize=8g \
              -Darcadedb.vectorIndex.locationCacheSize=100000 \
              -Darcadedb.vectorIndex.graphBuildCacheSize=3000 \
              -Darcadedb.vectorIndex.mutationsBeforeRebuild=200"

            # Development/testing (smaller memory)
            export ARCADEDB_JVM_ARGS="-Xmx2g -Xms2g"

    ARCADEDB_JVM_ERROR_FILE (optional)
        Path for JVM crash logs (default: ./log/hs_err_pid%p.log)

    Note: Environment variables must be set BEFORE importing arcadedb_embedded,
          as the JVM can only be configured once per Python process.
    """
    if jpype.isJVMStarted():
        return

    jar_path = get_jar_path()
    jar_files = glob.glob(os.path.join(jar_path, "*.jar"))

    if not jar_files:
        raise ArcadeDBError(
            f"No JAR files found in {jar_path}. "
            "The package may be corrupted or incomplete."
        )

    classpath = os.pathsep.join(jar_files)

    # Get bundled JRE's JVM library path
    jvm_path = get_bundled_jre_lib_path()

    jvm_args = _build_jvm_args()

    try:
        # Always use bundled JRE
        jpype.startJVM(jvm_path, *jvm_args, classpath=classpath)
    except Exception as e:
        raise ArcadeDBError(f"Failed to start JVM: {e}") from e


def _build_jvm_args() -> list[str]:
    """Helper to construct JVM arguments from env vars and defaults."""
    # JVM arguments: use env or defaults
    jvm_args_str = os.environ.get("ARCADEDB_JVM_ARGS")
    if jvm_args_str:
        jvm_args = jvm_args_str.split()

        # Merge mandatory defaults if missing from user arguments

        # 1. Enable vector module if not present (Critical for performance)
        # Check for --add-modules flag containing jdk.incubator.vector
        has_vector_module = any(
            arg.startswith("--add-modules") and "jdk.incubator.vector" in arg
            for arg in jvm_args
        )
        if not has_vector_module:
            jvm_args.append("--add-modules=jdk.incubator.vector")

        # 2. Headless mode if not set (Critical for server environments)
        if not any(arg.startswith("-Djava.awt.headless=") for arg in jvm_args):
            jvm_args.append("-Djava.awt.headless=true")
    else:
        # Default: 4GB heap, headless mode, SIMD vector support
        jvm_args = [
            "-Xmx4g",
            "-Djava.awt.headless=true",
            "--add-modules=jdk.incubator.vector",
        ]

    # Configure JVM crash log location (hs_err_pid*.log files)
    error_file = os.environ.get("ARCADEDB_JVM_ERROR_FILE")
    if error_file:
        jvm_args.append(f"-XX:ErrorFile={error_file}")
    else:
        jvm_args.append("-XX:ErrorFile=./log/hs_err_pid%p.log")

    return jvm_args


def shutdown_jvm():
    """Shutdown JVM if it was started by this module."""
    if jpype.isJVMStarted():
        try:
            jpype.shutdownJVM()
        except Exception:
            pass  # Ignore errors during shutdown
