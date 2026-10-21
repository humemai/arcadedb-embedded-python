/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Which route the three distance kernels take. Initialized at build time (pom --initialize-at-build-time), so the value is the
 * builder's -J-Dfastops.mode and the branch in FastOps folds away. 0 = C function pointers (phase 4, the default),
 * 1 = FFM downcall through an UNBOUND handle built at build time (symbol address passed as the first argument),
 * 2 = FFM downcall through a handle bound to the symbol at run time (what jextract generates; the control).
 */
package io.github.jbellis.jvector.vector.cnative;

final class FastMode {
  static final int MODE = Integer.getInteger("fastops.mode", 0);

  private FastMode() {
  }
}
