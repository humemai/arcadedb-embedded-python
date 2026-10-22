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
import com.arcadedb.database.DocumentCallback;
import com.arcadedb.database.Identifiable;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.database.RID;
import com.arcadedb.database.async.DatabaseAsyncExecutor;
import com.arcadedb.database.async.ErrorCallback;
import com.arcadedb.database.async.NewEdgeCallback;
import com.arcadedb.engine.ErrorRecordCallback;
import com.arcadedb.engine.WALFile;
import com.arcadedb.function.sql.DefaultSQLFunctionFactory;
import com.arcadedb.function.sql.SQLFunctionAbstract;
import com.arcadedb.graph.GraphBatch;
import com.arcadedb.graph.MutableVertex;
import com.arcadedb.graph.Vertex;
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

  /** A callback failure that must not stop an async writer: reported on stderr, not lost. */
  static void swallowed(final String where, final Throwable t) {
    System.err.println("[arcadedb-native] " + where + " failed: " + t);
  }

  /** Calls Python with an event whose reply nobody reads; a Python exception (reported in the reply) is logged, not lost. */
  static void fire(final String where, final long cb, final String message) {
    final String reply = upcall(cb, message);
    if (reply != null && reply.startsWith("{\"error\""))
      swallowed(where, new RuntimeException(reply));
  }

  /** Calls Python with an event whose reply is {"v":bool}: true (or no answer) goes on, false stops. */
  @SuppressWarnings("unchecked")
  static boolean goOn(final String where, final long cb, final String message) {
    final String reply = upcall(cb, message);
    if (reply == null)
      return true;
    final Map<String, Object> r = (Map<String, Object>) Json.parse(reply);
    if (r.get("error") != null) {
      swallowed(where, new RuntimeException(reply));
      return false;
    }
    return !Boolean.FALSE.equals(r.get("v"));
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

  private static final Object[] NO_PROPS = new Object[0]; // never written to: one shared array for every property-less edge and vertex

  /**
   * Edges without properties from two ';'-joined RID texts ("#12:34;#12:35"), as EdgeBatcher.newEdgesJoined does on the JPype path, but
   * each RID is read straight from the text into the engine's RID(bucket, position): no substring, split array or per-RID String.
   */
  static void newEdgesJoined(final GraphBatch batch, final String src, final String type, final String dst) {
    if (src.isEmpty() && dst.isEmpty())
      return;
    int a = 0, b = 0;
    while (true) {
      int ae = src.indexOf(';', a), be = dst.indexOf(';', b);
      if (ae < 0)
        ae = src.length();
      if (be < 0)
        be = dst.length();
      batch.newEdge(rid(src, a, ae), type, rid(dst, b, be), NO_PROPS);
      final boolean lastSrc = ae >= src.length(), lastDst = be >= dst.length();
      if (lastSrc != lastDst)
        throw new IllegalArgumentException("source_rids and destination_rids differ in length");
      if (lastSrc)
        return;
      a = ae + 1;
      b = be + 1;
    }
  }

  /** The RID of "#bucket:position" in text[from, to) (the '#' is optional); anything else goes through RID(String), which refuses it. */
  private static RID rid(final String text, final int from, final int to) {
    int p = from;
    if (p < to && text.charAt(p) == '#')
      p++;
    long bucket = 0, position = 0;
    int digits = p;
    while (p < to && text.charAt(p) >= '0' && text.charAt(p) <= '9' && p - digits < 9)
      bucket = bucket * 10 + (text.charAt(p++) - '0');
    if (p == digits || p >= to || text.charAt(p) != ':')
      return new RID(text.substring(from, to));
    digits = ++p;
    while (p < to && text.charAt(p) >= '0' && text.charAt(p) <= '9' && p - digits < 18)
      position = position * 10 + (text.charAt(p++) - '0');
    if (p == digits || p != to)
      return new RID(text.substring(from, to));
    return new RID((int) bucket, position);
  }

  static Object[] varargs(final Object props) {
    if (!(props instanceof Map<?, ?> m) || m.isEmpty())
      return NO_PROPS;
    final Object[] out = new Object[m.size() * 2];
    int i = 0;
    for (final Map.Entry<?, ?> e : m.entrySet()) {
      out[i++] = e.getKey();
      out[i++] = e.getValue();
    }
    return out;
  }

  static String ridList(final RID[] rids) {
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
      final String opName = ArcadeNative.str(op);
      final ArcadeNative.Chars chars = ArcadeNative.chars(argsJson);
      final List<Object[]> flats = new ArrayList<>(); // create_vertices: one property array per streamed row
      final Map<String, Object> a;
      if (chars.n == 0)
        a = new HashMap<>();
      else if (opName.equals("create_vertices"))
        a = Json.object(chars.b, chars.n, "rows", row -> flats.add(varargs(row)));
      else
        a = (Map<String, Object>) Json.parse(chars.b, chars.n, null, 0);
      switch (opName) {
      case "create_vertex" -> {
        final MutableVertex v = batch.createVertex((String) a.get("type"), varargs(a.get("props")));
        return ArcadeNative.out("{\"ok\":true,\"rid\":\"" + v.getIdentity() + "\"}");
      }
      case "create_vertices" -> {
        final RID[] rids;
        if (!(a.get("rows") instanceof Integer))
          rids = batch.createVertices((String) a.get("type"), intOf(a.get("count"), 0));
        else
          rids = batch.createVertices((String) a.get("type"), flats.toArray(new Object[0][]));
        return ArcadeNative.out("{\"ok\":true,\"rids\":" + ridList(rids) + "}");
      }
      case "new_edge" -> batch.newEdge(new RID((String) a.get("src")), (String) a.get("type"), new RID((String) a.get("dst")),
          varargs(a.get("props")));
      case "new_edges" -> {
        if (a.get("src") instanceof String srcText && a.get("dst") instanceof String dstText) {
          newEdgesJoined(batch, srcText, (String) a.get("type"), dstText);
          return ArcadeNative.OK();
        }
        final List<Object> src = (List<Object>) a.get("src"), dst = (List<Object>) a.get("dst");
        final List<Object> props = (List<Object>) a.get("props");
        for (int i = 0; i < src.size(); i++)
          batch.newEdge(new RID((String) src.get(i)), (String) a.get("type"), new RID((String) dst.get(i)),
              props == null ? NO_PROPS : varargs(props.get(i)));
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
        fire("error callback", cb, event("error", errorBody(t)));
      } catch (final Throwable e) {
        swallowed("error callback", e); // a failing Python error handler must not take down an async writer
      }
    };
  }

  private static NewEdgeCallback edgeCallback(final long cb) {
    if (cb == 0)
      return null;
    return (edge, createdSource, createdDestination) -> {
      try {
        final StringBuilder sb = new StringBuilder("\"edge\":");
        NativeCodec.append(sb, edge);
        sb.append(",\"src\":").append(createdSource).append(",\"dst\":").append(createdDestination);
        fire("edge callback", cb, event("edge", sb.toString()));
      } catch (final Throwable e) {
        swallowed("edge callback", e);
      }
    };
  }

  @SuppressWarnings("unchecked")
  private static String[] strings(final Object list) {
    final List<Object> in = (List<Object>) list;
    final String[] out = new String[in.size()];
    for (int i = 0; i < out.length; i++)
      out[i] = (String) in.get(i);
    return out;
  }

  @SuppressWarnings("unchecked")
  private static Object[] objects(final Object list) {
    return ((List<Object>) list).toArray();
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
            fire("record callback", cb, event("record", sb.toString()));
          } catch (final Throwable e) {
            swallowed("record callback", e); // the writer goes on
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
              fire("result callback", cb, event("result", "\"reply\":" + replyRows(rs)));
            } catch (final Throwable e) {
              swallowed("result callback", e); // the writer goes on
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
          fire("on_ok callback", cb, event("ok", ""));
        } catch (final Throwable e) {
          swallowed("on_ok callback", e); // the writer goes on
        }
      });
      case "on_error" -> ex.onError(errorCallback(cb));
      case "new_edge" -> {
        final Vertex src = db.lookupByRID(new RID((String) a.get("src")), true).asVertex();
        ex.newEdge(src, (String) a.get("type"), new RID((String) a.get("dst")), Boolean.TRUE.equals(a.get("light")), edgeCallback(cb),
            varargs(a.get("props")));
      }
      case "new_edge_by_keys" -> ex.newEdgeByKeys((String) a.get("src_type"), strings(a.get("src_names")), objects(a.get("src_values")),
          (String) a.get("dst_type"), strings(a.get("dst_names")), objects(a.get("dst_values")), Boolean.TRUE.equals(a.get("create")),
          (String) a.get("type"), Boolean.TRUE.equals(a.get("bidirectional")), Boolean.TRUE.equals(a.get("light")), edgeCallback(cb),
          varargs(a.get("props")));
      case "scan_type" -> {
        final DocumentCallback onRecord = rec -> {
          final StringBuilder sb = new StringBuilder("\"rec\":");
          NativeCodec.append(sb, rec);
          return goOn("scan callback", cb, event("record", sb.toString()));
        };
        final boolean polymorphic = !Boolean.FALSE.equals(a.get("polymorphic"));
        if (errCb == 0)
          ex.scanType((String) a.get("type"), polymorphic, onRecord);
        else
          ex.scanType((String) a.get("type"), polymorphic, onRecord, (rid, t) -> goOn("scan error callback", errCb,
              event("scan_error", "\"rid\":\"" + rid + "\"," + errorBody(t))));
      }
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
        try {
          for (final Object row : (List<Object>) a.get("rows")) {
            final MutableDocument doc = db.newDocument(type);
            for (final Map.Entry<String, Object> e : ((Map<String, Object>) row).entrySet())
              doc.set(e.getKey(), e.getValue());
            ex.createRecord(doc, null, onError);
          }
        } catch (final Throwable t) {
          ASYNC_FAILS.remove(fid); // the caller gets the error, not a token to read failures from
          ASYNC_FIRST.remove(fid);
          throw t;
        }
        return ArcadeNative.out("{\"ok\":true,\"fid\":" + fid + "}");
      }
      case "failures" -> {
        final long fid = ((Number) a.get("fid")).longValue();
        final AtomicLong count = ASYNC_FAILS.remove(fid);
        final AtomicReference<Throwable> firstRef = ASYNC_FIRST.remove(fid);
        final Throwable first = firstRef == null ? null : firstRef.get();
        final StringBuilder sb = new StringBuilder("{\"ok\":true,\"count\":").append(count == null ? 0 : count.get()).append(",\"first\":");
        if (first == null)
          sb.append("null");
        else
          NativeCodec.quote(sb, first.toString());
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
