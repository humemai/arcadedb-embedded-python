/*
 * SPDX-License-Identifier: Apache-2.0
 *
 * Feasibility spike: C entry points over the ArcadeDB embedded engine and server, for a
 * GraalVM native-image shared library. Every string result is malloc'd and must be released
 * with arcadedb_free. Every result is a JSON text: {"ok":true,"result":...} or {"ok":false,"error":"..."}.
 */
package org.humemai.nativelib;

import com.arcadedb.ContextConfiguration;
import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.serializer.json.JSONArray;
import com.arcadedb.serializer.json.JSONObject;
import com.arcadedb.server.ArcadeDBServer;
import org.graalvm.nativeimage.IsolateThread;
import org.graalvm.nativeimage.UnmanagedMemory;
import org.graalvm.nativeimage.c.function.CEntryPoint;
import org.graalvm.nativeimage.c.type.CCharPointer;
import org.graalvm.nativeimage.c.type.CTypeConversion;
import org.graalvm.word.PointerBase;
import org.graalvm.word.WordFactory;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public final class ArcadeLib {
  private static final Map<Long, Database> DATABASES = new ConcurrentHashMap<>();
  private static final AtomicLong NEXT = new AtomicLong(1);
  private static volatile ArcadeDBServer server;

  private ArcadeLib() {
  }

  /** Opens (creating if absent) the database at path. Returns a handle, or 0 with the error in the result of arcadedb_last_error. */
  @CEntryPoint(name = "arcadedb_open")
  public static long open(final IsolateThread thread, final CCharPointer path) {
    try {
      final DatabaseFactory factory = new DatabaseFactory(CTypeConversion.toJavaString(path));
      final Database db = factory.exists() ? factory.open() : factory.create();
      final long handle = NEXT.getAndIncrement();
      DATABASES.put(handle, db);
      return handle;
    } catch (final Throwable t) {
      lastError = describe(t);
      return 0;
    }
  }

  private static volatile String lastError = "";

  @CEntryPoint(name = "arcadedb_last_error")
  public static CCharPointer lastError(final IsolateThread thread) {
    return toC(lastError);
  }

  /** Runs one command (any language: sql, sqlscript, opencypher...) and returns its rows as JSON. */
  @CEntryPoint(name = "arcadedb_command")
  public static CCharPointer command(final IsolateThread thread, final long handle, final CCharPointer language,
      final CCharPointer text, final CCharPointer paramsJson) {
    try {
      final Database db = DATABASES.get(handle);
      if (db == null)
        throw new IllegalArgumentException("unknown handle " + handle);
      final String paramsText = CTypeConversion.toJavaString(paramsJson);
      final Map<String, Object> params = paramsText == null || paramsText.isEmpty() ? Map.of() : new JSONObject(paramsText).toMap();
      final JSONArray rows = new JSONArray();
      try (final ResultSet rs = db.command(CTypeConversion.toJavaString(language), CTypeConversion.toJavaString(text), params)) {
        while (rs.hasNext()) {
          final Result r = rs.next();
          rows.put(r.toJSON());
        }
      }
      return toC(new JSONObject().put("ok", true).put("result", rows).toString());
    } catch (final Throwable t) {
      return toC(new JSONObject().put("ok", false).put("error", describe(t)).toString());
    }
  }

  @CEntryPoint(name = "arcadedb_close")
  public static int close(final IsolateThread thread, final long handle) {
    try {
      final Database db = DATABASES.remove(handle);
      if (db == null)
        return 1;
      db.close();
      return 0;
    } catch (final Throwable t) {
      lastError = describe(t);
      return 2;
    }
  }

  /** Starts the in-process HTTP server (rootPath holds databases/). Returns 0 on success. */
  @CEntryPoint(name = "arcadedb_server_start")
  public static int serverStart(final IsolateThread thread, final CCharPointer rootPath, final int httpPort,
      final CCharPointer rootPassword) {
    try {
      final ContextConfiguration config = new ContextConfiguration();
      config.setValue("arcadedb.server.rootPath", CTypeConversion.toJavaString(rootPath));
      config.setValue("arcadedb.server.rootPassword", CTypeConversion.toJavaString(rootPassword));
      config.setValue("arcadedb.server.mode", "development");
      config.setValue("arcadedb.server.httpIncomingHost", "127.0.0.1");
      config.setValue("arcadedb.server.httpIncomingPort", httpPort);
      server = new ArcadeDBServer(config);
      server.start();
      return 0;
    } catch (final Throwable t) {
      lastError = describe(t);
      return 1;
    }
  }

  @CEntryPoint(name = "arcadedb_server_stop")
  public static int serverStop(final IsolateThread thread) {
    try {
      if (server != null)
        server.stop();
      server = null;
      return 0;
    } catch (final Throwable t) {
      lastError = describe(t);
      return 1;
    }
  }

  @CEntryPoint(name = "arcadedb_free")
  public static void free(final IsolateThread thread, final PointerBase ptr) {
    if (ptr.isNonNull())
      UnmanagedMemory.free(ptr);
  }

  private static String describe(final Throwable t) {
    final StringBuilder sb = new StringBuilder(t.getClass().getName()).append(": ").append(t.getMessage());
    Throwable c = t.getCause();
    for (int i = 0; c != null && i < 3; i++, c = c.getCause())
      sb.append(" <- ").append(c.getClass().getName()).append(": ").append(c.getMessage());
    return sb.toString();
  }

  private static CCharPointer toC(final String s) {
    final byte[] b = s.getBytes(StandardCharsets.UTF_8);
    final CCharPointer p = UnmanagedMemory.malloc(b.length + 1);
    for (int i = 0; i < b.length; i++)
      p.write(i, b[i]);
    p.write(b.length, (byte) 0);
    return p;
  }
}
