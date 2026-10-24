/*
 * Python-bindings bridge: float vectors that cross as one binary buffer instead of JSON text or one JPype call per element.
 *
 * Writing a 128-dimension embedding as JSON costs Python about 450 ns per number (float to text) and the engine's JSON parser
 * about the same again (text to Double, boxed in a List, converted back to float[] by the engine), so a vector load spent
 * most of its time on the text. Here a whole column of vectors crosses as ONE float[] (a numpy buffer copy) plus the
 * dimension, and each document gets its own float[] slice, which is what the engine stores for an ARRAY_OF_FLOATS property.
 *
 * Python uses this only for properties declared ARRAY_OF_FLOATS (declared() lists them): the engine converts every number of a
 * list for such a property to float, so a float32 buffer stores the same values as the list did. Any other property keeps the
 * JSON path, which keeps its exact values (Long and Double stay what they were).
 *
 * Compiled into arcadedb-python-bridge.jar during the wheel build and consumed by Database.insert_many(), Database.insert_columns()
 * and GraphBatch.create_vertices().
 */
package com.arcadedb.python;

import com.arcadedb.database.Database;
import com.arcadedb.schema.DocumentType;
import com.arcadedb.schema.Property;
import com.arcadedb.schema.Type;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class FloatVectors {

  private FloatVectors() {
  }

  /** The names of the properties of {@code typeName}, or of a type it extends, that are declared ARRAY_OF_FLOATS. */
  public static String[] declared(final Database db, final String typeName) {
    if (!db.getSchema().existsType(typeName))
      return new String[0];
    final DocumentType type = db.getSchema().getType(typeName);
    final List<String> names = new ArrayList<>();
    for (final String name : type.getPolymorphicPropertyNames()) {
      final Property property = type.getPolymorphicPropertyIfExists(name);
      if (property != null && property.getType() == Type.ARRAY_OF_FLOATS)
        names.add(name);
    }
    return names.toArray(new String[0]);
  }

  /** {@code n} vectors of {@code dim} floats each, back to back in one array. */
  public static final class Matrix {
    private final float[] data;
    private final int     dim;

    public Matrix(final float[] data, final int dim) {
      if (dim < 1)
        throw new IllegalArgumentException("a vector needs at least one dimension, got " + dim);
      if (data.length % dim != 0)
        throw new IllegalArgumentException(data.length + " floats are not a whole number of " + dim + "-dimension vectors");
      this.data = data;
      this.dim = dim;
    }

    public int rows() {
      return data.length / dim;
    }

    /** A copy of row {@code i}: the document owns its array, whatever happens to the buffer afterwards. */
    public float[] row(final int i) {
      return Arrays.copyOfRange(data, i * dim, (i + 1) * dim);
    }
  }

  /** Every matrix holds exactly {@code n} rows, and there is one name for each matrix. */
  static void check(final String[] names, final Object[] vectors, final int n) {
    if (names == null && vectors == null)
      return;
    if (names == null || vectors == null || names.length != vectors.length)
      throw new IllegalArgumentException("vector names and matrices differ in number");
    for (int c = 0; c < names.length; c++) {
      if (!(vectors[c] instanceof Matrix m))
        throw new IllegalArgumentException("'" + names[c] + "' is not a float matrix");
      if (m.rows() != n)
        throw new IllegalArgumentException("'" + names[c] + "' has " + m.rows() + " vectors for " + n + " rows");
    }
  }
}
