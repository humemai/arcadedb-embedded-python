# FAISS HNSW Benchmark

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
- **Algorithm**: hnsw

**Note:**
- **Metric Equations**:
  - **Euclidean**: Similarity = $1 / (1 + d^2)$ (Higher is better)
  - **Cosine**: Distance = $(1 - \cos(\theta)) / 2$ (Lower is better)

## dataset_size: full

- **Dimensions**: 128
- **Vector Count**: 1000000
- **Queries**: 10000
- **Data Load Time**: 0.1772s
- **Ground Truth Time**: 0.0000s
- **Index Build Time**: 804.4697s
- **Total Time**: 84.69 min (5081.51s)

### k = 10

| M | efConstruction | efConstructionFactor | efSearch | Recall (Before) | Recall (After) | Latency (ms) (Before) | Latency (ms) (After) | Build (s) | Warmup (s) | Open (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | 128 | 8 | 32 | 0.9067 | 0.9067 | 0.26 | 0.19 | 804.47 | 0.0006 | 0.4797 |
| 16 | 128 | 8 | 64 | 0.9642 | 0.9642 | 0.33 | 0.48 | 804.47 | 0.0006 | 0.4797 |
| 16 | 128 | 8 | 128 | 0.9891 | 0.9891 | 0.78 | 0.89 | 804.47 | 0.0006 | 0.4797 |
| 16 | 256 | 16 | 32 | 0.9176 | 0.9176 | 0.18 | 0.17 | 1511.62 | 0.0003 | 0.4327 |
| 16 | 256 | 16 | 64 | 0.9725 | 0.9725 | 0.23 | 0.27 | 1511.62 | 0.0003 | 0.4327 |
| 16 | 256 | 16 | 128 | 0.9929 | 0.9929 | 0.62 | 0.57 | 1511.62 | 0.0003 | 0.4327 |
| 32 | 256 | 8 | 32 | 0.9460 | 0.9460 | 0.18 | 0.16 | 962.37 | 0.0002 | 0.3935 |
| 32 | 256 | 8 | 64 | 0.9839 | 0.9839 | 0.26 | 0.28 | 962.37 | 0.0002 | 0.3935 |
| 32 | 256 | 8 | 128 | 0.9960 | 0.9960 | 0.49 | 0.50 | 962.37 | 0.0002 | 0.3935 |
| 32 | 512 | 16 | 32 | 0.9533 | 0.9533 | 0.17 | 0.18 | 1708.78 | 0.0002 | 0.3850 |
| 32 | 512 | 16 | 64 | 0.9876 | 0.9876 | 0.30 | 0.30 | 1708.78 | 0.0002 | 0.3850 |
| 32 | 512 | 16 | 128 | 0.9972 | 0.9972 | 0.54 | 0.55 | 1708.78 | 0.0002 | 0.3850 |
