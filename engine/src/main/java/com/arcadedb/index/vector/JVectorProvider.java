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
 * The default provider: the jvector graph plus the delta buffer, which is what {@link LSMVectorIndex} always did.
 * <p>
 * It owns no state. The graph, the ordinal map, the delta buffer and the mutation counter are read and written at more than
 * two hundred sites of {@code LSMVectorIndex} (builds, persistence, compaction, rebuild timers), so moving the fields would
 * rewrite the class. Each operation delegates to a package-private method of the index that holds the former body, moved
 * verbatim or renamed, so behaviour is unchanged.
 */
final class JVectorProvider implements VectorIndexProvider {
  private final LSMVectorIndex owner;

  JVectorProvider(final LSMVectorIndex owner) {
    this.owner = owner;
  }

  @Override
  public String name() {
    return DEFAULT_NAME;
  }

  @Override
  public List<Pair<RID, Float>> search(final float[] queryVector, final int k, final int efSearch,
      final Set<RID> allowedRIDs, final WorkGuard guard) {
    return owner.searchNeighborsJVector(queryVector, k, efSearch, allowedRIDs, guard);
  }

  @Override
  public void awaitReady(final WorkGuard guard) {
    owner.ensureGraphAvailable(guard);
  }

  @Override
  public boolean isReady() {
    return owner.hasResidentGraph();
  }

  @Override
  public void onVectorAdded(final int vectorId, final RID rid, final float[] vector, final ReplayJournal journal) {
    owner.jvectorOnAdded(vectorId, rid, vector, (VectorIndexReplayUndo) journal);
  }

  @Override
  public void onVectorsRemoved(final List<Integer> vectorIds, final RID rid, final ReplayJournal journal) {
    owner.jvectorOnRemoved(vectorIds, rid, (VectorIndexReplayUndo) journal);
  }
}
