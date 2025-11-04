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
    ARCADEDB_JVM_MAX_HEAP (default: "4g")
        Maximum heap memory the JVM can use (e.g., "8g", "16g").
        This is the main memory control - increase for large datasets.
        Examples:
            export ARCADEDB_JVM_MAX_HEAP="8g"    # 8 gigabytes
            export ARCADEDB_JVM_MAX_HEAP="512m"  # 512 megabytes

    ARCADEDB_JVM_ARGS (optional)
        Additional JVM arguments for advanced configuration.
        Common memory-related options:
            -Xms<size>
                Set initial heap size (recommended: same as -Xmx)
            -XX:MaxDirectMemorySize=<size>
                Limit off-heap direct buffer memory
            -XX:MaxMetaspaceSize=<size>
                Limit metadata (class definitions) memory

        Examples:
            # Set initial heap = max heap (eliminates resizing overhead)
            export ARCADEDB_JVM_ARGS="-Xms8g"

            # Multiple options (space-separated)
            export ARCADEDB_JVM_ARGS="-Xms8g -XX:MaxDirectMemorySize=2g"

    ARCADEDB_JVM_ERROR_FILE (optional)
        Path for JVM crash logs (default: ./log/hs_err_pid%p.log)

    Performance Tips:
    -----------------
    For production or large datasets:
        export ARCADEDB_JVM_MAX_HEAP="8g"
        export ARCADEDB_JVM_ARGS="-Xms8g"  # Initial = Max (best practice)

    For development/testing (smaller memory):
        export ARCADEDB_JVM_MAX_HEAP="2g"

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

    # JVM Memory Configuration
    # Maximum heap memory (most important setting for large datasets)
    max_heap = os.environ.get("ARCADEDB_JVM_MAX_HEAP", "4g")

    # Prepare JVM arguments
    jvm_args = [
        f"-Xmx{max_heap}",  # Max heap size
        "-Djava.awt.headless=true",  # Headless mode for server use
    ]

    # Configure JVM crash log location (hs_err_pid*.log files)
    # Default: ./log/hs_err_pid%p.log (keeps crash logs with application logs)
    error_file = os.environ.get("ARCADEDB_JVM_ERROR_FILE")
    if error_file:
        jvm_args.append(f"-XX:ErrorFile={error_file}")
    else:
        jvm_args.append("-XX:ErrorFile=./log/hs_err_pid%p.log")

    # Additional custom JVM arguments (for power users)
    # Example: export ARCADEDB_JVM_ARGS="-Xms8g -XX:MaxDirectMemorySize=2g"
    extra_args = os.environ.get("ARCADEDB_JVM_ARGS")
    if extra_args:
        jvm_args.extend(extra_args.split())

    try:
        # Always use bundled JRE
        jpype.startJVM(jvm_path, *jvm_args, classpath=classpath)
    except Exception as e:
        raise ArcadeDBError(f"Failed to start JVM: {e}") from e


def shutdown_jvm():
    """Shutdown JVM if it was started by this module."""
    if jpype.isJVMStarted():
        try:
            jpype.shutdownJVM()
        except Exception:
            pass  # Ignore errors during shutdown
