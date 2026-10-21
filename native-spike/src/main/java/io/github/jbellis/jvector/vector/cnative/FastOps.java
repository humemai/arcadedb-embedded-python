/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 4: the hot libjvector distance kernels called through GraalVM's C interop (@InvokeCFunctionPointer, no thread-state
 * transition) instead of FFM downcall handles. The function address comes from the symbol lookup of the loaded library, once.
 * Heap segments (float[]-backed vectors) are pinned for the duration of the call.
 */
package io.github.jbellis.jvector.vector.cnative;

import org.graalvm.nativeimage.PinnedObject;
import org.graalvm.nativeimage.c.function.CFunctionPointer;
import org.graalvm.nativeimage.c.function.InvokeCFunctionPointer;
import org.graalvm.nativeimage.c.function.CFunction.Transition;
import org.graalvm.word.Pointer;
import org.graalvm.word.PointerBase;
import org.graalvm.word.WordFactory;

import java.lang.foreign.MemorySegment;

final class FastOps {
  static final int COSINE = 0, DOT = 1, EUCLIDEAN = 2;
  private static final long[] ADDRESS = new long[3];
  // what MemorySegment.address() of a float[]-backed segment starts at: the JDK's array base offset, which the image's own layout does not share
  private static final long FLOAT_BASE = MemorySegment.ofArray(new float[0]).address();

  interface Kernel extends CFunctionPointer {
    @InvokeCFunctionPointer(transition = Transition.NO_TRANSITION)
    float call(PointerBase a, long aoffset, PointerBase b, long boffset, long length);
  }

  private FastOps() {
  }

  static float call(final int which, final MemorySegment symbol, final MemorySegment a, final long aoffset,
      final MemorySegment b, final long boffset, final long length) {
    if (FastMode.MODE != 0)
      return FfmKernels.call(which, symbol, a, aoffset, b, boffset, length);
    long fn = ADDRESS[which];
    if (fn == 0)
      ADDRESS[which] = fn = symbol.address();
    final Object baseA = a.isNative() ? null : a.heapBase().orElse(null);
    final Object baseB = b.isNative() ? null : b.heapBase().orElse(null);
    if (!(baseA == null || baseA instanceof float[]) || !(baseB == null || baseB instanceof float[]))
      throw new UnsupportedOperationException("the image's distance kernels take float[]-backed or native segments");
    final PinnedObject pinA = baseA == null ? null : PinnedObject.create(baseA);
    final PinnedObject pinB = baseB == null ? null : PinnedObject.create(baseB);
    try {
      final Pointer pa = pinA == null ? WordFactory.pointer(a.address()) : ((Pointer) pinA.addressOfArrayElement(0)).add(WordFactory.signed(a.address() - FLOAT_BASE));
      final Pointer pb = pinB == null ? WordFactory.pointer(b.address()) : ((Pointer) pinB.addressOfArrayElement(0)).add(WordFactory.signed(b.address() - FLOAT_BASE));
      return ((Kernel) WordFactory.pointer(fn)).call(pa, aoffset, pb, boffset, length);
    } finally {
      if (pinA != null)
        pinA.close();
      if (pinB != null)
        pinB.close();
    }
  }
}
