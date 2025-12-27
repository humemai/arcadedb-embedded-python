# FAISS IVF_FLAT Benchmark

## Dataset Information

**GloVe-100-Angular**

- Vectors: ~1.2M
- Dimensions: 100
- Queries: 10,000
- Metric: Cosine

- **Name**: glove-100-angular
- **Source**: http://ann-benchmarks.com/glove-100-angular.hdf5
- **Metric**: Cosine
- **K Values**: [10]
- **Algorithm**: ivf_flat

**Note:**

- **Metric Equations**:
  - **Euclidean**: Similarity = $1 / (1 + d^2)$ (Higher is better)
  - **Cosine**: Distance = $(1 - \cos(\theta)) / 2$ (Lower is better)

## dataset_size: full

- **Dimensions**: 100
- **Vector Count**: 1183514
- **Queries**: 10000
- **Data Load Time**: 0.3564s
- **Ground Truth Time**: 0.0000s
- **Index Build Time**: 0.7593s
- **Total Time**: 38.55 min (2313.02s)

### k = 10

| nlist | nprobe | Recall (Before) | Recall (After) | Latency (ms) (Before) | Latency (ms) (After) | Build (s) | Warmup (s) | Open (s) |
| ----- | ------ | --------------- | -------------- | --------------------- | -------------------- | --------- | ---------- | -------- |
| 64    | 16     | 0.9601          | 0.9601         | 9.29                  | 8.92                 | 0.76      | 0.0006     | 0.2358   |
| 64    | 32     | 0.9917          | 0.9917         | 17.62                 | 18.21                | 0.76      | 0.0006     | 0.2358   |
| 64    | 64     | 1.0000          | 1.0000         | 33.01                 | 33.58                | 0.76      | 0.0006     | 0.2358   |
| 128   | 16     | 0.9277          | 0.9277         | 4.56                  | 4.52                 | 1.34      | 0.0005     | 0.3196   |
| 128   | 32     | 0.9709          | 0.9709         | 8.94                  | 8.99                 | 1.34      | 0.0005     | 0.3196   |
| 128   | 64     | 0.9937          | 0.9937         | 17.33                 | 17.82                | 1.34      | 0.0005     | 0.3196   |
| 256   | 16     | 0.8941          | 0.8941         | 2.24                  | 2.32                 | 2.44      | 0.0003     | 0.3240   |
| 256   | 32     | 0.9438          | 0.9438         | 4.40                  | 4.75                 | 2.44      | 0.0003     | 0.3240   |
| 256   | 64     | 0.9783          | 0.9783         | 8.71                  | 8.51                 | 2.44      | 0.0003     | 0.3240   |
| 512   | 16     | 0.8574          | 0.8574         | 1.14                  | 1.06                 | 4.46      | 0.0002     | 0.2850   |
| 512   | 32     | 0.9140          | 0.9140         | 2.48                  | 2.36                 | 4.46      | 0.0002     | 0.2850   |
| 512   | 64     | 0.9556          | 0.9556         | 4.37                  | 4.36                 | 4.46      | 0.0002     | 0.2850   |
