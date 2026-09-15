# ResultSet Arrow Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_resultset_arrow.py)

Tests for ResultSet.to_arrow().

There are 10 tests.

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

### 6) to arrow multi batch int then float column

A column that is int in one batch and float in the next is a legal result set, since
ArcadeDB is schemaless per document, and each batch's type is inferred on its own. The
chunks are widened to float64 so they concatenate (#7108).

### 7) to arrow multi batch mixed type degrades to string

Numeric in one batch and a string in another has no common numeric type, so the column
degrades to string rather than raising at concatenation.

### 8) to arrow multi batch non representable int forces string fallback

int64 values outside float64's exact ±2^53 range next to a batch of floats: pyarrow's
cast is safe by default and refuses the lossy widening, so the column falls back to
string instead of raising.

### 9) to arrow empty

An empty result is an empty table, not None and not an error.

### 10) to arrow matches to columns when not null

With no nulls the two paths must agree; only null handling differs.

## Running

```bash
uv run pytest bindings/python/tests/test_resultset_arrow.py -v
```
