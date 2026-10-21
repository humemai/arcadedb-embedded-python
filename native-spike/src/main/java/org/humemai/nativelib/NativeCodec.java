/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Result rows as type-faithful JSON for the Python native backend. Same tagging scheme as the JPype bridge's
 * TypedRows (bindings/python/src/java), but with no side array of Java objects (there is no JVM to hold them): every
 * value is plain JSON or a tagged value that Python restores.
 *
 *   {"\u0001": ["n", "1.25"]}     BigDecimal           {"\u0001": ["i", "123"]}     BigInteger
 *   {"\u0001": ["D", "2020-01-01"]}  LocalDate         {"\u0001": ["T", "2020-01-01T12:00:00.000000"]}  LocalDateTime, Date, Calendar (UTC wall clock)
 *   {"\u0001": ["Z", "...+00:00"]}   Instant, ZonedDateTime, OffsetDateTime (UTC)
 *   {"\u0001": ["s", [..]]}       Set                  {"\u0001": ["f", "NaN"]}     non-finite Float/Double
 *   {"\u0001": ["m", [[k, v]..]]} Map with non-String keys
 *
 * A RID is its text ("#12:3"); a record nested in a value is an object with "@rid" and "@type" members next to its
 * properties; float[] and double[] are JSON number lists (a float widens to double, as it does through the bridge);
 * byte[], short[], int[], long[] and boolean[] are lists.
 */
package org.humemai.nativelib;

import com.arcadedb.database.Document;
import com.arcadedb.database.Identifiable;
import com.arcadedb.graph.Edge;
import com.arcadedb.graph.Vertex;
import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.Calendar;
import java.util.Collection;
import java.util.Date;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

final class NativeCodec {
  static final int MAX_BATCH_CHARS = 4 * 1024 * 1024;

  private NativeCodec() {
  }

  /**
   * Appends {@code "rows":[..],"meta":[..],"drained":b} (no braces) with up to max rows. meta has one entry per row: 0
   * for a projection, or [rid, typeName, kind] for a record row (kind v, e or d).
   */
  static boolean appendBatch(final StringBuilder sb, final ResultSet rs, final int max) {
    final StringBuilder meta = new StringBuilder("[");
    sb.append("\"rows\":[");
    int n = 0;
    boolean drained = false;
    String readError = null;
    try {
      while (n < max) {
        if (!rs.hasNext()) {
          drained = true;
          break;
        }
        final Result row = rs.next();
        final int rowStart = sb.length();
        final int metaStart = meta.length();
        try {
          if (n > 0) {
            sb.append(',');
            meta.append(',');
          }
          appendRow(sb, meta, row);
        } catch (final Throwable t) {
          sb.setLength(rowStart);
          meta.setLength(metaStart);
          throw t;
        }
        n++;
        if (sb.length() >= MAX_BATCH_CHARS)
          break;
      }
    } catch (final Throwable t) {
      // The engine plans and computes lazily: a statement's error can surface while its rows are read. The rows read
      // before it still go to the caller; the error is raised when they have been consumed. The cursor is finished.
      readError = ArcadeNative.errorJson(t);
      drained = true;
    }
    sb.append("],\"meta\":").append(meta).append("],\"drained\":").append(drained);
    if (readError != null)
      sb.append(",\"rerr\":").append(readError);
    return drained;
  }

  private static void appendRow(final StringBuilder sb, final StringBuilder meta, final Result row) {
    sb.append('{');
    boolean first = true;
    for (final String name : row.getPropertyNames()) {
      if (!first)
        sb.append(',');
      first = false;
      quote(sb, name);
      sb.append(':');
      append(sb, row.getProperty(name));
    }
    sb.append('}');
    if (row.isElement()) {
      final Optional<Document> element = row.getElement();
      if (element.isPresent()) {
        final Document d = element.get();
        meta.append('[');
        quote(meta, d.getIdentity() == null ? "" : d.getIdentity().toString());
        meta.append(',');
        quote(meta, d.getTypeName());
        meta.append(",\"").append(d instanceof Vertex ? 'v' : d instanceof Edge ? 'e' : 'd').append("\"]");
        return;
      }
    }
    meta.append('0');
  }

  static void append(final StringBuilder sb, final Object value) {
    if (value == null) {
      sb.append("null");
    } else if (value instanceof String s) {
      quote(sb, s);
    } else if (value instanceof Boolean b) {
      sb.append(b.booleanValue() ? "true" : "false");
    } else if (value instanceof Integer || value instanceof Long || value instanceof Short || value instanceof Byte) {
      sb.append(value);
    } else if (value instanceof Double || value instanceof Float) {
      final double d = ((Number) value).doubleValue();
      if (Double.isFinite(d))
        sb.append(d);
      else
        tagged(sb, "f").append('"').append(Double.isNaN(d) ? "nan" : d > 0 ? "inf" : "-inf").append("\"]}");
    } else if (value instanceof Character c) {
      quote(sb, String.valueOf(c));
    } else if (value instanceof BigDecimal bd) {
      tagged(sb, "n").append('"').append(bd.toString()).append("\"]}");
    } else if (value instanceof BigInteger bi) {
      tagged(sb, "i").append('"').append(bi.toString()).append("\"]}");
    } else if (value instanceof LocalDate date) {
      if (yearFits(date.getYear())) {
        tagged(sb, "D").append('"');
        appendDate(sb, date.getYear(), date.getMonthValue(), date.getDayOfMonth());
        sb.append("\"]}");
      } else
        quote(sb, date.toString());
    } else if (value instanceof LocalDateTime dt) {
      appendDateTime(sb, "T", dt, "", value);
    } else if (value instanceof Instant instant) {
      appendDateTime(sb, "Z", LocalDateTime.ofEpochSecond(instant.getEpochSecond(), instant.getNano(), ZoneOffset.UTC), "+00:00",
          value);
    } else if (value instanceof ZonedDateTime zdt) {
      final Instant instant = zdt.toInstant();
      appendDateTime(sb, "Z", LocalDateTime.ofEpochSecond(instant.getEpochSecond(), instant.getNano(), ZoneOffset.UTC), "+00:00",
          value);
    } else if (value instanceof OffsetDateTime odt) {
      final Instant instant = odt.toInstant();
      appendDateTime(sb, "Z", LocalDateTime.ofEpochSecond(instant.getEpochSecond(), instant.getNano(), ZoneOffset.UTC), "+00:00",
          value);
    } else if (value instanceof Date date) {
      appendEpochMillis(sb, date.getTime(), value);
    } else if (value instanceof Calendar calendar) {
      appendEpochMillis(sb, calendar.getTimeInMillis(), value);
    } else if (value instanceof Document doc) {
      appendDocument(sb, doc);
    } else if (value instanceof Identifiable id) {
      quote(sb, id.getIdentity().toString());
    } else if (value instanceof Map<?, ?> map) {
      boolean stringKeys = true;
      for (final Object key : map.keySet())
        if (!(key instanceof String k) || Json.TAG.equals(k)) {
          stringKeys = false;
          break;
        }
      if (stringKeys) {
        sb.append('{');
        boolean first = true;
        for (final Map.Entry<?, ?> entry : map.entrySet()) {
          if (!first)
            sb.append(',');
          first = false;
          quote(sb, (String) entry.getKey());
          sb.append(':');
          append(sb, entry.getValue());
        }
        sb.append('}');
      } else {
        tagged(sb, "m").append('[');
        boolean first = true;
        for (final Map.Entry<?, ?> entry : map.entrySet()) {
          if (!first)
            sb.append(',');
          first = false;
          sb.append('[');
          append(sb, entry.getKey());
          sb.append(',');
          append(sb, entry.getValue());
          sb.append(']');
        }
        sb.append("]]}");
      }
    } else if (value instanceof Set<?> set) {
      tagged(sb, "s").append('[');
      appendElements(sb, set);
      sb.append("]]}");
    } else if (value instanceof Collection<?> collection) {
      sb.append('[');
      appendElements(sb, collection);
      sb.append(']');
    } else if (value instanceof float[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++) {
        if (i > 0)
          sb.append(',');
        appendFloating(sb, a[i]);
      }
      sb.append(']');
    } else if (value instanceof double[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++) {
        if (i > 0)
          sb.append(',');
        appendFloating(sb, a[i]);
      }
      sb.append(']');
    } else if (value instanceof byte[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++)
        sb.append(i > 0 ? "," : "").append(a[i]);
      sb.append(']');
    } else if (value instanceof short[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++)
        sb.append(i > 0 ? "," : "").append(a[i]);
      sb.append(']');
    } else if (value instanceof int[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++)
        sb.append(i > 0 ? "," : "").append(a[i]);
      sb.append(']');
    } else if (value instanceof long[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++)
        sb.append(i > 0 ? "," : "").append(a[i]);
      sb.append(']');
    } else if (value instanceof boolean[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++)
        sb.append(i > 0 ? "," : "").append(a[i]);
      sb.append(']');
    } else if (value instanceof Object[] a) {
      sb.append('[');
      for (int i = 0; i < a.length; i++) {
        if (i > 0)
          sb.append(',');
        append(sb, a[i]);
      }
      sb.append(']');
    } else
      quote(sb, String.valueOf(value));
  }

  private static void appendFloating(final StringBuilder sb, final double d) {
    if (Double.isFinite(d))
      sb.append(d);
    else
      tagged(sb, "f").append('"').append(Double.isNaN(d) ? "nan" : d > 0 ? "inf" : "-inf").append("\"]}");
  }

  private static void appendDocument(final StringBuilder sb, final Document doc) {
    sb.append('{');
    if (doc.getIdentity() != null) {
      sb.append("\"@rid\":");
      quote(sb, doc.getIdentity().toString());
      sb.append(',');
    }
    sb.append("\"@type\":");
    quote(sb, doc.getTypeName());
    for (final String name : doc.getPropertyNames()) {
      sb.append(',');
      quote(sb, name);
      sb.append(':');
      append(sb, doc.get(name));
    }
    sb.append('}');
  }

  private static void appendElements(final StringBuilder sb, final Collection<?> elements) {
    boolean first = true;
    for (final Object element : elements) {
      if (!first)
        sb.append(',');
      first = false;
      append(sb, element);
    }
  }

  private static StringBuilder tagged(final StringBuilder sb, final String kind) {
    return sb.append("{\"\\u0001\":[\"").append(kind).append("\",");
  }

  private static boolean yearFits(final int year) {
    return year >= 1 && year <= 9999;
  }

  private static void appendDateTime(final StringBuilder sb, final String kind, final LocalDateTime dt, final String suffix,
      final Object original) {
    if (!yearFits(dt.getYear())) {
      quote(sb, String.valueOf(original));
      return;
    }
    tagged(sb, kind).append('"');
    appendDate(sb, dt.getYear(), dt.getMonthValue(), dt.getDayOfMonth());
    sb.append('T');
    pad(sb, dt.getHour(), 2).append(':');
    pad(sb, dt.getMinute(), 2).append(':');
    pad(sb, dt.getSecond(), 2).append('.');
    pad(sb, dt.getNano() / 1000, 6).append(suffix).append("\"]}");
  }

  private static void appendEpochMillis(final StringBuilder sb, final long millis, final Object original) {
    appendDateTime(sb, "T",
        LocalDateTime.ofEpochSecond(Math.floorDiv(millis, 1000L), Math.floorMod(millis, 1000) * 1_000_000, ZoneOffset.UTC), "",
        original);
  }

  private static void appendDate(final StringBuilder sb, final int year, final int month, final int day) {
    pad(sb, year, 4).append('-');
    pad(sb, month, 2).append('-');
    pad(sb, day, 2);
  }

  private static StringBuilder pad(final StringBuilder sb, final int value, final int width) {
    int digits = 1;
    for (int v = value; v >= 10; v /= 10)
      digits++;
    for (int i = digits; i < width; i++)
      sb.append('0');
    return sb.append(value);
  }

  static void quote(final StringBuilder sb, final String s) {
    sb.append('"');
    final int length = s.length();
    for (int i = 0; i < length; i++) {
      final char c = s.charAt(i);
      if (c == '"')
        sb.append("\\\"");
      else if (c == '\\')
        sb.append("\\\\");
      else if (c < 0x20 || (c >= 0xD800 && c <= 0xDFFF)) {
        sb.append("\\u");
        final String hex = Integer.toHexString(c);
        for (int k = hex.length(); k < 4; k++)
          sb.append('0');
        sb.append(hex);
      } else
        sb.append(c);
    }
    sb.append('"');
  }
}
