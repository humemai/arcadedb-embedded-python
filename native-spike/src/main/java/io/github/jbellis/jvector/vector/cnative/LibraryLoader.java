/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Image-side shadow of jvector 4.0.2's cnative.LibraryLoader (it precedes jvector on the image class path, as the wildfly
 * Substitutions shadow does). The original extracts libjvector-<arch>.so from the jar into java.io.tmpdir through a class path
 * resource; in a native image that resource is not in the image. This version looks for the library where the Python backend
 * ships it, next to libarcadedb.so (directory in the environment variable ARCADEDB_NATIVE_LIBDIR, or java.library.path), and
 * then falls back to a resource copy of the library. Same contract: true when the library is loaded, false when it is unavailable.
 */
package io.github.jbellis.jvector.vector.cnative;

import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;

public class LibraryLoader {
  private LibraryLoader() {
  }

  static String resourceNameForArch() {
    final String arch = System.getProperty("os.arch", "");
    if (arch.equals("aarch64") || arch.equals("arm64"))
      return "/libjvector-aarch64.so";
    if (arch.equals("amd64") || arch.equals("x86_64"))
      return "/libjvector-x86_64.so";
    return null;
  }

  public static boolean loadJvector() {
    try {
      System.loadLibrary("jvector");
      return true;
    } catch (final UnsatisfiedLinkError e) {
      // not on java.library.path
    } catch (final IllegalCallerException | SecurityException e) {
      return false;
    }
    final String resource = resourceNameForArch();
    if (resource == null)
      return false;
    final String file = resource.substring(1);
    final String dir = System.getenv("ARCADEDB_NATIVE_LIBDIR");
    if (dir != null && !dir.isEmpty()) {
      final File f = new File(dir, file);
      if (f.isFile()) {
        try {
          System.load(f.getAbsolutePath());
          return true;
        } catch (final UnsatisfiedLinkError | RuntimeException e) {
          System.err.println("jvector: loading " + f + " failed: " + e);
        }
      }
    }
    for (final String name : new String[] { resource, "/META-INF/versions/22" + resource }) {
      try (InputStream in = LibraryLoader.class.getResourceAsStream(name)) {
        if (in == null)
          continue;
        final File tmp = File.createTempFile(file.substring(0, file.lastIndexOf('.')), file.substring(file.lastIndexOf('.')));
        try {
          Files.copy(in, tmp.toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
          System.load(tmp.getAbsolutePath());
          return true;
        } finally {
          Files.deleteIfExists(tmp.toPath());
        }
      } catch (final Exception | UnsatisfiedLinkError e) {
        System.err.println("jvector: loading the bundled " + name + " failed: " + e);
      }
    }
    return false;
  }
}
