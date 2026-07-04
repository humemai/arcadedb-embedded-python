/*
 * Python-bindings bridge: batched row transport.
 *
 * Materializing large result sets from Python via JPype costs 2+C boundary
 * crossings per row (hasNext/next + one getProperty per column), which
 * dominates wide scans (measured 15-21x slower than Java-native iteration).
 * This helper serializes up to `max` rows into ONE JSON-array string
 * Java-side, so Python pays a single crossing per batch and parses with the
 * C-fast json module (measured ~6x faster end-to-end, ~2.7x of Java-native).
 *
 * Rows are serialized property-by-property (not via Result.toJSON()) because
 * the engine's default row JSON renders primitive arrays like float[] as
 * their Java toString ("[F@..."); normalize() turns them into JSON arrays.
 *
 * Compiled into arcadedb-python-bridge.jar during the wheel build
 * (scripts/Dockerfile.build and scripts/build-native.sh) and consumed by
 * ResultSet.to_json_list() in the Python bindings. Values carry JSON-native
 * types (temporals as strings) — documented on the Python side.
 */
package com.arcadedb.python;

import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.serializer.json.JSONArray;
import com.arcadedb.serializer.json.JSONObject;

import java.util.Collection;
import java.util.Map;

public final class RowBatcher {

  private RowBatcher() {
  }

  /**
   * Serialize up to {@code max} rows of the result set into a JSON array
   * string. Returns {@code "[]"} once the result set is drained; callers loop
   * until then.
   */
  public static String nextJsonBatch(final ResultSet rs, final int max) {
    final StringBuilder sb = new StringBuilder(64 * 1024);
    sb.append('[');
    int n = 0;
    while (n < max && rs.hasNext()) {
      final Result row = rs.next();
      if (n > 0)
        sb.append(',');
      appendRow(sb, row);
      n++;
    }
    return sb.append(']').toString();
  }

  private static void appendRow(final StringBuilder sb, final Result row) {
    final JSONObject obj = new JSONObject();
    for (final String property : row.getPropertyNames())
      obj.put(property, normalize(row.getProperty(property)));
    sb.append(obj);
  }

  static Object normalize(final Object value) {
    switch (value) {
    case null -> {
      return null;
    }
    case float[] a -> {
      final JSONArray arr = new JSONArray();
      for (final float v : a)
        arr.put(v);
      return arr;
    }
    case double[] a -> {
      final JSONArray arr = new JSONArray();
      for (final double v : a)
        arr.put(v);
      return arr;
    }
    case int[] a -> {
      final JSONArray arr = new JSONArray();
      for (final int v : a)
        arr.put(v);
      return arr;
    }
    case long[] a -> {
      final JSONArray arr = new JSONArray();
      for (final long v : a)
        arr.put(v);
      return arr;
    }
    case short[] a -> {
      final JSONArray arr = new JSONArray();
      for (final short v : a)
        arr.put(v);
      return arr;
    }
    case boolean[] a -> {
      final JSONArray arr = new JSONArray();
      for (final boolean v : a)
        arr.put(v);
      return arr;
    }
    case byte[] a -> {
      final JSONArray arr = new JSONArray();
      for (final byte v : a)
        arr.put(v);
      return arr;
    }
    case Object[] a -> {
      final JSONArray arr = new JSONArray();
      for (final Object v : a)
        arr.put(normalize(v));
      return arr;
    }
    case Collection<?> c -> {
      final JSONArray arr = new JSONArray();
      for (final Object v : c)
        arr.put(normalize(v));
      return arr;
    }
    case Map<?, ?> m -> {
      final JSONObject obj = new JSONObject();
      for (final Map.Entry<?, ?> e : m.entrySet())
        obj.put(String.valueOf(e.getKey()), normalize(e.getValue()));
      return obj;
    }
    // everything else (numbers, strings, booleans, temporals, embedded
    // documents) serializes the same way Result.toJSON() would
    default -> {
      return value;
    }
    }
  }
}
