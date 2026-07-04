// Round-3 probe: batched row transport. Serializes up to `max` rows of a
// ResultSet into ONE JSON-array string Java-side, so Python pays a single
// JPype crossing per batch instead of 2+C crossings per row, then parses
// with the C-fast json module.
//
// Probe-only for now: compiled into a jar dropped into the wheel's jars/
// directory. If validated, the production home is a bridge jar built during
// the wheel build (or upstreamed next to the engine).

import com.arcadedb.query.sql.executor.Result;
import com.arcadedb.query.sql.executor.ResultSet;

public final class RowBatcher {

  private RowBatcher() {
  }

  /** Serialize up to max rows into a JSON array string; empty array when drained. */
  public static String nextJsonBatch(final ResultSet rs, final int max) {
    final StringBuilder sb = new StringBuilder(64 * 1024);
    sb.append('[');
    int n = 0;
    while (n < max && rs.hasNext()) {
      final Result row = rs.next();
      if (n > 0)
        sb.append(',');
      sb.append(row.toJSON().toString());
      n++;
    }
    return sb.append(']').toString();
  }
}
