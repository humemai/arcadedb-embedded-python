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
 * the async executor's parallel bucket writers (parallel=true; caller is
 * responsible for waitCompletion via the AsyncExecutor wrapper).
 *
 * JSON-representable property values only (str/int/float/bool/null and
 * nested lists/maps thereof) — the Python side falls back to the per-row
 * new_document path for anything else (e.g. datetime, bytes).
 */
package com.arcadedb.python;

import com.arcadedb.database.Database;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.serializer.json.JSONArray;
import com.arcadedb.serializer.json.JSONObject;

public final class DocumentBatcher {

  private DocumentBatcher() {
  }

  public static long insertManyJson(final Database db, final String typeName, final String jsonRows,
      final int commitEvery, final boolean parallel) {
    final JSONArray rows = new JSONArray(jsonRows);
    final int n = rows.length();
    if (parallel) {
      for (int i = 0; i < n; i++) {
        final MutableDocument doc = db.newDocument(typeName);
        fill(doc, rows.getJSONObject(i));
        db.async().createRecord(doc, null);
      }
      return n;
    }
    final boolean wasActive = db.isTransactionActive();
    if (!wasActive)
      db.begin();
    for (int i = 0; i < n; i++) {
      final MutableDocument doc = db.newDocument(typeName);
      fill(doc, rows.getJSONObject(i));
      doc.save();
      if (commitEvery > 0 && (i + 1) % commitEvery == 0) {
        db.commit();
        db.begin();
      }
    }
    if (!wasActive)
      db.commit();
    return n;
  }

  private static void fill(final MutableDocument doc, final JSONObject row) {
    for (final String key : row.keySet())
      doc.set(key, row.isNull(key) ? null : row.get(key));
  }
}
