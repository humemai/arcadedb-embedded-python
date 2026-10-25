/*
 * Python-bindings bridge: per-call glue for graph traversal and vector search results.
 *
 * Same idea as DbCalls: a JPype call costs a few microseconds of dispatch, so the paths that make one call per edge
 * or per hit are dominated by the number of calls. Iterating the Iterable that Vertex.getEdges() returns took a
 * hasNext() and a next() crossing per edge, and wrapping a vector search hit took getFirst(), getSecond(), and the
 * record lookup. These return the same objects in one crossing, as arrays whose elements Python reads without method
 * dispatch.
 *
 * Compiled into arcadedb-python-bridge.jar during the wheel build and consumed by Vertex.get_out_edges() and its
 * siblings and by the vector index search methods in the Python bindings.
 */
package com.arcadedb.python;

import com.arcadedb.database.Database;
import com.arcadedb.database.RID;
import com.arcadedb.graph.Edge;
import com.arcadedb.graph.Vertex;
import com.arcadedb.utility.Pair;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class GraphCalls {

  private GraphCalls() {
  }

  private static Edge[] drain(final Iterable<Edge> edges) {
    final List<Edge> list = new ArrayList<>();
    for (final Edge edge : edges)
      list.add(edge);
    return list.toArray(new Edge[0]);
  }

  /** The edges of {@code vertex.getEdges(Vertex.DIRECTION.OUT, labels)}, in iteration order. */
  public static Edge[] outEdges(final Vertex vertex, final String... labels) {
    return drain(vertex.getEdges(Vertex.DIRECTION.OUT, labels));
  }

  /** The edges of {@code vertex.getEdges(Vertex.DIRECTION.IN, labels)}, in iteration order. */
  public static Edge[] inEdges(final Vertex vertex, final String... labels) {
    return drain(vertex.getEdges(Vertex.DIRECTION.IN, labels));
  }

  /** The edges of {@code vertex.getEdges(Vertex.DIRECTION.BOTH, labels)}, in iteration order. */
  public static Edge[] bothEdges(final Vertex vertex, final String... labels) {
    return drain(vertex.getEdges(Vertex.DIRECTION.BOTH, labels));
  }

  /**
   * A set of RIDs from their text, for the {@code allowed_rids} filter of a vector search: building it from Python took a RID
   * constructor call and an {@code add} call per RID (about 5 microseconds each), here the strings cross as one array.
   */
  public static Set<RID> ridSet(final String[] rids) {
    final Set<RID> set = new HashSet<>(Math.max(16, (int) (rids.length / 0.75f) + 1));
    for (final String rid : rids)
      set.add(new RID(rid));
    return set;
  }

  /**
   * The records and scores of vector search hits: for each {@code Pair<RID, Float>}, {@code db.lookupByRID(rid, true)}
   * and the score as a double. Returns {@code {Object[] records, double[] scores}}; a record is null where the engine
   * returned null, so the caller can name that hit.
   */
  public static Object[] hits(final Database db, final Iterable<?> pairs) {
    final List<Object> records = new ArrayList<>();
    final List<Double> scores = new ArrayList<>();
    for (final Object item : pairs) {
      final Pair<?, ?> pair = (Pair<?, ?>) item;
      records.add(db.lookupByRID((RID) pair.getFirst(), true));
      scores.add(((Number) pair.getSecond()).doubleValue());
    }
    final double[] s = new double[scores.size()];
    for (int i = 0; i < s.length; i++)
      s[i] = scores.get(i);
    return new Object[] { records.toArray(), s };
  }

  /**
   * The best {@code k} hits across the result lists of several vector indexes (one list per bucket index): merge by score
   * first, load only those. {@code hits} on each list costs one record lookup per hit, so a type with B buckets paid
   * B * k lookups and kept k. Scores are distances (lower is better); the sort is stable, so ties keep the order the
   * lists were given in, as the Python sort of the concatenated hits did. Returns
   * {@code {Object[] records, double[] scores, Object[] rids}} for the kept hits in order; a record is null where the
   * engine returned null, so the caller can name that hit by its RID.
   */
  public static Object[] topHits(final Database db, final Object[] pairLists, final int k) {
    final List<Pair<?, ?>> all = new ArrayList<>();
    for (final Object list : pairLists)
      for (final Object item : (Iterable<?>) list)
        all.add((Pair<?, ?>) item);
    final int total = all.size();
    final double[] score = new double[total];
    final Integer[] order = new Integer[total];
    for (int i = 0; i < total; i++) {
      score[i] = ((Number) all.get(i).getSecond()).doubleValue() + 0.0; // + 0.0: -0.0 sorts equal to 0.0, as in Python
      order[i] = i;
    }
    Arrays.sort(order, (a, b) -> Double.compare(score[a], score[b])); // stable for objects
    final int n = Math.max(0, Math.min(k, total));
    final Object[] records = new Object[n];
    final double[] scores = new double[n];
    final Object[] rids = new Object[n];
    for (int i = 0; i < n; i++) {
      final Pair<?, ?> pair = all.get(order[i]);
      rids[i] = pair.getFirst();
      records[i] = db.lookupByRID((RID) rids[i], true);
      scores[i] = score[order[i]];
    }
    return new Object[] { records, scores, rids };
  }
}
