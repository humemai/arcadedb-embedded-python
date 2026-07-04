// Java-native baseline for the JPype-overhead benchmark.
//
// Runs against the SAME JARs and JRE bundled in the arcadedb-embedded wheel, with the
// SAME JVM flags arcadedb_embedded.jvm uses, so any latency delta vs the Python
// benchmark is attributable to the caller side (JPype boundary + binding logic), not
// to the engine, JVM, or flags.
//
// Workload shapes mirror the real examples in bindings/python/examples (07/08 ingest +
// OLAP scans, 02/09 graph, 11/12 vector, 13 fulltext, 14 lifecycle).
//
// Output protocol (parsed by the report step):
//   RESULT,<phase>,<layer>,<n>,<mean_us>,<p50_us>,<p95_us>,<p99_us>,<extra>
//   PARITY,<phase>,<layer>,<comma-joined values>
//
// Usage: OverheadBench <phase> <dataDir> <dbDir>
//   phases: vector-build | vector-bench | seed-docs | bench-query | bench-write
//           | seed-graph | bench-cypher | seed-text | bench-fulltext | bench-lifecycle

import com.arcadedb.database.Database;
import com.arcadedb.database.DatabaseFactory;
import com.arcadedb.database.RID;
import com.arcadedb.index.vector.LSMVectorIndex;
import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;
import com.arcadedb.schema.Type;
import com.arcadedb.utility.Pair;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Random;

public class OverheadBench {

  static final int WARMUP = 20;
  static final int MEASURED = 100;

  public static void main(final String[] args) throws Exception {
    final String phase = args[0];
    final Path dataDir = args.length > 1 ? Path.of(args[1]) : null;
    final String dbDir = args.length > 2 ? args[2] : null;

    switch (phase) {
    case "vector-build" -> vectorBuild(dataDir, dbDir);
    case "vector-bench" -> vectorBench(dataDir, dbDir);
    case "seed-docs" -> seedDocs(dbDir);
    case "bench-query" -> benchQuery(dbDir);
    case "bench-write" -> benchWrite(dbDir);
    case "seed-graph" -> seedGraph(dbDir);
    case "bench-cypher" -> benchCypher(dbDir);
    case "seed-text" -> seedText(dbDir);
    case "bench-fulltext" -> benchFulltext(dbDir);
    case "bench-lifecycle" -> benchLifecycle(dbDir);
    case "bench-async" -> benchAsync(dbDir);
    default -> throw new IllegalArgumentException("unknown phase: " + phase);
    }
  }

  // ---------- helpers ----------

  static float[][] readVectors(final Path file, final int count, final int dims) throws IOException {
    final byte[] bytes = Files.readAllBytes(file);
    final ByteBuffer buf = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
    final float[][] out = new float[count][dims];
    for (int i = 0; i < count; i++)
      for (int j = 0; j < dims; j++)
        out[i][j] = buf.getFloat();
    return out;
  }

  static int[] readMeta(final Path dataDir) throws IOException {
    // meta.json is flat; parse the few int fields without a JSON lib
    final String json = Files.readString(dataDir.resolve("meta.json"));
    return new int[] { jsonInt(json, "num_vectors"), jsonInt(json, "dimensions"),
        jsonInt(json, "num_queries_warmup"), jsonInt(json, "num_queries_measured"),
        jsonInt(json, "k"), jsonInt(json, "ef_search") };
  }

  static int jsonInt(final String json, final String key) {
    final var m = java.util.regex.Pattern.compile("\"" + key + "\"\\s*:\\s*(\\d+)").matcher(json);
    if (!m.find())
      throw new IllegalStateException("missing meta key " + key);
    return Integer.parseInt(m.group(1));
  }

  static void report(final String phase, final String layer, final long[] latenciesNs, final String extra) {
    final long[] sorted = latenciesNs.clone();
    Arrays.sort(sorted);
    final double mean = Arrays.stream(sorted).average().orElse(0) / 1e3;
    final double p50 = sorted[sorted.length / 2] / 1e3;
    final double p95 = sorted[(int) (sorted.length * 0.95)] / 1e3;
    final double p99 = sorted[Math.min(sorted.length - 1, (int) (sorted.length * 0.99))] / 1e3;
    System.out.printf("RESULT,%s,%s,%d,%.1f,%.1f,%.1f,%.1f,%s%n",
        phase, layer, sorted.length, mean, p50, p95, p99, extra == null ? "" : extra);
  }

  static String vectorToSqlLiteral(final float[] v) {
    final StringBuilder sb = new StringBuilder("[");
    for (int i = 0; i < v.length; i++) {
      if (i > 0) sb.append(',');
      sb.append(v[i]);
    }
    return sb.append(']').toString();
  }

  static LSMVectorIndex lsmIndex(final Database db, final String type, final String prop) {
    return (LSMVectorIndex) db.getSchema().getType(type)
        .getPolymorphicIndexByProperties(prop).getIndexesOnBuckets()[0];
  }

  // ---------- phase A/G: vector ----------

  static void vectorBuild(final Path dataDir, final String dbDir) throws IOException {
    final int[] meta = readMeta(dataDir);
    final int numVectors = meta[0], dims = meta[1];
    final float[][] vectors = readVectors(dataDir.resolve("vectors.bin"), numVectors, dims);

    final long t0 = System.nanoTime();
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir)) {
      try (final Database db = factory.create()) {
        db.transaction(() -> {
          final var type = db.getSchema().createDocumentType("VectorData");
          type.createProperty("id", Type.INTEGER);
          type.createProperty("vector", Type.ARRAY_OF_FLOATS);
          db.command("sql", String.format(
              "CREATE INDEX ON VectorData (vector) LSM_VECTOR METADATA { \"dimensions\": %d, \"similarity\": \"COSINE\" }",
              dims));
        });
        db.begin();
        for (int i = 0; i < numVectors; i++) {
          db.newDocument("VectorData").set("id", i).set("vector", vectors[i]).save();
          if ((i + 1) % 5000 == 0) {
            db.commit();
            db.begin();
          }
        }
        if (db.isTransactionActive())
          db.commit();
      }
    }
    System.out.printf("INFO,vector-build,ingest_s,%.1f%n", (System.nanoTime() - t0) / 1e9);
  }

  static void vectorBench(final Path dataDir, final String dbDir) throws IOException {
    final int[] meta = readMeta(dataDir);
    final int dims = meta[1], warm = meta[2], measured = meta[3], k = meta[4], ef = meta[5];
    final float[][] queries = readVectors(dataDir.resolve("queries.bin"), warm + measured, dims);

    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.open()) {
      final LSMVectorIndex index = lsmIndex(db, "VectorData", "vector");

      final long buildStart = System.nanoTime();
      index.findNeighborsFromVector(queries[0], k, ef);
      System.out.printf("INFO,vector-bench,graph_build_s,%.1f%n", (System.nanoTime() - buildStart) / 1e9);

      // ---- J-direct ----
      for (int i = 0; i < warm; i++)
        index.findNeighborsFromVector(queries[i], k, ef);
      final long[] lat = new long[measured];
      int total = 0;
      List<Pair<RID, Float>> firstResult = null;
      for (int q = 0; q < measured; q++) {
        final float[] query = queries[warm + q];
        final long s = System.nanoTime();
        final List<Pair<RID, Float>> res = index.findNeighborsFromVector(query, k, ef);
        lat[q] = System.nanoTime() - s;
        total += res.size();
        if (q == 0)
          firstResult = res;
      }
      report("vector", "J-direct", lat, "hits=" + (total / (double) measured));
      final StringBuilder parity = new StringBuilder();
      for (final Pair<RID, Float> p : firstResult)
        parity.append(p.getFirst().toString()).append(';');
      System.out.println("PARITY,vector,J-direct," + parity);

      // ---- J-SQL ---- (literal vector in SQL, exactly like VectorSearchLatencyBenchmark)
      for (int i = 0; i < warm; i++) {
        try (final ResultSet rs = db.query("sql", String.format(
            "SELECT vectorNeighbors('VectorData[vector]', %s, %d, %d) as res",
            vectorToSqlLiteral(queries[i]), k, ef))) {
          while (rs.hasNext()) rs.next();
        }
      }
      final long[] latSql = new long[measured];
      int totalSql = 0;
      for (int q = 0; q < measured; q++) {
        final String vecStr = vectorToSqlLiteral(queries[warm + q]);
        final long s = System.nanoTime();
        try (final ResultSet rs = db.query("sql", String.format(
            "SELECT vectorNeighbors('VectorData[vector]', %s, %d, %d) as res", vecStr, k, ef))) {
          while (rs.hasNext()) {
            final Result row = rs.next();
            final Object res = row.getProperty("res");
            if (res instanceof List<?> list)
              totalSql += list.size();
          }
        }
        latSql[q] = System.nanoTime() - s;
      }
      report("vector", "J-SQL", latSql, "hits=" + (totalSql / (double) measured));
    }
  }

  // ---------- phase B: docs / result materialization ----------

  static final String[] WORDS = { "graph", "vector", "database", "embedded", "python", "java",
      "index", "search", "engine", "arcade", "query", "result", "latency", "bench" };

  static void seedDocs(final String dbDir) {
    final Random rnd = new Random(42);
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.create()) {
      db.transaction(() -> {
        final var type = db.getSchema().createDocumentType("Doc");
        type.createProperty("id", Type.INTEGER);
        type.createProperty("score", Type.DOUBLE);
        type.createProperty("name", Type.STRING);
        type.createProperty("category", Type.STRING);
        type.createProperty("active", Type.BOOLEAN);
        type.createProperty("created", Type.DATETIME);
        type.createProperty("counts", Type.LIST);
        type.createProperty("embedding", Type.ARRAY_OF_FLOATS);
      });
      db.begin();
      for (int i = 0; i < 100_000; i++) {
        final float[] emb = new float[16];
        for (int j = 0; j < emb.length; j++)
          emb[j] = rnd.nextFloat();
        db.newDocument("Doc")
            .set("id", i)
            .set("score", rnd.nextDouble() * 100)
            .set("name", WORDS[i % WORDS.length] + "-" + i)
            .set("category", WORDS[rnd.nextInt(WORDS.length)])
            .set("active", (i & 1) == 0)
            .set("created", new java.util.Date(1700000000000L + i * 1000L))
            .set("counts", List.of(rnd.nextInt(100), rnd.nextInt(100), rnd.nextInt(100)))
            .set("embedding", emb)
            .save();
        if ((i + 1) % 5000 == 0) {
          db.commit();
          db.begin();
        }
      }
      if (db.isTransactionActive())
        db.commit();
      System.out.println("INFO,seed-docs,done,100000");
    }
  }

  static void benchQuery(final String dbDir) {
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.open()) {
      for (final int limit : new int[] { 1_000, 10_000, 100_000 }) {
        // full row materialization: read every scalar property (like an OLAP scan, ex. 08)
        benchQueryLayer(db, "J-allcols-" + limit,
            "SELECT id, score, name, category, active, created, counts FROM Doc LIMIT " + limit,
            new String[] { "id", "score", "name", "category", "active", "created", "counts" });
        // one column only
        benchQueryLayer(db, "J-onecol-" + limit, "SELECT id FROM Doc LIMIT " + limit,
            new String[] { "id" });
        // with the float-array column (recursion stressor in Python)
        benchQueryLayer(db, "J-embcol-" + limit, "SELECT id, embedding FROM Doc LIMIT " + limit,
            new String[] { "id", "embedding" });
      }
      // aggregation: engine-heavy, tiny result (ex. 08 OLAP)
      final long[] lat = new long[Math.max(10, MEASURED / 2)];
      for (int i = 0; i < 5; i++)
        drainAgg(db);
      for (int q = 0; q < lat.length; q++) {
        final long s = System.nanoTime();
        drainAgg(db);
        lat[q] = System.nanoTime() - s;
      }
      report("query", "J-groupby", lat, "");
    }
  }

  static void drainAgg(final Database db) {
    try (final ResultSet rs = db.query("sql",
        "SELECT category, count(*) as c, avg(score) as a FROM Doc GROUP BY category")) {
      while (rs.hasNext()) {
        final Result r = rs.next();
        r.getProperty("category");
        r.getProperty("c");
        r.getProperty("a");
      }
    }
  }

  static void benchQueryLayer(final Database db, final String layer, final String sql, final String[] cols) {
    final int reps = 12;
    long checksum = 0;
    final long[] lat = new long[reps];
    for (int r = -3; r < reps; r++) { // 3 warmup reps
      final long s = System.nanoTime();
      try (final ResultSet rs = db.query("sql", sql)) {
        while (rs.hasNext()) {
          final Result row = rs.next();
          for (final String c : cols) {
            final Object v = row.getProperty(c);
            if (v != null)
              checksum += v.hashCode();
          }
        }
      }
      if (r >= 0)
        lat[r] = System.nanoTime() - s;
    }
    report("query", layer, lat, "checksum=" + (checksum & 0xffff));
  }

  // ---------- phase C: write path ----------

  static void benchWrite(final String dbDir) {
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.create()) {
      db.transaction(() -> {
        final var type = db.getSchema().createDocumentType("W");
        type.createProperty("id", Type.INTEGER);
        type.createProperty("name", Type.STRING);
        type.createProperty("score", Type.DOUBLE);
      });
      // warmup 1k
      insertBatchSQL(db, 0, 1_000);
      // measured: 10k inserts via SQL command (mirrors examples 07/15 transactional ingest),
      // timing each db.command individually
      final long[] lat = new long[10_000];
      int i = 0;
      for (int batch = 0; batch < 10; batch++) {
        db.begin();
        for (int j = 0; j < 1_000; j++, i++) {
          final long s = System.nanoTime();
          db.command("sql", "INSERT INTO W SET id = ?, name = ?, score = ?", 1_000 + i, "n" + i, i * 0.5);
          lat[i] = System.nanoTime() - s;
        }
        db.commit();
      }
      report("write", "J-insert-sql", lat, "");
    }
  }

  static void insertBatchSQL(final Database db, final int base, final int n) {
    db.begin();
    for (int j = 0; j < n; j++)
      db.command("sql", "INSERT INTO W SET id = ?, name = ?, score = ?", base + j, "n" + j, j * 0.5);
    db.commit();
  }

  // ---------- phase D: cypher / graph ----------

  static void seedGraph(final String dbDir) {
    final Random rnd = new Random(7);
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.create()) {
      db.transaction(() -> {
        db.getSchema().createVertexType("Person");
        db.getSchema().createEdgeType("KNOWS");
      });
      final List<com.arcadedb.graph.MutableVertex> people = new ArrayList<>(10_000);
      db.begin();
      for (int i = 0; i < 10_000; i++) {
        final var v = db.newVertex("Person").set("id", i).set("name", "p" + i).set("age", 20 + (i % 50));
        v.save();
        people.add(v);
        if ((i + 1) % 2000 == 0) {
          db.commit();
          db.begin();
        }
      }
      db.commit();
      db.begin();
      for (int e = 0; e < 30_000; e++) {
        final var a = people.get(rnd.nextInt(people.size()));
        final var b = people.get(rnd.nextInt(people.size()));
        a.newEdge("KNOWS", b).save();
        if ((e + 1) % 2000 == 0) {
          db.commit();
          db.begin();
        }
      }
      if (db.isTransactionActive())
        db.commit();
      System.out.println("INFO,seed-graph,done,10000v/30000e");
    }
  }

  static void benchCypher(final String dbDir) {
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.open()) {
      // traversal-heavy, tiny result
      benchCypherQuery(db, "J-traverse",
          "MATCH (a:Person {id: 1})-[:KNOWS*1..2]->(b) RETURN count(b) AS c", MEASURED);
      // projection-heavy: 10k rows back
      benchCypherQuery(db, "J-project", "MATCH (p:Person) RETURN p.name AS name, p.age AS age", 12);
    }
  }

  static void benchCypherQuery(final Database db, final String layer, final String cypher, final int reps) {
    long checksum = 0;
    final long[] lat = new long[reps];
    final int warm = Math.max(3, reps / 10);
    for (int r = -warm; r < reps; r++) {
      final long s = System.nanoTime();
      try (final ResultSet rs = db.query("opencypher", cypher)) {
        while (rs.hasNext()) {
          final Result row = rs.next();
          for (final String p : row.getPropertyNames()) {
            final Object v = row.getProperty(p);
            if (v != null)
              checksum += v.hashCode();
          }
        }
      }
      if (r >= 0)
        lat[r] = System.nanoTime() - s;
    }
    report("cypher", layer, lat, "checksum=" + (checksum & 0xffff));
  }

  // ---------- phase E: fulltext ----------

  static void seedText(final String dbDir) {
    final Random rnd = new Random(13);
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.create()) {
      db.transaction(() -> {
        final var type = db.getSchema().createDocumentType("Article");
        type.createProperty("content", Type.STRING);
        db.command("sql", "CREATE INDEX ON Article (content) FULL_TEXT");
      });
      db.begin();
      for (int i = 0; i < 100_000; i++) {
        final StringBuilder sb = new StringBuilder();
        for (int w = 0; w < 12; w++)
          sb.append(WORDS[rnd.nextInt(WORDS.length)]).append(' ');
        db.newDocument("Article").set("content", sb.toString()).save();
        if ((i + 1) % 5000 == 0) {
          db.commit();
          db.begin();
        }
      }
      if (db.isTransactionActive())
        db.commit();
      System.out.println("INFO,seed-text,done,100000");
    }
  }

  static void benchFulltext(final String dbDir) {
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.open()) {
      final String sql = "SELECT content, $score FROM Article "
          + "WHERE SEARCH_INDEX('Article[content]', 'vector^2.0 graph') = true "
          + "ORDER BY $score DESC LIMIT 100";
      long checksum = 0;
      final long[] lat = new long[MEASURED];
      for (int r = -WARMUP; r < MEASURED; r++) {
        final long s = System.nanoTime();
        try (final ResultSet rs = db.query("sql", sql)) {
          while (rs.hasNext()) {
            final Result row = rs.next();
            final Object c = row.getProperty("content");
            if (c != null)
              checksum += c.hashCode();
          }
        }
        if (r >= 0)
          lat[r] = System.nanoTime() - s;
      }
      report("fulltext", "J-bm25", lat, "checksum=" + (checksum & 0xffff));
    }
  }

  // ---------- async executor (callback bridging counterpart) ----------

  static void benchAsync(final String dbDir) {
    try (final DatabaseFactory factory = new DatabaseFactory(dbDir); final Database db = factory.create()) {
      db.transaction(() -> {
        final var type = db.getSchema().createDocumentType("A");
        type.createProperty("id", Type.INTEGER);
        type.createProperty("name", Type.STRING);
      });

      // warmup
      for (int i = 0; i < 1_000; i++)
        db.async().command("sql", "INSERT INTO A SET id = ?, name = ?", null, i, "w" + i);
      db.async().waitCompletion();

      // no-callback throughput: 10k async inserts, one wall-clock number
      long s = System.nanoTime();
      for (int i = 0; i < 10_000; i++)
        db.async().command("sql", "INSERT INTO A SET id = ?, name = ?", null, 1_000 + i, "n" + i);
      db.async().waitCompletion();
      final long perInsertNoCb = (System.nanoTime() - s) / 10_000;
      report("async", "J-async-insert", new long[] { perInsertNoCb }, "total10k");

      // with a Java ok-callback per command
      final int[] done = { 0 };
      final com.arcadedb.database.async.AsyncResultsetCallback cb =
          new com.arcadedb.database.async.AsyncResultsetCallback() {
            @Override
            public void onComplete(final ResultSet resultset) {
              done[0]++;
            }
          };
      s = System.nanoTime();
      for (int i = 0; i < 10_000; i++)
        db.async().command("sql", "INSERT INTO A SET id = ?, name = ?", cb, 11_000 + i, "c" + i);
      db.async().waitCompletion();
      final long perInsertCb = (System.nanoTime() - s) / 10_000;
      report("async", "J-async-insert-callback", new long[] { perInsertCb }, "cb=" + done[0]);
    }
  }

  // ---------- phase H: lifecycle (mirrors example 14) ----------

  static void benchLifecycle(final String dbBase) throws IOException {
    final long[] createNs = new long[10];
    final long[] openNs = new long[10];
    final long[] firstQueryNs = new long[10];
    for (int i = 0; i < 10; i++) {
      final String p = dbBase + "/lc_" + i;
      long s = System.nanoTime();
      try (final DatabaseFactory f = new DatabaseFactory(p); final Database db = f.create()) {
        db.transaction(() -> db.getSchema().createDocumentType("T"));
      }
      createNs[i] = System.nanoTime() - s;

      s = System.nanoTime();
      try (final DatabaseFactory f = new DatabaseFactory(p); final Database db = f.open()) {
        openNs[i] = System.nanoTime() - s;
        s = System.nanoTime();
        try (final ResultSet rs = db.query("sql", "SELECT count(*) as c FROM T")) {
          while (rs.hasNext()) rs.next();
        }
        firstQueryNs[i] = System.nanoTime() - s;
      }
    }
    report("lifecycle", "J-create-close", createNs, "");
    report("lifecycle", "J-open", openNs, "");
    report("lifecycle", "J-first-query", firstQueryNs, "");
  }
}
