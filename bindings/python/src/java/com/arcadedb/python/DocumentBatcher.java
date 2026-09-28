/*
 * Python-bindings bridge: bulk document insertion.
 *
 * Database.insert_many() from Python would otherwise pay ~5 JNI calls per
 * row (newDocument + set per property + save), which caps ingest around
 * 30-130k rows/s regardless of engine speed. This helper accepts the rows
 * as ONE JSON string and loops Java-side, so the whole batch costs one bulk
 * string copy plus the engine's own write path.
 *
 * Two modes: transactional batches on the calling thread (commitEvery), or
 * the async executor's parallel bucket writers (insertManyJsonParallel; the
 * Python insert_many wrapper waits for completion itself, then reads the
 * failures the writers reported). The boxDoubles/boxLongs
 * helpers below serve AsyncExecutor.append_samples' numpy fast path.
 *
 * JSON-representable property values only (str/int/float/bool/null and
 * nested lists/maps thereof) — the Python side falls back to the per-row
 * new_document path for anything else (e.g. datetime, bytes).
 */
package com.arcadedb.python;

import com.arcadedb.database.Database;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.database.async.ErrorCallback;
import com.arcadedb.serializer.json.JSONArray;
import com.arcadedb.serializer.json.JSONObject;

import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

public final class DocumentBatcher {

  private DocumentBatcher() {
  }

  public static long insertManyJson(final Database db, final String typeName, final String jsonRows,
      final int commitEvery, final boolean parallel) {
    final JSONArray rows = new JSONArray(jsonRows);
    final int n = rows.length();
    if (parallel) {
      insertManyJsonParallel(db, typeName, rows);
      return n;
    }
    final boolean wasActive = db.isTransactionActive();
    if (!wasActive)
      db.begin();
    for (int i = 0; i < n; i++) {
      final MutableDocument doc = db.newDocument(typeName);
      fill(doc, rows.getJSONObject(i));
      doc.save();
      // Batches commit only a transaction this call opened: inside the
      // caller's transaction the caller's commit or rollback decides the whole
      // load, as the Python fallback path and the documentation already had it.
      if (!wasActive && commitEvery > 0 && (i + 1) % commitEvery == 0) {
        db.commit();
        db.begin();
      }
    }
    if (!wasActive)
      db.commit();
    return n;
  }

  /**
   * The failures the async writers reported for one parallel load. A record the writers reject (a duplicate key, a
   * failed batch commit that abandons every record buffered with it) reaches only the per-record error callback and the
   * executor's global one, which by default just logs: without this the load returned its input row count while
   * dropping records (ArcadeData/arcadedb#8478: register an error callback "so a failed record can't pass silently").
   * Read it after waitCompletion().
   */
  public static final class AsyncFailures {
    private final AtomicLong                 count = new AtomicLong();
    private final AtomicReference<Throwable> first = new AtomicReference<>();

    void record(final Throwable exception) {
      count.incrementAndGet();
      first.compareAndSet(null, exception);
    }

    public long getCount() {
      return count.get();
    }

    public String getFirstMessage() {
      final Throwable t = first.get();
      return t == null ? null : t.toString();
    }
  }

  public static AsyncFailures insertManyJsonParallel(final Database db, final String typeName, final String jsonRows) {
    return insertManyJsonParallel(db, typeName, new JSONArray(jsonRows));
  }

  private static AsyncFailures insertManyJsonParallel(final Database db, final String typeName, final JSONArray rows) {
    final AsyncFailures failures = new AsyncFailures();
    final ErrorCallback onError = failures::record;
    final int n = rows.length();
    for (int i = 0; i < n; i++) {
      final MutableDocument doc = db.newDocument(typeName);
      fill(doc, rows.getJSONObject(i));
      db.async().createRecord(doc, null, onError);
    }
    return failures;
  }

  /** Box primitive columns Java-side so numpy arrays can cross the FFI as
   * one buffer copy and still feed Object[]-typed engine APIs (e.g.
   * TimeSeriesEngine.appendSamples). */
  public static Object[] boxDoubles(final double[] a) {
    final Object[] out = new Object[a.length];
    for (int i = 0; i < a.length; i++)
      out[i] = a[i];
    return out;
  }

  public static Object[] boxLongs(final long[] a) {
    final Object[] out = new Object[a.length];
    for (int i = 0; i < a.length; i++)
      out[i] = a[i];
    return out;
  }

  private static void fill(final MutableDocument doc, final JSONObject row) {
    for (final String key : row.keySet())
      doc.set(key, row.isNull(key) ? null : row.get(key));
  }
}
