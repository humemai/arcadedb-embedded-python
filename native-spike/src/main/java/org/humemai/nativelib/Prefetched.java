/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 7: a ResultSet that has pulled its first rows from the engine (the statement has run) without encoding them. The
 * rows are encoded when the caller reads them (arcadedb_n_next); a caller that only closes the result (an INSERT whose
 * created record nobody reads) never pays for the encoding of the record, the vector in it included.
 */
package org.humemai.nativelib;

import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;

import java.util.ArrayDeque;

final class Prefetched implements ResultSet {
  private final ArrayDeque<Result> head = new ArrayDeque<>();
  private final ResultSet tail;
  private Throwable pending;

  Prefetched(final ResultSet tail, final int max) {
    this.tail = tail;
    try {
      while (head.size() < max && tail.hasNext())
        head.add(tail.next());
    } catch (final Throwable t) {
      // met while the engine computed the first rows: raised when the rows before it have been read (as the eager path did)
      pending = t;
    }
  }

  @Override
  public boolean hasNext() {
    if (!head.isEmpty())
      return true;
    if (pending != null) {
      final Throwable t = pending;
      pending = null;
      if (t instanceof RuntimeException r)
        throw r;
      if (t instanceof Error e)
        throw e;
      throw new RuntimeException(t);
    }
    return tail.hasNext();
  }

  @Override
  public Result next() {
    final Result r = head.poll();
    return r != null ? r : tail.next();
  }

  @Override
  public void close() {
    tail.close();
  }
}
