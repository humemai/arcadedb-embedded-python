/*
 * Python-bindings bridge: bulk edge buffering for GraphBatch.
 *
 * GraphBatch.newEdge() from Python costs one JPype crossing per edge
 * (measured 4.9us/edge vs 0.2us Java-native — 24x). This helper accepts the
 * whole edge list as String[] RIDs (marshaled in one bulk array copy) and
 * loops Java-side, so Python pays one crossing per batch.
 *
 * Property-less edges only — the common bulk-ingest shape; edges with
 * properties keep the per-edge path.
 */
package com.arcadedb.python;

import com.arcadedb.database.RID;
import com.arcadedb.graph.GraphBatch;

public final class EdgeBatcher {

  private EdgeBatcher() {
  }

  public static void newEdges(final GraphBatch batch, final String[] sourceRids, final String edgeType,
      final String[] destinationRids) {
    if (sourceRids.length != destinationRids.length)
      throw new IllegalArgumentException(
          "sourceRids and destinationRids must have the same length (" + sourceRids.length + " vs "
              + destinationRids.length + ")");
    for (int i = 0; i < sourceRids.length; i++)
      batch.newEdge(new RID(sourceRids[i]), edgeType, new RID(destinationRids[i]));
  }

  /**
   * Same as {@link #newEdges} but takes semicolon-joined RID lists. JPype
   * converts a Python list of N strings to String[] element-by-element
   * (measured ~4us/edge — as slow as the per-edge path); a single joined
   * string crosses in one bulk copy and is split here.
   */
  public static void newEdgesJoined(final GraphBatch batch, final String joinedSourceRids, final String edgeType,
      final String joinedDestinationRids) {
    final String[] sources = joinedSourceRids.split(";");
    final String[] destinations = joinedDestinationRids.split(";");
    newEdges(batch, sources, edgeType, destinations);
  }
}
