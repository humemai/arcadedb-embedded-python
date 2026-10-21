/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 5: the distance kernels through FFM downcalls on GraalVM CE 25.4. Mode 1 uses an unbound handle created once in this
 * class, which is initialized at build time; the address of the libjvector symbol is the first argument of every call (the
 * pattern oracle/graal#12219 reports as fast on 25.1+). Mode 2 binds a handle to the symbol at run time, as jextract does.
 */
package io.github.jbellis.jvector.vector.cnative;

import java.lang.foreign.AddressLayout;
import java.lang.foreign.FunctionDescriptor;
import java.lang.foreign.Linker;
import java.lang.foreign.MemoryLayout;
import java.lang.foreign.MemorySegment;
import java.lang.foreign.ValueLayout;
import java.lang.invoke.MethodHandle;

final class FfmKernels {
  private static final AddressLayout PTR = ValueLayout.ADDRESS
      .withTargetLayout(MemoryLayout.sequenceLayout(Long.MAX_VALUE, ValueLayout.JAVA_BYTE));
  private static final FunctionDescriptor DESC = FunctionDescriptor.of(ValueLayout.JAVA_FLOAT, PTR, ValueLayout.JAVA_LONG, PTR,
      ValueLayout.JAVA_LONG, ValueLayout.JAVA_LONG);

  /** built at build time: no symbol yet, the address is the first call argument */
  static final MethodHandle UNBOUND = FastMode.MODE == 1 ? Linker.nativeLinker().downcallHandle(DESC, Linker.Option.critical(true)) : null;

  private static final MethodHandle[] BOUND = new MethodHandle[3];

  private FfmKernels() {
  }

  static float call(final int which, final MemorySegment symbol, final MemorySegment a, final long aoffset,
      final MemorySegment b, final long boffset, final long length) {
    try {
      if (FastMode.MODE == 1)
        return (float) UNBOUND.invokeExact(symbol, a, aoffset, b, boffset, length);
      MethodHandle h = BOUND[which];
      if (h == null)
        BOUND[which] = h = Linker.nativeLinker().downcallHandle(symbol, DESC, Linker.Option.critical(true));
      return (float) h.invokeExact(a, aoffset, b, boffset, length);
    } catch (final Throwable t) {
      throw new AssertionError("should not reach here", t);
    }
  }
}
