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

/**
 * Service interface of a vector index provider that lives outside the engine. Found with {@link java.util.ServiceLoader}, so a
 * provider artifact only has to ship {@code META-INF/services/com.arcadedb.index.vector.VectorIndexProviderFactory}; the engine
 * has no compile-time or run-time dependency on it, and an index whose provider is "jvector" never looks.
 */
public interface VectorIndexProviderFactory {

  /** The value of the {@code provider} metadata entry this factory serves, matched ignoring case. */
  String name();

  /** Creates the provider of one index. Called once per index instance, on first use, from any thread. */
  VectorIndexProvider create(VectorIndexHost host);
}
