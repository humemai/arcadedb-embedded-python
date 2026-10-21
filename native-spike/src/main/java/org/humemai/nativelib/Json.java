/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Minimal strict JSON reader for the native entry points. Integers without a fraction or exponent come back as Long
 * (BigInteger past 64 bits), other numbers as Double, objects as HashMap (the iteration order of the JPype path's java.util.HashMap). NaN/Infinity/-Infinity are accepted
 * because Python's json module writes them. An object {"\u0001": [kind, payload]} is a tagged value (see decodeTag).
 */
package org.humemai.nativelib;

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
  private int i;

  private Json(final String s) {
    this.s = s;
  }

  static Object parse(final String text) {
    final Json j = new Json(text);
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
      return new BigInteger(t);
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
    if (out.size() == 1 && out.get(TAG) instanceof List<?> tag && tag.size() == 2 && tag.get(0) instanceof String kind)
      return decodeTag(kind, tag.get(1));
    return out;
  }

  /** Python -> Java tagged values: n Decimal, i big int, D date, T datetime (UTC wall clock), s set, b bytes (base64), F float[]. */
  @SuppressWarnings("unchecked")
  private static Object decodeTag(final String kind, final Object payload) {
    switch (kind) {
    case "n":
      return new BigDecimal((String) payload);
    case "i":
      return new BigInteger((String) payload);
    case "D":
      return LocalDate.parse((String) payload);
    case "T":
      return LocalDateTime.parse((String) payload);
    case "s":
      return new HashSet<>((List<Object>) payload);
    case "b":
      return Base64.getDecoder().decode((String) payload);
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
