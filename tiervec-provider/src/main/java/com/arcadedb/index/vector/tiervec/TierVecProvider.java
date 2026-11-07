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
package com.arcadedb.index.vector.tiervec;

import com.arcadedb.database.RID;
import com.arcadedb.index.IndexException;
import com.arcadedb.index.vector.PredicateRidSet;
import com.arcadedb.index.vector.VectorIndexHost;
import com.arcadedb.index.vector.VectorIndexProvider;
import com.arcadedb.query.sql.executor.WorkGuard;
import com.arcadedb.utility.Pair;
import com.humemai.vec.Hit;
import com.humemai.vec.Metric;
import com.humemai.vec.TieredIndex;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;
import java.util.Set;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.function.LongPredicate;

/**
 * SKETCH, never compiled. A {@link VectorIndexProvider} that answers the nearest-neighbour search of an {@code LSM_VECTOR} index
 * from a tiervec {@link TieredIndex} (immutable graph segments plus an exact tail) instead of the jvector graph and delta buffer.
 * <p>
 * Division of work. The host keeps everything transactional: pages, tombstones, the location map, the transaction overlay and the
 * replay journal. This class keeps only derived state, in memory (no segment file is written in this cut, so every open starts COLD
 * and rebuilds from the records).
 * <p>
 * Id model B of the contract: the key of a vector is the host's {@code vectorId} (an int) widened to the long key of tiervec. An RID
 * never reaches tiervec. The host maps a hit back to its RID with the location map, one probe per hit.
 * <p>
 * Apply protocol: deferred. The write hooks only stage operations in the transaction's replay journal; the host calls
 * {@link #publishStaged} when the transaction's changes stand, so an id of a rolled-back transaction never reaches the tier and
 * nothing has to be retracted.
 * <p>
 * Every place where the contract needs something tiervec does not have yet is marked {@code CONTRACT LATER} with the gap id of the
 * contract note's gap table.
 */
public final class TierVecProvider implements VectorIndexProvider {
  public static final String NAME = "tiervec";

  private static final long ID_MASK              = 0xFFFFFFFFL;
  private static final long BUILD_PERMIT_WAIT_MS = 600_000L; // the wait of the default async rebuild (LSMVectorIndex), not re-read

  private enum State {
    COLD, BUILDING, READY, CLOSED
  }

  /** One staged operation: an add (vector non-null) or a delete of the id. */
  private record Op(long id, float[] vector) {
  }

  /** The operations of one transaction for this index, kept in the replay journal until the host publishes. */
  private static final class Batch {
    final List<Op> ops = new ArrayList<>();
  }

  private final VectorIndexHost host;
  private final Object         lock   = new Object();
  private final List<List<Op>> queued = new ArrayList<>(); // batches published while a build runs, replayed after its swap

  private volatile TieredIndex tier;
  private volatile State       state = State.COLD;
  private volatile Future<?>   build;
  private long                 generation; // bumped by onRenumber; a build of an older generation is discarded

  public TierVecProvider(final VectorIndexHost host) {
    this.host = host;
  }

  @Override
  public String name() {
    return NAME;
  }

  @Override
  public boolean usesHostGraph() {
    return false;
  }

  @Override
  public Set<String> unsupportedFeatures() {
    // SE9 / CP1: the host is meant to refuse such an index definition at CREATE; nothing checks this set yet.
    return Set.of("grouped-search", "approximate-pq", "binary-rerank", "quantization");
  }

  // ---------------------------------------------------------------- search

  @Override
  public List<Pair<RID, Float>> search(final float[] queryVector, final int k, final int efSearch, final Set<RID> allowedRIDs,
      final WorkGuard guard) {
    if (queryVector == null)
      throw new IllegalArgumentException("Query vector cannot be null");
    if (k < 0)
      throw new IllegalArgumentException("k must be >= 0, got " + k);
    final int dim = host.dimensions();
    if (k == 0 || dim <= 0)
      return Collections.emptyList();
    if (queryVector.length != dim)
      throw new IllegalArgumentException(
          "Query vector dimension " + queryVector.length + " does not match index dimension " + dim);

    // CONTRACT LATER (SE4): tiervec polls no deadline inside the beam; the guard is checked before and after the call only.
    guard.check();
    awaitReady(guard);

    final VectorIndexHost.OverlayView overlay = host.overlay();
    final LongPredicate allow = allowPredicate(allowedRIDs, overlay);

    final TieredIndex current = tier;
    if (current == null)
      return Collections.emptyList(); // the index was closed or renumbered between awaitReady and here
    // CONTRACT LATER (SE2): no size hint and no selective plan; the predicate is applied inside the beam, so the top k of the
    // qualifying set is correct, but a very selective filter costs a long walk (the default provider switches to an exact listing).
    final Hit[] hits = efSearch > 0 ? current.search(queryVector, k, allow, efSearch) : current.search(queryVector, k, allow);
    guard.check();

    final List<Pair<RID, Float>> results = new ArrayList<>(k);
    final Metric metric = metric();
    for (final Hit hit : hits) {
      final RID rid = host.ridOf((int) hit.id());
      if (rid != null)
        results.add(new Pair<>(rid, toDistance(metric, hit.score())));
    }

    // The transaction's own uncommitted rows: scanned exactly and merged by distance. The committed rows the transaction
    // superseded were already masked by the predicate above.
    if (overlay != null && overlay.pendingCount() > 0)
      overlay.forEachPending((rid, vector) -> {
        if (vector.length == dim && passes(allowedRIDs, rid))
          results.add(new Pair<>(rid, exactDistance(metric, queryVector, vector)));
      });

    results.sort(Comparator.comparing((Pair<RID, Float> pair) -> pair.getSecond()));
    return results.size() > k ? new ArrayList<>(results.subList(0, k)) : results;
  }

  /**
   * The allowed-RID to id-predicate bridge. An id is allowed when the host still knows it as live, the calling transaction did not
   * supersede its record, and the allow-list (a plain set, or a lazy {@link PredicateRidSet} whose {@code contains} may cost a
   * record read) accepts the record. Runs on the searching thread only. An empty plain set means "no filter", as in the default
   * provider; a lazy set is always asked, because its {@code isEmpty()} says nothing about what it accepts.
   */
  private LongPredicate allowPredicate(final Set<RID> allowedRIDs, final VectorIndexHost.OverlayView overlay) {
    return id -> {
      final RID rid = host.ridOf((int) id);
      if (rid == null)
        return false;
      if (overlay != null && overlay.supersedes(rid))
        return false;
      return passes(allowedRIDs, rid);
    };
  }

  private static boolean passes(final Set<RID> allowedRIDs, final RID rid) {
    if (allowedRIDs == null)
      return true;
    if (allowedRIDs instanceof PredicateRidSet)
      return allowedRIDs.contains(rid);
    return allowedRIDs.isEmpty() || allowedRIDs.contains(rid);
  }

  private Metric metric() {
    return switch (host.similarityName()) {
      case "COSINE" -> Metric.COSINE;
      case "DOT_PRODUCT" -> Metric.DOT;
      case "EUCLIDEAN" -> Metric.L2;
      default -> throw new IndexException("Unsupported similarity for the tiervec provider: " + host.similarityName());
    };
  }

  /**
   * Converts a tiervec score (higher is better) to the distance the host reports (lower is better). COSINE and EUCLIDEAN follow
   * from the engine's own conversion (2 * (1 - s) with s = (1 + cos) / 2, and 1 / s - 1 with s = 1 / (1 + d^2)), derived here and
   * not yet verified by a parity test. CONTRACT LATER (SE6): DOT is a guess, the jvector dot similarity was not read.
   */
  private static float toDistance(final Metric metric, final float score) {
    return switch (metric) {
      case COSINE -> 1f - score;
      case L2 -> -score;
      case DOT -> -score;
    };
  }

  /**
   * Exact distance of one pending row. CONTRACT LATER (SE6): tiervec has no public scorer, so this is a local scalar twin; it must
   * agree with the kernels of the segments or pending rows and committed rows rank on slightly different scales.
   */
  private static float exactDistance(final Metric metric, final float[] q, final float[] v) {
    double dot = 0, nq = 0, nv = 0, l2 = 0;
    for (int i = 0; i < q.length; i++) {
      dot += (double) q[i] * v[i];
      nq += (double) q[i] * q[i];
      nv += (double) v[i] * v[i];
      final double d = (double) q[i] - v[i];
      l2 += d * d;
    }
    return switch (metric) {
      case COSINE -> (float) (1.0 - dot / Math.max(Math.sqrt(nq * nv), 1e-30));
      case L2 -> (float) l2;
      case DOT -> (float) -dot;
    };
  }

  // ---------------------------------------------------------------- readiness and rebuild from the records

  @Override
  public boolean isReady() {
    return state == State.READY;
  }

  @Override
  public void awaitReady(final WorkGuard guard) {
    if (state == State.READY || host.dimensions() <= 0)
      return; // nothing written yet: there is nothing to build
    final Future<?> running = startBuildIfCold();
    if (running == null)
      return;
    while (true) {
      try {
        running.get(50, TimeUnit.MILLISECONDS);
        return;
      } catch (final TimeoutException e) {
        guard.check(); // a terminated or expired statement stops waiting; the build goes on
      } catch (final ExecutionException e) {
        throw new IndexException("The tiervec build of index '" + host.indexName() + "' failed", e.getCause());
      } catch (final InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new IndexException("Interrupted while waiting for the tiervec build of index '" + host.indexName() + "'", e);
      }
    }
  }

  private Future<?> startBuildIfCold() {
    synchronized (lock) {
      if (state == State.CLOSED)
        throw new IndexException("The tiervec provider of index '" + host.indexName() + "' is closed");
      if (state == State.READY)
        return null;
      if (state == State.COLD) {
        state = State.BUILDING;
        final long startedGeneration = generation;
        build = host.executor().submit(() -> runBuild(startedGeneration));
      }
      return build;
    }
  }

  /**
   * The rebuild-from-records path, also the only way this cut ever gets state (no persistence, so COLD at every open). Builds a
   * FRESH tier from a snapshot of the live records, so searches and writers never wait on the build (the live-tier
   * {@code rebuildFrom} holds the writer lock for the whole build, contract gap LC3), then swaps it in and replays the batches
   * published meanwhile. Adds are idempotent replaces and deletes of absent ids are no-ops, so a batch that the snapshot already
   * contains does no harm.
   */
  private void runBuild(final long startedGeneration) {
    final int dim = host.dimensions();
    // ESTIMATE, not measured: fp32 row plus about 126 B of graph per vector (segment format note 3.6), doubled for the build peak.
    final long estimate = (long) host.liveCount() * (dim * 4L + 160L) * 2L;
    VectorIndexHost.Permit permit = null;
    try {
      permit = host.tryAcquireBuild(BUILD_PERMIT_WAIT_MS, estimate);
      if (permit == null)
        throw new IllegalStateException("tiervec build refused by the host: rebuild permit, heap gate or budget (estimate "
            + estimate + " bytes)");

      // CONTRACT LATER (RS1): TieredIndex starts its own worker thread and, for a build, its own build threads (TI:345, TI:845);
      // the contract wants every task on host.executor().
      final TieredIndex fresh = new TieredIndex(dim, metric(), TieredIndex.Config.defaults());
      final Iterable<VectorIndexHost.LiveVector> live = host.scanLive();
      fresh.rebuildFrom(() -> new Iterator<>() {
        private final Iterator<VectorIndexHost.LiveVector> it = live.iterator();

        @Override
        public boolean hasNext() {
          return it.hasNext();
        }

        @Override
        public TieredIndex.IdVector next() {
          if (!hasNext())
            throw new NoSuchElementException();
          final VectorIndexHost.LiveVector row = it.next();
          return new TieredIndex.IdVector(row.id() & ID_MASK, row.vector());
        }
      });

      final TieredIndex old;
      synchronized (lock) {
        if (state != State.BUILDING || generation != startedGeneration) {
          fresh.close(); // renumbered or closed while building: the snapshot speaks a dead id space
          return;
        }
        old = tier;
        tier = fresh;
        for (final List<Op> batch : queued)
          applyTo(fresh, batch);
        queued.clear();
        state = State.READY;
      }
      closeQuietly(old);
    } catch (final RuntimeException | Error e) {
      synchronized (lock) {
        if (state == State.BUILDING)
          state = State.COLD; // the next search tries again
        queued.clear();
      }
      throw e;
    } finally {
      if (permit != null)
        permit.close();
    }
  }

  // ---------------------------------------------------------------- writes: staged by the hooks, applied at publish

  @Override
  public void onVectorAdded(final int vectorId, final RID rid, final float[] vector, final ReplayJournal journal) {
    stage(journal, new Op(vectorId & ID_MASK, vector.clone()));
  }

  @Override
  public void onVectorsRemoved(final List<Integer> vectorIds, final RID rid, final ReplayJournal journal) {
    for (final int vectorId : vectorIds)
      stage(journal, new Op(vectorId & ID_MASK, null));
  }

  private void stage(final ReplayJournal journal, final Op op) {
    if (journal == null) {
      // No transaction that could still abort: nothing to defer. CONTRACT LATER (MU6): TieredIndex.add may park the calling
      // thread up to 10 s under back pressure, and this thread holds the index write lock.
      apply(List.of(op));
      return;
    }
    journal.stagedBatch(Batch::new).ops.add(op);
  }

  @Override
  public void publishStaged(final Object stagedBatch) {
    apply(((Batch) stagedBatch).ops);
  }

  /** The one entry point that mutates the tier: idempotent, adds before deletes so an update never shows neither id. */
  private void apply(final List<Op> ops) {
    final TieredIndex current;
    synchronized (lock) {
      switch (state) {
      case CLOSED, COLD -> {
        // COLD: assumption A1, not verified, that the build which will run later reads this batch from the pages, because the
        // host wrote them at replay and publishes only after the commit's pages are visible. CLOSED: nothing to do.
        return;
      }
      case BUILDING -> {
        queued.add(ops);
        return;
      }
      default -> current = tier;
      }
    }
    applyTo(current, ops);
  }

  private static void applyTo(final TieredIndex target, final List<Op> ops) {
    // CONTRACT LATER (MU1): one atomic apply(batch). Sequential here, so a concurrent search between two calls can see the new id
    // beside a not yet deleted old one; the host's location map already hides the old id (tombstoned at replay), so the window
    // shows at worst a record twice, which the SQL layer de-duplicates.
    for (final Op op : ops)
      if (op.vector() != null)
        target.add(op.id(), op.vector());
    for (final Op op : ops)
      if (op.vector() == null)
        target.delete(op.id());
  }

  // ---------------------------------------------------------------- lifecycle

  @Override
  public void onRenumber() {
    // LC9: a renumbering compaction reissued every id, so everything derived is in a dead id space. Drop it; the next search
    // rebuilds from the records. Called under the index write lock. CONTRACT LATER (ID2): with a persisted epoch a crash between
    // the compaction and this call would also be detected at open; here nothing persists, so there is nothing stale to detect.
    final TieredIndex old;
    synchronized (lock) {
      if (state == State.CLOSED)
        return;
      generation++;
      old = tier;
      tier = null;
      queued.clear();
      state = State.COLD;
    }
    closeQuietly(old);
  }

  @Override
  public void flush() {
    // CONTRACT LATER (LC1, LC4): no persistence yet, so nothing to write; a reopen is COLD.
  }

  @Override
  public void suspendMaintenance() {
    // CONTRACT LATER (LC7): TieredIndex has no hold-off for seals and merges during a bulk load.
  }

  @Override
  public void resumeMaintenance() {
  }

  @Override
  public List<String> verify() {
    // CONTRACT LATER (LC8): no verify() on TieredIndex and no files to check.
    return List.of();
  }

  @Override
  public void addStats(final Map<String, Long> stats) {
    stats.put("tiervec.state", (long) state.ordinal());
    final TieredIndex current = tier;
    if (current != null) {
      final TieredIndex.Stats s = current.stats();
      stats.put("tiervec.segments", (long) s.segments());
      stats.put("tiervec.tailSize", (long) s.tailSize());
      stats.put("tiervec.bytesHeld", s.bytesHeld());
      stats.put("tiervec.seals", s.seals());
      stats.put("tiervec.merges", s.merges());
    }
  }

  @Override
  public void close() {
    final TieredIndex old;
    final Future<?> running;
    synchronized (lock) {
      state = State.CLOSED;
      old = tier;
      tier = null;
      running = build;
      queued.clear();
    }
    if (running != null)
      running.cancel(true);
    closeQuietly(old); // CONTRACT LATER (LC5): searches in flight get no ClosedException, they finish on the old view
  }

  @Override
  public void drop() {
    // No file is written in this cut, so dropping is closing. CONTRACT LATER (LC6): remove the segment directory.
    close();
  }

  private static void closeQuietly(final TieredIndex index) {
    if (index == null)
      return;
    try {
      index.close();
    } catch (final RuntimeException ignored) {
      // a failed close of derived state must not fail the host's close or compaction
    }
  }
}
