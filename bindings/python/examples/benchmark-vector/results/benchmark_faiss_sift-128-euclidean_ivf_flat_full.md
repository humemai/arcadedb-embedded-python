# FAISS IVF_FLAT Benchmark

## Dataset Information

**SIFT-128-Euclidean**
- Vectors: 1,000,000
- Dimensions: 128
- Queries: 10,000
- Metric: Euclidean

- **Name**: sift-128-euclidean
- **Source**: http://ann-benchmarks.com/sift-128-euclidean.hdf5
- **Metric**: Euclidean
- **K Values**: [10]
- **Algorithm**: ivf_flat

**Note:**
- **Metric Equations**:
  - **Euclidean**: Similarity = $1 / (1 + d^2)$ (Higher is better)
  - **Cosine**: Distance = $(1 - \cos(\theta)) / 2$ (Lower is better)

## dataset_size: full

- **Dimensions**: 128
- **Vector Count**: 1000000
- **Queries**: 10000
- **Data Load Time**: 0.2714s
- **Ground Truth Time**: 0.0000s
- **Index Build Time**: 1.1082s
- **Total Time**: 41.12 min (2467.16s)

### k = 10

| nlist | nprobe | Recall (Before) | Recall (After) | Latency (ms) (Before) | Latency (ms) (After) | Build (s) | Warmup (s) | Open (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 64 | 16 | 0.9988 | 0.9988 | 10.20 | 10.19 | 1.11 | 0.0010 | 0.3905 |
| 64 | 32 | 0.9994 | 0.9994 | 18.36 | 18.32 | 1.11 | 0.0010 | 0.3905 |
| 64 | 64 | 0.9994 | 0.9994 | 38.91 | 38.61 | 1.11 | 0.0010 | 0.3905 |
| 128 | 16 | 0.9952 | 0.9952 | 5.11 | 5.02 | 1.47 | 0.0006 | 0.3196 |
| 128 | 32 | 0.9992 | 0.9992 | 9.96 | 9.94 | 1.47 | 0.0006 | 0.3196 |
| 128 | 64 | 0.9993 | 0.9993 | 18.61 | 18.40 | 1.47 | 0.0006 | 0.3196 |
| 256 | 16 | 0.9834 | 0.9834 | 2.79 | 2.55 | 2.07 | 0.0004 | 0.4267 |
| 256 | 32 | 0.9972 | 0.9972 | 4.97 | 4.58 | 2.07 | 0.0004 | 0.4267 |
| 256 | 64 | 0.9993 | 0.9993 | 9.47 | 7.54 | 2.07 | 0.0004 | 0.4267 |
| 512 | 16 | 0.9624 | 0.9624 | 0.88 | 0.87 | 3.46 | 0.0002 | 0.2678 |
| 512 | 32 | 0.9908 | 0.9908 | 1.72 | 1.62 | 3.46 | 0.0002 | 0.2678 |
| 512 | 64 | 0.9986 | 0.9986 | 3.14 | 3.24 | 3.46 | 0.0002 | 0.2678 |
