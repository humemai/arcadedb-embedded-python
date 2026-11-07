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
import java.util.Iterator;
import java.util.NoSuchElementException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/**
 * The {@link VectorIndexHost} of one {@link LSMVectorIndex}: thin forwarding to package-private members of the index.
 */
final class LSMVectorIndexHost implements VectorIndexHost {

  // CONTRACT LATER (RS1): one daemon thread shared by every provider of the JVM. The contract asks for a DedicatedThreadPool-backed
  // executor sized by the engine (see the engine-concurrency skill); not written, because that pool's API was not read.
  private static final ExecutorService EXECUTOR = Executors.newFixedThreadPool(1, runnable -> {
    final Thread thread = new Thread(runnable, "arcadedb-vector-provider");
    thread.setDaemon(true);
    return thread;
  });

  private final LSMVectorIndex owner;

  LSMVectorIndexHost(final LSMVectorIndex owner) {
    this.owner = owner;
  }

  @Override
  public String indexName() {
    return owner.getName();
  }

  @Override
  public int dimensions() {
    return owner.getMetadata().dimensions;
  }

  @Override
  public String similarityName() {
    return owner.getMetadata().similarityFunction.name();
  }

  @Override
  public int liveCount() {
    return (int) owner.locationsForProvider().getActiveCount();
  }

  @Override
  public RID ridOf(final int vectorId) {
    final RID rid = owner.locationsForProvider().getRid(vectorId);
    return rid == null ? null : owner.boundRidForProvider(rid);
  }

  @Override
  public boolean isLive(final int vectorId) {
    return owner.locationsForProvider().isLive(vectorId);
  }

  @Override
  public Iterable<LiveVector> scanLive() {
    final VectorLocationIndex locations = owner.locationsForProvider();
    final int[] ids = locations.getAllVectorIds().filter(locations::isLive).toArray();
    return () -> new Iterator<>() {
      private int      next;
      private LiveVector pending;

      private void advance() {
        while (pending == null && next < ids.length) {
          final int id = ids[next++];
          if (!locations.isLive(id))
            continue;
          final float[] vector = owner.readPersistedVectorArray(id);
          if (vector != null)
            pending = new LiveVector(id, vector);
        }
      }

      @Override
      public boolean hasNext() {
        advance();
        return pending != null;
      }

      @Override
      public LiveVector next() {
        advance();
        if (pending == null)
          throw new NoSuchElementException();
        final LiveVector result = pending;
        pending = null;
        return result;
      }
    };
  }

  @Override
  public OverlayView overlay() {
    return owner.transactionOverlay();
  }

  @Override
  public ExecutorService executor() {
    return EXECUTOR;
  }

  @Override
  public Permit tryAcquireBuild(final long timeoutMs, final long estimatedPeakBytes) {
    if (estimatedPeakBytes > memoryBudgetBytes())
      return null;
    final Semaphore permit = LSMVectorIndex.rebuildPermit();
    try {
      if (!permit.tryAcquire(timeoutMs, TimeUnit.MILLISECONDS))
        return null;
    } catch (final InterruptedException e) {
      Thread.currentThread().interrupt();
      return null;
    }
    if (!owner.admitOnlineRebuild()) {
      permit.release();
      return null;
    }
    return permit::release;
  }

  @Override
  public long memoryBudgetBytes() {
    // CONTRACT LATER (RS3): read VectorHeapBudget and rebuildMaxHeapPercent here; the helper's signature was not read.
    return (long) (Runtime.getRuntime().maxMemory() * 0.9);
  }

  @Override
  public File directory() {
    return owner.directoryForProvider();
  }

  @Override
  public long idEpoch() {
    return 0L;
  }
}
