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
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

final class Json {
  static final String TAG = "\u0001";

  private final String s;
  private final CFloatPointer buf;
  private final long bufFloats;
  private int i;

  private Json(final String s, final CFloatPointer buf, final long bufFloats) {
    this.s = s;
    this.buf = buf;
    this.bufFloats = bufFloats;
  }

  static Object parse(final String text) {
    return parse(text, WordFactory.nullPointer(), 0);
  }

  /** buf: the float32 side buffer that {"\u0001":["B",offset,count]} values point into (offset and count in floats); may be null. */
  static Object parse(final String text, final CFloatPointer buf, final long bufFloats) {
    final Json j = new Json(text, buf, bufFloats);
    final Object v = j.value();
    j.ws();
    if (j.i != j.s.length())
      throw new IllegalArgumentException("trailing characters in JSON at " + j.i);
    return v;
  }

  private void ws() {
    while (i < s.length()) {
      final char c = s.charAt(i);
      if (c == ' ' || c == '\n' || c == '\t' || c == '\r')
        i++;
      else
        break;
    }
  }

  private Object value() {
    ws();
    if (i >= s.length())
      throw new IllegalArgumentException("unexpected end of JSON");
    final char c = s.charAt(i);
    switch (c) {
    case '{':
      return object();
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

  private void expect(final String word) {
    if (!s.startsWith(word, i))
      throw new IllegalArgumentException("bad JSON literal at " + i);
    i += word.length();
  }

  private Object number() {
    final int start = i;
    if (s.charAt(i) == '-' && s.startsWith("-Infinity", i)) {
      i += 9;
      return Double.NEGATIVE_INFINITY;
    }
    boolean fractional = false;
    while (i < s.length()) {
      final char c = s.charAt(i);
      if (c == '.' || c == 'e' || c == 'E') {
        fractional = true;
        i++;
      } else if ((c >= '0' && c <= '9') || c == '-' || c == '+')
        i++;
      else
        break;
    }
    final String t = s.substring(start, i);
    if (t.isEmpty())
      throw new IllegalArgumentException("bad JSON value at " + start);
    if (fractional)
      return Double.parseDouble(t);
    try {
      return Long.parseLong(t);
    } catch (final NumberFormatException e) {
      // the JPype path raises OverflowError for a Python int beyond 64 bits (query parameters and the bulk paths alike):
      // refuse it here instead of letting the engine wrap or widen it
      new BigInteger(t);
      throw new IllegalArgumentException("integer out of range for a 64-bit parameter: " + t);
    }
  }

  private String string() {
    i++;
    StringBuilder sb = null;
    int start = i;
    while (true) {
      if (i >= s.length())
        throw new IllegalArgumentException("unterminated JSON string");
      final char c = s.charAt(i);
      if (c == '"') {
        final String r = sb == null ? s.substring(start, i) : sb.append(s, start, i).toString();
        i++;
        return r;
      }
      if (c == '\\') {
        if (sb == null)
          sb = new StringBuilder();
        sb.append(s, start, i);
        i++;
        final char e = s.charAt(i++);
        switch (e) {
        case 'n' -> sb.append('\n');
        case 't' -> sb.append('\t');
        case 'r' -> sb.append('\r');
        case 'b' -> sb.append('\b');
        case 'f' -> sb.append('\f');
        case 'u' -> {
          sb.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
          i += 4;
        }
        default -> sb.append(e);
        }
        start = i;
      } else
        i++;
    }
  }

  private List<Object> array() {
    i++;
    final List<Object> out = new ArrayList<>();
    ws();
    if (s.charAt(i) == ']') {
      i++;
      return out;
    }
    while (true) {
      out.add(value());
      ws();
      final char c = s.charAt(i++);
      if (c == ']')
        return out;
      if (c != ',')
        throw new IllegalArgumentException("bad JSON array at " + (i - 1));
    }
  }

  private Object object() {
    i++;
    final Map<String, Object> out = new HashMap<>();
    ws();
    if (s.charAt(i) == '}') {
      i++;
      return out;
    }
    while (true) {
      ws();
      final String k = string();
      ws();
      if (s.charAt(i++) != ':')
        throw new IllegalArgumentException("bad JSON object at " + (i - 1));
      out.put(k, value());
      ws();
      final char c = s.charAt(i++);
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
      if (buf.isNull() || off < 0 || count < 0 || off + count > bufFloats)
        throw new IllegalArgumentException("binary parameter outside the side buffer");
      final float[] f = new float[count];
      for (int k = 0; k < count; k++)
        f[k] = buf.read((int) off + k);
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
