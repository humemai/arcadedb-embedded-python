There have been some changes.

1. As for document bulk ingest, now I use async SQL insert, as it's faster.
2. As for graph bulk ingest, now I use `GraphBatch`, which is a new java api to add bulk graph data.
3. Graph OLAP queries have been updated too.
4. Now as for non-range values, I use HASH index, instead of LSM index

## 07_stackoverflow_tables_oltp

### Dataset: stackoverflow-large

| db           | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib   |
| ------------ | ------- | ------------ | ---------- | --------- | ------------------ | -------------- | ------------ | ---------------- | ------------ | ------ | ------------ | -------- |
| arcadedb_sql | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 857.024        | 961.97       | 633.084          | 394.892      | 15.669 | 7,594.062    | 8,756.41 |
| arcadedb_sql | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 463.906        | 866.117      | 469.48           | 532.504      | 42.117 | 7,197.27     | 8,756.41 |

## 08_stackoverflow_tables_olap

### Dataset: stackoverflow-large

| db           | batch_size | mem_limit | threads | query_runs | ingest_mode       |  load_s |  index_s |    query_s | rss_peak_mib |    du_mib |
| ------------ | ---------: | --------- | ------: | ---------: | ----------------- | ------: | -------: | ---------: | -----------: | --------: |
| arcadedb_sql |     10,000 | 8g        |       1 |        100 | bulk_tuned_insert | 746.905 | 1,067.28 | 12,141.284 |    6,892.363 | 8,947.773 |
| arcadedb_sql |     10,000 | 8g        |       4 |        100 | bulk_tuned_insert | 430.836 |  873.472 | 13,620.748 |    7,052.184 | 8,947.773 |

## 09_stackoverflow_graph_oltp

### Dataset: stackoverflow-large

| db              | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | index_time_s | load_time_s | counts_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib     |
| --------------- | ------- | ------------ | ---------- | --------- | --------------- | --------------- | ------------ | ----------- | ------------- | ---------------- | ------------ | ------ | ------------ | ---------- |
| arcadedb_cypher | 1       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 149.889      | 6,914.567   | 0.001         | 666.779          | 374.937      | 6.213  | 17,154.641   | 3,972.059  |
| arcadedb_cypher | 4       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 135.821      | 6,789.425   | 0.002         | 356.979          | 700.321      | 19.377 | 20,666.551   | 12,753.051 |

## 10_stackoverflow_graph_olap

### Dataset: stackoverflow-large

| db              | batch_size | mem_limit | threads | query_runs |    load_s | index_s |   query_s | rss_peak_mib |    du_mib |
| --------------- | ---------: | --------- | ------: | ---------: | --------: | ------: | --------: | -----------: | --------: |
| arcadedb_cypher |     10,000 | 32g       |       1 |        100 | 5,275.918 | 124.897 | 3,579.275 |    19,691.93 | 3,968.625 |
| arcadedb_cypher |     10,000 | 32g       |       4 |        100 | 4,213.075 | 118.659 | 3,080.738 |   22,526.727 | 12,750.77 |

## Notes

- The biggest gain was shorter index time, especially for document type data, less graph data ingest time, and less graph OLAP time, although they are not a huge amount.
- The numbers are not perfect, we'll have to run them at least three times and report the mean and std.
- As you can see from example 09 and 10, 32GB memory was allocated to ArcadeDB containers, since they go OoM, if they have less memory allocated. Other dbs tested for the same examples require far less memory (4 times less)
- Note that sqlite / duckdb are embedded relational dbs. As for example 09 and 10, I've "repurposed" them to behave like a graph db, yet they were surprisingly competitive. Of course, the downside is that this approach requires them to be always repurposed for the given task.
