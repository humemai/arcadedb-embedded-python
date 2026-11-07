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

import java.io.File;
import java.util.concurrent.ExecutorService;

/**
 * What a {@link VectorIndexProvider} may ask of the {@link LSMVectorIndex} that hosts it. Neutral on purpose: only RIDs, ints,
 * floats and JDK types, so a provider artifact needs nothing of the engine beyond this package's two interfaces and a few
 * value types. Every method is callable from any thread unless it says otherwise.
 * <p>
 * CONTRACT LATER as a whole: the default provider reads the index directly and does not use it; it exists for a second
 * provider (the contract's HostEnv, RecordSource and SearchContext in one interface).
 */
public interface VectorIndexHost {

  /** A live vector and its id, as read from the index pages. */
  record LiveVector(int id, float[] vector) {
  }

  /** A permit to run one heavy build; closing it releases the JVM-wide rebuild permit. */
  @FunctionalInterface
  interface Permit extends AutoCloseable {
    @Override
    void close();
  }

  /** Receives one uncommitted row of the calling transaction. */
  @FunctionalInterface
  interface PendingConsumer {
    void accept(RID rid, float[] vector);
  }

  /** What the calling transaction wrote to this index and has not committed. Thread-confined to the transaction's thread. */
  interface OverlayView {
    /** Whether the committed rows of {@code rid} must be ignored: the transaction removed or rewrote the record. */
    boolean supersedes(RID rid);

    int pendingCount();

    /** Visits the rows the transaction added, in write order. */
    void forEachPending(PendingConsumer consumer);
  }

  String indexName();

  /** Components per vector, or 0 while the index is waiting for its first vector. */
  int dimensions();

  /** One of COSINE, DOT_PRODUCT, EUCLIDEAN. */
  String similarityName();

  /** Number of live vectors. */
  int liveCount();

  /** The record of a live vector id (bound to its database, like the RIDs a search returns), or null when the id is dead or unknown. */
  RID ridOf(int vectorId);

  boolean isLive(int vectorId);

  /** A snapshot of the live ids, each vector read from the index pages when the iterator reaches it; ids that died meanwhile are skipped. */
  Iterable<LiveVector> scanLive();

  /** The overlay of the calling thread's transaction, or null when it wrote nothing here (every read-only query). */
  OverlayView overlay();

  /** Executor for every background task of the provider. The provider creates no thread of its own. */
  ExecutorService executor();

  /**
   * Asks to run one heavy build: takes the JVM-wide rebuild permit (waiting up to {@code timeoutMs}) and the heap admission
   * gate of the graph rebuilds. Returns null when refused, which the provider treats as "try later", never as "go ahead".
   */
  Permit tryAcquireBuild(long timeoutMs, long estimatedPeakBytes);

  /** Bytes the provider may keep resident, read at each decision. */
  long memoryBudgetBytes();

  /** The database directory the index files live in (the parent of the index page file), for node-local provider files. */
  File directory();

  /** Id-space token that changes whenever the index renumbers its ids. CONTRACT LATER (Q1): the engine persists none, so 0. */
  long idEpoch();
}
