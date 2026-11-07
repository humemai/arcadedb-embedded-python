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
import com.arcadedb.index.IndexException;

/**
 * Picks the {@link VectorIndexProvider} of one index from the {@code provider} entry of its metadata, or from
 * {@link GlobalConfiguration#VECTOR_INDEX_PROVIDER} when the metadata names none. Only the default exists in this change.
 */
final class VectorIndexProviders {
  private VectorIndexProviders() {
  }

  static VectorIndexProvider create(final LSMVectorIndex owner, final String requested) {
    final String name = requested == null || requested.isBlank() ?
        GlobalConfiguration.VECTOR_INDEX_PROVIDER.getValueAsString() :
        requested;
    if (VectorIndexProvider.DEFAULT_NAME.equals(name))
      return new JVectorProvider(owner);
    throw new IndexException("Unknown vector index provider '" + name + "' for index '" + owner.getName() + "'");
  }
}
