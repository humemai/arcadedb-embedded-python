/*
 * Copyright © 2021-present Arcade Data Ltd (info@arcadedata.com)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * SPDX-FileCopyrightText: 2021-present Arcade Data Ltd (info@arcadedata.com)
 * SPDX-License-Identifier: Apache-2.0
 */
package com.arcadedb.index.vector;

import com.arcadedb.GlobalConfiguration;
import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.Type;
import com.arcadedb.utility.FileUtils;
import org.awaitility.Awaitility;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;

import java.io.File;
import java.time.Duration;
import java.util.Random;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The first search after a mutation below the rebuild threshold must not start a full async rebuild.
 * <p>
 * Scenario: a persisted graph over N vectors; a session inserts ONE vector and closes without searching; the next
 * session searches once. {@code ensureGraphAvailable()} correctly reuses the persisted graph as a stale prefix and
 * queues the one vector into the delta buffer, then {@code reuseStalePrefixGraph()} unconditionally calls
 * {@code startAsyncGraphRebuild()}, which logs "accumulated 1 mutations, threshold: N" and rebuilds the whole graph
 * anyway. {@code close()} then waits up to 5 s for that thread. So a process that opens, searches once and exits pays
 * a full rebuild plus a five-second close for one queued vector, and the next process repeats it, because the
 * rebuild was cancelled before it could persist. The inactivity timer learned to respect the threshold in #6857;
 * this path did not.
 */
@Tag("vector")
class Issue7183StalePrefixReuseOneMutationRebuildTest {
  private static final String DB_ROOT    = "target/test-databases/Issue7183StalePrefixReuseOneMutationRebuildTest";
  private static final int    DIMENSIONS = 32;
  private static final int    COUNT      = 1_500;
  private static final int    THRESHOLD  = 100;
  private static final Duration REBUILD_SETTLE_TIMEOUT =
      Duration.ofMillis(GlobalConfiguration.VECTOR_INDEX_REBUILD_PERMIT_TIMEOUT_MS.getValueAsLong() + 60_000L);

  private String dbPath;

  @BeforeEach
  void setUp(final TestInfo testInfo) {
    dbPath = DB_ROOT + "-" + testInfo.getTestMethod().orElseThrow().getName();
    FileUtils.deleteRecursively(new File(dbPath));
  }

  @AfterEach
  void tearDown() {
    FileUtils.deleteRecursively(new File(dbPath));
  }

  @Test
  void firstSearchAfterOneInsertMustNotRebuildTheWholeGraph() {
    buildAndPersistFixture();
    insertWithoutSearching(1);

    try (final DatabaseFactory factory = new DatabaseFactory(dbPath)) {
      final Database db = factory.open();
      configure(db);
      try {
        search(db);

        final LSMVectorIndex index = vectorIndex(db);
        assertThat(index.getStats().get("stalePrefixGraphReuses"))
            .as("precondition: the search reused the persisted graph as a stale prefix")
            .isEqualTo(1L);
        assertThat(index.getStats().get("mutationsSinceRebuild"))
            .as("precondition: exactly one mutation is pending, well under the threshold of " + THRESHOLD)
            .isEqualTo(1L);

        // The defect. One queued vector is served from the delta scan; nothing about it justifies rebuilding all
        // COUNT nodes, and the mutation threshold says so. Today this reads 1 and the log says
        // "Starting async graph rebuild (accumulated 1 mutations, threshold: 100)".
        assertThat(index.getStats().get("asyncRebuildInProgress"))
            .as("one mutation below the threshold must not start an async rebuild on the first search")
            .isZero();
        assertThat(index.getStats().get("graphRebuildCount"))
            .as("and must not have completed one either")
            .isZero();

        // The consequence a user sees: close() joins the rebuild thread for up to 5 s. Generous bound; the point is
        // "not five seconds", not a latency target.
        final long t0 = System.nanoTime();
        db.close();
        final long closeMs = (System.nanoTime() - t0) / 1_000_000L;
        assertThat(closeMs)
            .as("close() must not wait on a rebuild that had no reason to start")
            .isLessThan(2_000L);
      } finally {
        if (db.isOpen())
          db.close();
      }
    }
  }

  /**
   * Positive control: with pending mutations AT the threshold the first search is entitled to rebuild, and does.
   * Without this the assertions above would hold just as well on a build where the async path never ran at all.
   */
  @Test
  void firstSearchAtTheThresholdStillRebuilds() {
    buildAndPersistFixture();
    insertWithoutSearching(THRESHOLD);

    try (final DatabaseFactory factory = new DatabaseFactory(dbPath)) {
      final Database db = factory.open();
      configure(db);
      try {
        search(db);
        final LSMVectorIndex index = vectorIndex(db);
        Awaitility.await("a search with the threshold reached rebuilds the graph")
            .atMost(REBUILD_SETTLE_TIMEOUT)
            .untilAsserted(() -> assertThat(index.getStats().get("graphRebuildCount")).isPositive());
        Awaitility.await("the rebuild settles before the close")
            .atMost(REBUILD_SETTLE_TIMEOUT)
            .untilAsserted(() -> assertThat(index.getStats().get("asyncRebuildInProgress")).isZero());
      } finally {
        if (db.isOpen())
          db.close();
      }
    }
  }

  private void buildAndPersistFixture() {
    try (final DatabaseFactory factory = new DatabaseFactory(dbPath)) {
      final Database db = factory.create();
      configure(db);
      try {
        insert(db, 0, COUNT);
        final LSMVectorIndex index = vectorIndex(db);
        index.buildVectorGraphNow();
        assertThat(index.getStats().get("graphState"))
            .as("precondition: the graph must be built and IMMUTABLE before the close that persists it")
            .isEqualTo(1L); // GraphState.IMMUTABLE
      } finally {
        if (db.isOpen())
          db.close();
      }
    }
  }

  /** A session that writes and leaves: the shape of a batch job, or of a client that inserts and exits. */
  private void insertWithoutSearching(final int howMany) {
    try (final DatabaseFactory factory = new DatabaseFactory(dbPath)) {
      final Database db = factory.open();
      configure(db);
      try {
        insert(db, COUNT, COUNT + howMany);
      } finally {
        if (db.isOpen())
          db.close();
      }
    }
  }

  private static void search(final Database db) {
    final StringBuilder q = new StringBuilder();
    for (int d = 0; d < DIMENSIONS; d++)
      q.append(d == 0 ? "" : ", ").append("0.5");
    try (final ResultSet rs = db.query("sql",
        "SELECT expand(vectorNeighbors('Doc[vector]', [" + q + "], 5))")) {
      assertThat(rs.hasNext()).as("the search returns neighbours").isTrue();
      while (rs.hasNext())
        rs.next();
    }
  }

  private static void configure(final Database db) {
    db.getConfiguration().setValue(GlobalConfiguration.VECTOR_INDEX_MUTATIONS_BEFORE_REBUILD, THRESHOLD);
    db.getConfiguration().setValue(GlobalConfiguration.VECTOR_INDEX_REBUILD_GRAPH_RATIO, 0f);
    // Keep the inactivity timer out of the picture: this test is about the search path.
    db.getConfiguration().setValue(GlobalConfiguration.VECTOR_INDEX_INACTIVITY_REBUILD_TIMEOUT_MS, 600_000);
  }

  private static void insert(final Database db, final int fromInclusive, final int toExclusive) {
    db.transaction(() -> {
      if (db.getSchema().existsType("Doc"))
        return;
      final var type = db.getSchema().createDocumentType("Doc");
      type.createProperty("id", Type.INTEGER);
      type.createProperty("vector", Type.ARRAY_OF_FLOATS);
      db.command("sql", "CREATE INDEX ON Doc (vector) LSM_VECTOR METADATA { \"dimensions\": " + DIMENSIONS
          + ", \"similarity\": \"EUCLIDEAN\" }");
    });
    db.begin();
    for (int i = fromInclusive; i < toExclusive; i++) {
      db.newDocument("Doc").set("id", i).set("vector", embedding(i)).save();
      if ((i - fromInclusive) % 500 == 499) {
        db.commit();
        db.begin();
      }
    }
    db.commit();
  }

  private static float[] embedding(final int id) {
    final Random random = new Random(0x7150L * 31 + id);
    final float[] vector = new float[DIMENSIONS];
    for (int d = 0; d < DIMENSIONS; d++)
      vector[d] = random.nextFloat();
    return vector;
  }

  private static LSMVectorIndex vectorIndex(final Database db) {
    return (LSMVectorIndex) db.getSchema().getType("Doc")
        .getPolymorphicIndexByProperties("vector").getIndexesOnBuckets()[0];
  }
}
