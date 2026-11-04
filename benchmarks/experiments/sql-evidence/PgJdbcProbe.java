// pgJDBC DatabaseMetaData probe. Run in a JDK container with the driver jar on the classpath:
//   java -cp /w/postgresql.jar /w/PgJdbcProbe.java HOST PORT USER PASSWORD
// Prints one JSON line per step: {client, client_version, step, ok, error}.
import java.sql.*;

public class PgJdbcProbe {
    interface Step { void run(Connection c) throws Exception; }

    static String ver = "pgjdbc";

    static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ").replace("\r", " ");
    }

    static void emit(String step, boolean ok, String err) {
        System.out.println("{\"client\":\"pgjdbc\",\"client_version\":\"" + esc(ver) + "\",\"step\":\"" + step
                + "\",\"ok\":" + ok + ",\"error\":" + (ok || err == null ? "null" : "\"" + esc(err.length() > 400 ? err.substring(0, 400) : err) + "\"") + "}");
    }

    static void run(String name, Connection c, Step s) {
        try {
            s.run(c);
            emit(name, true, null);
        } catch (Exception e) {
            emit(name, false, e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    static int rows(ResultSet rs) throws SQLException {
        int n = 0;
        while (rs.next()) n++;
        if (n == 0) throw new IllegalStateException("no rows returned");
        return n;
    }

    public static void main(String[] a) throws Exception {
        String url = "jdbc:postgresql://" + a[0] + ":" + a[1] + "/sqlev?sslmode=disable";
        Connection conn;
        try {
            conn = DriverManager.getConnection(url, a[2], a[3]);
            ver = "pgjdbc " + conn.getMetaData().getDriverVersion();
            try (Statement st = conn.createStatement(); ResultSet rs = st.executeQuery("SELECT 1")) { rows(rs); }
            emit("connect", true, null);
        } catch (Exception e) {
            emit("connect", false, e.getClass().getSimpleName() + ": " + e.getMessage());
            return;
        }
        conn.setAutoCommit(true);
        run("list_tables", conn, c -> {
            boolean found = false;
            try (ResultSet rs = c.getMetaData().getTables(null, null, "%", new String[]{"TABLE"})) {
                while (rs.next()) if ("person".equalsIgnoreCase(rs.getString("TABLE_NAME"))) found = true;
            }
            if (!found) throw new IllegalStateException("Person not in getTables result");
        });
        run("list_columns", conn, c -> {
            try (ResultSet rs = c.getMetaData().getColumns(null, null, "Person", "%")) { rows(rs); }
        });
        run("select", conn, c -> {
            try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery("SELECT id, name FROM Person ORDER BY id LIMIT 5")) { rows(rs); }
        });
        run("select_param", conn, c -> {
            try (PreparedStatement ps = c.prepareStatement("SELECT id, name FROM Person WHERE id = ?")) {
                ps.setLong(1, 7);
                try (ResultSet rs = ps.executeQuery()) { rows(rs); }
            }
        });
        run("join", conn, c -> {
            try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery(
                    "SELECT p.name, c.name AS city FROM Person p JOIN City c ON p.city_id = c.id WHERE p.id < 10")) { rows(rs); }
        });
        run("group_by", conn, c -> {
            try (Statement st = c.createStatement(); ResultSet rs = st.executeQuery(
                    "SELECT city_id, count(*) AS n FROM Person GROUP BY city_id ORDER BY n DESC LIMIT 5")) { rows(rs); }
        });
        conn.close();
    }
}
