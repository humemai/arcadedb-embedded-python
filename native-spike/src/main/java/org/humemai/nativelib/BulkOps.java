/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 7: columnar bulk insert through one crossing. The documents are built here from whole columns that Python lays out
 * in one native-endian buffer (int64, float64, bool bytes, float32 vector matrix), as DocumentBatcher.insertColumns does on
 * the JPype path from long[], double[], boolean[] and Object[] columns.
 */
package org.humemai.nativelib;

import com.arcadedb.database.Database;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.schema.VertexType;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.List;
import java.util.Map;

final class BulkOps {
  private BulkOps() {
  }

  /**
   * header: {"n":rows,"commit":every,"cols":[[name,kind,dim],..]} with kind q (int64), d (float64), b (bool byte) or f
   * (float32 matrix, dim floats per row); the buffer holds the columns in that order. Same transaction contract as
   * DocumentBatcher.insertColumns: batch commits and the rollback on failure apply only to a transaction opened here.
   */
  @SuppressWarnings("unchecked")
  static long insertColumns(final Database db, final String type, final String header, final ByteBuffer raw) {
    final Map<String, Object> h = (Map<String, Object>) Json.parse(header);
    final int n = ((Number) h.get("n")).intValue();
    final int commitEvery = ((Number) h.get("commit")).intValue();
    final List<Object> cols = (List<Object>) h.get("cols");
    final int k = cols.size();
    final String[] names = new String[k];
    final char[] kinds = new char[k];
    final Object[] data = new Object[k];
    final int[] dims = new int[k];
    raw.order(ByteOrder.nativeOrder());
    int pos = 0;
    for (int c = 0; c < k; c++) {
      final List<Object> col = (List<Object>) cols.get(c);
      names[c] = (String) col.get(0);
      kinds[c] = ((String) col.get(1)).charAt(0);
      dims[c] = ((Number) col.get(2)).intValue();
      final int bytes = switch (kinds[c]) {
        case 'q', 'd' -> 8 * n;
        case 'b' -> n;
        case 'f' -> 4 * n * dims[c];
        default -> throw new IllegalArgumentException("unknown column kind " + kinds[c]);
      };
      final ByteBuffer part = raw.slice(pos, bytes).order(ByteOrder.nativeOrder());
      pos += bytes;
      switch (kinds[c]) {
        case 'q' -> {
          final long[] a = new long[n];
          part.asLongBuffer().get(a);
          data[c] = a;
        }
        case 'd' -> {
          final double[] a = new double[n];
          part.asDoubleBuffer().get(a);
          data[c] = a;
        }
        case 'b' -> {
          final boolean[] a = new boolean[n];
          for (int i = 0; i < n; i++)
            a[i] = part.get(i) != 0;
          data[c] = a;
        }
        default -> data[c] = part.asFloatBuffer();
      }
    }
    final boolean vertex = db.getSchema().getType(type) instanceof VertexType;
    final boolean wasActive = db.isTransactionActive();
    if (!wasActive)
      db.begin();
    try {
      for (int i = 0; i < n; i++) {
        final MutableDocument doc = vertex ? db.newVertex(type) : db.newDocument(type);
        for (int c = 0; c < k; c++) {
          switch (kinds[c]) {
            case 'q' -> doc.set(names[c], ((long[]) data[c])[i]);
            case 'd' -> doc.set(names[c], ((double[]) data[c])[i]);
            case 'b' -> doc.set(names[c], ((boolean[]) data[c])[i]);
            default -> {
              final float[] v = new float[dims[c]];
              ((java.nio.FloatBuffer) data[c]).get(i * dims[c], v);
              doc.set(names[c], v);
            }
          }
        }
        doc.save();
        if (!wasActive && commitEvery > 0 && (i + 1) % commitEvery == 0) {
          db.commit();
          db.begin();
        }
      }
      if (!wasActive)
        db.commit();
    } catch (final Throwable e) {
      if (!wasActive && db.isTransactionActive()) {
        try {
          db.rollback();
        } catch (final Throwable rollbackError) {
          e.addSuppressed(rollbackError);
        }
      }
      throw e;
    }
    return n;
  }
}
