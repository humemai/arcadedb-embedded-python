// Probe: binary columnar transport (columnar-lite candidate).
//
// Encodes up to `max` rows of a ResultSet into ONE byte[]: a JSON header
// (column names/types/counts) followed by per-column buffers — fixed-width
// little-endian for numerics/bools/temporals (epoch millis), offset+UTF-8
// for strings, plus a null bitmap per column. Python decodes with
// numpy.frombuffer. Throwaway probe: if it beats to_json_list decisively,
// the production version goes into the bridge.

import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ColumnProbe {

  public static byte[] nextColumnBatch(final ResultSet rs, final int max, final String[] columns) {
    final int n = columns.length;
    final List<Object[]> rows = new ArrayList<>(Math.min(max, 1 << 16));
    while (rows.size() < max && rs.hasNext()) {
      final Result row = rs.next();
      final Object[] vals = new Object[n];
      for (int c = 0; c < n; c++)
        vals[c] = row.getProperty(columns[c]);
      rows.add(vals);
    }
    final int count = rows.size();

    final StringBuilder header = new StringBuilder("{\"count\":" + count + ",\"cols\":[");
    final ByteArrayOutputStream body = new ByteArrayOutputStream(count * n * 8);

    for (int c = 0; c < n; c++) {
      // null bitmap
      final byte[] nulls = new byte[(count + 7) / 8];
      // detect type from first non-null value
      String type = "str";
      for (int r = 0; r < count; r++) {
        final Object v = rows.get(r)[c];
        if (v != null) {
          if (v instanceof Long || v instanceof Integer || v instanceof Short || v instanceof Byte)
            type = "i8";
          else if (v instanceof Double || v instanceof Float)
            type = "f8";
          else if (v instanceof Boolean)
            type = "b1";
          else if (v instanceof java.util.Date)
            type = "dt";
          else
            type = "str";
          break;
        }
      }

      byte[] colBuf;
      if (type.equals("i8") || type.equals("dt")) {
        final ByteBuffer bb = ByteBuffer.allocate(count * 8).order(ByteOrder.LITTLE_ENDIAN);
        for (int r = 0; r < count; r++) {
          final Object v = rows.get(r)[c];
          if (v == null) {
            nulls[r >> 3] |= (1 << (r & 7));
            bb.putLong(0);
          } else if (type.equals("dt"))
            bb.putLong(((java.util.Date) v).getTime());
          else
            bb.putLong(((Number) v).longValue());
        }
        colBuf = bb.array();
      } else if (type.equals("f8")) {
        final ByteBuffer bb = ByteBuffer.allocate(count * 8).order(ByteOrder.LITTLE_ENDIAN);
        for (int r = 0; r < count; r++) {
          final Object v = rows.get(r)[c];
          if (v == null) {
            nulls[r >> 3] |= (1 << (r & 7));
            bb.putDouble(Double.NaN);
          } else
            bb.putDouble(((Number) v).doubleValue());
        }
        colBuf = bb.array();
      } else if (type.equals("b1")) {
        final ByteBuffer bb = ByteBuffer.allocate(count);
        for (int r = 0; r < count; r++) {
          final Object v = rows.get(r)[c];
          if (v == null) {
            nulls[r >> 3] |= (1 << (r & 7));
            bb.put((byte) 0);
          } else
            bb.put((byte) (((Boolean) v) ? 1 : 0));
        }
        colBuf = bb.array();
      } else { // strings: int32 offsets (count+1) then utf8 bytes
        final ByteArrayOutputStream chars = new ByteArrayOutputStream(count * 16);
        final ByteBuffer offs = ByteBuffer.allocate((count + 1) * 4).order(ByteOrder.LITTLE_ENDIAN);
        int pos = 0;
        offs.putInt(0);
        for (int r = 0; r < count; r++) {
          final Object v = rows.get(r)[c];
          if (v == null)
            nulls[r >> 3] |= (1 << (r & 7));
          else {
            final byte[] b = v.toString().getBytes(StandardCharsets.UTF_8);
            chars.write(b, 0, b.length);
            pos += b.length;
          }
          offs.putInt(pos);
        }
        final byte[] charBytes = chars.toByteArray();
        final ByteBuffer bb = ByteBuffer.allocate(offs.capacity() + charBytes.length);
        bb.put(offs.array());
        bb.put(charBytes);
        colBuf = bb.array();
      }

      if (c > 0)
        header.append(',');
      header.append("{\"name\":\"").append(columns[c]).append("\",\"type\":\"").append(type)
          .append("\",\"nulls\":").append(nulls.length).append(",\"bytes\":").append(colBuf.length).append('}');
      body.write(nulls, 0, nulls.length);
      body.write(colBuf, 0, colBuf.length);
    }
    header.append("]}");

    final byte[] headerBytes = header.toString().getBytes(StandardCharsets.UTF_8);
    final byte[] bodyBytes = body.toByteArray();
    final ByteBuffer out = ByteBuffer.allocate(4 + headerBytes.length + bodyBytes.length)
        .order(ByteOrder.LITTLE_ENDIAN);
    out.putInt(headerBytes.length);
    out.put(headerBytes);
    out.put(bodyBytes);
    return out.array();
  }
}
