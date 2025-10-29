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


def get_bundled_jre_path() -> str | None:
    """
    Get the path to bundled JRE if available.

    Returns:
        Path to bundled JRE's java executable, or None if not bundled.
    """
    package_dir = Path(__file__).parent
    jre_dir = package_dir / "jre"

    # Check if JRE directory exists
    if not jre_dir.exists():
        return None

    # Look for java executable in standard JRE locations
    java_executable = jre_dir / "bin" / "java"

    if java_executable.exists():
        return str(java_executable)

    return None


def start_jvm():
    """Start the JVM with ArcadeDB JARs if not already started."""
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

    # Check for bundled JRE
    bundled_jre = get_bundled_jre_path()
    jvm_path = None

    if bundled_jre:
        # Use bundled JRE - need to find JVM library (platform-specific)
        jre_dir = Path(bundled_jre).parent.parent  # Go from bin/java to jre root

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

        if jvm_lib_path.exists():
            jvm_path = str(jvm_lib_path)

    # Allow customization via environment variables
    max_heap = os.environ.get("ARCADEDB_JVM_MAX_HEAP", "4g")

    # Prepare JVM arguments
    jvm_args = [
        f"-Xmx{max_heap}",  # Max heap (default 4g, override with env var)
        "-Djava.awt.headless=true",  # Headless mode for server use
    ]

    # Configure JVM error log location (hs_err_pid*.log files)
    # Default: ./log/hs_err_pid%p.log (keeps crash logs with application logs)
    error_file = os.environ.get("ARCADEDB_JVM_ERROR_FILE")
    if error_file:
        jvm_args.append(f"-XX:ErrorFile={error_file}")
    else:
        # Set sensible default: put JVM crash logs in ./log/ directory
        jvm_args.append("-XX:ErrorFile=./log/hs_err_pid%p.log")

    # Allow additional custom JVM arguments
    extra_args = os.environ.get("ARCADEDB_JVM_ARGS")
    if extra_args:
        jvm_args.extend(extra_args.split())

    try:
        if jvm_path:
            # Use bundled JRE
            jpype.startJVM(jvm_path, *jvm_args, classpath=classpath)
        else:
            # Use system Java
            jpype.startJVM(*jvm_args, classpath=classpath)
    except Exception as e:
        raise ArcadeDBError(f"Failed to start JVM: {e}") from e


def shutdown_jvm():
    """Shutdown JVM if it was started by this module."""
    if jpype.isJVMStarted():
        try:
            jpype.shutdownJVM()
        except Exception:
            pass  # Ignore errors during shutdown
