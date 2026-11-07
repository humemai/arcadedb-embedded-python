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

import com.arcadedb.database.RID;
import com.arcadedb.query.sql.executor.WorkGuard;
import com.arcadedb.utility.Pair;

import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The part of an {@link LSMVectorIndex} that decides HOW the nearest neighbours of a query are found and what is kept in memory
 * for that: the jvector graph plus the delta buffer today ({@link JVectorProvider}, the default), another structure behind the
 * same index tomorrow. Everything that makes a write durable and transactional stays in {@code LSMVectorIndex}: the index
 * pages, the tombstones, the location map, the transaction overlay, the replay journal, backup and replication.
 * <p>
 * <b>Public, not package-private</b>, because a second provider lives in another artifact and has to implement it. It is an
 * INTERNAL interface: no stability promise until a second provider exists.
 * <p>
 * Each operation is tagged. REQUIRED NOW: the default provider needs it for the extraction, and it has a call site in
 * {@code LSMVectorIndex}. CONTRACT LATER operations are added as {@code default} methods by the provider that needs them, so
 * adding one never breaks an implementation.
 * <p>
 * Ids: {@code vectorId} is the index's own dense id (never reused inside an id epoch, see LSMVectorIndex#allocateVectorId),
 * not an RID.
 */
public interface VectorIndexProvider {

  /** Name of the provider every index has unless its metadata says otherwise. */
  String DEFAULT_NAME = "jvector";

  /** The per-transaction replay journal the host hands to the write hooks; null when no transaction could still abort. */
  interface ReplayJournal {
    /** CONTRACT LATER (MU5): the provider's own state for this transaction, created on first use and handed to publishStaged. */
    <T> T stagedBatch(java.util.function.Supplier<T> factory);
  }

  /** REQUIRED NOW: the key the {@code provider} metadata entry is matched against. */
  String name();

  /**
   * REQUIRED NOW: the one search door, the body of the former {@code LSMVectorIndex#searchNeighbors}. Same contract: at most
   * {@code k} pairs of (record id, distance), lower distance is better, {@code efSearch} negative means the index default,
   * {@code allowedRIDs} may be a lazy {@link PredicateRidSet}, {@code guard} carries the statement deadline. The calling
   * transaction's own uncommitted rows are the provider's business too: the default consults the host's overlay.
   */
  List<Pair<RID, Float>> search(float[] queryVector, int k, int efSearch, Set<RID> allowedRIDs, WorkGuard guard);

  /**
   * REQUIRED NOW: make the provider ready to answer a search without waiting on first use (the former
   * {@code ensureGraphAvailable} call of {@code warmUp()}). Safe from any thread, honours {@code guard}.
   */
  void awaitReady(WorkGuard guard);

  /** REQUIRED NOW: whether {@link #awaitReady} would return at once (the former {@code isWarm()} test). */
  boolean isReady();

  /**
   * REQUIRED NOW: a vector was committed (replay of an ADD, or a non-transactional put). Called under the index write lock,
   * after the vector and its location are on the pages, with the replay journal of the open transaction or null when there is
   * none. The default provider appends it to the delta buffer and flips the graph to MUTABLE, exactly as {@code put()} did.
   */
  void onVectorAdded(int vectorId, RID rid, float[] vector, ReplayJournal journal);

  /**
   * REQUIRED NOW: every live vector of {@code rid} was just tombstoned (replay of a REMOVE), under the index write lock, after
   * the tombstones are on the pages. {@code vectorIds} is never empty. The default provider sweeps the delta buffer and flips the
   * graph to MUTABLE, exactly as {@code remove()} did.
   */
  void onVectorsRemoved(List<Integer> vectorIds, RID rid, ReplayJournal journal);

  // ---- CONTRACT LATER: default methods. The provider that needs one overrides it; the default provider is unaffected.

  /**
   * CONTRACT LATER (RS): whether the host builds, loads, persists and rebuilds its jvector graph for this index. False means the
   * provider owns all of that, and the host keeps its graph machinery (inactivity timer, async rebuild, graph build at flush) off.
   */
  default boolean usesHostGraph() {
    return true;
  }

  /** CONTRACT LATER (SE9, CP1): features this provider cannot serve; the host should refuse such an index at CREATE. Not wired yet. */
  default Set<String> unsupportedFeatures() {
    return Set.of();
  }

  /** CONTRACT LATER (MU5): apply what the write hooks staged in the replay journal; called when the transaction's changes stand. */
  default void publishStaged(Object stagedBatch) {
  }

  /** CONTRACT LATER (LC9): the index renumbered every vector id; everything derived is in a dead id space. Under the write lock. */
  default void onRenumber() {
  }

  /** CONTRACT LATER (LC4): make the provider's state durable; called where the index flushes. */
  default void flush() {
  }

  /** CONTRACT LATER (LC5): release background work and resources; called from releaseBackgroundResources. Idempotent. */
  default void close() {
  }

  /** CONTRACT LATER (LC6): remove everything the provider wrote; called from drop. Idempotent. */
  default void drop() {
  }

  /** CONTRACT LATER (LC7): bulk-load hold-off, mirrors suspendBackgroundMaintenance and resumeBackgroundMaintenance. */
  default void suspendMaintenance() {
  }

  default void resumeMaintenance() {
  }

  /** CONTRACT LATER (LC8): problems found by a structural check, empty when none. Not wired to checkIntegrity yet. */
  default List<String> verify() {
    return List.of();
  }

  /** CONTRACT LATER (MT1): adds the provider's counters to the map getStats() returns. */
  default void addStats(Map<String, Long> stats) {
  }
}
