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

  /** Marker for the per-transaction replay journal the host hands to the write hooks; a provider that does not need it ignores it. */
  interface ReplayJournal {
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
}
