# Results

Let's see how we can improve. we'll run

```bash
cd /mnt/ssd2/repos/arcadedb-embedded-python/bindings/python && /mnt/ssd2/repos/arcadedb-embedded-python/.venv/bin/python scripts/profile-python/profile_bindings.py --runs 5 --scenarios result_lazy_scan,result_to_list,result_iter_chunks,document_to_dict,nested_conversion,graph_traversal,graph_batch_ingest,vector_search --records 5000 --graph-vertices 1000 --graph-degree 3 --nested-width 250 --vector-records 1500 --query-runs 100 --heap-size 1g
```

## Commit hash: `100c51ee4dcf699877d333d9e66d6972cfbfced1`
