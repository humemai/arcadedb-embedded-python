/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 9 (N-R2): query results as columns. The read-side counterpart of the columnar insert (BulkOps): a batch of rows is laid out as
 * one frame, a fixed header, a small JSON header with the column names and kinds, then one buffer per column in the layout BulkOps reads
 * (native-endian int64 / float64 / bool bytes, UTF-8 strings as Arrow int32 offsets plus a byte blob, float32 vector matrix, bitmaps with
 * bit i of byte i/8, least significant first). Python restores the rows from the buffers (_native/colres.py) without parsing text.
 *
 * Frame (all numbers native-endian, every buffer starts on an 8-byte boundary):
 *   0  u32 magic "ACR1"      4  u32 length of the JSON header (padded with spaces to a multiple of 8)    8  u64 frame bytes
 *   16 i64 cursor id (0 = drained)    24 u32 rows    28 u32 flags (bit 0: drained)    32 JSON header    then the buffers
 * JSON header: {"c":[[name,kind,dim,data,aux,valid,present],..],"m":0|[kind,rid,ridAux,type,typeAux][,"o":[[row,[column,..]],..]][,"rerr":{..}]}. Offsets are relative to
 * the first byte after the header and 0 means "none" (the buffers start at 8). Kinds: q int64, d float64, b bool, D days (int64), T and Z
 * microseconds since the epoch (int64; T a wall clock, Z UTC), s string, R record id as text, v float[] with int32 offsets, f float[] of
 * one length (dim floats per row), n only nulls. valid: bit set = the row has a value; present: bit set = the property exists in the row
 * (valid without present = null, neither = the row has no such property); no bitmap = all rows. m: the record rows' meta, kind = one byte per
 * row (0 none, v, e, d), rid and type as string columns. o: rows whose properties come in another order than the columns (the engine does not
 * order the properties of schemaless records alike), as the column indexes in the row's order; a batch with more of them than half its rows goes as JSON.
 *
 * A batch that cannot be carried (a nested map, list or record, a value type the buffers do not have, a column that mixes kinds, property
 * order that differs between rows, more than MAX_COLS columns, a mostly empty table, an unpaired surrogate) is answered as the JSON text of
 * arcadedb_n_next_bin, so every result still comes back. So is a batch of fewer than minRows rows: a point lookup gains nothing from columns.
 */
package org.humemai.nativelib;

import com.arcadedb.database.Document;
import com.arcadedb.database.Identifiable;
import com.arcadedb.graph.Edge;
import com.arcadedb.graph.Vertex;
import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Calendar;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

final class ColResult {
  static final int MAGIC = 0x31524341; // 'A' 'C' 'R' '1' as a little-endian int
  static final int HEADER = 32;
  static final int MAX_COLS = 256;
  static final long MAX_BYTES = 4L << 20; // column bytes per batch, as NativeCodec.MAX_BATCH_CHARS for the text
  private static final byte[] ZEROS = new byte[8];
  /** Why the last batch of this process went as JSON (tests and the JVM gate read it; racy by design). */
  static String lastFallback;

  private ColResult() {
  }

  /** The batch cannot be carried as columns; the rows go as JSON. */
  private static final class Unsupported extends RuntimeException {
    Unsupported(final String why) {
      super(why, null, false, false);
    }
  }

  /** One reply: a JSON batch (bytes) or a columnar frame (the builder). */
  static final class Reply {
    boolean drained;
    int rows;
    byte[] json; // text, or text + NUL + padding + float32 tail, without the terminating zero
    Frame frame;

    int size() {
      return json != null ? json.length + 1 : frame.total;
    }

    void writeTo(final ByteBuffer bb) {
      if (json != null) {
        bb.put(0, json, 0, json.length);
        bb.put(json.length, (byte) 0);
      } else
        frame.write(bb);
    }
  }

  /**
   * Reads up to max rows of rs and answers them: a columnar frame when the rows are carried and there are at least minRows of them, else the
   * JSON batch (with the float32 tail when tail is set). id is the cursor id shown to the caller (0 once drained).
   */
  static Reply read(final long id, final ResultSet rs, final int max, final int minRows, final boolean tail) {
    final NativeCodec.FloatSink sink = tail ? new NativeCodec.FloatSink() : null;
    if (sink != null)
      NativeCodec.SINK.set(sink);
    try {
      final List<Result> rows = new ArrayList<>();
      Builder cb = null;
      boolean colOk = minRows >= 0;
      final int start = Math.min(Math.max(1, minRows), Math.max(1, max)); // rows in hand before the columns are started
      StringBuilder sb = null, meta = null; // JSON mode, once the columns are given up
      int encoded = 0;
      boolean drained = false;
      String readError = null;
      try {
        while (rows.size() < max) {
          if (!rs.hasNext()) {
            drained = true;
            break;
          }
          final Result row = rs.next();
          rows.add(row);
          if (colOk && rows.size() >= start) {
            try {
              if (cb == null) {
                cb = new Builder();
                for (final Result r : rows)
                  cb.add(r);
              } else
                cb.add(row);
            } catch (final Throwable t) { // Unsupported, or a value the engine would not give up: the JSON path meets it again and reports it
              lastFallback = t.toString();
              colOk = false;
              cb = null;
            }
          }
          if (cb != null && cb.bytes >= MAX_BYTES)
            break;
          if (!colOk) {
            if (sb == null) {
              sb = new StringBuilder();
              meta = new StringBuilder();
            }
            // JSON mode: encode what has not been encoded yet (all rows so far on the first turn), then keep the 4M-char cap of the text path
            while (encoded < rows.size()) {
              final int rowStart = sb.length(), metaStart = meta.length();
              try {
                if (encoded > 0) {
                  sb.append(',');
                  meta.append(',');
                }
                NativeCodec.appendRow(sb, meta, rows.get(encoded));
              } catch (final Throwable t) {
                sb.setLength(rowStart);
                meta.setLength(metaStart);
                throw t;
              }
              encoded++;
            }
            if (sb.length() >= NativeCodec.MAX_BATCH_CHARS)
              break;
          }
        }
      } catch (final Throwable t) {
        readError = ArcadeNative.errorJson(t);
        drained = true;
      }
      final Reply reply = new Reply();
      reply.drained = drained;
      reply.rows = rows.size();
      final long shown = drained ? 0 : id;
      if (cb != null && colOk && !cb.sparse()) { // a builder that is alive holds every pulled row
        reply.rows = cb.n;
        reply.frame = cb.finish(shown, drained, readError);
        return reply;
      }
      if (sb == null || encoded < rows.size()) {
        // never in JSON mode (fewer than minRows rows, or the columns were dropped late): encode every pulled row now
        sb = new StringBuilder();
        meta = new StringBuilder();
        encoded = 0;
        for (final Result r : rows) {
          final int rowStart = sb.length(), metaStart = meta.length();
          try {
            if (encoded > 0) {
              sb.append(',');
              meta.append(',');
            }
            NativeCodec.appendRow(sb, meta, r);
          } catch (final Throwable t) {
            sb.setLength(rowStart);
            meta.setLength(metaStart);
            readError = ArcadeNative.errorJson(t);
            drained = true;
            break;
          }
          encoded++;
        }
        reply.drained = drained;
      }
      final long shownJson = reply.drained ? 0 : id;
      final StringBuilder out = new StringBuilder("{\"ok\":true,\"rs\":").append(shownJson).append(",\"rows\":[").append(sb)
          .append("],\"meta\":[").append(meta).append("],\"drained\":").append(reply.drained);
      if (readError != null)
        out.append(",\"rerr\":").append(readError);
      out.append('}');
      reply.rows = encoded;
      reply.json = jsonBytes(out.toString(), sink);
      return reply;
    } finally {
      if (sink != null)
        NativeCodec.SINK.remove();
    }
  }

  /** The reply text as bytes; with a float32 tail: the text ending ,"bin":N}, a NUL, padding to 4 bytes and the floats (see ArcadeNative.withFloatTail). */
  static byte[] jsonBytes(final String text, final NativeCodec.FloatSink sink) {
    if (sink == null || sink.n == 0)
      return text.getBytes(StandardCharsets.UTF_8);
    final byte[] b = (text.substring(0, text.length() - 1) + ",\"bin\":" + sink.n + "}").getBytes(StandardCharsets.UTF_8);
    final int off = (b.length + 1 + 3) & ~3;
    final ByteBuffer bb = ByteBuffer.allocate(off + 4 * sink.n);
    bb.put(b);
    bb.order(ByteOrder.nativeOrder()).position(off).asFloatBuffer().put(sink.a, 0, sink.n);
    return bb.array();
  }

  // ---- the columns

  private static int align8(final long n) {
    return (int) ((n + 7) & ~7L);
  }

  private static boolean yearFits(final int year) {
    return year >= 1 && year <= 9999;
  }

  private static long micros(final LocalDateTime dt) {
    if (!yearFits(dt.getYear()))
      throw new Unsupported("year");
    return dt.toEpochSecond(ZoneOffset.UTC) * 1_000_000L + dt.getNano() / 1000;
  }

  private static long millisToMicros(final long millis) {
    return micros(LocalDateTime.ofEpochSecond(Math.floorDiv(millis, 1000L), Math.floorMod(millis, 1000) * 1_000_000, ZoneOffset.UTC));
  }

  private static long instantMicros(final Instant i) {
    return micros(LocalDateTime.ofEpochSecond(i.getEpochSecond(), i.getNano(), ZoneOffset.UTC));
  }

  private static char kindOf(final Object v) {
    if (v instanceof String || v instanceof Character)
      return 's';
    if (v instanceof Integer || v instanceof Long || v instanceof Short || v instanceof Byte)
      return 'q';
    if (v instanceof Double || v instanceof Float)
      return 'd';
    if (v instanceof Boolean)
      return 'b';
    if (v instanceof float[])
      return 'v';
    if (v instanceof LocalDate)
      return 'D';
    if (v instanceof LocalDateTime || v instanceof Date || v instanceof Calendar)
      return 'T';
    if (v instanceof Instant || v instanceof ZonedDateTime || v instanceof OffsetDateTime)
      return 'Z';
    if (v instanceof Identifiable && !(v instanceof Document))
      return 'R';
    throw new Unsupported(v.getClass().getName());
  }

  /** One column under construction. Cell arrays are zero-filled, so a row without a value costs nothing but its bit and, for strings and vectors, its offset. */
  static final class Col {
    final String name;
    int idx;
    char kind; // 0 until the first value
    int rows; // cells so far
    long[] l;
    double[] d;
    byte[] b;
    byte[] blob;
    int blobLen;
    int[] off;
    float[] fl;
    int flLen;
    int dim = -1;
    boolean sameDim = true;
    byte[] pres = new byte[8], val = new byte[8];
    int nPres, nVal;
    // layout, set by Frame
    int dataOff, auxOff, valOff, presOff;
    char wireKind;
    boolean hasVal, hasPres;

    Col(final String name, final int rowsBefore) {
      this.name = name;
      this.rows = rowsBefore;
    }

    private void room() {
      final int need = rows + 1;
      if ((pres.length << 3) < need) {
        final int bytes = Math.max(pres.length * 2, (need + 7) >> 3);
        pres = Arrays.copyOf(pres, bytes);
        val = Arrays.copyOf(val, bytes);
      }
      switch (kind) {
        case 'q', 'D', 'T', 'Z' -> {
          if (l.length < need)
            l = Arrays.copyOf(l, Math.max(need, l.length * 2));
        }
        case 'd' -> {
          if (d.length < need)
            d = Arrays.copyOf(d, Math.max(need, d.length * 2));
        }
        case 'b' -> {
          if (b.length < need)
            b = Arrays.copyOf(b, Math.max(need, b.length * 2));
        }
        case 's', 'R', 'v' -> {
          if (off.length < need + 1)
            off = Arrays.copyOf(off, Math.max(need + 1, off.length * 2));
        }
        default -> {
        }
      }
    }

    private void init(final char k) {
      kind = k;
      final int cap = Math.max(16, rows + 16);
      switch (k) {
        case 'q', 'D', 'T', 'Z' -> l = new long[cap];
        case 'd' -> d = new double[cap];
        case 'b' -> b = new byte[cap];
        case 's', 'R' -> {
          off = new int[cap + 1];
          blob = new byte[Math.max(64, cap * 8)];
        }
        default -> { // v
          off = new int[cap + 1];
          fl = new float[Math.max(64, cap * 8)];
        }
      }
    }

    /** Adds the cell of row r (== rows) and returns the bytes it brings. */
    long put(final Object v, final int r) {
      room();
      pres[r >> 3] |= (byte) (1 << (r & 7));
      nPres++;
      if (v == null) {
        gap();
        return 0;
      }
      final char k = kindOf(v);
      if (kind == 0)
        init(k);
      else if (kind != k)
        throw new Unsupported("column " + name + " mixes kinds " + kind + " and " + k);
      room();
      val[r >> 3] |= (byte) (1 << (r & 7));
      nVal++;
      long added = 8;
      switch (k) {
        case 'q' -> l[rows] = ((Number) v).longValue();
        case 'd' -> d[rows] = ((Number) v).doubleValue();
        case 'b' -> {
          b[rows] = (byte) (((Boolean) v) ? 1 : 0);
          added = 1;
        }
        case 'D' -> {
          final LocalDate date = (LocalDate) v;
          if (!yearFits(date.getYear()))
            throw new Unsupported("year");
          l[rows] = date.toEpochDay();
        }
        case 'T' -> l[rows] = v instanceof LocalDateTime dt ? micros(dt) : v instanceof Date date ? millisToMicros(date.getTime())
            : millisToMicros(((Calendar) v).getTimeInMillis());
        case 'Z' -> l[rows] = v instanceof Instant i ? instantMicros(i) : v instanceof ZonedDateTime z ? instantMicros(z.toInstant())
            : instantMicros(((OffsetDateTime) v).toInstant());
        case 's', 'R' -> added = 4 + putString(k == 'R' ? ((Identifiable) v).getIdentity().toString() : String.valueOf(v));
        default -> {
          final float[] a = (float[]) v;
          if (dim < 0)
            dim = a.length;
          else if (dim != a.length)
            sameDim = false;
          if (flLen + a.length > fl.length)
            fl = Arrays.copyOf(fl, Math.max(fl.length * 2, flLen + a.length));
          System.arraycopy(a, 0, fl, flLen, a.length);
          flLen += a.length;
          off[rows + 1] = flLen;
          added = 4 + 4L * a.length;
        }
      }
      rows++;
      return added;
    }

    /** A string cell of a column without kind logic or bitmaps (the record meta). */
    int putPlain(final String s) {
      if (off.length < rows + 2)
        off = Arrays.copyOf(off, Math.max(rows + 2, off.length * 2));
      final int added = putString(s);
      rows++;
      return added + 4;
    }

    /** A row with the property null or absent: a zero cell. */
    void gap() {
      if (kind == 's' || kind == 'R' || kind == 'v')
        off[rows + 1] = kind == 'v' ? flLen : blobLen;
      rows++;
    }

    void absent() {
      room();
      gap();
    }

    private int putString(final String s) {
      final int len = s.length();
      if (blobLen + 3L * len > blob.length)
        blob = Arrays.copyOf(blob, (int) Math.min(Integer.MAX_VALUE - 8L, Math.max(blob.length * 2L, blobLen + 3L * len)));
      int p = blobLen;
      final byte[] o = blob;
      for (int i = 0; i < len; i++) {
        final char c = s.charAt(i);
        if (c < 0x80)
          o[p++] = (byte) c;
        else if (c < 0x800) {
          o[p++] = (byte) (0xC0 | (c >> 6));
          o[p++] = (byte) (0x80 | (c & 0x3F));
        } else if (c >= 0xD800 && c <= 0xDFFF) {
          if (c <= 0xDBFF && i + 1 < len && Character.isLowSurrogate(s.charAt(i + 1))) {
            final int cp = Character.toCodePoint(c, s.charAt(++i));
            o[p++] = (byte) (0xF0 | (cp >> 18));
            o[p++] = (byte) (0x80 | ((cp >> 12) & 0x3F));
            o[p++] = (byte) (0x80 | ((cp >> 6) & 0x3F));
            o[p++] = (byte) (0x80 | (cp & 0x3F));
          } else
            throw new Unsupported("unpaired surrogate");
        } else {
          o[p++] = (byte) (0xE0 | (c >> 12));
          o[p++] = (byte) (0x80 | ((c >> 6) & 0x3F));
          o[p++] = (byte) (0x80 | (c & 0x3F));
        }
      }
      final int added = p - blobLen;
      blobLen = p;
      off[rows + 1] = p;
      return added;
    }
  }

  /** The rows of one batch as columns, filled row by row. */
  static final class Builder {
    final ArrayList<Col> cols = new ArrayList<>();
    final Map<String, Col> byName = new HashMap<>();
    Col metaRid, metaType;
    byte[] metaKind = new byte[64];
    int n;
    long bytes;
    long cells;
    final int[] seq = new int[MAX_COLS + 1];
    final Map<Integer, int[]> orders = new java.util.LinkedHashMap<>(); // rows whose property order is not the column order: the order, as column indexes

    void add(final Result row) {
      final int r = n;
      int last = -1, count = 0;
      boolean inOrder = true;
      for (final String name : row.getPropertyNames()) {
        Col c = byName.get(name);
        if (c == null) {
          if (cols.size() >= MAX_COLS)
            throw new Unsupported("columns");
          c = new Col(name, r);
          c.idx = cols.size();
          cols.add(c);
          byName.put(name, c);
        }
        if (c.idx <= last)
          inOrder = false;
        last = c.idx;
        seq[count++] = c.idx;
        bytes += c.put(row.getProperty(name), r);
        cells++;
      }
      for (final Col c : cols)
        if (c.rows == r)
          c.absent();
      if (!inOrder)
        orders.put(r, Arrays.copyOf(seq, count));
      byte k = 0;
      String rid = "", type = "";
      if (row.isElement()) {
        final Optional<Document> element = row.getElement();
        if (element.isPresent()) {
          final Document d = element.get();
          k = (byte) (d instanceof Vertex ? 'v' : d instanceof Edge ? 'e' : 'd');
          rid = d.getIdentity() == null ? "" : d.getIdentity().toString();
          type = d.getTypeName();
        }
      }
      if (k != 0 && metaRid == null) {
        metaRid = new Col("@rid", r);
        metaType = new Col("@type", r);
        metaRid.kind = metaType.kind = 's';
        metaRid.off = new int[Math.max(16, r + 16) + 1];
        metaType.off = new int[Math.max(16, r + 16) + 1];
        metaRid.blob = new byte[256];
        metaType.blob = new byte[256];
        metaRid.pres = null;
      }
      if (metaKind.length <= r)
        metaKind = Arrays.copyOf(metaKind, metaKind.length * 2);
      metaKind[r] = k;
      if (metaRid != null) {
        bytes += 1 + metaRid.putPlain(rid) + metaType.putPlain(type);
      }
      n++;
    }

    /** A table that is mostly holes is bigger and slower as columns than as rows. */
    boolean sparse() {
      return (cols.size() > 1 && cells * 4 < (long) n * cols.size()) || orders.size() > n / 2;
    }

    Frame finish(final long rs, final boolean drained, final String rerr) {
      return new Frame(this, rs, drained, rerr);
    }
  }

  /** The laid-out frame: sizes and offsets decided, ready to be written into a buffer of exactly total bytes. */
  static final class Frame {
    final Builder b;
    final long rs;
    final boolean drained;
    final byte[] hdr;
    final int hdrLen;
    final int total;
    int pos = 8; // offsets within the data section; 0 means none
    int metaKindAt;

    Frame(final Builder b, final long rs, final boolean drained, final String rerr) {
      this.b = b;
      this.rs = rs;
      this.drained = drained;
      final int n = b.n;
      for (final Col c : b.cols)
        layout(c, n);
      int metaKind = 0;
      if (b.metaRid != null) {
        metaKind = pos;
        metaKindAt = pos;
        pos += align8(n);
        layout(b.metaRid, n);
        layout(b.metaType, n);
      }
      final StringBuilder sb = new StringBuilder("{\"c\":[");
      boolean first = true;
      for (final Col c : b.cols) {
        if (!first)
          sb.append(',');
        first = false;
        sb.append('[');
        NativeCodec.quote(sb, c.name);
        sb.append(",\"").append(c.wireKind).append("\",").append(c.wireKind == 'f' ? c.dim : 0).append(',').append(c.dataOff).append(',')
            .append(c.auxOff).append(',').append(c.valOff).append(',').append(c.presOff).append(']');
      }
      sb.append("],\"m\":");
      if (b.metaRid == null)
        sb.append('0');
      else
        sb.append('[').append(metaKind).append(',').append(b.metaRid.dataOff).append(',').append(b.metaRid.auxOff).append(',')
            .append(b.metaType.dataOff).append(',').append(b.metaType.auxOff).append(']');
      if (!b.orders.isEmpty()) {
        sb.append(",\"o\":[");
        boolean firstOrder = true;
        for (final Map.Entry<Integer, int[]> e : b.orders.entrySet()) {
          if (!firstOrder)
            sb.append(',');
          firstOrder = false;
          sb.append('[').append(e.getKey()).append(",[");
          for (int i = 0; i < e.getValue().length; i++)
            sb.append(i > 0 ? "," : "").append(e.getValue()[i]);
          sb.append("]]");
        }
        sb.append(']');
      }
      if (rerr != null)
        sb.append(",\"rerr\":").append(rerr);
      sb.append('}');
      while ((sb.length() & 7) != 0)
        sb.append(' ');
      hdr = sb.toString().getBytes(StandardCharsets.UTF_8);
      hdrLen = hdr.length;
      total = HEADER + hdrLen + pos;
    }

    private void layout(final Col c, final int n) {
      c.hasVal = c.nVal < n;
      c.hasPres = c.nPres < n;
      if (c.pres == null) { // meta columns carry no bitmaps
        c.hasVal = c.hasPres = false;
      }
      if (c.hasVal) {
        c.valOff = pos;
        pos += align8((n + 7) >> 3);
      }
      if (c.hasPres) {
        c.presOff = pos;
        pos += align8((n + 7) >> 3);
      }
      char k = c.kind == 0 ? 'n' : c.kind;
      if (k == 'v' && !c.hasVal && c.sameDim && c.dim >= 1)
        k = 'f';
      c.wireKind = k;
      switch (k) {
        case 'q', 'd', 'D', 'T', 'Z' -> {
          c.dataOff = pos;
          pos += align8(8L * n);
        }
        case 'b' -> {
          c.dataOff = pos;
          pos += align8(n);
        }
        case 's', 'R' -> {
          c.dataOff = pos;
          pos += align8(4L * (n + 1));
          c.auxOff = pos;
          pos += align8(c.blobLen);
        }
        case 'v' -> {
          c.dataOff = pos;
          pos += align8(4L * (n + 1));
          c.auxOff = pos;
          pos += align8(4L * c.flLen);
        }
        case 'f' -> {
          c.dataOff = pos;
          pos += align8(4L * n * c.dim);
        }
        default -> {
        }
      }
    }

    void write(final ByteBuffer out) {
      final ByteBuffer bb = out;
      bb.order(ByteOrder.nativeOrder());
      final int base = HEADER + hdrLen;
      bb.putInt(0, MAGIC);
      bb.putInt(4, hdrLen);
      bb.putLong(8, total);
      bb.putLong(16, rs);
      bb.putInt(24, b.n);
      bb.putInt(28, drained ? 1 : 0);
      bb.put(HEADER, hdr, 0, hdrLen);
      bb.put(base, ZEROS, 0, 8);
      final int n = b.n;
      for (final Col c : b.cols)
        writeCol(bb, base, c, n);
      if (b.metaRid != null) {
        final int at = base + metaKindAt;
        bb.put(at, b.metaKind, 0, n);
        pad(bb, at + n);
        writeCol(bb, base, b.metaRid, n);
        writeCol(bb, base, b.metaType, n);
      }
    }

    private static void pad(final ByteBuffer bb, final int end) {
      final int p = align8(end) - end;
      if (p > 0)
        bb.put(end, ZEROS, 0, p);
    }

    private static void writeCol(final ByteBuffer bb, final int base, final Col c, final int n) {
      final int bitmap = (n + 7) >> 3;
      if (c.hasVal) {
        bb.put(base + c.valOff, c.val, 0, bitmap);
        pad(bb, base + c.valOff + bitmap);
      }
      if (c.hasPres) {
        bb.put(base + c.presOff, c.pres, 0, bitmap);
        pad(bb, base + c.presOff + bitmap);
      }
      final int at = base + c.dataOff;
      switch (c.wireKind) {
        case 'q', 'd', 'D', 'T', 'Z' -> {
          final ByteBuffer s = bb.slice(at, 8 * n).order(ByteOrder.nativeOrder());
          if (c.wireKind == 'd')
            s.asDoubleBuffer().put(c.d, 0, n);
          else
            s.asLongBuffer().put(c.l, 0, n);
        }
        case 'b' -> {
          bb.put(at, c.b, 0, n);
          pad(bb, at + n);
        }
        case 's', 'R' -> {
          bb.slice(at, 4 * (n + 1)).order(ByteOrder.nativeOrder()).asIntBuffer().put(c.off, 0, n + 1);
          pad(bb, at + 4 * (n + 1));
          bb.put(base + c.auxOff, c.blob, 0, c.blobLen);
          pad(bb, base + c.auxOff + c.blobLen);
        }
        case 'v' -> {
          bb.slice(at, 4 * (n + 1)).order(ByteOrder.nativeOrder()).asIntBuffer().put(c.off, 0, n + 1);
          pad(bb, at + 4 * (n + 1));
          bb.slice(base + c.auxOff, 4 * c.flLen).order(ByteOrder.nativeOrder()).asFloatBuffer().put(c.fl, 0, c.flLen);
          pad(bb, base + c.auxOff + 4 * c.flLen);
        }
        case 'f' -> {
          bb.slice(at, 4 * n * c.dim).order(ByteOrder.nativeOrder()).asFloatBuffer().put(c.fl, 0, n * c.dim);
          pad(bb, at + 4 * n * c.dim);
        }
        default -> {
        }
      }
    }
  }
}
