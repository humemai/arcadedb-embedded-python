## 07_stackoverflow_tables_oltp

### Dataset: stackoverflow-large

| db           | threads | transactions | batch_size | mem_limit | preload_rows_total | preload_time_s | index_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib    |
| ------------ | ------- | ------------ | ---------- | --------- | ------------------ | -------------- | ------------ | ---------------- | ------------ | ------ | ------------ | --------- |
| arcadedb_sql | 1       | 250,000      | 10,000     | 8g        | 22,649,754         | 783.969        | 1,179.189    | 550.472          | 454.156      | 15.048 | 7,614.371    | 8,756.41  |
| arcadedb_sql | 4       | 250,000      | 10,000     | 8g        | 22,649,754         | 412.823        | 943.983      | 465.265          | 537.328      | 40.147 | 6,040.414    | 8,756.473 |

## 08_stackoverflow_tables_olap

### Dataset: stackoverflow-large

| db           | batch_size | mem_limit | threads | query_runs |  load_s |   index_s |    query_s | rss_peak_mib |    du_mib |
| ------------ | ---------: | --------- | ------: | ---------: | ------: | --------: | ---------: | -----------: | --------: |
| arcadedb_sql |     10,000 | 8g        |       1 |        100 | 720.561 | 1,234.116 | 11,030.042 |    6,915.301 | 8,947.781 |
| arcadedb_sql |     10,000 | 8g        |       4 |        100 | 377.287 | 1,048.143 |  9,651.969 |    6,429.398 | 8,947.777 |

## 09_stackoverflow_graph_oltp

### Dataset: stackoverflow-large

| db              | threads | transactions | batch_size | mem_limit | load_node_count | load_edge_count | index_time_s | load_time_s | oltp_crud_time_s | throughput_s | p95_ms | rss_peak_mib | du_mib     |
| --------------- | ------- | ------------ | ---------- | --------- | --------------- | --------------- | ------------ | ----------- | ---------------- | ------------ | ------ | ------------ | ---------- |
| arcadedb_cypher | 1       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 155.333      | 6,088.078   | 541.346          | 461.812      | 5.694  | 17,128.445   | 3,972.051  |
| arcadedb_cypher | 4       | 250,000      | 10,000     | 32g       | 7,782,816       | 9,770,001       | 133.167      | 6,238.478   | 245.873          | 1,016.783    | 15.274 | 19,118.336   | 12,753.121 |

## 10_stackoverflow_graph_olap

### Dataset: stackoverflow-large

| db              | batch_size | mem_limit | threads | query_runs |    load_s | index_s |   query_s | rss_peak_mib |    du_mib |
| --------------- | ---------: | --------- | ------: | ---------: | --------: | ------: | --------: | -----------: | --------: |
| arcadedb_cypher |     10,000 | 32g       |       1 |        100 | 6,035.364 | 131.903 | 2,846.361 |   29,819.965 | 3,968.629 |
| arcadedb_cypher |     10,000 | 32g       |       4 |        100 | 3,738.254 | 115.099 | 2,098.662 |   25,973.844 | 12,750.77 |

## Notes

- I ran these benchmarks again, cuz there have been some updates in graphs, e.g., OLAP.
- I see that example 10 has less query time time now, but at the same time, memory consumption is higher. Bulk graph ingest still takes a long time.
