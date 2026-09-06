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
import com.arcadedb.log.LogManager;
import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.Type;
import com.arcadedb.utility.FileUtils;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.logging.Level;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * A vector the graph build could not link ("orphan") is served from the delta scan in the session that built it.
 * That delta set is not persisted with the graph, so after close() and reopen the orphans are gone from every
 * search while the index still reports every vector present. Measured 2026-08-20 at 50k / M=32: 0 of 331 orphans
 * missed their own self-query before close, 331 of 331 after reopen. This test re-measures it on the current engine.
 * <p>
 * The engine's own build warning ("Graph build left N of M vectors unreachable ... serving them from the delta
 * scan. A later rebuild does not repair this") is captured so the test cannot pass because no orphan was produced.
 */
@Tag("vector")
class Issue7190OrphanVectorsSurviveRestartTest {
  private static final String DB_ROOT    = "target/test-databases/Issue7190OrphanVectorsSurviveRestartTest";
  private static final int    DIMENSIONS = 32;
  private static final int    COUNT      = Integer.getInteger("orphans.count", 50_000);
  private static final int    M          = 32;
  private static final int    K          = 10;
  private static final Pattern UNREACHABLE = Pattern.compile("left (\\d+) of (\\d+) vectors unreachable");

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
  void orphansFoundBeforeCloseAreStillFoundAfterReopen() {
    final List<String> warnings = new ArrayList<>();
    final com.arcadedb.log.Logger original = LogManager.instance().getLogger();
    final com.arcadedb.log.Logger capture = new com.arcadedb.log.Logger() {
      private void keep(final String msg, final Object... args) {
        if (msg != null && msg.contains("unreachable"))
          synchronized (warnings) {
            try {
              warnings.add(String.format(msg, args));
            } catch (final Exception e) {
              warnings.add(msg);
            }
          }
      }

      @Override
      public void log(final Object r, final Level l, final String m, final Throwable t, final String c, final Object a1, final Object a2,
          final Object a3, final Object a4, final Object a5, final Object a6, final Object a7, final Object a8, final Object a9,
          final Object a10, final Object a11, final Object a12, final Object a13, final Object a14, final Object a15, final Object a16,
          final Object a17) {
        keep(m, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15, a16, a17);
        original.log(r, l, m, t, c, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12, a13, a14, a15, a16, a17);
      }

      @Override
      public void log(final Object r, final Level l, final String m, final Throwable t, final String c, final Object... args) {
        keep(m, args);
        original.log(r, l, m, t, c, args);
      }

      @Override
      public void flush() {
        original.flush();
      }
    };
    LogManager.instance().setLogger(capture);

    final List<Integer> missesBefore;
    final List<Integer> hardBefore;
    final long reportedOrphans;
    try {
      try (final DatabaseFactory factory = new DatabaseFactory(dbPath)) {
        final Database db = factory.create();
        try {
          insert(db, COUNT);
          final LSMVectorIndex index = vectorIndex(db);
          index.buildVectorGraphNow();
          System.out.println("ORPHANS stats after build: " + index.getStats());
          missesBefore = selfQueryMisses(db, -1);
          hardBefore = stillMissing(db, missesBefore, 2000);
          reportedOrphans = orphansFromWarnings(warnings);
          System.out.println("ORPHANS count=" + COUNT + " M=" + M + " reportedByBuild=" + reportedOrphans
              + " selfQueryMissesBeforeClose=" + missesBefore.size() + " stillMissingAtEf2000=" + hardBefore.size()
              + " warningsCaptured=" + warnings.size() + " sample=" + missesBefore.subList(0, Math.min(8, missesBefore.size())));
        } finally {
          if (db.isOpen())
            db.close();
        }
      }

      try (final DatabaseFactory factory = new DatabaseFactory(dbPath)) {
        final Database db = factory.open();
        try {
          final List<Integer> missesAfter = selfQueryMisses(db, -1);
          final List<Integer> hardAfter = stillMissing(db, missesAfter, 2000);
          final LSMVectorIndex index = vectorIndex(db);
          System.out.println("ORPHANS selfQueryMissesAfterReopen=" + missesAfter.size() + " stillMissingAtEf2000=" + hardAfter.size()
              + " sample=" + missesAfter.subList(0, Math.min(8, missesAfter.size()))
              + " stats=" + index.getStats());
          assertThat(index.getStats().get("totalVectors"))
              .as("the index still reports every vector after reopen")
              .isEqualTo((long) COUNT);
          // The defect. The build reported `reportedOrphans` unreachable vectors and served them from the delta
          // scan; that set did not survive the restart, so exactly those vectors no longer find themselves, while
          // the stats above say nothing is missing. k results still come back, so a caller cannot tell.
          // Self-misses at the default beam are recall (all of them are found at efSearch=2000 before AND after
          // close), so they are not this test's subject. The subject is what a WIDE beam still cannot find after
          // the restart: exactly the vectors the build reported unreachable and served from the delta scan, which
          // was not persisted with the graph.
          assertThat(hardBefore)
              .as("before close every vector is found at efSearch=2000; the delta scan serves the unreachable ones")
              .isEmpty();
          assertThat(hardAfter)
              .as("after reopen the %d vector(s) the build left unreachable must still be findable (delta set persisted, "
                  + "or re-linked); today they are gone from every search while totalVectors still counts them", reportedOrphans)
              .isEmpty();
          // Vacuity guard LAST, so the numbers above are always measured and printed first.
          assertThat(reportedOrphans)
              .as("precondition: the build must have left at least one vector unreachable, or the test proves "
                  + "nothing. Raise -Dorphans.count or lower M if the current engine links everything at this size")
              .isPositive();
        } finally {
          if (db.isOpen())
            db.close();
        }
      }
    } finally {
      LogManager.instance().setLogger(original);
    }
  }

  /** Ids that do not appear in their own top-K at the given efSearch (-1 = the index default). */
  private static List<Integer> selfQueryMisses(final Database db, final int ef) {
    final List<Integer> ids = new ArrayList<>(COUNT);
    for (int id = 0; id < COUNT; id++)
      ids.add(id);
    return stillMissing(db, ids, ef);
  }

  private static List<Integer> stillMissing(final Database db, final List<Integer> ids, final int ef) {
    final List<Integer> misses = new ArrayList<>();
    for (final int id : ids) {
      final float[] v = embedding(id);
      final StringBuilder q = new StringBuilder();
      for (int d = 0; d < DIMENSIONS; d++)
        q.append(d == 0 ? "" : ",").append(v[d]);
      boolean found = false;
      final String efArg = ef > 0 ? ", " + ef : "";
      try (final ResultSet rs = db.query("sql",
          "SELECT id FROM (SELECT expand(vectorNeighbors('Doc[vector]', [" + q + "], " + K + efArg + ")))")) {
        while (rs.hasNext()) {
          final Result r = rs.next();
          if (r.<Integer>getProperty("id") == id) {
            found = true;
            break;
          }
        }
      }
      if (!found)
        misses.add(id);
    }
    return misses;
  }

  private static long orphansFromWarnings(final List<String> warnings) {
    long n = 0;
    synchronized (warnings) {
      for (final String w : warnings) {
        final Matcher m = UNREACHABLE.matcher(w);
        if (m.find())
          n += Long.parseLong(m.group(1));
      }
    }
    return n;
  }

  private static void insert(final Database db, final int count) {
    db.transaction(() -> {
      final var type = db.getSchema().createDocumentType("Doc");
      type.createProperty("id", Type.INTEGER);
      type.createProperty("vector", Type.ARRAY_OF_FLOATS);
      db.command("sql", "CREATE INDEX ON Doc (vector) LSM_VECTOR METADATA { \"dimensions\": " + DIMENSIONS
          + ", \"similarity\": \"EUCLIDEAN\", \"maxConnections\": " + M + " }");
    });
    db.begin();
    for (int i = 0; i < count; i++) {
      db.newDocument("Doc").set("id", i).set("vector", embedding(i)).save();
      if (i % 1000 == 999) {
        db.commit();
        db.begin();
      }
    }
    db.commit();
  }

  private static float[] embedding(final int id) {
    final Random random = new Random(0x0F0A1L * 31 + id);
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
