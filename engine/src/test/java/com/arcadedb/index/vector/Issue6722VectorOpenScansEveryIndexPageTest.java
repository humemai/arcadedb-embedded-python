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

import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.index.TypeIndex;
import com.arcadedb.schema.DocumentType;
import com.arcadedb.schema.Type;
import com.arcadedb.utility.FileUtils;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Random;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Issue #6722. Opening a database walks every page of every LSM_VECTOR index, whether or not the
 * session will ever search.
 * <p>
 * Reproduced on upstream main e215d61c1.
 * <p>
 * {@code loadVectorsAfterSchemaLoad()} runs on schema load and calls
 * {@code loadVectorsFromPages()} (:1091), which parses every page of the mutable file and of the
 * compacted sub-index and calls {@code vectorIndex.addOrUpdate(...)} once per entry
 * ({@code loadVectorsFromFile}, :3455). The result is an in-memory {@code VectorLocationIndex}
 * with one entry per vector, rebuilt from scratch on every open.
 * <p>
 * The graph, by contrast, is already deferred, and the code says so at the call site:
 * <pre>
 *   loadVectorsFromPages();
 *   // Graph will be lazy-loaded on first search via ensureGraphAvailable()
 * </pre>
 * so after a reopen the index reports {@code graphState=LOADING(0)} and
 * {@code graphNodeCount=0} while {@code totalVectors} is already the full corpus. This test
 * asserts exactly that pair, which is what makes the cost attributable: the expensive structure
 * is lazy and the O(N) one is not.
 * <p>
 * WHAT IT COSTS. Measured through the embedded API on an i9-12900HK, one open of a quiesced
 * database, no query issued, median of a 5-cycle run at 64 dimensions:
 * <pre>
 *   vectors      open (warm)   open (page cache evicted)   what the cache buys
 *      10,000        2.9 ms                     5.7 ms                    49%
 *     100,000       10.2 ms                    11.6 ms                    12%
 *   1,000,000       90.3 ms                    93.4 ms                     3%
 *  10,000,000    1,378.8 ms                 1,495.3 ms                     8%
 * </pre>
 * Every other workload measured the same way (plain documents, a graph, a Graph Analytical View)
 * opens in 1.1-1.9 ms at every one of those sizes and gets 40-55% from the page cache. The vector
 * index gets 3-8%, because the cost is not the read: it is parsing every entry and populating a
 * map, redone per open. A 10M-vector database therefore costs ~1.4 s to open before the caller
 * does anything, and a process that opens it to write one document pays in full.
 * <p>
 * This test uses two sizes and asserts the RATIO rather than a wall-clock bound, so it cannot go
 * red on a slow or loaded machine: 4x the vectors must not cost ~1x the open.
 */
@Tag("vector")
class Issue6722VectorOpenScansEveryIndexPageTest {
  private static final int    DIMENSIONS = 64;
  /**
   * BASE exists to be subtracted. Opening a database costs ~25 ms here before a single vector is
   * considered, and at unit-test sizes that fixed cost swamps the per-vector term: a first draft of
   * this test compared 25k against 100k, saw 27 ms against 36 ms, and read 1.3x as "not
   * proportional". It is proportional -- in the MARGIN. Measuring a near-empty index of the same
   * shape and subtracting it is what exposes the slope.
   */
  private static final int    BASE       = 2_000;
  private static final int    SMALL      = 50_000;
  private static final int    LARGE      = 200_000;   // 4x SMALL
  private static final int    REOPENS    = 3;
  private static final String DB_PATH    = "./target/databases/Issue6722VectorOpenScansEveryIndexPageTest";

  @AfterEach
  void cleanUp() {
    FileUtils.deleteRecursively(new File(DB_PATH));
  }

  @Test
  void openingWithoutSearchingStillMaterialisesEveryVectorLocation() {
    final long baseMs  = medianReopenMs(BASE);
    final long smallMs = medianReopenMs(SMALL);
    final long largeMs = medianReopenMs(LARGE);

    final double smallMarginal = Math.max(0.0, smallMs - baseMs);
    final double largeMarginal = Math.max(0.0, largeMs - baseMs);
    final double ratio = largeMarginal / Math.max(1.0, smallMarginal);

    System.out.printf("open, no query issued (median of %d reopens each)%n", REOPENS);
    System.out.printf("  %,10d vectors -> %4d ms   (baseline, subtracted below)%n", BASE, baseMs);
    System.out.printf("  %,10d vectors -> %4d ms   marginal %5.0f ms   %.3f us/vector%n",
        SMALL, smallMs, smallMarginal, smallMarginal * 1000.0 / (SMALL - BASE));
    System.out.printf("  %,10d vectors -> %4d ms   marginal %5.0f ms   %.3f us/vector%n",
        LARGE, largeMs, largeMarginal, largeMarginal * 1000.0 / (LARGE - BASE));
    System.out.printf("  marginal ratio %.1fx for 4x the vectors%n", ratio);

    // The assertion is on the MARGIN and on a ratio, so neither a slow machine nor a fast one can
    // change the verdict: a constant-time open would show ~1x. 2.5 leaves headroom under the ~4x
    // a linear scan produces.
    assertThat(ratio)
        .as("THE DEFECT: the open's cost above baseline is proportional to the number of indexed "
            + "vectors, for a session that issues no query. 4x the vectors cost %.0f ms of "
            + "marginal open against %.0f ms", largeMarginal, smallMarginal)
        .isGreaterThanOrEqualTo(2.5);
  }

  /**
   * Build once, then reopen REOPENS times and return the median open. Every reopen after the first
   * runs against a fully warm page cache, so a cost that amortised would fall away here; it does not.
   */
  private long medianReopenMs(final int numVectors) {
    FileUtils.deleteRecursively(new File(DB_PATH));

    try (final DatabaseFactory factory = new DatabaseFactory(DB_PATH)) {
      final Database db = factory.create();
      final Random rng = new Random(11);
      db.transaction(() -> {
        final DocumentType docType = db.getSchema().createDocumentType("Doc");
        docType.createProperty("id", Type.INTEGER);
        docType.createProperty("embedding", Type.ARRAY_OF_FLOATS);
        for (int i = 0; i < numVectors; i++)
          db.newDocument("Doc").set("id", i).set("embedding", randomVector(rng)).save();
      });
      db.command("sql", "CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA "
          + "{ \"dimensions\": " + DIMENSIONS + ", \"similarity\": \"EUCLIDEAN\", "
          + "\"storeVectorsInGraph\": false, \"addHierarchy\": true }");
      db.close();
    }

    final List<Long> opens = new ArrayList<>(REOPENS);
    for (int cycle = 0; cycle < REOPENS; cycle++) {
      try (final DatabaseFactory factory = new DatabaseFactory(DB_PATH)) {
        final long t0 = System.nanoTime();
        final Database db = factory.open();
        opens.add((System.nanoTime() - t0) / 1_000_000L);

        // NOT A QUERY. Reading the stats is what tells us where the open's work went.
        final TypeIndex idx = (TypeIndex) db.getSchema().getIndexByName("Doc[embedding]");
        final Map<String, Long> stats = ((LSMVectorIndex) idx.getIndexesOnBuckets()[0]).getStats();

        assertThat(stats.get("totalVectors"))
            .as("open materialised one location entry per vector without being asked to")
            .isEqualTo((long) numVectors);
        assertThat(stats.get("graphState"))
            .as("the graph is still LOADING(0): the expensive structure IS deferred, which is "
                + "what makes the eager location scan a choice rather than a necessity")
            .isEqualTo(0L);
        assertThat(stats.get("graphNodeCount"))
            .as("no graph node has been touched, so the open's cost is the location index alone")
            .isEqualTo(0L);

        db.close();
      }
    }
    opens.sort(Long::compare);
    return opens.get(opens.size() / 2);
  }

  private static float[] randomVector(final Random rng) {
    final float[] v = new float[DIMENSIONS];
    for (int i = 0; i < DIMENSIONS; i++)
      v[i] = (float) rng.nextGaussian();
    return v;
  }
}
