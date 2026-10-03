# ResultSet Arrow Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_resultset_arrow.py)

Tests for ResultSet.to_arrow().

The whole module skips when pyarrow is not installed.

## Test Cases

### 1) to arrow basic types

`name` and `n` read back exactly; `n`, `x`, and `name` have integer, floating-point, and string Arrow types; `ok` is selected but not checked.

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

## Schemaless and DECIMAL data (`test_columnar_readers.py`)

`to_columns()`, `to_dataframe()`, and `to_arrow()` read rows over the bridge in batches, and these tests
run at batch sizes 25,000, 2, and 1 because the fixes are about the answer not depending on where the
batch boundaries fall. They need the bridge jar built from the tree (the wheel build does that); on the
bridge jar and Python of 2026-10-02, 29 of the 31 fail.

- **a property the first row lacks is kept** (humemai/arcadedb-embedded-python#113): three events where
  `reason` first appears on the second; `to_columns()` and `to_arrow()` return `n`, `kind`, `reason` with
  `reason == [None, "timeout", "user"]` at every batch size, and `to_dataframe()` keeps the column.
- **a late numeric property keeps its type**: `level` absent from the first three rows; `to_columns()` is
  float64 with NaN, `to_arrow()` int64 with nulls, at every batch size.
- **Arrow types do not depend on batch size** (#114): five readings where `level` is missing on rows 3 and 4
  and `tags` is empty on rows 2 and 4; `level` is int64 and `tags` is `list<string>` at every batch size
  (they were strings at batch size 2 and 1), and `to_columns()` agrees.
- **a column of mixed types becomes strings in Arrow**: an int in one row and `'seven'` in the next, in one
  batch, raised a raw `ArrowInvalid`; it is now the string column `["1", "seven"]`.
- **a DECIMAL column keeps every digit** (#115): a 36-digit amount, whole amounts only, whole and fractional,
  a whole amount above 2**63, and one with a null, each at batch size 25,000 and 1: an object array of exact
  `Decimal` from `to_columns()` and `to_dataframe()`, a decimal Arrow column from `to_arrow()`.
- **batches of different scale unify**: `2`, `2.5`, `30` at batch size 1 is one decimal type.
- **wider than decimal128 stays exact**: a 41-digit value is `decimal256(41, 1)`, an 80-digit one an exact
  string.
- **pinned columns are read as given**: `columns=["reason", "n"]` returns exactly those, in that order, and a name no row has is an all-null column.
- **`export_to_csv` header is the union** (#113): the header names every property of the rows; a column that
  first appears after the first batch of 10,000 rows raises `ArcadeDBError` naming it.

## Running

```bash
uv run pytest bindings/python/tests/test_resultset_arrow.py -v
uv run pytest bindings/python/tests/test_columnar_readers.py -v
```
