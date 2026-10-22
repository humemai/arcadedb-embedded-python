/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal strict JSON reader for the native entry points. Integers without a fraction or exponent come back as Long
 * (BigInteger past 64 bits), other numbers as Double, objects as HashMap (the iteration order of the JPype path's java.util.HashMap). NaN/Infinity/-Infinity are accepted
 * because Python's json module writes them. An object {"\u0001": [kind, payload]} is a tagged value (see decodeTag).
 */
package org.humemai.nativelib;

import org.graalvm.nativeimage.c.type.CFloatPointer;
import org.graalvm.word.WordFactory;


import java.math.BigDecimal;
import java.math.BigInteger;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

final class Json {
  static final String TAG = "\u0001";

  /** One row of a streamed top-level array; the map is reused for the next row, so a sink must not keep it. */
  interface RowSink {
    void row(Map<String, Object> row);
  }

  private static final double[] POW10 = { 1e0, 1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8, 1e9, 1e10, 1e11, 1e12, 1e13, 1e14, 1e15, 1e16, 1e17, 1e18, 1e19,
      1e20, 1e21, 1e22 };
  private static final int CACHE_MIN_INPUT = 4096; // below this a string cache costs more than it saves
  private static final int CACHE_SLOTS = 1024;
  private static final int CACHE_MAX_LEN = 24;
  private static final int DEFAULT_TABLE_ENTRIES = 12; // a HashMap of 16 buckets resizes on the 13th entry

  private final byte[] s;
  private final int n;
  private final long buf; // address of the float32 side buffer, 0 for none (a plain long: no Word value flows through this shared parser)
  private final long bufFloats;
  private int i;
  private String[] cache; // direct-mapped: short ASCII keys and values shared across rows instead of one new String per occurrence
  private Map<String, Object> rowMap = new HashMap<>();

  private Json(final byte[] s, final int n, final long buf, final long bufFloats) {
    this.s = s;
    this.n = n;
    this.buf = buf;
    this.bufFloats = bufFloats;
    if (n >= CACHE_MIN_INPUT)
      cache = new String[CACHE_SLOTS];
  }

  static Object parse(final String text) {
    return parse(text, 0L, 0);
  }

  /** buf: the float32 side buffer that {"\u0001":["B",offset,count]} values point into (offset and count in floats); may be null. */
  static Object parse(final String text, final long buf, final long bufFloats) {
    final byte[] b = text.getBytes(StandardCharsets.UTF_8);
    return parse(b, b.length, buf, bufFloats);
  }

  static Object parse(final byte[] b, final int len, final long buf, final long bufFloats) {
    final Json j = new Json(b, len, buf, bufFloats);
    final Object v = j.value();
    j.end();
    return v;
  }

  /** Streams the elements of a top-level array of objects to the sink (one reused map, so no tree of the whole payload is built). */
  @SuppressWarnings("unchecked")
  static void rows(final byte[] b, final int len, final RowSink sink) {
    final Json j = new Json(b, len, 0L, 0);
    j.rowsOf(sink);
    j.end();
  }

  /**
   * Parses a top-level object whose value for streamKey is an array of objects: those rows go to the sink one by one and the key maps to
   * the row count (Integer) instead of the list. Every other key is parsed as usual. A streamKey value that is not an array stays as parsed.
   */
  @SuppressWarnings("unchecked")
  static Map<String, Object> object(final byte[] b, final int len, final String streamKey, final RowSink sink) {
    final Json j = new Json(b, len, 0L, 0);
    j.ws();
    if (j.i >= j.n || j.s[j.i] != '{')
      throw new IllegalArgumentException("expected a JSON object");
    j.i++;
    final Map<String, Object> out = new HashMap<>();
    j.ws();
    if (j.s[j.i] == '}')
      j.i++;
    else
      while (true) {
        j.ws();
        final String k = j.string();
        j.ws();
        if (j.s[j.i++] != ':')
          throw new IllegalArgumentException("bad JSON object at " + (j.i - 1));
        j.ws();
        if (k.equals(streamKey) && j.i < j.n && j.s[j.i] == '[')
          out.put(k, j.rowsOf(sink));
        else
          out.put(k, j.value());
        j.ws();
        final char c = (char) j.s[j.i++];
        if (c == '}')
          break;
        if (c != ',')
          throw new IllegalArgumentException("bad JSON object at " + (j.i - 1));
      }
    j.end();
    return out;
  }

  @SuppressWarnings("unchecked")
  private Integer rowsOf(final RowSink sink) {
    ws();
    if (i >= n || s[i] != '[')
      throw new IllegalArgumentException("expected a JSON array");
    i++;
    int count = 0;
    ws();
    if (s[i] == ']') {
      i++;
      return 0;
    }
    while (true) {
      ws();
      if (i < n && s[i] == '{') {
        final Object r = object(rowMap);
        final boolean grown = rowMap.size() > DEFAULT_TABLE_ENTRIES; // a bigger table would iterate a later row in another order than a fresh map
        sink.row((Map<String, Object>) r);
        count++;
        if (grown)
          rowMap = new HashMap<>();
        else
          rowMap.clear();
      } else {
        sink.row((Map<String, Object>) value()); // null or a non-object: the cast fails as it did for the whole-tree parse
        count++;
      }
      ws();
      final char c = (char) s[i++];
      if (c == ']')
        return count;
      if (c != ',')
        throw new IllegalArgumentException("bad JSON array at " + (i - 1));
    }
  }

  private void end() {
    ws();
    if (i != n)
      throw new IllegalArgumentException("trailing characters in JSON at " + i);
  }

  private void ws() {
    while (i < n) {
      final byte c = s[i];
      if (c == ' ' || c == '\n' || c == '\t' || c == '\r')
        i++;
      else
        break;
    }
  }

  private Object value() {
    ws();
    if (i >= n)
      throw new IllegalArgumentException("unexpected end of JSON");
    final char c = (char) s[i];
    switch (c) {
    case '{':
      return object(null);
    case '[':
      return array();
    case '"':
      return string();
    case 't':
      expect("true");
      return Boolean.TRUE;
    case 'f':
      expect("false");
      return Boolean.FALSE;
    case 'n':
      expect("null");
      return null;
    case 'N':
      expect("NaN");
      return Double.NaN;
    case 'I':
      expect("Infinity");
      return Double.POSITIVE_INFINITY;
    default:
      return number();
    }
  }

  private boolean startsWith(final String word) {
    if (i + word.length() > n)
      return false;
    for (int k = 0; k < word.length(); k++)
      if (s[i + k] != word.charAt(k))
        return false;
    return true;
  }

  private void expect(final String word) {
    if (!startsWith(word))
      throw new IllegalArgumentException("bad JSON literal at " + i);
    i += word.length();
  }

  private Object number() {
    final int start = i;
    if (s[i] == '-' && startsWith("-Infinity")) {
      i += 9;
      return Double.NEGATIVE_INFINITY;
    }
    boolean fractional = false;
    boolean plain = true; // an optional '-' and digits (one '.' for a double) only: summed up without a String
    long acc = 0;
    int digits = 0;
    int dots = 0, fracDigits = 0;
    while (i < n) {
      final byte c = s[i];
      if (c == '.' || c == 'e' || c == 'E') {
        fractional = true;
        if (c == '.')
          dots++;
        else
          plain = false;
        i++;
      } else if (c >= '0' && c <= '9') {
        if (++digits <= 18)
          acc = acc * 10 + (c - '0');
        if (dots > 0)
          fracDigits++;
        i++;
      } else if (c == '-' || c == '+') {
        if (i != start || c == '+')
          plain = false;
        i++;
      } else
        break;
    }
    if (i == start)
      throw new IllegalArgumentException("bad JSON value at " + start);
    if (fractional && plain && dots == 1 && digits <= 18 && fracDigits >= 1 && fracDigits <= 22 && acc <= (1L << 53)
        && s[i - 1] != '.' && s[start] != '.') {
      // m / 10^k with m <= 2^53 and k <= 22: both exactly representable, so the one division is the correctly rounded decimal value
      // (what Double.parseDouble returns), without the String and the big-number scratch that parseDouble allocates
      final double d = (double) acc / POW10[fracDigits];
      return s[start] == '-' ? -d : d;
    }
    if (fractional)
      return Double.parseDouble(new String(s, start, i - start, StandardCharsets.ISO_8859_1));
    if (plain && digits > 0 && digits <= 18)
      return s[start] == '-' ? -acc : acc;
    final String t = new String(s, start, i - start, StandardCharsets.ISO_8859_1);
    try {
      return Long.parseLong(t);
    } catch (final NumberFormatException e) {
      // the JPype path raises OverflowError for a Python int beyond 64 bits (query parameters and the bulk paths alike):
      // refuse it here instead of letting the engine wrap or widen it
      new BigInteger(t);
      throw new IllegalArgumentException("integer out of range for a 64-bit parameter: " + t);
    }
  }

  /** The text of s[start, end): a short pure-ASCII one comes from the cache when an equal one was read before. */
  private String text(final int start, final int len, final boolean ascii) {
    if (len == 0)
      return "";
    if (!ascii)
      return new String(s, start, len, StandardCharsets.UTF_8);
    final String[] c = cache;
    if (c == null || len > CACHE_MAX_LEN)
      return new String(s, start, len, StandardCharsets.ISO_8859_1);
    int h = len;
    for (int k = 0; k < len; k++)
      h = h * 31 + s[start + k];
    final int slot = (h ^ (h >>> 15)) & (CACHE_SLOTS - 1);
    final String hit = c[slot];
    if (hit != null && hit.length() == len) {
      int k = 0;
      while (k < len && hit.charAt(k) == s[start + k])
        k++;
      if (k == len)
        return hit;
    }
    final String made = new String(s, start, len, StandardCharsets.ISO_8859_1);
    c[slot] = made;
    return made;
  }

  private String string() {
    i++;
    final int start = i;
    int p = i;
    boolean ascii = true;
    while (true) {
      if (p >= n)
        throw new IllegalArgumentException("unterminated JSON string");
      final byte c = s[p];
      if (c == '"') {
        i = p + 1;
        return text(start, p - start, ascii);
      }
      if (c == '\\')
        break;
      if (c < 0)
        ascii = false;
      p++;
    }
    // an escape in the string: a builder for this one
    final StringBuilder sb = new StringBuilder();
    int seg = start;
    i = p;
    while (true) {
      if (i >= n)
        throw new IllegalArgumentException("unterminated JSON string");
      final byte c = s[i];
      if (c == '"') {
        sb.append(new String(s, seg, i - seg, StandardCharsets.UTF_8));
        i++;
        return sb.toString();
      }
      if (c == '\\') {
        sb.append(new String(s, seg, i - seg, StandardCharsets.UTF_8));
        i++;
        final char e = (char) s[i++];
        switch (e) {
        case 'n' -> sb.append('\n');
        case 't' -> sb.append('\t');
        case 'r' -> sb.append('\r');
        case 'b' -> sb.append('\b');
        case 'f' -> sb.append('\f');
        case 'u' -> {
          int v = 0;
          for (int k = 0; k < 4; k++) {
            final int d = Character.digit((char) s[i + k], 16);
            if (d < 0)
              throw new NumberFormatException("bad \\u escape in JSON at " + i);
            v = v * 16 + d;
          }
          sb.append((char) v);
          i += 4;
        }
        default -> sb.append(e);
        }
        seg = i;
      } else
        i++;
    }
  }

  private List<Object> array() {
    i++;
    final List<Object> out = new ArrayList<>();
    ws();
    if (s[i] == ']') {
      i++;
      return out;
    }
    while (true) {
      out.add(value());
      ws();
      final char c = (char) s[i++];
      if (c == ']')
        return out;
      if (c != ',')
        throw new IllegalArgumentException("bad JSON array at " + (i - 1));
    }
  }

  /** into: a map to fill (a streamed row, reused by the caller), or null for a fresh one. */
  private Object object(final Map<String, Object> into) {
    i++;
    final Map<String, Object> out = into != null ? into : new HashMap<>();
    ws();
    if (s[i] == '}') {
      i++;
      return out;
    }
    while (true) {
      ws();
      final String k = string();
      ws();
      if (s[i++] != ':')
        throw new IllegalArgumentException("bad JSON object at " + (i - 1));
      out.put(k, value());
      ws();
      final char c = (char) s[i++];
      if (c == '}')
        break;
      if (c != ',')
        throw new IllegalArgumentException("bad JSON object at " + (i - 1));
    }
    if (out.size() == 1 && out.get(TAG) instanceof List<?> tag && tag.size() >= 2 && tag.get(0) instanceof String kind)
      return decodeTag(kind, tag);
    return out;
  }

  /** Python -> Java tagged values: n Decimal, i big int, m map with non-str keys, D date, T datetime (UTC wall clock), s set, b bytes (base64), F float[] (as a list), B float[] (from the side buffer), R RID. */
  @SuppressWarnings("unchecked")
  private Object decodeTag(final String kind, final List<?> tag) {
    final Object payload = tag.get(1);
    switch (kind) {
    case "B": {
      // binary side buffer: float32 values [offset, offset + count) of the buffer passed beside the JSON, no text round trip
      final long off = ((Number) payload).longValue();
      final int count = ((Number) tag.get(2)).intValue();
      if (buf == 0 || off < 0 || count < 0 || off + count > bufFloats)
        throw new IllegalArgumentException("binary parameter outside the side buffer");
      final float[] f = new float[count];
      final CFloatPointer fp = WordFactory.pointer(buf);
      for (int k = 0; k < count; k++)
        f[k] = fp.read((int) off + k);
      return f;
    }
    case "n":
      return new BigDecimal((String) payload);
    case "i":
      return new BigInteger((String) payload);
    case "m": {
      // a Python dict with a non-str key: [[k, v], ..] (the plain JSON object form can only carry str keys)
      final Map<Object, Object> m = new HashMap<>();
      for (final Object pair : (List<Object>) payload) {
        final List<Object> kv = (List<Object>) pair;
        m.put(kv.get(0), kv.get(1));
      }
      return m;
    }
    case "D":
      return LocalDate.parse((String) payload);
    case "T":
      return LocalDateTime.parse((String) payload);
    case "s":
      return new HashSet<>((List<Object>) payload);
    case "b":
      return Base64.getDecoder().decode((String) payload);
    case "R":
      return new com.arcadedb.database.RID((String) payload);
    case "F": {
      final List<Object> l = (List<Object>) payload;
      final float[] f = new float[l.size()];
      for (int k = 0; k < f.length; k++)
        f[k] = ((Number) l.get(k)).floatValue();
      return f;
    }
    default:
      throw new IllegalArgumentException("unknown parameter tag " + kind);
    }
  }
}
