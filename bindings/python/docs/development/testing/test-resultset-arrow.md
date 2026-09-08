# ResultSet Arrow Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_resultset_arrow.py)

Tests for ResultSet.to_arrow().

There are 7 tests.

## Test Cases

### 1) to arrow basic types

Ints, floats, strings and bools survive the round trip with types.

### 2) to arrow keeps int64 with nulls

A nullable integer stays an integer here; to_columns turns it into float64.

### 3) to arrow keeps bool with nulls

A nullable boolean stays a bool column rather than becoming a list.

### 4) to arrow nullable strings

Strings are wrapped from the offsets+blob buffer, nulls included.

### 5) to arrow multi batch

More rows than one batch: chunks must concatenate, not truncate.

### 6) to arrow empty

An empty result is an empty table, not None and not an error.

### 7) to arrow matches to columns when not null

With no nulls the two paths must agree; only null handling differs.

## Running

```bash
uv run pytest bindings/python/tests/test_resultset_arrow.py -v
```
