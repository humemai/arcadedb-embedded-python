/*
 * Copyright © 2021-present Arcade Data Ltd (info@arcadedata.com)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * SPDX-FileCopyrightText: 2021-present Arcade Data Ltd (info@arcadedata.com)
 * SPDX-License-Identifier: Apache-2.0
 */
package com.arcadedb.index.vector;

import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.index.TypeIndex;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.DocumentType;
import com.arcadedb.schema.Type;
import com.arcadedb.utility.FileUtils;

import org.awaitility.Awaitility;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.time.Duration;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Comparator;
import java.util.Map;
import java.util.Random;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * A session that INSERTS before it searches misses the stale-prefix reuse of issue #6655 and pays a
 * synchronous full rebuild of the whole index on the search thread. A session that only searches, against
 * the identical database, reuses the persisted graph and pays for the appended vectors alone.
 * <p>
 * Both arms start from a byte-identical copy of the same database: one built, closed (so #6067's close-time
 * deferral leaves the graph stale by one vector and the manifest marked close-deferred), and never touched
 * since. The only difference between the arms is whether the session inserts one vector before searching.
 * <p>
 * WHY THE WRITE CHANGES THE PATH. {@code put()}/{@code putBatch()} promote {@code graphState} from LOADING
 * to MUTABLE on commit (:6227-6228, :6349-6350), before any search runs. {@code ensureGraphAvailable()}
 * then returns at its very first statement:
 * <pre>
 *   if (graphState != GraphState.LOADING)
 *     return; // Graph already available or being built            // :1500-1501
 * </pre>
 * so the persisted graph is never loaded, {@code graphIndex} stays null, and the #6655 prefix test at :1689
 * is unreachable. Line numbers are against upstream main 87695796d. {@code rebuildGraphBeforeSearch()} then reads that null:
 * <pre>
 *   final boolean isSmallGraph = graphIndex == null || graphIndex.size() &lt; ASYNC_REBUILD_MIN_GRAPH_SIZE;  // :3525
 *   if (isSmallGraph) { ... buildGraphFromScratch(); }                                                     // :3527,:3533
 * </pre>
 * and rebuilds the entire index synchronously on the calling thread. The flag conflates "a loaded graph now
 * has pending deltas" with "no graph has been loaded yet and there are pending deltas"; only the first
 * meaning makes {@code graphIndex == null} mean "small".
 * <p>
 * The test asserts on the RATIO and on the two state metrics, never on a wall clock, so it cannot go red on
 * a slow machine.
 */
@Tag("vector")
class WriteThenSearchMissesPrefixReuseTest {
  private static final int    DIMENSIONS = 64;
  private static final int    VECTORS    = 20_000;   // >> ASYNC_REBUILD_MIN_GRAPH_SIZE (1000)
  private static final String BASE       = "./target/databases/WriteThenSearchMissesPrefixReuse";
  private static final String TEMPLATE   = BASE + "-template";
  private static final String ARM        = BASE + "-arm";

  @AfterEach
  void cleanUp() {
    FileUtils.deleteRecursively(new File(TEMPLATE));
    FileUtils.deleteRecursively(new File(ARM));
  }

  @Test
  void insertingBeforeSearchingCostsAFullRebuildInsteadOfAPrefixReuse() {
    buildTemplate();

    final long[] readOnly = runArm(false);
    final long[] wroteFirst = runArm(true);

    System.out.printf("### %,d vectors, one appended vector, first search after reopen%n", VECTORS);
    System.out.printf("###   read-only session : %5d ms   stalePrefixGraphReuses=%d graphNodeCount=%,d%n",
        readOnly[0], readOnly[1], readOnly[2]);
    System.out.printf("###   wrote-first session: %5d ms   stalePrefixGraphReuses=%d graphNodeCount=%,d%n",
        wroteFirst[0], wroteFirst[1], wroteFirst[2]);
    System.out.printf("###   ratio: %.1fx%n", wroteFirst[0] / Math.max(1.0, (double) readOnly[0]));

    assertThat(readOnly[1])
        .as("the read-only session reused the persisted graph as a stale prefix (issue #6655)")
        .isEqualTo(1L);
    assertThat(wroteFirst[1])
        .as("THE DEFECT: the session that inserted first never reached the prefix-reuse path, because "
            + "the insert promoted graphState to MUTABLE and ensureGraphAvailable() returned at its first line")
        .isEqualTo(0L);
    assertThat(wroteFirst[2])
        .as("instead it rebuilt the WHOLE index on the search thread, so the graph it ends up with covers "
            + "every live vector rather than the persisted prefix plus the appended one")
        .isGreaterThanOrEqualTo((long) VECTORS + 1);
    assertThat(wroteFirst[0] / Math.max(1.0, (double) readOnly[0]))
        .as("a full rebuild against a prefix reuse, for ONE appended vector: %d ms against %d ms",
            wroteFirst[0], readOnly[0])
        .isGreaterThanOrEqualTo(3.0);
  }

  /** Build the index, close, then append one vector and close again so the persisted graph is stale by one. */
  private void buildTemplate() {
    FileUtils.deleteRecursively(new File(TEMPLATE));
    try (final DatabaseFactory factory = new DatabaseFactory(TEMPLATE)) {
      final Database db = factory.create();
      final Random rng = new Random(7);
      db.transaction(() -> {
        final DocumentType t = db.getSchema().createDocumentType("Doc");
        t.createProperty("id", Type.INTEGER);
        t.createProperty("embedding", Type.ARRAY_OF_FLOATS);
        for (int i = 0; i < VECTORS; i++)
          db.newDocument("Doc").set("id", i).set("embedding", randomVector(rng)).save();
      });
      db.command("sql", "CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA "
          + "{ \"dimensions\": " + DIMENSIONS + ", \"similarity\": \"EUCLIDEAN\", "
          + "\"storeVectorsInGraph\": false, \"addHierarchy\": true }");
      awaitGraph(db);
      db.close();
    }
    // One appended vector, then close. Close defers the rebuild (issue #6067), so the persisted graph is
    // now a valid PREFIX of the live set - exactly the state issue #6655's reuse path exists for.
    try (final DatabaseFactory factory = new DatabaseFactory(TEMPLATE)) {
      final Database db = factory.open();
      final Random rng = new Random(99);
      db.transaction(() -> db.newDocument("Doc").set("id", VECTORS).set("embedding", randomVector(rng)).save());
      db.close();
    }
  }

  /**
   * @return {first search ms, stalePrefixGraphReuses, graphNodeCount}
   */
  private long[] runArm(final boolean insertBeforeSearching) {
    copyTemplate();
    try (final DatabaseFactory factory = new DatabaseFactory(ARM)) {
      final Database db = factory.open();

      if (insertBeforeSearching) {
        final Random rng = new Random(123);
        db.transaction(() -> db.newDocument("Doc").set("id", VECTORS + 1).set("embedding", randomVector(rng)).save());
      }

      final StringBuilder probe = new StringBuilder("[");
      for (int i = 0; i < DIMENSIONS; i++)
        probe.append(i == 0 ? "" : ", ").append("0.25");
      probe.append("]");

      final long t0 = System.nanoTime();
      try (final ResultSet rs = db.query("sql",
          "SELECT FROM (SELECT expand(vectorNeighbors('Doc[embedding]', " + probe + ", 10)))")) {
        while (rs.hasNext()) rs.next();
      }
      final long searchMs = (System.nanoTime() - t0) / 1_000_000L;

      final LSMVectorIndex index = lsm(db);
      final Map<String, Long> stats = index.getStats();
      final long[] out = { searchMs, stats.getOrDefault("stalePrefixGraphReuses", -1L),
                           stats.getOrDefault("graphNodeCount", -1L) };

      // Both arms owe an async rebuild by this point: the reuse arm kicks one off at the end of
      // reuseStalePrefixGraph(), and the rebuild arm has already done its work synchronously.
      // Closing while that thread is still running lands its persist on a closing database and
      // prints a SEVERE TransactionException that has nothing to do with what this test measures.
      // Upstream's own Issue6655StaleGraphPrefixReuseTest waits the same way, and a repro that
      // ships with an unexplained SEVERE in its output invites the reader to discount all of it.
      Awaitility.await("the async rebuild this session owes completes before close")
          .atMost(Duration.ofSeconds(120))
          .pollInterval(Duration.ofMillis(200))
          .untilAsserted(() -> assertThat(index.getStats().get("asyncRebuildInProgress")).isZero());

      db.close();
      return out;
    }
  }

  private void copyTemplate() {
    FileUtils.deleteRecursively(new File(ARM));
    try {
      final Path from = Path.of(TEMPLATE), to = Path.of(ARM);
      Files.createDirectories(to);
      try (final var walk = Files.walk(from)) {
        walk.sorted(Comparator.naturalOrder()).forEach(src -> {
          try {
            final Path dst = to.resolve(from.relativize(src).toString());
            if (Files.isDirectory(src))
              Files.createDirectories(dst);
            else
              Files.copy(src, dst, StandardCopyOption.REPLACE_EXISTING);
          } catch (final Exception e) {
            throw new RuntimeException(e);
          }
        });
      }
    } catch (final Exception e) {
      throw new RuntimeException("could not copy the template database", e);
    }
  }

  private static LSMVectorIndex lsm(final Database db) {
    final TypeIndex idx = (TypeIndex) db.getSchema().getIndexByName("Doc[embedding]");
    return (LSMVectorIndex) idx.getIndexesOnBuckets()[0];
  }

  private static void awaitGraph(final Database db) {
    final LSMVectorIndex index = lsm(db);
    for (int i = 0; i < 1200 && index.getStats().get("graphNodeCount") < VECTORS; i++)
      try { Thread.sleep(100); } catch (final InterruptedException ignored) { break; }
  }

  private static float[] randomVector(final Random rng) {
    final float[] v = new float[DIMENSIONS];
    for (int i = 0; i < DIMENSIONS; i++)
      v[i] = (float) rng.nextGaussian();
    return v;
  }
}
