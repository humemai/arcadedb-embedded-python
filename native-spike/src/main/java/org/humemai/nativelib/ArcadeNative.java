/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Phase 2: the C entry points behind the Python native backend (arcadedb_embedded/_native). Every function returns a
 * malloc'd UTF-8 JSON text that the caller releases with arcadedb_free: {"ok":true,...} or
 * {"ok":false,"error":msg,"cls":java class,"chain":[[class,msg],..],"retry":"need_retry"|"duplicated_key"|null,"retry_ms":n}.
 * Databases, result sets and servers are long handles. Any thread attached to the isolate may call any function; a
 * transaction belongs to the (Java) thread that began it, as in the embedded API.
 */
package org.humemai.nativelib;

import com.arcadedb.ContextConfiguration;
import com.arcadedb.GlobalConfiguration;
import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.database.DatabaseInternal;
import com.arcadedb.database.LocalDatabase;
import com.arcadedb.database.MutableDocument;
import com.arcadedb.database.TransactionContext;
import com.arcadedb.engine.ComponentFile;
import com.arcadedb.exception.DuplicatedKeyException;
import com.arcadedb.exception.NeedRetryException;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.VertexType;
import com.arcadedb.server.ArcadeDBServer;
import org.graalvm.nativeimage.IsolateThread;
import org.graalvm.nativeimage.UnmanagedMemory;
import org.graalvm.nativeimage.c.function.CEntryPoint;
import org.graalvm.nativeimage.c.type.CCharPointer;
import org.graalvm.nativeimage.c.type.CFloatPointer;
import org.graalvm.nativeimage.c.type.CLongPointer;
import org.graalvm.word.WordFactory;
import org.graalvm.nativeimage.c.type.CTypeConversion;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public final class ArcadeNative {
  static final Map<Long, Database> DBS = new ConcurrentHashMap<>();
  private static final Map<Long, ResultSet> RESULT_SETS = new ConcurrentHashMap<>();
  private static final Map<Long, ArcadeDBServer> SERVERS = new ConcurrentHashMap<>();
  static final AtomicLong IDS = new AtomicLong(1);

  static {
    // The image carries no GraalVM polyglot languages by design, so the engine's polyglot registration can only find none and
    // would log "GraalVM Polyglot Engine: no languages found" at WARNING in every process (#477). Turn the engine off before the
    // first database is opened (QueryEngineManager reads this when it first loads); no other warning is touched.
    GlobalConfiguration.POLYGLOT_ENGINE_ENABLED.setValue(false);
  }

  static {
    // ARCADEDB_VECTOR_PROVIDER = native | panama | default (jvector's VectorizationProvider, forced); unset: jvector chooses
    // (Highway through the FFM downcalls when the bundled libjvector loads, else the Vector API classes).
    final String forced = System.getenv("ARCADEDB_VECTOR_PROVIDER");
    if (forced != null && !forced.isEmpty() && System.getProperty("jvector.vectorization_provider") == null)
      System.setProperty("jvector.vectorization_provider", forced);
  }

  private ArcadeNative() {
  }

  // ---- phase 6: stack-sampling profiler (ARCADEDB_NATIVE_SAMPLE=<ms>, a CPU profile of the image without perf/JFR). A daemon thread
  // takes Thread.getAllStackTraces every <ms>, counts the top frame per runnable thread ("self") and every distinct frame in the top
  // 40 ("incl"); arcadedb_n_sample_dump returns the counts as JSON. Safepoint-biased, like any Java sampler: a direction, not a measurement.
  private static final Map<String, long[]> SELF = new ConcurrentHashMap<>(), INCL = new ConcurrentHashMap<>();
  private static volatile long samples;

  static {
    final String ms = System.getenv("ARCADEDB_NATIVE_SAMPLE");
    if (ms != null && !ms.isEmpty()) {
      final long every = Long.parseLong(ms);
      final Thread t = new Thread(() -> {
        final Thread me = Thread.currentThread();
        while (true) {
          try {
            Thread.sleep(every);
            for (final Map.Entry<Thread, StackTraceElement[]> e : Thread.getAllStackTraces().entrySet()) {
              final StackTraceElement[] st = e.getValue();
              if (e.getKey() == me || st.length == 0 || e.getKey().getState() != Thread.State.RUNNABLE)
                continue;
              SELF.computeIfAbsent(st[0].getClassName() + "." + st[0].getMethodName(), k -> new long[1])[0]++;
              final java.util.HashSet<String> seen = new java.util.HashSet<>();
              for (int i = 0; i < st.length && i < 40; i++)
                if (seen.add(st[i].getClassName() + "." + st[i].getMethodName()))
                  INCL.computeIfAbsent(st[i].getClassName() + "." + st[i].getMethodName(), k -> new long[1])[0]++;
              samples++;
            }
          } catch (final Throwable ignored) {
            // keep sampling
          }
        }
      }, "native-sampler");
      t.setDaemon(true);
      t.start();
    }
  }

  @CEntryPoint(name = "arcadedb_n_sample_dump")
  public static CCharPointer sampleDump(final IsolateThread thread) {
    final StringBuilder sb = new StringBuilder("{\"ok\":true,\"samples\":").append(samples);
    for (final String which : new String[] { "self", "incl" }) {
      sb.append(",\"").append(which).append("\":[");
      final java.util.List<Map.Entry<String, long[]>> l = new java.util.ArrayList<>((which.equals("self") ? SELF : INCL).entrySet());
      l.sort((a, b) -> Long.compare(b.getValue()[0], a.getValue()[0]));
      for (int i = 0; i < l.size() && i < 70; i++) {
        if (i > 0)
          sb.append(',');
        sb.append('[');
        NativeCodec.quote(sb, l.get(i).getKey());
        sb.append(',').append(l.get(i).getValue()[0]).append(']');
      }
      sb.append(']');
    }
    return out(sb.append('}').toString());
  }

  // ---- databases

  /** mode 0 create, 1 open read-write, 2 open read-only, 3 exists. */
  @CEntryPoint(name = "arcadedb_n_open")
  public static CCharPointer open(final IsolateThread thread, final CCharPointer path, final int mode) {
    try {
      final DatabaseFactory factory = new DatabaseFactory(str(path));
      if (mode == 3)
        return out("{\"ok\":true,\"exists\":" + factory.exists() + "}");
      final Database db = switch (mode) {
        case 0 -> factory.create();
        case 1 -> factory.open();
        default -> factory.open(ComponentFile.MODE.READ_ONLY);
      };
      return out(registered(db));
    } catch (final Throwable t) {
      return err(t);
    }
  }

  private static String registered(final Database db) {
    final long h = IDS.getAndIncrement();
    DBS.put(h, db);
    return "{\"ok\":true,\"h\":" + h + "}";
  }

  /** drop 0: close, 1: drop (close and delete the files). A database owned by a server reports its refusal. */
  @CEntryPoint(name = "arcadedb_n_close")
  public static CCharPointer close(final IsolateThread thread, final long h, final int drop) {
    try {
      final Database db = db(h);
      if (drop != 0 && db instanceof LocalDatabase local)
        local.drop();
      else
        db.close();
      DBS.remove(h);
      return OK();
    } catch (final Throwable t) {
      return err(t);
    }
  }

  @CEntryPoint(name = "arcadedb_n_info")
  public static CCharPointer info(final IsolateThread thread, final long h) {
    try {
      final Database db = db(h);
      final StringBuilder sb = new StringBuilder("{\"ok\":true,\"open\":").append(db.isOpen());
      if (db.isOpen()) {
        sb.append(",\"name\":");
        NativeCodec.quote(sb, db.getName());
        sb.append(",\"path\":");
        NativeCodec.quote(sb, db.getDatabasePath());
        sb.append(",\"mode\":");
        NativeCodec.quote(sb, String.valueOf(db.getMode()));
      }
      return out(sb.append('}').toString());
    } catch (final Throwable t) {
      return err(t);
    }
  }

  /** op 0 begin, 1 commit, 2 rollback, 3 mark. Every reply carries {"active":b,"depth":n,"commits":n}. */
  @CEntryPoint(name = "arcadedb_n_tx")
  public static CCharPointer tx(final IsolateThread thread, final long h, final int op) {
    try {
      final Database db = db(h);
      switch (op) {
      case 0 -> db.begin();
      case 1 -> db.commit();
      case 2 -> db.rollback();
      default -> {
      }
      }
      return out(txState(db));
    } catch (final Throwable t) {
      return err(t);
    }
  }

  private static String txState(final Database db) {
    int depth = 0;
    long commits = 0;
    if (db instanceof LocalDatabase local)
      depth = local.getNestedTransactions();
    if (db instanceof DatabaseInternal internal) {
      final TransactionContext ctx = internal.getTransactionIfExists();
      if (ctx != null)
        commits = ctx.getCommitCount();
    }
    return "{\"ok\":true,\"active\":" + db.isTransactionActive() + ",\"depth\":" + depth + ",\"commits\":" + commits + "}";
  }

  // ---- statements

  /**
   * flags bit 0: command (else query). params: "" or {"named":{..}} or {"pos":[..]} (tagged values, see Json). Runs the
   * statement and returns its first batch of up to max rows; {"rs":id} is the open cursor (0 once drained and closed).
   */
  @CEntryPoint(name = "arcadedb_n_exec")
  public static CCharPointer exec(final IsolateThread thread, final long h, final int flags, final CCharPointer language,
      final CCharPointer text, final CCharPointer params, final int max) {
    return execImpl(h, flags, language, text, params, max, WordFactory.nullPointer(), 0);
  }

  /** Same as arcadedb_n_exec plus a float32 side buffer (pointer + count of floats) that params values {"\u0001":["B",offset,count]} read from. */
  @CEntryPoint(name = "arcadedb_n_exec_bin")
  public static CCharPointer execBin(final IsolateThread thread, final long h, final int flags, final CCharPointer language,
      final CCharPointer text, final CCharPointer params, final int max, final CFloatPointer buf, final long bufFloats) {
    return execImpl(h, flags, language, text, params, max, buf, bufFloats);
  }

  /** Timers (ns) of the exec path, read through arcadedb_n_diag: decode of the text arguments, JSON parse, engine call, reply encoding. */
  static final long[] T = new long[5];

  @SuppressWarnings("unchecked")
  private static CCharPointer execImpl(final long h, final int flags, final CCharPointer language, final CCharPointer text,
      final CCharPointer params, final int max, final CFloatPointer buf, final long bufFloats) {
    ResultSet rs = null;
    try {
      final long t0 = System.nanoTime();
      final Database db = db(h);
      final String lang = str(language);
      final String sql = str(text);
      final String p = str(params);
      final boolean command = (flags & 1) != 0;
      final long t1 = System.nanoTime();
      Map<String, Object> named = null;
      Object[] pos = null;
      if (p != null && !p.isEmpty()) {
        final Map<String, Object> env = (Map<String, Object>) Json.parse(p, buf.rawValue(), bufFloats);
        final Object n = env.get("named");
        if (n instanceof Map<?, ?> m)
          named = (Map<String, Object>) m;
        else
          pos = ((List<Object>) env.get("pos")).toArray();
      }
      final long t2 = System.nanoTime();
      if (named != null)
        rs = command ? db.command(lang, sql, named) : db.query(lang, sql, named);
      else if (pos != null)
        rs = command ? db.command(lang, sql, pos) : db.query(lang, sql, pos);
      else
        rs = command ? db.command(lang, sql) : db.query(lang, sql);
      final long t3 = System.nanoTime();
      final CCharPointer o = replyOf(rs, max, flags);
      final long t4 = System.nanoTime();
      T[0]++;
      T[1] += t1 - t0;
      T[2] += t2 - t1;
      T[3] += t3 - t2;
      T[4] += t4 - t3;
      return o;
    } catch (final Throwable t) {
      closeQuietly(rs);
      return err(t);
    }
  }

  @CEntryPoint(name = "arcadedb_n_next")
  public static CCharPointer next(final IsolateThread thread, final long rsId, final int max) {
    ResultSet rs = null;
    try {
      rs = RESULT_SETS.get(rsId);
      if (rs == null)
        throw new IllegalArgumentException("unknown result set " + rsId);
      return out(batchOf(rsId, rs, max));
    } catch (final Throwable t) {
      RESULT_SETS.remove(rsId);
      closeQuietly(rs);
      return err(t);
    }
  }

  /**
   * arcadedb_n_next with the float32 tail of arcadedb_n_exec flag 4: float[] values of 8 or more elements of the batch come back in a binary tail
   * ({"\u0001":["B",offset,count]} in the rows, ,"bin":total at the end of the JSON, the floats after its NUL), not as number text. Offsets are
   * per reply. A reply without such a value is the same text arcadedb_n_next returns.
   */
  @CEntryPoint(name = "arcadedb_n_next_bin")
  public static CCharPointer nextBin(final IsolateThread thread, final long rsId, final int max) {
    ResultSet rs = null;
    try {
      rs = RESULT_SETS.get(rsId);
      if (rs == null)
        throw new IllegalArgumentException("unknown result set " + rsId);
      final ResultSet cursor = rs;
      return withFloatTail(() -> batchOf(rsId, cursor, max));
    } catch (final Throwable t) {
      RESULT_SETS.remove(rsId);
      closeQuietly(rs);
      return err(t);
    }
  }

  @CEntryPoint(name = "arcadedb_n_rs_close")
  public static CCharPointer rsClose(final IsolateThread thread, final long rsId) {
    closeQuietly(RESULT_SETS.remove(rsId));
    return OK();
  }

  private static String batch(final ResultSet rs, final int max) {
    if (rs == null)
      return "{\"ok\":true,\"rs\":0,\"rows\":[],\"meta\":[],\"drained\":true}";
    final long id = IDS.getAndIncrement();
    RESULT_SETS.put(id, rs);
    return batchOf(id, rs, max);
  }

  private static String batchOf(final long id, final ResultSet rs, final int max) {
    final StringBuilder sb = new StringBuilder("{\"ok\":true,\"rs\":");
    final int mark = sb.length();
    sb.append(id).append(',');
    final boolean drained = NativeCodec.appendBatch(sb, rs, max);
    if (drained) {
      RESULT_SETS.remove(id);
      closeQuietly(rs);
      sb.replace(mark, mark + String.valueOf(id).length(), "0");
    }
    return sb.append('}').toString();
  }

  private static void closeQuietly(final ResultSet rs) {
    if (rs != null)
      try {
        rs.close();
      } catch (final Throwable ignored) {
        // closing a failed cursor must not hide the error that is being reported
      }
  }

  // ---- server

  /**
   * config: {"settings":{"arcadedb.x.y":value,..},"host":"localhost"}: every listener host setting that defaults to all
   * interfaces and is absent from settings is set to host (the bindings never expose a listener unasked).
   */
  @CEntryPoint(name = "arcadedb_n_server_start")
  @SuppressWarnings("unchecked")
  public static CCharPointer serverStart(final IsolateThread thread, final CCharPointer configJson) {
    ArcadeDBServer server = null;
    try {
      final Map<String, Object> cfg = (Map<String, Object>) Json.parse(str(configJson));
      final Map<String, Object> settings = (Map<String, Object>) cfg.get("settings");
      final String host = (String) cfg.get("host");
      final ContextConfiguration config = new ContextConfiguration();
      if (host != null)
        for (final GlobalConfiguration setting : GlobalConfiguration.values()) {
          final String key = setting.getKey();
          final Object def = setting.getDefValue();
          if (key.endsWith(".host") && ("0.0.0.0".equals(def) || "::".equals(def)) && !settings.containsKey(key))
            config.setValue(key, host);
        }
      for (final Map.Entry<String, Object> e : settings.entrySet())
        config.setValue(e.getKey(), e.getValue());
      server = new ArcadeDBServer(config);
      server.start();
      final long id = IDS.getAndIncrement();
      SERVERS.put(id, server);
      return out("{\"ok\":true,\"h\":" + id + "}");
    } catch (final Throwable t) {
      if (server != null)
        try {
          server.stop();
        } catch (final Throwable ignored) {
          // the start error is what the caller needs
        }
      return err(t);
    }
  }

  @CEntryPoint(name = "arcadedb_n_server_stop")
  public static CCharPointer serverStop(final IsolateThread thread, final long id) {
    try {
      final ArcadeDBServer server = SERVERS.remove(id);
      if (server != null)
        server.stop();
      return OK();
    } catch (final Throwable t) {
      return err(t);
    }
  }

  /** create 0: getDatabase(name); 1: getDatabase(name, true, true). */
  @CEntryPoint(name = "arcadedb_n_server_db")
  public static CCharPointer serverDb(final IsolateThread thread, final long id, final CCharPointer name, final int create) {
    try {
      final ArcadeDBServer server = SERVERS.get(id);
      if (server == null)
        throw new IllegalArgumentException("unknown server " + id);
      final Database db = create != 0 ? server.getDatabase(str(name), true, true) : server.getDatabase(str(name));
      return out(registered(db));
    } catch (final Throwable t) {
      return err(t);
    }
  }

  /** Which vector math the image runs: jvector's VectorizationProvider and VectorUtilSupport classes (no logging needed). */
  @CEntryPoint(name = "arcadedb_n_diag")
  public static CCharPointer diag(final IsolateThread thread) {
    try {
      final StringBuilder sb = new StringBuilder("{\"ok\":true,\"java\":");
      NativeCodec.quote(sb, Runtime.version().toString());
      sb.append(",\"vector_module\":").append(ModuleLayer.boot().findModule("jdk.incubator.vector").isPresent());
      sb.append(",\"cpus\":").append(Runtime.getRuntime().availableProcessors());
      sb.append(",\"max_heap\":").append(Runtime.getRuntime().maxMemory());
      sb.append(",\"exec_timers_ns\":{\"calls\":").append(T[0]).append(",\"args\":").append(T[1]).append(",\"json\":").append(T[2])
          .append(",\"engine\":").append(T[3]).append(",\"reply\":").append(T[4]).append('}');
      final io.github.jbellis.jvector.vector.VectorizationProvider vp = io.github.jbellis.jvector.vector.VectorizationProvider.getInstance();
      sb.append(",\"provider\":");
      NativeCodec.quote(sb, vp.getClass().getName());
      sb.append(",\"util_support\":");
      NativeCodec.quote(sb, vp.getVectorUtilSupport().getClass().getName());
      sb.append(",\"isa\":");
      String isa = null;
      try {
        final Object support = vp.getVectorUtilSupport();
        isa = (String) support.getClass().getMethod("getActiveIsa").invoke(support);
      } catch (final ReflectiveOperationException | RuntimeException e) {
        // the Panama and default providers have no ISA tier
      }
      NativeCodec.quote(sb, String.valueOf(isa));
      return out(sb.append('}').toString());
    } catch (final Throwable t) {
      return err(t);
    }
  }

  // ---- plumbing

  static Database db(final long h) {
    final Database db = DBS.get(h);
    if (db == null)
      throw new IllegalArgumentException("unknown database handle " + h);
    return db;
  }

  static String str(final CCharPointer p) {
    return CTypeConversion.toJavaString(p);
  }

  static CCharPointer OK() {
    return out("{\"ok\":true}");
  }

  static CCharPointer err(final Throwable t) {
    return out(errorJson(t));
  }

  static String errorJson(final Throwable t) {
    final StringBuilder sb = new StringBuilder("{\"ok\":false,\"error\":");
    NativeCodec.quote(sb, String.valueOf(t.getMessage()));
    sb.append(",\"cls\":");
    NativeCodec.quote(sb, t.getClass().getName());
    sb.append(",\"chain\":[");
    String retry = null;
    long retryMs = 0;
    Throwable c = t;
    for (int i = 0; c != null && i < 16; i++, c = c.getCause()) {
      if (i > 0)
        sb.append(',');
      sb.append('[');
      NativeCodec.quote(sb, c.getClass().getName());
      sb.append(',');
      NativeCodec.quote(sb, String.valueOf(c.getMessage()));
      sb.append(']');
      if (retry == null && c instanceof NeedRetryException nre) {
        retry = "need_retry";
        retryMs = nre.getRetryAfterMs();
      } else if (retry == null && c instanceof DuplicatedKeyException)
        retry = "duplicated_key";
    }
    sb.append("],\"retry\":").append(retry == null ? "null" : "\"" + retry + "\"").append(",\"retry_ms\":").append(retryMs).append('}');
    return sb.toString();
  }

  // ---- phase 7: lazy command rows, binary float reply, columnar insert (small and separate: BulkOps, Prefetched, NativeCodec.SINK)

  /**
   * flags bit 1 (2): the statement has run and its first rows are pulled, but not encoded; arcadedb_n_next encodes them when
   * read. Bit 2 (4): float[] values of 8 or more elements in the reply go to a float32 tail of the reply ({"\u0001":["B",off,n]},
   * the JSON ends with ,"bin":total and the floats follow the NUL, 4-byte aligned) instead of number text.
   */
  private static CCharPointer replyOf(final ResultSet rs, final int max, final int flags) {
    if ((flags & 2) != 0 && rs != null) {
      final ResultSet lazy = new Prefetched(rs, max);
      final long id = IDS.getAndIncrement();
      RESULT_SETS.put(id, lazy);
      return out("{\"ok\":true,\"rs\":" + id + ",\"rows\":[],\"meta\":[],\"drained\":false}");
    }
    if ((flags & 4) == 0)
      return out(batch(rs, max));
    return withFloatTail(() -> batch(rs, max));
  }

  /**
   * Runs encode with the float32 sink set (float[] values of 8 or more elements go to the tail of the reply as {"\u0001":["B",off,n]}) and returns
   * the reply: out(text) when no vector was met, else the text with ,"bin":total, a NUL, padding to 4 bytes and the floats.
   */
  private static CCharPointer withFloatTail(final java.util.function.Supplier<String> encode) {
    final NativeCodec.FloatSink sink = new NativeCodec.FloatSink();
    NativeCodec.SINK.set(sink);
    final String reply;
    try {
      reply = encode.get();
    } finally {
      NativeCodec.SINK.remove();
    }
    if (sink.n == 0)
      return out(reply);
    final byte[] b = (reply.substring(0, reply.length() - 1) + ",\"bin\":" + sink.n + "}").getBytes(StandardCharsets.UTF_8);
    final int off = (b.length + 1 + 3) & ~3;
    final CCharPointer p = UnmanagedMemory.malloc(off + 4 * sink.n);
    // bulk copies (Unsafe.copyMemory), not one p.write per byte: the text, the zero padding up to the 4-byte boundary, then the float32 tail in native order
    final java.nio.ByteBuffer bb = CTypeConversion.asByteBuffer(p, (int) (off + 4L * sink.n));
    bb.put(b, 0, b.length);
    while (bb.position() < off)
      bb.put((byte) 0);
    bb.order(java.nio.ByteOrder.nativeOrder()).asFloatBuffer().put(sink.a, 0, sink.n);
    return p;
  }

  /** Columnar insert (see BulkOps): header JSON, one buffer holding the columns. Returns {"ok":true,"n":rows}. */
  @CEntryPoint(name = "arcadedb_n_insert_cols")
  public static CCharPointer insertCols(final IsolateThread thread, final long h, final CCharPointer type, final CCharPointer header,
      final CCharPointer buf, final long bufBytes) {
    try {
      final java.nio.ByteBuffer bb = CTypeConversion.asByteBuffer(buf, (int) bufBytes);
      return out("{\"ok\":true,\"n\":" + BulkOps.insertColumns(db(h), str(type), str(header), bb) + "}");
    } catch (final Throwable t) {
      return err(t);
    }
  }

  // ---- phase 8: fewer crossings and no reply text for a command whose rows are read late or never; batches of statements and rows per crossing

  private static final ThreadLocal<String> LAST_ERROR = new ThreadLocal<>();

  /**
   * A command (flags bit 0 selects command, else query) whose first rows are pulled but not encoded (as flags bit 1 of arcadedb_n_exec).
   * Returns the cursor id (> 0, read with arcadedb_n_next, closed with arcadedb_n_rs_close or arcadedb_n_rs_close_many), 0 when the
   * statement gave no cursor, -1 on error: the error text is then read with arcadedb_n_last_error on the same thread. No reply text, so
   * no malloc, no arcadedb_free and no JSON decode in the caller.
   */
  @CEntryPoint(name = "arcadedb_n_cmd")
  @SuppressWarnings("unchecked")
  public static long cmd(final IsolateThread thread, final long h, final int flags, final CCharPointer language, final CCharPointer text,
      final CCharPointer params, final CFloatPointer buf, final long bufFloats, final int max) {
    ResultSet rs = null;
    try {
      final long t0 = System.nanoTime();
      final Database db = db(h);
      final String lang = str(language);
      final String sql = str(text);
      final String p = str(params);
      final boolean command = (flags & 1) != 0;
      final long t1 = System.nanoTime();
      Map<String, Object> named = null;
      Object[] pos = null;
      if (p != null && !p.isEmpty()) {
        final Map<String, Object> env = (Map<String, Object>) Json.parse(p, buf.rawValue(), bufFloats);
        final Object n = env.get("named");
        if (n instanceof Map<?, ?> m)
          named = (Map<String, Object>) m;
        else
          pos = ((List<Object>) env.get("pos")).toArray();
      }
      final long t2 = System.nanoTime();
      if (named != null)
        rs = command ? db.command(lang, sql, named) : db.query(lang, sql, named);
      else if (pos != null)
        rs = command ? db.command(lang, sql, pos) : db.query(lang, sql, pos);
      else
        rs = command ? db.command(lang, sql) : db.query(lang, sql);
      final long t3 = System.nanoTime();
      long id = 0;
      if (rs != null) {
        id = IDS.getAndIncrement();
        RESULT_SETS.put(id, new Prefetched(rs, max));
      }
      final long t4 = System.nanoTime();
      T[0]++;
      T[1] += t1 - t0;
      T[2] += t2 - t1;
      T[3] += t3 - t2;
      T[4] += t4 - t3;
      return id;
    } catch (final Throwable t) {
      closeQuietly(rs);
      LAST_ERROR.set(errorJson(t));
      return -1;
    }
  }

  /** The error of the last failed arcadedb_n_cmd on this thread, in the usual {"ok":false,...} form. */
  @CEntryPoint(name = "arcadedb_n_last_error")
  public static CCharPointer lastError(final IsolateThread thread) {
    final String e = LAST_ERROR.get();
    return out(e != null ? e : "{\"ok\":false,\"error\":\"no error recorded\",\"cls\":\"java.lang.IllegalStateException\",\"chain\":[],\"retry\":null,\"retry_ms\":0}");
  }

  /** Closes n cursors in one crossing (ids is an array of n longs). */
  @CEntryPoint(name = "arcadedb_n_rs_close_many")
  public static void rsCloseMany(final IsolateThread thread, final CLongPointer ids, final int n) {
    try {
      for (int i = 0; i < n; i++)
        closeQuietly(RESULT_SETS.remove(ids.read(i)));
    } catch (final Throwable ignored) {
      // closing is best effort, as in arcadedb_n_rs_close
    }
  }

  /**
   * One statement run once per row of rowsJson, all in this crossing and in the caller's transaction (none is opened here). rowsJson is
   * [[positional values],..] or [{named},..] (tagged values, see Json). The cursors are drained and closed. On a failure the reply is the
   * usual error plus "at": the index of the failed row; the rows before it stay done.
   */
  @CEntryPoint(name = "arcadedb_n_exec_many")
  @SuppressWarnings("unchecked")
  public static CCharPointer execMany(final IsolateThread thread, final long h, final CCharPointer language, final CCharPointer text,
      final CCharPointer rowsJson) {
    int i = 0;
    try {
      final Database db = db(h);
      final String lang = str(language);
      final String sql = str(text);
      final List<Object> rows = (List<Object>) Json.parse(str(rowsJson));
      for (; i < rows.size(); i++) {
        final Object row = rows.get(i);
        final ResultSet rs = row instanceof Map<?, ?> m ? db.command(lang, sql, (Map<String, Object>) m)
            : db.command(lang, sql, ((List<Object>) row).toArray());
        if (rs != null) {
          while (rs.hasNext())
            rs.next();
          rs.close();
        }
      }
      return out("{\"ok\":true,\"n\":" + rows.size() + "}");
    } catch (final Throwable t) {
      final String e = errorJson(t);
      return out(e.substring(0, e.length() - 1) + ",\"at\":" + i + "}");
    }
  }

  /**
   * Documents (or vertices of a vertex type) from rows [{property: value},..], one record per row through newDocument/newVertex, set per
   * property and save, as DocumentBatcher.insertManyJson does on the JPype path; no transaction is opened or closed here.
   */
  @CEntryPoint(name = "arcadedb_n_insert_rows")
  public static CCharPointer insertRows(final IsolateThread thread, final long h, final CCharPointer type, final CCharPointer rowsJson) {
    try {
      final Database db = db(h);
      final String t = str(type);
      final Chars c = chars(rowsJson);
      return out("{\"ok\":true,\"n\":" + BulkOps.insertRows(db, t, c.b, c.n) + "}");
    } catch (final Throwable t) {
      return err(t);
    }
  }

  /** The bytes of a C string in a per-thread scratch array (grown on demand, zero-terminated at n): no String and no new array per call. */
  static final class Chars {
    byte[] b = new byte[1 << 16];
    int n;
  }

  private static final int SCRATCH_KEEP = 32 << 20; // a payload above this is read into a one-off array, not kept by the thread
  private static final ThreadLocal<Chars> CHARS = ThreadLocal.withInitial(Chars::new);

  static Chars chars(final CCharPointer p) {
    int n = 0;
    while (p.read(n) != 0)
      n++;
    final Chars c = CHARS.get();
    byte[] b = c.b;
    if (b.length <= n) {
      b = new byte[Math.max(n + 1, b.length * 2)];
      if (b.length <= SCRATCH_KEEP)
        c.b = b;
    }
    CTypeConversion.asByteBuffer(p, n).get(b, 0, n);
    b[n] = 0;
    if (b != c.b) {
      final Chars once = new Chars();
      once.b = b;
      once.n = n;
      return once;
    }
    c.n = n;
    return c;
  }

  static CCharPointer out(final String s) {
    final byte[] b = s.getBytes(StandardCharsets.UTF_8);
    final CCharPointer p = UnmanagedMemory.malloc(b.length + 1);
    // one bulk copy (Unsafe.copyMemory) and the terminating zero; this was a Java loop of p.write(i, b[i]), one byte per iteration
    CTypeConversion.asByteBuffer(p, b.length + 1).put(b, 0, b.length).put((byte) 0);
    return p;
  }
}
