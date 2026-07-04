import com.arcadedb.database.DatabaseFactory;

public class HangRepro {
  public static void main(String[] args) {
    try (DatabaseFactory f = new DatabaseFactory("/tmp/definitely_missing_db")) {
      f.open();
    } catch (Exception e) {
      System.out.println("caught: " + e.getClass().getSimpleName());
    }
    System.out.println("main returning; JVM should exit now");
  }
}
