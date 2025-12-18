# Vector Search Benchmark: ArcadeDB (JVector) vs FAISS

## TL;DR
*   **Speed:** ArcadeDB (JVector) is surprisingly fast, often matching or beating in-memory FAISS.
*   **Recall:** ArcadeDB has much lower recall than FAISS (likely due to lazy loading issues).
*   **Persistence:** Works correctly, but has a significant "warmup" latency on the first query.
*   **Verdict:** Promising performance, but recall issues need addressing for high-precision production use.

This project benchmarks the performance and accuracy of **ArcadeDB's embedded Python bindings (JVector)** against **FAISS (HNSW)**, a standard in-memory vector search library.

The goal is to evaluate ArcadeDB's suitability for vector search tasks, specifically focusing on **Recall@k**, **Latency**, and **Persistence**.

## Key Findings

### 1. Performance (Speed)
**JVector is surprisingly fast.**
Despite being a persistent database solution, ArcadeDB's JVector implementation demonstrates search latencies that are often comparable to, and in some cases faster than, FAISS (which operates entirely in memory). This is a strong indicator of the efficiency of the underlying JVector implementation.

### 2. Recall & Accuracy
**JVector's recall is currently lower than FAISS.**
While FAISS consistently achieves high recall (>0.99) with appropriate parameter tuning, JVector struggles to match this level of accuracy, particularly as $k$ increases (e.g., $k=50$).
*   **Note:** Discussions with ArcadeDB authors suggest this discrepancy might be due to **"lazy loading"** mechanisms within the database, where the graph is not fully traversed or loaded during the search, leading to missed candidates.
*   **Implication:** For production use cases requiring strict high-precision recall, this is currently a limiting factor.

### 3. Persistence & Warmup
**Persistence is robust, but "Warmup" is significant.**
*   **Robustness:** We verified that the vector index is not corrupted or lost after closing and reopening the database. Recall metrics remained consistent before and after a restart.
*   **Warmup Time:** We observed a significant latency spike (warmup time) during the first query after opening the database.
*   **Hypothesis:** This suggests that the persistent vector index might be undergoing a lazy load or partial rebuild process upon the first access, rather than being fully ready immediately after the database opens.

### 4. Note on Qdrant
**Qdrant was excluded from the final report.**
Initial benchmarks included `qdrant-client`, but it was excluded due to anomalous results (unexpectedly slow performance paired with consistently perfect recall). This likely indicates a configuration or parameter issue in the test setup rather than a fundamental issue with Qdrant itself.

## Datasets

The benchmark utilizes standard ANN datasets:
*   **SIFT-128-Euclidean**: 1M vectors, 128 dimensions (Metric: Euclidean)
*   **GloVe-100-Angular**: 1.2M vectors, 100 dimensions (Metric: Cosine)

## Results

Detailed markdown reports are generated for each dataset

### JVector

*   [SIFT-128 Results](benchmark_results_sift-128-euclidean.md)
*   [GloVe-100 Results](benchmark_results_glove-100-angular.md)

### FAISS (HNSW)

*   [SIFT-128 Results](benchmark_faiss_sift-128-euclidean.md)
*   [GloVe-100 Results](benchmark_faiss_glove-100-angular.md)
