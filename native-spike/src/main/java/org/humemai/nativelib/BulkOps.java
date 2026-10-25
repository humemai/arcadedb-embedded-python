/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 7: columnar bulk insert through one crossing. The documents are built here from whole columns that Python lays out
 * in native-endian buffers (int64, float64, bool bytes, int32, float32, float32 vector matrix, UTF-8 strings as Arrow offsets plus
 * bytes, optional Arrow null bitmaps), as DocumentBatcher.insertColumns does on the JPype path from long[], double[], boolean[] and
 * Object[] columns. Values are read straight from the caller's buffers; no JSON text, no parser, no intermediate arrays.
 */
package org.humemai.nativelib;

import com.arcadedb.database.Database;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.schema.VertexType;

import org.graalvm.nativeimage.c.type.CTypeConversion;
import org.graalvm.word.Pointer;
import org.graalvm.word.WordFactory;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

final class BulkOps {
  private BulkOps() {
  }

  /** Slots per column in the address table: data (address, bytes), aux (address, bytes), nulls (address, bytes). */
  static final int SLOTS = 6;

  /**
   * The original single-buffer form (arcadedb_n_insert_cols): the columns of kind q, d, b or f lie back to back in one buffer, in
   * header order. The address table of the pointer form is derived from the layout, so one loop builds the documents for both.
   */
  @SuppressWarnings("unchecked")
  static long insertColumns(final Database db, final String type, final String header, final Pointer buf, final long bufBytes) {
    final Map<String, Object> h = (Map<String, Object>) Json.parse(header);
    final long n = ((Number) h.get("n")).longValue();
    final List<Object> cols = (List<Object>) h.get("cols");
    final long[] spec = new long[SLOTS * cols.size()];
    long pos = 0;
    for (int c = 0; c < cols.size(); c++) {
      final List<Object> col = (List<Object>) cols.get(c);
      final char kind = ((String) col.get(1)).charAt(0);
      final long dim = ((Number) col.get(2)).longValue();
      final long bytes = switch (kind) {
        case 'q', 'd' -> 8 * n;
        case 'b' -> n;
        case 'f' -> 4 * n * dim;
        default -> throw new IllegalArgumentException("unknown column kind " + kind);
      };
      if (pos + bytes > bufBytes)
        throw new IllegalArgumentException("column '" + col.get(0) + "' ends at byte " + (pos + bytes) + ", the buffer has " + bufBytes);
      spec[SLOTS * c] = buf.rawValue() + pos;
      spec[SLOTS * c + 1] = bytes;
      pos += bytes;
    }
    return insertColumns(db, type, h, spec);
  }

  /** The pointer form (arcadedb_n_insert_colp): the table holds SLOTS longs per column, see {@link #insertColumns(Database, String, Map, long[])}. */
  @SuppressWarnings("unchecked")
  static long insertColumns(final Database db, final String type, final String header, final long[] spec) {
    return insertColumns(db, type, (Map<String, Object>) Json.parse(header), spec);
  }

  /**
   * header: {"n":rows,"commit":every,"cols":[[name,kind,dim],..]}. Kinds: q (int64), d (float64), b (bool byte), i (int32), e (float32),
   * f (float32 matrix, dim floats per row), s (UTF-8 string: int32 offsets[n+1] in the data slot, the bytes they index in the aux slot, as
   * an Arrow string array; offsets[0] need not be 0). spec: per column six longs, [data address, data bytes, aux address, aux bytes, null
   * bitmap address, null bitmap bytes]; the bitmap is Arrow's (bit i of byte i/8, least significant first; 1 = present), an address of 0
   * means no nulls. The memory belongs to the caller for the duration of the call; nothing is kept. Every length is checked here before
   * the first document is built, so a wrong table is an exception and nothing is written. Same transaction contract as
   * DocumentBatcher.insertColumns: batch commits and the rollback on failure apply only to a transaction opened here.
   */
  @SuppressWarnings("unchecked")
  private static long insertColumns(final Database db, final String type, final Map<String, Object> h, final long[] spec) {
    final long nRows = ((Number) h.get("n")).longValue();
    if (nRows < 0 || nRows > Integer.MAX_VALUE)
      throw new IllegalArgumentException("row count out of range: " + nRows);
    final int n = (int) nRows;
    final int commitEvery = ((Number) h.get("commit")).intValue();
    final List<Object> cols = (List<Object>) h.get("cols");
    final int k = cols.size();
    if (spec.length != SLOTS * k)
      throw new IllegalArgumentException("address table has " + spec.length + " entries for " + k + " columns, expected " + SLOTS * k);
    final String[] names = new String[k];
    final char[] kinds = new char[k];
    final int[] dims = new int[k];
    final long[] data = new long[k]; // addresses: a Word value cannot live in an array or be compared with null
    final long[] nulls = new long[k]; // 0 = no nulls
    final ByteBuffer[] blobs = new ByteBuffer[k];
    int longest = 0;
    for (int c = 0; c < k; c++) {
      final List<Object> col = (List<Object>) cols.get(c);
      names[c] = (String) col.get(0);
      kinds[c] = ((String) col.get(1)).charAt(0);
      dims[c] = ((Number) col.get(2)).intValue();
      final long dataAddr = spec[SLOTS * c], dataBytes = spec[SLOTS * c + 1];
      final long auxAddr = spec[SLOTS * c + 2], auxBytes = spec[SLOTS * c + 3];
      final long nullAddr = spec[SLOTS * c + 4], nullBytes = spec[SLOTS * c + 5];
      final long need = switch (kinds[c]) {
        case 'q', 'd' -> 8L * n;
        case 'b' -> n;
        case 'i', 'e' -> 4L * n;
        case 'f' -> {
          if (dims[c] <= 0)
            throw new IllegalArgumentException("column '" + names[c] + "': a vector column needs a dimension above 0");
          yield 4L * n * dims[c];
        }
        case 's' -> 4L * (n + 1L);
        default -> throw new IllegalArgumentException("unknown column kind " + kinds[c]);
      };
      if (dataBytes < need || (need > 0 && dataAddr == 0))
        throw new IllegalArgumentException("column '" + names[c] + "' has " + dataBytes + " bytes, " + need + " needed");
      data[c] = dataAddr;
      if (nullAddr != 0) {
        if (nullBytes < (n + 7L) / 8)
          throw new IllegalArgumentException("column '" + names[c] + "' has a null bitmap of " + nullBytes + " bytes, " + (n + 7L) / 8 + " needed");
        nulls[c] = nullAddr;
      }
      if (kinds[c] == 's') {
        if (auxBytes < 0 || auxBytes > Integer.MAX_VALUE || (auxBytes > 0 && auxAddr == 0))
          throw new IllegalArgumentException("column '" + names[c] + "': the string bytes are missing or beyond 2 GiB");
        blobs[c] = auxBytes == 0 ? ByteBuffer.allocate(0) : CTypeConversion.asByteBuffer(WordFactory.pointer(auxAddr), (int) auxBytes);
        final Pointer offsets = WordFactory.pointer(data[c]);
        int prev = offsets.readInt(WordFactory.signed(0));
        if (prev < 0)
          throw new IllegalArgumentException("column '" + names[c] + "': negative string offset");
        for (int i = 1; i <= n; i++) {
          final int off = offsets.readInt(WordFactory.signed(4L * i));
          if (off < prev || off > auxBytes)
            throw new IllegalArgumentException("column '" + names[c] + "': string offsets are not increasing within the " + auxBytes + " bytes (row " + (i - 1) + ")");
          longest = Math.max(longest, off - prev);
          prev = off;
        }
      }
    }
    final byte[] scratch = new byte[longest];
    final boolean vertex = db.getSchema().getType(type) instanceof VertexType;
    final boolean wasActive = db.isTransactionActive();
    if (!wasActive)
      db.begin();
    try {
      for (int i = 0; i < n; i++) {
        final MutableDocument doc = vertex ? db.newVertex(type) : db.newDocument(type);
        for (int c = 0; c < k; c++) {
          final Pointer base = WordFactory.pointer(data[c]);
          if (nulls[c] != 0 && ((WordFactory.<Pointer>pointer(nulls[c]).readByte(WordFactory.signed(i >> 3)) >> (i & 7)) & 1) == 0) {
            doc.set(names[c], null);
            continue;
          }
          switch (kinds[c]) {
            case 'q' -> doc.set(names[c], base.readLong(WordFactory.signed(8L * i)));
            case 'd' -> doc.set(names[c], base.readDouble(WordFactory.signed(8L * i)));
            case 'b' -> doc.set(names[c], base.readByte(WordFactory.signed(i)) != 0);
            case 'i' -> doc.set(names[c], base.readInt(WordFactory.signed(4L * i)));
            case 'e' -> doc.set(names[c], base.readFloat(WordFactory.signed(4L * i)));
            case 's' -> {
              final int from = base.readInt(WordFactory.signed(4L * i));
              final int len = base.readInt(WordFactory.signed(4L * (i + 1L))) - from;
              if (len == 0)
                doc.set(names[c], "");
              else {
                blobs[c].get(from, scratch, 0, len);
                doc.set(names[c], new String(scratch, 0, len, StandardCharsets.UTF_8));
              }
            }
            default -> {
              final int dim = dims[c];
              final float[] v = new float[dim];
              final long at = 4L * i * dim;
              for (int j = 0; j < dim; j++)
                v[j] = base.readFloat(WordFactory.signed(at + 4L * j));
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

  /**
   * Documents (or vertices of a vertex type) from rows [{property: value},..] in the UTF-8 JSON text b[0, n): one record per row through
   * newDocument/newVertex, set per property and save, as DocumentBatcher.insertManyJson does on the JPype path; no transaction is opened
   * or closed here. The rows are parsed one at a time into one reused map (the property order of a fresh HashMap), so no tree of the
   * chunk and no String of the whole text is built.
   */
  static int insertRows(final Database db, final String type, final byte[] b, final int n) {
    final boolean vertex = db.getSchema().getType(type) instanceof VertexType;
    final int[] count = new int[1];
    Json.rows(b, n, row -> {
      final MutableDocument doc = vertex ? db.newVertex(type) : db.newDocument(type);
      for (final Map.Entry<String, Object> e : row.entrySet())
        doc.set(e.getKey(), e.getValue());
      doc.save();
      count[0]++;
    });
    return count[0];
  }
}
