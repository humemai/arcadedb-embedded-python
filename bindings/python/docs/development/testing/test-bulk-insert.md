# Bulk Insert Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_bulk_insert.py)

Tests for Database.insert_many and AsyncExecutor.create_record.

There are 14 tests.

## Test Cases

### 1) basic roundtrip

See the source for the exact assertions.

### 2) null values

See the source for the exact assertions.

### 3) empty

See the source for the exact assertions.

### 4) parallel

See the source for the exact assertions.

### 5) non json fallback

See the source for the exact assertions.

### 6) inside open transaction

See the source for the exact assertions.

### 7) create and wait

See the source for the exact assertions.

### 8) callback

See the source for the exact assertions.

### 9) float array column to columns

See the source for the exact assertions.

### 10) numpy columns

See the source for the exact assertions.

### 11) primitive batch matches object path

primitive=True must store exactly what the Object[] path stores.

### 12) repeated tag values are stored distinctly

Memoised string conversion must not conflate or alias tag values.

### 13) primitive batch accepts plain sequences

Lists, not just ndarrays: the batch path types each column itself.

### 14) vector column to dataframe

See the source for the exact assertions.

## Running

```bash
uv run pytest bindings/python/tests/test_bulk_insert.py -v
```
