// Per-call probe for the phase 5 images (GraalVM CE 25.4.4.1.1): args[0] = jvector provider (default | panama | native).
// Prints (1) direct euclidean_f32 ns/call on off-heap and heap segments when the provider is native, (2) ns/call of
// VectorUtil.squareL2Distance over 20k float vectors, 2M calls x 3, the same loop as the phase 3/4 probe.
import io.github.jbellis.jvector.vector.*;
import io.github.jbellis.jvector.vector.types.*;
import io.github.jbellis.jvector.vector.cnative.NativeSimdOps;
import java.lang.foreign.*;

public class Probe5 {
  public static void main(String[] a) throws Exception {
    final String prov = a.length > 0 ? a[0] : "default";
    System.setProperty("jvector.vectorization_provider", prov);
    long t0 = System.nanoTime();
    VectorizationProvider vp = VectorizationProvider.getInstance();
    System.out.println("provider=" + vp.getClass().getName() + " util=" + vp.getVectorUtilSupport().getClass().getName() + " init_ms=" + (System.nanoTime() - t0) / 1e6);
    int dim = 128;
    if (prov.equals("native")) {
      int n = 200_000;
      float[] x = new float[dim], y = new float[dim];
      for (int i = 0; i < dim; i++) { x[i] = i; y[i] = dim - i; }
      MemorySegment hx = MemorySegment.ofArray(x), hy = MemorySegment.ofArray(y);
      Arena arena = Arena.ofAuto();
      MemorySegment ox = arena.allocate(dim * 4L, 64), oy = arena.allocate(dim * 4L, 64);
      MemorySegment.copy(hx, 0, ox, 0, dim * 4L); MemorySegment.copy(hy, 0, oy, 0, dim * 4L);
      float acc = 0;
      for (int rep = 0; rep < 3; rep++) {
        long t = System.nanoTime();
        for (int k = 0; k < n; k++) acc += NativeSimdOps.euclidean_f32(ox, 0, oy, 0, dim);
        double off = (System.nanoTime() - t) / (double) n;
        t = System.nanoTime();
        for (int k = 0; k < n; k++) acc += NativeSimdOps.euclidean_f32(hx, 0, hy, 0, dim);
        double heap = (System.nanoTime() - t) / (double) n;
        System.out.println("direct euclidean_f32 off-heap ns/call=" + off + " heap ns/call=" + heap + " acc=" + acc);
      }
    }
    VectorTypeSupport vts = vp.getVectorTypeSupport();
    float[] x = new float[dim], y = new float[dim];
    for (int i = 0; i < dim; i++) { x[i] = i * 0.5f; y[i] = (dim - i) * 0.25f; }
    VectorFloat<?> vx = vts.createFloatVector(x), vy = vts.createFloatVector(y);
    float d = VectorUtil.squareL2Distance(vx, vy);
    double ref = 0; for (int i = 0; i < dim; i++) ref += (double) (x[i] - y[i]) * (x[i] - y[i]);
    System.out.println("l2=" + d + " ref=" + ref);
    int n = 20000;
    VectorFloat<?>[] vs = new VectorFloat<?>[n];
    java.util.Random r = new java.util.Random(1);
    for (int i = 0; i < n; i++) { float[] f = new float[dim]; for (int j = 0; j < dim; j++) f[j] = r.nextFloat(); vs[i] = vts.createFloatVector(f); }
    float acc = 0;
    for (int rep = 0; rep < 3; rep++) {
      long t = System.nanoTime();
      for (int k = 0; k < 2_000_000; k++) acc += VectorUtil.squareL2Distance(vs[k % n], vs[(k * 7 + 1) % n]);
      double ms = (System.nanoTime() - t) / 1e6;
      System.out.println("squareL2Distance 2M ms=" + ms + " ns/call=" + (ms * 1e6 / 2_000_000) + " acc=" + acc);
    }
  }
}
