/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Coverage entry points of the Python native backend that are not the DSL core (ArcadeNative): GraphBatch, the async executor,
 * database settings, import and export, and the Java->Python upcall (async callbacks, Python functions in SQL).
 * Same reply convention as ArcadeNative: a malloc'd JSON text, {"ok":true,...} or {"ok":false,"error":..,"cls":..,"chain":..}.
 *
 * Upcalls. Python registers ONE ctypes function pointer with arcadedb_n_set_upcall: CCharPointer fn(long id, CCharPointer json).
 * `id` names a Python-side callback, `json` is the message, the return value is a JSON reply that Python keeps alive until its
 * next call on the same thread (Java copies it at once). The call is a transition-to-native C function pointer call, so the
 * isolate can run a safepoint or a GC while the Python callback holds the GIL and calls back into the library on its thread.
 * ctypes takes the GIL itself (PyGILState_Ensure) when a foreign Java thread (an async writer) or the engine thread inside a
 * query calls the pointer.
 */
package org.humemai.nativelib;

import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseInternal;
import com.arcadedb.database.Document;
import com.arcadedb.database.Identifiable;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.database.RID;
import com.arcadedb.database.async.DatabaseAsyncExecutor;
import com.arcadedb.database.async.ErrorCallback;
import com.arcadedb.engine.WALFile;
import com.arcadedb.function.sql.DefaultSQLFunctionFactory;
import com.arcadedb.function.sql.SQLFunctionAbstract;
import com.arcadedb.graph.GraphBatch;
import com.arcadedb.graph.MutableVertex;
import com.arcadedb.integration.exporter.Exporter;
import com.arcadedb.integration.importer.Importer;
import com.arcadedb.query.sql.executor.CommandContext;
import com.arcadedb.query.sql.executor.ResultSet;
import org.graalvm.nativeimage.IsolateThread;
import org.graalvm.nativeimage.c.function.CEntryPoint;
import org.graalvm.nativeimage.c.function.CFunctionPointer;
import org.graalvm.nativeimage.c.function.InvokeCFunctionPointer;
import org.graalvm.nativeimage.c.type.CCharPointer;
import org.graalvm.nativeimage.c.type.CTypeConversion;
import org.graalvm.word.WordFactory;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

public final class NativeExtras {
  private NativeExtras() {
  }

  // ---- the upcall

  interface PyCallback extends CFunctionPointer {
    @InvokeCFunctionPointer
    CCharPointer invoke(long id, CCharPointer json);
  }

  private static volatile long upcallPointer;

  @CEntryPoint(name = "arcadedb_n_set_upcall")
  public static void setUpcall(final IsolateThread thread, final PyCallback fn) {
    upcallPointer = fn.rawValue();
  }

  /** Calls the Python callback `id` with `json`; the reply text, or null when Python returned NULL. */
  static String upcall(final long id, final String json) {
    final long raw = upcallPointer;
    if (raw == 0)
      throw new IllegalStateException("no Python callback is registered (arcadedb_n_set_upcall)");
    final PyCallback fn = WordFactory.pointer(raw);
    try (CTypeConversion.CCharPointerHolder in = CTypeConversion.toCString(json)) {
      final CCharPointer reply = fn.invoke(id, in.get());
      return reply.isNull() ? null : CTypeConversion.toJavaString(reply);
    }
  }

  private static String event(final String kind, final String body) {
    return "{\"k\":\"" + kind + "\"" + (body.isEmpty() ? "" : "," + body) + "}";
  }

  private static String errorBody(final Throwable t) {
    final StringBuilder sb = new StringBuilder("\"err\":");
    sb.append(ArcadeNative.errorJson(t));
    return sb.toString();
  }

  // ---- small helpers

  @SuppressWarnings("unchecked")
  private static Map<String, Object> args(final CCharPointer json) {
    final String text = ArcadeNative.str(json);
    if (text == null || text.isEmpty())
      return new HashMap<>();
    return (Map<String, Object>) Json.parse(text);
  }

  private static int intOf(final Object v, final int def) {
    return v instanceof Number n ? n.intValue() : def;
  }

  private static Object[] varargs(final Object props) {
    if (!(props instanceof Map<?, ?> m) || m.isEmpty())
      return new Object[0];
    final Object[] out = new Object[m.size() * 2];
    int i = 0;
    for (final Map.Entry<?, ?> e : m.entrySet()) {
      out[i++] = e.getKey();
      out[i++] = e.getValue();
    }
    return out;
  }

  private static String ridList(final RID[] rids) {
    final StringBuilder sb = new StringBuilder("[");
    for (int i = 0; i < rids.length; i++) {
      if (i > 0)
        sb.append(',');
      sb.append('"').append(rids[i]).append('"');
    }
    return sb.append(']').toString();
  }

  private static WALFile.FlushType flushType(final String name) {
    return WALFile.FlushType.valueOf(name);
  }

  // ---- database settings: op wal_flush | read_your_writes | auto_transaction ; value "" reads (where the engine can)

  @CEntryPoint(name = "arcadedb_n_dbset")
  public static CCharPointer dbSet(final IsolateThread thread, final long h, final CCharPointer op, final CCharPointer value) {
    try {
      final Database db = ArcadeNative.db(h);
      final String o = ArcadeNative.str(op);
      final String v = ArcadeNative.str(value);
      switch (o) {
      case "wal_flush" -> db.setWALFlush(flushType(v));
      case "read_your_writes" -> {
        if (v == null || v.isEmpty())
          return ArcadeNative.out("{\"ok\":true,\"v\":" + db.isReadYourWrites() + "}");
        db.setReadYourWrites(Boolean.parseBoolean(v));
      }
      case "auto_transaction" -> ((DatabaseInternal) db).setAutoTransaction(Boolean.parseBoolean(v));
      default -> throw new IllegalArgumentException("unknown database setting " + o);
      }
      return ArcadeNative.OK();
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }

  // ---- GraphBatch

  private record BatchEntry(GraphBatch batch, Database db) {
  }

  private static final Map<Long, BatchEntry> BATCHES = new ConcurrentHashMap<>();

  /** options: the Python keyword names of Database.graph_batch (absent = engine default). */
  @CEntryPoint(name = "arcadedb_n_gb_create")
  public static CCharPointer gbCreate(final IsolateThread thread, final long dbh, final CCharPointer options) {
    try {
      final Database db = ArcadeNative.db(dbh);
      final Map<String, Object> o = args(options);
      GraphBatch.Builder b = GraphBatch.builder(db);
      for (final Map.Entry<String, Object> e : o.entrySet()) {
        final Object v = e.getValue();
        final int iv = intOf(v, 0);
        switch (e.getKey()) {
        case "batch_size" -> b = b.withBatchSize(iv);
        case "expected_edge_count" -> b = b.withExpectedEdgeCount(iv);
        case "edge_list_initial_size" -> b = b.withEdgeListInitialSize(iv);
        case "light_edges" -> b = b.withLightEdges((Boolean) v);
        case "bidirectional" -> b = b.withBidirectional((Boolean) v);
        case "commit_every" -> b = b.withCommitEvery(iv);
        case "use_wal" -> b = b.withWAL((Boolean) v);
        case "wal_flush" -> b = b.withWALFlush(flushType((String) v));
        case "pre_allocate_edge_chunks" -> b = b.withPreAllocateEdgeChunks((Boolean) v);
        case "parallel_flush" -> b = b.withParallelFlush((Boolean) v);
        case "commit_retries" -> b = b.withCommitRetries(iv);
        case "commit_retry_delay_ms" -> b = b.withCommitRetryDelay(((Number) v).longValue());
        case "chunk_cache_capacity" -> b = b.withChunkCacheCapacity(iv);
        case "max_deferred_incoming_edges" -> b = b.withMaxDeferredIncomingEdges(iv);
        default -> throw new IllegalArgumentException("unknown GraphBatch option " + e.getKey());
        }
      }
      final long id = ArcadeNative.IDS.getAndIncrement();
      BATCHES.put(id, new BatchEntry(b.build(), db));
      return ArcadeNative.out("{\"ok\":true,\"h\":" + id + "}");
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }

  /**
   * ops: create_vertex {type, props} -> rid; create_vertices {type, count} | {type, rows} -> rids; new_edge {src, type, dst, props};
   * new_edges {src:[..], type, dst:[..], props:[..]|null}; flush; close; stats.
   */
  @CEntryPoint(name = "arcadedb_n_gb")
  @SuppressWarnings("unchecked")
  public static CCharPointer gb(final IsolateThread thread, final long h, final CCharPointer op, final CCharPointer argsJson) {
    try {
      final BatchEntry entry = BATCHES.get(h);
      if (entry == null)
        throw new IllegalArgumentException("unknown GraphBatch " + h);
      final GraphBatch batch = entry.batch();
      final Map<String, Object> a = args(argsJson);
      switch (ArcadeNative.str(op)) {
      case "create_vertex" -> {
        final MutableVertex v = batch.createVertex((String) a.get("type"), varargs(a.get("props")));
        return ArcadeNative.out("{\"ok\":true,\"rid\":\"" + v.getIdentity() + "\"}");
      }
      case "create_vertices" -> {
        final RID[] rids;
        if (a.get("rows") == null)
          rids = batch.createVertices((String) a.get("type"), intOf(a.get("count"), 0));
        else {
          final List<Object> rows = (List<Object>) a.get("rows");
          final Object[][] matrix = new Object[rows.size()][];
          for (int i = 0; i < matrix.length; i++)
            matrix[i] = varargs(rows.get(i));
          rids = batch.createVertices((String) a.get("type"), matrix);
        }
        return ArcadeNative.out("{\"ok\":true,\"rids\":" + ridList(rids) + "}");
      }
      case "new_edge" -> batch.newEdge(new RID((String) a.get("src")), (String) a.get("type"), new RID((String) a.get("dst")),
          varargs(a.get("props")));
      case "new_edges" -> {
        final List<Object> src = (List<Object>) a.get("src"), dst = (List<Object>) a.get("dst");
        final List<Object> props = (List<Object>) a.get("props");
        for (int i = 0; i < src.size(); i++)
          batch.newEdge(new RID((String) src.get(i)), (String) a.get("type"), new RID((String) dst.get(i)),
              props == null ? new Object[0] : varargs(props.get(i)));
      }
      case "flush" -> batch.flush();
      case "close" -> {
        batch.close();
        BATCHES.remove(h);
      }
      case "stats" -> {
        return ArcadeNative.out("{\"ok\":true,\"total_edges\":" + batch.getTotalEdgesCreated() + ",\"buffered\":" + batch.getBufferedEdgeCount()
            + ",\"deferred\":" + batch.getDeferredIncomingEdgeCount() + "}");
      }
      default -> throw new IllegalArgumentException("unknown GraphBatch operation " + ArcadeNative.str(op));
      }
      return ArcadeNative.OK();
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }

  // ---- async executor (one per database)

  private static final Map<Long, AtomicLong> ASYNC_FAILS = new ConcurrentHashMap<>();
  private static final Map<Long, AtomicReference<Throwable>> ASYNC_FIRST = new ConcurrentHashMap<>();

  private static String replyRows(final ResultSet rs) {
    final StringBuilder sb = new StringBuilder("{\"ok\":true,\"rs\":0,");
    NativeCodec.appendBatch(sb, rs, Integer.MAX_VALUE);
    return sb.append('}').toString();
  }

  private static ErrorCallback errorCallback(final long cb) {
    return t -> {
      try {
        upcall(cb, event("error", errorBody(t)));
      } catch (final Throwable ignored) {
        // a failing Python error handler must not take down an async writer
      }
    };
  }

  /**
   * ops: get | set {key,value} | wait {timeout_ms} | kill | create_record {type, kind, props, cb, err} | command / query {lang, text, params,
   * cb, err} | on_ok {cb} | on_error {cb} | append_samples {type, ts, cols} | insert_parallel {type, rows} | failures {fid}.
   */
  @CEntryPoint(name = "arcadedb_n_async")
  @SuppressWarnings("unchecked")
  public static CCharPointer async(final IsolateThread thread, final long dbh, final CCharPointer op, final CCharPointer argsJson) {
    try {
      final DatabaseInternal db = (DatabaseInternal) ArcadeNative.db(dbh);
      final DatabaseAsyncExecutor ex = db.async();
      final Map<String, Object> a = args(argsJson);
      final long cb = a.get("cb") instanceof Number n ? n.longValue() : 0L;
      final long errCb = a.get("err") instanceof Number n ? n.longValue() : 0L;
      switch (ArcadeNative.str(op)) {
      case "get" -> {
        return ArcadeNative.out("{\"ok\":true,\"parallel\":" + ex.getParallelLevel() + ",\"back_pressure\":" + ex.getBackPressure()
            + ",\"commit_every\":" + ex.getCommitEvery() + ",\"wal\":" + ex.isTransactionUseWAL() + ",\"sync\":\"" + ex.getTransactionSync()
            + "\",\"threads\":" + ex.getThreadCount() + ",\"processing\":" + ex.isProcessing() + "}");
      }
      case "set" -> {
        final Object v = a.get("value");
        switch ((String) a.get("key")) {
        case "parallel" -> ex.setParallelLevel(intOf(v, 1));
        case "back_pressure" -> ex.setBackPressure(intOf(v, 0));
        case "commit_every" -> ex.setCommitEvery(intOf(v, 0));
        case "wal" -> ex.setTransactionUseWAL((Boolean) v);
        case "sync" -> ex.setTransactionSync(flushType((String) v));
        default -> throw new IllegalArgumentException("unknown async setting " + a.get("key"));
        }
      }
      case "wait" -> {
        final boolean done;
        if (a.get("timeout_ms") instanceof Number n)
          done = ex.waitCompletion(n.longValue());
        else {
          ex.waitCompletion();
          done = true;
        }
        return ArcadeNative.out("{\"ok\":true,\"done\":" + done + "}");
      }
      case "kill" -> ex.kill();
      case "close" -> {
        if (ex instanceof com.arcadedb.database.async.DatabaseAsyncExecutorImpl impl)
          impl.close();
      }
      case "create_record" -> {
        final String type = (String) a.get("type");
        final MutableDocument doc = "v".equals(a.get("kind")) ? db.newVertex(type) : db.newDocument(type);
        for (final Map.Entry<String, Object> e : ((Map<String, Object>) a.get("props")).entrySet())
          doc.set(e.getKey(), e.getValue());
        final com.arcadedb.database.async.NewRecordCallback ok = cb == 0 ? null : rec -> {
          try {
            final StringBuilder sb = new StringBuilder("\"rec\":");
            NativeCodec.append(sb, rec);
            upcall(cb, event("record", sb.toString()));
          } catch (final Throwable ignored) {
            // the writer goes on
          }
        };
        if (errCb == 0)
          ex.createRecord(doc, ok);
        else
          ex.createRecord(doc, ok, errorCallback(errCb));
      }
      case "command", "query" -> {
        final boolean command = "command".equals(ArcadeNative.str(op));
        final com.arcadedb.database.async.AsyncResultsetCallback callback = cb == 0 && errCb == 0 ? null : new com.arcadedb.database.async.AsyncResultsetCallback() {
          @Override
          public void onComplete(final ResultSet rs) {
            if (cb == 0)
              return;
            try {
              upcall(cb, event("result", "\"reply\":" + replyRows(rs)));
            } catch (final Throwable ignored) {
              // the writer goes on
            }
          }

          @Override
          public void onError(final Exception e) {
            if (errCb != 0)
              errorCallback(errCb).call(e);
          }
        };
        final String lang = (String) a.get("lang"), text = (String) a.get("text");
        final Object params = a.get("params");
        if (params instanceof Map<?, ?> m) {
          if (command)
            ex.command(lang, text, callback, (Map<String, Object>) m);
          else
            ex.query(lang, text, callback, (Map<String, Object>) m);
        } else if (params instanceof List<?> l) {
          if (command)
            ex.command(lang, text, callback, l.toArray());
          else
            ex.query(lang, text, callback, l.toArray());
        } else if (command)
          ex.command(lang, text, callback);
        else
          ex.query(lang, text, callback);
      }
      case "on_ok" -> ex.onOk(() -> {
        try {
          upcall(cb, event("ok", ""));
        } catch (final Throwable ignored) {
          // the writer goes on
        }
      });
      case "on_error" -> ex.onError(errorCallback(cb));
      case "append_samples" -> {
        final List<Object> ts = (List<Object>) a.get("ts");
        final long[] stamps = new long[ts.size()];
        for (int i = 0; i < stamps.length; i++)
          stamps[i] = ((Number) ts.get(i)).longValue();
        final List<Object> cols = (List<Object>) a.get("cols");
        final Object[][] columns = new Object[cols.size()][];
        for (int i = 0; i < columns.length; i++)
          columns[i] = ((List<Object>) cols.get(i)).toArray();
        ex.appendSamples((String) a.get("type"), stamps, columns);
      }
      case "insert_parallel" -> {
        final long fid = ArcadeNative.IDS.getAndIncrement();
        final AtomicLong count = new AtomicLong();
        final AtomicReference<Throwable> first = new AtomicReference<>();
        ASYNC_FAILS.put(fid, count);
        ASYNC_FIRST.put(fid, first);
        final ErrorCallback onError = t -> {
          count.incrementAndGet();
          first.compareAndSet(null, t);
        };
        final String type = (String) a.get("type");
        for (final Object row : (List<Object>) a.get("rows")) {
          final MutableDocument doc = db.newDocument(type);
          for (final Map.Entry<String, Object> e : ((Map<String, Object>) row).entrySet())
            doc.set(e.getKey(), e.getValue());
          ex.createRecord(doc, null, onError);
        }
        return ArcadeNative.out("{\"ok\":true,\"fid\":" + fid + "}");
      }
      case "failures" -> {
        final long fid = ((Number) a.get("fid")).longValue();
        final AtomicLong count = ASYNC_FAILS.remove(fid);
        final Throwable first = ASYNC_FIRST.remove(fid).get();
        final StringBuilder sb = new StringBuilder("{\"ok\":true,\"count\":").append(count == null ? 0 : count.get()).append(",\"first\":");
        NativeCodec.quote(sb, first == null ? null : first.toString());
        return ArcadeNative.out(sb.append('}').toString());
      }
      default -> throw new IllegalArgumentException("unknown async operation " + ArcadeNative.str(op));
      }
      return ArcadeNative.OK();
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }

  // ---- import and export

  /** settings: {key: string} as the Python importer builds them; the reply is {"ok":true,"stats":{..}|null}. */
  @CEntryPoint(name = "arcadedb_n_import")
  public static CCharPointer importDocuments(final IsolateThread thread, final long dbh, final CCharPointer settingsJson) {
    try {
      final Database db = ArcadeNative.db(dbh);
      final Map<String, String> settings = new HashMap<>();
      for (final Map.Entry<String, Object> e : args(settingsJson).entrySet())
        settings.put(e.getKey(), String.valueOf(e.getValue()));
      final Importer importer = new Importer(db, null);
      importer.setSettings(settings);
      final Map<String, Object> stats = importer.load();
      final StringBuilder sb = new StringBuilder("{\"ok\":true,\"stats\":");
      if (stats == null)
        sb.append("null");
      else
        NativeCodec.append(sb, stats);
      return ArcadeNative.out(sb.append('}').toString());
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }

  @CEntryPoint(name = "arcadedb_n_export")
  public static CCharPointer exportDatabase(final IsolateThread thread, final long dbh, final CCharPointer path, final CCharPointer format,
      final int overwrite, final CCharPointer settingsJson) {
    try {
      final Database db = ArcadeNative.db(dbh);
      final Exporter exporter = new Exporter(db, ArcadeNative.str(path));
      exporter.setFormat(ArcadeNative.str(format));
      exporter.setOverwrite(overwrite != 0);
      final Map<String, String> settings = new HashMap<>();
      for (final Map.Entry<String, Object> e : args(settingsJson).entrySet())
        settings.put(e.getKey(), String.valueOf(e.getValue()));
      if (!settings.isEmpty())
        exporter.setSettings(settings);
      final Map<String, Object> stats = exporter.exportDatabase();
      final StringBuilder sb = new StringBuilder("{\"ok\":true,\"stats\":");
      NativeCodec.append(sb, stats == null ? new HashMap<String, Object>() : stats);
      return ArcadeNative.out(sb.append('}').toString());
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }

  // ---- Python functions in SQL: arcadedb_n_udf_register(name, callbackId, minArgs, maxArgs)

  /**
   * A SQL function whose body is a Python callable. The engine thread that runs the statement calls the upcall with
   * {"k":"fn","args":[..]} (tagged values, as parameters) and expects {"v":<value>} or {"error":"text"}; an error is thrown
   * as a CommandExecutionException from the function, so the statement fails with the Python message.
   */
  static final class PythonFunction extends SQLFunctionAbstract {
    private final long cb;
    private final int min, max;

    PythonFunction(final String name, final long cb, final int min, final int max) {
      super(name);
      this.cb = cb;
      this.min = min;
      this.max = max;
    }

    @Override
    public Object execute(final Object self, final Identifiable record, final Object result, final Object[] params, final CommandContext ctx) {
      final StringBuilder sb = new StringBuilder("{\"k\":\"fn\",\"args\":[");
      for (int i = 0; i < params.length; i++) {
        if (i > 0)
          sb.append(',');
        NativeCodec.append(sb, params[i]);
      }
      final String reply = upcall(cb, sb.append("]}").toString());
      if (reply == null)
        return null;
      @SuppressWarnings("unchecked") final Map<String, Object> r = (Map<String, Object>) Json.parse(reply);
      if (r.get("error") != null)
        throw new com.arcadedb.exception.CommandExecutionException(String.valueOf(r.get("error")));
      return r.get("v");
    }

    @Override
    public int getMinArgs() {
      return min;
    }

    @Override
    public int getMaxArgs() {
      return max;
    }

    @Override
    public String getSyntax() {
      return getName() + "(<arg>*)";
    }
  }

  @CEntryPoint(name = "arcadedb_n_udf_register")
  public static CCharPointer udfRegister(final IsolateThread thread, final CCharPointer name, final long cb, final int min, final int max) {
    try {
      DefaultSQLFunctionFactory.getInstance().register(new PythonFunction(ArcadeNative.str(name), cb, min, max));
      return ArcadeNative.OK();
    } catch (final Throwable t) {
      return ArcadeNative.err(t);
    }
  }
}
