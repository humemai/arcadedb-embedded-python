# Query Languages Guide

!!! warning "Known engine issues"
    Three open ArcadeDB bugs can return a wrong answer or change the wrong rows without an
    error: a unique composite index read by its first property, a SQL `UPDATE` that moves an
    indexed key, and index range reads inside a transaction that has written. See
    [Known Engine Issues](../known-issues.md) for the versions and the workarounds.

The bindings run SQL and OpenCypher through `db.query()` and `db.command()`. Use them
for schema, CRUD, and graph operations: SQL for relational-style work and OpenCypher
for graph traversals.

## Best Practice: Use DSL for CRUD

For creating, updating, and managing data, prefer SQL/OpenCypher statements:

### Creating Documents

```python
# Create schema
db.command("sql", "CREATE DOCUMENT TYPE Task")
db.command("sql", "CREATE PROPERTY Task.title STRING")
db.command("sql", "CREATE PROPERTY Task.completed BOOLEAN")

# Insert using SQL (RECOMMENDED)
with db.transaction():
    db.command(
        "sql",
        "INSERT INTO Task SET title = ?, completed = ?, tags = ?",
        "Buy groceries",
        False,
        ["shopping", "urgent"],
    )
```

### Creating Vertices

```python
# Create schema
db.command("sql", "CREATE VERTEX TYPE Person")
db.command("sql", "CREATE EDGE TYPE Knows")

# Insert using SQL (RECOMMENDED)
with db.transaction():
    db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Alice", 30)
    db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Bob", 25)
```

### Bulk Inserts (preferred: `insert_many` and `graph_batch`)

For bulk document ingest, use `db.insert_many(...)`; for bulk graph ingest, use
`db.graph_batch(...)`. Both batch rows across the FFI boundary once per call. Chunked
SQL transactions are still a good fit when you want manual control over each statement.

```python
# Chunked SQL transactions: manual control, one statement at a time
chunk_size = 500
for start in range(0, len(people_data), chunk_size):
    with db.transaction():
        for name, age, city in people_data[start : start + chunk_size]:
            db.command(
                "sql",
                "INSERT INTO Person SET name = ?, age = ?, city = ?",
                name,
                age,
                city,
            )

# Chunked transactions are the per-statement option for embedded bulk work.
# Higher-level batch APIs also exist: `Database.insert_many(...)` for documents
# and `Database.graph_batch(...)` for graphs.
```

## SQL for Queries

### Basic Queries

```python
# Count using efficient method (RECOMMENDED)
count = db.count_type("Person")

# Query all with ordering
result = db.query("sql", "SELECT FROM Person ORDER BY name")
for person in result:
    print(person.get("name"))

# Query with WHERE
result = db.query("sql", "SELECT FROM Task WHERE priority = ? AND completed = ?", "high", False)
tasks = result.to_list()
for task in tasks:
    title = task["title"]
    tags = task["tags"]  # Automatically Python list
    print(f"{title}: {', '.join(tags)}")

# NULL checks
result = db.query(
    "sql",
    "SELECT name, phone, verified FROM Person WHERE email IS NULL"
)
```

### Pagination

**Use @rid-based pagination for best performance:**

```python
# RECOMMENDED: @rid-based pagination (fastest method)
last_rid = "#-1:-1"  # Start from beginning
batch_size = 1000

while True:
    # Bind the cursor and the page size; @rid > ? keeps each page a range scan
    chunk = db.query(
        "sql",
        "SELECT @rid AS rid, name FROM User WHERE @rid > ? LIMIT ?",
        last_rid,
        batch_size,
    ).to_list()

    if not chunk:
        break  # No more records

    # Process batch
    for user in chunk:
        name = user["name"]
        # Process user...

    # Update cursor to last record's @rid
    last_rid = str(chunk[-1]["rid"])

# Alternative: OFFSET-based pagination (slower, not recommended for large datasets)
page = 0
page_size = 100
result = db.query(
    "sql",
    "SELECT FROM User SKIP :skip LIMIT :limit",
    {"skip": page * page_size, "limit": page_size},
)
```

### Parameters

Always bind values as parameters instead of pasting them into the query text,
for two reasons. **Safety**: a pasted value can change the statement (SQL
injection), and a quote in a name breaks it. **Speed**: ArcadeDB caches parsed
statements and plans by their text, so every distinct value pasted in is a new
text that is parsed again. Before 26.10.1 the stream of one-off texts also
evicted the cached statements that do repeat (ArcadeDB
[#8286](https://github.com/ArcadeData/arcadedb/issues/8286)); from 26.10.1 the
SQL and Cypher caches protect statements that are hit repeatedly, but every
pasted value still costs a parse. Measured on an indexed point lookup, 20,000
records: Cypher 0.87 ms with the value pasted in against 0.09 ms with `$id`
bound, SQL 0.48 ms against 0.09 ms. If an application cannot avoid pasting
values, raising `arcadedb.sqlStatementCache` and
`arcadedb.opencypher.statementCache` keeps more texts parsed. Identifiers
(type, property, bucket names) cannot be bound and belong in the text.

```python
# Named parameters (recommended)
result = db.query(
    "sql",
    "SELECT FROM Person WHERE name = :name AND age > :min_age",
    {"name": "Alice", "min_age": 25}
)

# Named collection parameter
result = db.query(
    "sql",
    "SELECT FROM Person WHERE age IN :ages ORDER BY age",
    {"ages": [25, 30, 35]}
)

# Positional parameters
result = db.query(
    "sql",
    "SELECT FROM Person WHERE name = ? AND age > ?",
    "Alice",
    25,
)
```

### SQLScript (multi-statement)

Use `sqlscript` to run multiple statements in one call. When there is no
explicit `RETURN`, the result set contains the **last executed statement**
(including DDL such as `CREATE`/`ALTER`).

```python
script = """
    CREATE VERTEX TYPE SqlScriptVertex;
    INSERT INTO SqlScriptVertex SET name = 'test';
    ALTER TYPE SqlScriptVertex ALIASES ss;
"""

with db.transaction():
    result = db.command("sqlscript", script)

last = result.first()
assert last.get("operation") == "ALTER TYPE"
assert last.get("typeName") == "SqlScriptVertex"
```

### Updating Data

**Prefer SQL for updates:**

```python
# RECOMMENDED: SQL UPDATE
with db.transaction():
    db.command("sql", """
        UPDATE Movie
        SET embedding = :embedding, vector_id = :vector_id
        WHERE movieId = :movie_id
        """, {
        "embedding": java_embedding,
        "vector_id": "movie_1",
        "movie_id": "1"
    })

# SQL UPDATE is also ideal for bulk operations
with db.transaction():
    db.command("sql", """
        UPDATE Task SET completed = true, cost = 127.50
        WHERE title = ?
    """, "Buy groceries")
```

#### Update with JSON array content

ArcadeDB supports `UPDATE ... CONTENT` with JSON arrays to update multiple
documents in one statement.

{% raw %}

```python
db.command("sql", "CREATE DOCUMENT TYPE JsonArrayDoc")

with db.transaction():
    db.command(
        "sql",
        """
        INSERT INTO JsonArrayDoc CONTENT
        [{"name":"tim"},{"name":"tom"}]
        """,
    )

with db.transaction():
    inserted = db.query("sql", "SELECT @rid, name FROM JsonArrayDoc").to_list()
    update_content = ", ".join(
        f"{{@rid:'{row['@rid']}',name:'{row['name']}',status:'updated'}}"
        for row in inserted
    )

    result = db.command(
        "sql",
        f"UPDATE JsonArrayDoc CONTENT [{update_content}] RETURN AFTER",
    )

rows = result.to_list()
assert {row["status"] for row in rows} == {"updated"}
```

{% endraw %}

#### TRUNCATE BUCKET

Use `TRUNCATE BUCKET` to quickly delete all records in a bucket. This is a
low-level operation; prefer `DELETE FROM <Type>` unless you specifically need
bucket-level maintenance.

```python
db.command("sql", "CREATE DOCUMENT TYPE BucketDoc BUCKETS 1")
bucket_info = db.query(
    "sql",
    "SELECT name FROM schema:buckets WHERE name LIKE 'BucketDoc_%' LIMIT 1",
).first()
bucket_name = bucket_info.get("name")

with db.transaction():
    db.command("sql", f"TRUNCATE BUCKET {bucket_name}")
```

### Graph Traversal

```python
# Find friends using MATCH
result = db.query(
    "sql",
    """
    MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
            -FRIEND_OF->
            {type: Person, as: friend}
    RETURN friend.name as name, friend.city as city
    ORDER BY friend.name
""",
)

friends = result.to_list()
for friend in friends:
    print(f"{friend['name']} from {friend['city']}")

# Friends of friends (2 degrees)
result = db.query(
    "sql",
    """
    MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
            -FRIEND_OF->
            {type: Person, as: friend}
            -FRIEND_OF->
            {type: Person, as: friend_of_friend, where: (name <> 'Alice Johnson')}
    RETURN DISTINCT friend_of_friend.name as name, friend.name as through_friend
    ORDER BY friend_of_friend.name
""",
)

for row in result:
    name = row.get("name")
    through = row.get("through_friend")
    print(f"{name} (through {through})")
```

### Aggregations

```python
# Count with first()
result = db.query("sql", "SELECT count(*) as count FROM Test")
count = result.first().get("count")

# Group by with statistics
result = db.query(
    "sql",
    """
    SELECT city, COUNT(*) as person_count,
            AVG(age) as avg_age
    FROM Person
    GROUP BY city
    ORDER BY person_count DESC, city
""",
)

for row in result:
    city = row.get("city")  # Python str
    count = row.get("person_count")  # Python int
    avg_age = row.get("avg_age")  # Python float
    print(f"{city}: {count} people, avg age {avg_age:.1f}")
```

### Full-text search ($score)

When using full-text indexes, ArcadeDB exposes a `$score` variable that you can
select and order by.

```python
# Create full-text index
db.command("sql", "CREATE DOCUMENT TYPE Article")
db.command("sql", "CREATE PROPERTY Article.content STRING")
db.command("sql", "CREATE INDEX ON Article (content) FULL_TEXT")

# Query with SEARCH_FIELDS and $score
result = db.query(
    "sql",
    "SELECT content, $score FROM Article WHERE SEARCH_FIELDS(['content'], 'database') = true ORDER BY $score DESC",
)
for row in result:
    print(row.get("content"), row.get("$score"))
```

Scoring uses native BM25 ranking. Individual query terms can be weighted with
caret boosts (`term^weight`), which shifts `$score` accordingly:

```python
# 'database' matches count 5x more than 'java' matches
result = db.query(
    "sql",
    "SELECT content, $score FROM Article "
    "WHERE SEARCH_INDEX('Article[content]', 'java^1.0 database^5.0') = true "
    "ORDER BY $score DESC",
)
```

`SEARCH_INDEX('Type[property]', query)` targets one specific index and supports
the same syntax, including wildcards (`'Hel*'`) and boosts.

### Choosing index types in SQL DSL

When you create indexes through SQL, the index keyword controls both the index
structure and uniqueness.

```python
# General-purpose ordered index (LSM_TREE)
db.command("sql", "CREATE INDEX ON User (email) UNIQUE")
db.command("sql", "CREATE INDEX ON Event (createdAt) NOTUNIQUE")

# Exact-match hash index
db.command("sql", "CREATE INDEX ON User (email) UNIQUE_HASH")
db.command("sql", "CREATE INDEX ON Order (customerId) NOTUNIQUE_HASH")

# Specialized indexes
db.command("sql", "CREATE INDEX ON Article (content) FULL_TEXT")
db.command("sql", "CREATE INDEX ON Doc (embedding) LSM_VECTOR METADATA {\"dimensions\": 128}")
db.command("sql", "CREATE INDEX ON Place (location) GEOSPATIAL")

# MAP properties: index by keys or values (accelerates CONTAINSKEY / CONTAINSVALUE)
db.command("sql", "CREATE INDEX ON Movie (thumbs BY KEY) NOTUNIQUE")
db.command("sql", "CREATE INDEX ON Movie (thumbs BY VALUE) NOTUNIQUE")
```

For `LSM_VECTOR`, SQL builds the graph immediately by default. If you need to defer that
work, pass `"buildGraphNow": false` inside `METADATA`.

Rules of thumb:

- Use `UNIQUE_HASH` or `NOTUNIQUE_HASH` for exact-match lookups only.
- Use `UNIQUE` or `NOTUNIQUE` for `LSM_TREE` indexes when you need ranges, ordering, or a safe general-purpose default.
- Use `FULL_TEXT` for tokenized text search, not normal equality lookups.
- Use `LSM_VECTOR` for embeddings and nearest-neighbor search.
- Use `GEOSPATIAL` for spatial predicates.

Examples:

- `email = ?`, `userId = ?`, `movieId = ?`: usually `UNIQUE_HASH` or `NOTUNIQUE_HASH`
- `createdAt BETWEEN ? AND ?`, `price > ?`, ordered scans: usually `UNIQUE` or `NOTUNIQUE`

An index on a range column is not free when the range matches most of the rows. From
26.10.1 a scan runs on several workers, while the index entries are read by one thread,
so the engine gives up the index for the scan once a range matches more than
`arcadedb.queryIndexMaxSelectivity` of the type: 0.6 on one thread, divided by (1 + W) / 2
for W scan workers (24% on 4 workers, 6% on 18). `PROFILE` names the branch that ran
(`served by full scan` or `served by physical order`). Even so, a range matching 96% of
2,000,000 rows measured 1.2x to 1.3x slower with the index than without it on a 4-core
laptop, and a one-year slice (14%) 1.5x to 1.6x faster (`ArcadeData/arcadedb#8333`).
Index a range column for the selective ranges you actually run, and measure with and
without the index when most of your ranges are wide.

`HASH` does not imply uniqueness: a non-unique hash index serves exact-match lookups on a
value that a few records share. Until a release carries the fix for ArcadeDB
[#8829](https://github.com/ArcadeData/arcadedb/issues/8829), avoid `NOTUNIQUE_HASH` where a
value can hold a few dozen records or more, such as a `status`, a `country`, or a customer
with many orders: deleting some of those records can fail at commit. Index such a property
with `NOTUNIQUE` instead (see [Known Engine Issues](../known-issues.md)).

**Ordered reads over an optional property.** A SQL `ORDER BY p LIMIT k` reads an `LSM_TREE`
index on `p` in order, but nulls sort first in ascending order, and an index created with
the default null strategy holds no key for a record whose `p` is null or absent, so an
ascending read first scans the whole type for those records. From 26.10.1 that scan is
skipped when the `WHERE` clause excludes nulls on `p` (`p IS NOT NULL`, `p = ?`, `p < ?`, or
`p > ?`; not `>=` or `<=`, which two nulls satisfy), or when `p` is declared both
`MANDATORY` and `NOTNULL`. `NOTNULL` alone is not enough: it rejects an explicit null but
not a record that leaves `p` out (ArcadeDB [#8701](https://github.com/ArcadeData/arcadedb/issues/8701)).
Otherwise, create the index with `NULL_STRATEGY INDEX` so the nulls are in it. Descending
SQL reads are not affected. At 1,000,000 rows the ascending top 10 measured about 290 ms
with the scan and about 1 ms without it (ArcadeDB [#8664](https://github.com/ArcadeData/arcadedb/issues/8664)).
SQL reads the index in order whether the query projects `p` under its own name, under an
alias, or not at all: `SELECT title FROM Event ORDER BY createdAt DESC LIMIT 10` reads ten
index entries. Before ArcadeDB [#8811](https://github.com/ArcadeData/arcadedb/issues/8811),
fixed in 26.10.1, the aliased and unprojected forms scanned the type and sorted it (642 to
806 ms at 1,000,000 records, against 0.45 to 0.93 ms with the fix). openCypher reads the index
in order in every form.
For the first or last value past a bound, write the ordered read too:
`SELECT ts FROM Event WHERE ts > ? ORDER BY ts LIMIT 1` reads one index entry, while
`SELECT min(ts) FROM Event WHERE ts > ?` reads every record in the range, in both languages
(at 1,000,000 records 0.2 to 0.5 ms against 136 to 145 ms in SQL and about 800 ms in openCypher;
ArcadeDB [#8812](https://github.com/ArcadeData/arcadedb/issues/8812)). Over a whole type,
without a range, `min()` and `max()` already read one end of the index.

openCypher sorts nulls last in ascending order and first in descending order. From 26.10.1
it reads the index in order over a whole label, in either direction, for
`ORDER BY n.p LIMIT k` when `p` is declared both `MANDATORY` and `NOTNULL`, when the `WHERE`
is `n.p IS NOT NULL`, or when the index was created with `NULL_STRATEGY INDEX`. With the
default null strategy and neither declaration it does so only ascending: a descending read
must return the null keys first, that index holds none, and it scans the label. At
1,000,000 vertices on a 26.10.1 snapshot the index-ordered reads measured 0.4 to 1.6 ms
(about 10 ms descending on a `NULL_STRATEGY INDEX` index, which reads its null keys first),
against 0.8 to 1.1 s for the scan (ArcadeDB [#8724](https://github.com/ArcadeData/arcadedb/issues/8724)).
Declare `MANDATORY` and `NOTNULL` before loading data: both languages trust the declaration,
and `ALTER PROPERTY` does not check records written before it.

```python
db.command("sql", "CREATE PROPERTY Event.createdAt DATETIME (mandatory true, notnull true)")  # every record has a key: no scan
db.command("sql", "CREATE INDEX ON Task (dueAt) NOTUNIQUE NULL_STRATEGY INDEX")  # optional property, SQL reads
```

**Prefix matches.** From 26.10.1 a SQL `LIKE 'abc%'` and a Cypher `STARTS WITH 'abc'`
read an ordered index on the property as a range and then check the condition, instead of
scanning the type; case-insensitive indexes are not used for them, and Cypher
`min(n.p)` / `max(n.p)` read one end of an index on that label and property alone when
the index holds no nulls (ArcadeDB [#8666](https://github.com/ArcadeData/arcadedb/issues/8666)).

**Disjunctions.** From 26.10.1 a Cypher `WHERE` that is an `OR` of equalities or `IN` lists on
indexed properties reads the indexes, as SQL does: `n.x = $a OR n.x = $b` becomes the seek
`n.x IN [$a, $b]` does, and an `OR` across properties a union of index seeks. One disjunct on
a property with no index makes it a scan of the label. At 1,000,000 vertices on a 26.10.1
snapshot the `OR` forms measured 0.5 to 0.9 ms against 340 to 430 ms before
(ArcadeDB [#8723](https://github.com/ArcadeData/arcadedb/issues/8723)).

**Scans run in parallel only outside a transaction.** A filtered scan of a type runs on
several cores, from 26.10.1 in both SQL and Cypher
(ArcadeDB [#8725](https://github.com/ArcadeData/arcadedb/issues/8725)), but only when no
transaction is open: inside `db.begin()` or `with db.transaction():` it runs on one thread,
because the workers would not see the transaction's own changes. At 1,000,000 records on 12
cores the same filtered count measured 43 to 57 ms with no transaction open and 255 to 291 ms
inside one, in both languages. Run analytical reads outside an explicit transaction.

**Whole-type aggregates.** In 26.10.1 a SQL aggregate over a type scan is computed in the
parallel workers, and so are openCypher `count`, `sum`, `avg`, `min`, and `max` over a label,
with or without grouping or a `WHERE` (ArcadeDB
[#8797](https://github.com/ArcadeData/arcadedb/issues/8797)). At 2,000,000 vertices on 12
cores, with no transaction open, `sum` over a property measured 128 ms in SQL and 84 ms in
openCypher, and a group-by with a count and a sum 221 ms against 141 ms. openCypher `DISTINCT`
aggregates such as `count(DISTINCT n.p)`, `collect()`, and aggregates over a function call
still run on one thread (`count(DISTINCT n.grp)` measured 827 ms); the SQL form of the same
question runs in the workers.

```python
# openCypher aggregates over a label run in the parallel workers (26.10.1)
by_city = db.query(
    "opencypher", "MATCH (p:Person) RETURN p.city AS city, count(*) AS n, avg(p.age) AS a"
).to_list()

# A DISTINCT aggregate does not; count the distinct values in SQL instead
n_cities = db.query(
    "sql", "SELECT count(*) AS n FROM (SELECT DISTINCT city FROM Person)"
).to_list()[0]["n"]
```

**Distinct values.** In 26.10.1 a plain `SELECT DISTINCT p FROM Type` over at least 10,000
records runs like the `GROUP BY` over the same property, in the parallel workers, and returns
the same rows in the same order: at 2,000,000 records 94 ms, against 1,185 ms before ArcadeDB
[#8799](https://github.com/ArcadeData/arcadedb/issues/8799). It is not rewritten when it has a
`LIMIT`, an `ORDER BY`, a computed expression, or `*`, or inside a transaction; there,
`SELECT p FROM Type GROUP BY p` returns the same rows from the workers.

```python
# Sorted distinct values: the ORDER BY keeps SELECT DISTINCT off the parallel path, GROUP BY is on it
cities = [r.get("city") for r in db.query("sql", "SELECT city FROM Person GROUP BY city ORDER BY city")]
```

### ResultSet Methods

Use `first()` or direct iteration when you want the lowest-overhead path.
`to_list()` eagerly materializes the full result set into Python dictionaries, so it
is best reserved for smaller results or explicit interop steps.

```python
# first() - get first result
result = db.query("sql", "SELECT FROM Person ORDER BY name")
first_person = result.first()
assert first_person.get("name") == "Alice"

# to_list() - convert all to list
result2 = db.query("sql", "SELECT FROM Person ORDER BY name")
people_list = result2.to_list()
assert len(people_list) == 2
assert people_list[1]["name"] == "Bob"

# first() to check if results exist
result = db.query("sql", "SELECT FROM Person WHERE name = ?", "Unknown")
first_mutual = result.first()
if first_mutual:
    print(f"Found: {first_mutual.get('name')}")
else:
    print("No results found")
```

### Performance and Materialization

Rule of thumb: **iterate when you're selective or the result is small; use the
bulk APIs when you're taking everything from a large result.**

- Use `first()` when you only need one row.
- Use direct iteration plus `get()` when you read only some columns, need live
    records (`get_element()`), or may stop early. Ideal for small/medium results;
    on very large results it pays a per-row boundary cost.
- Use `to_columns()` / `to_dataframe()` to bulk-load large results into
    numpy/pandas. This is the fastest path (~12x over `to_list()` on a
    10,000-row, nine-property scan, laptop, 2026-09-27), with typed columns
    including real `datetime64`.
- Use `to_json_list()` (or `iter_json_batches()` when it may not fit in memory)
    to bulk-load large results as plain dicts. JSON-native types: temporals
    arrive as ISO strings.
- Use `to_list()` when you need full Python-type fidelity (`datetime`,
    `Decimal`) as row dicts and the result is not huge.
- Use wrapper `to_dict()` only when you truly want the full document in Python.

A result set closes itself when it is exhausted (by iteration or any `to_*`
method) and when `first()` or `one()` returns. If you stop reading early and keep
the result set around, use it as a context manager or call `close()`: an unclosed
result set can hold engine threads that other queries need
(ArcadeData/arcadedb#8594; see [`close()`](../../api/results.md#close-none)).

```python
# Selective or small results: iterate
result = db.query("sql", "SELECT name, score FROM Item WHERE score > ?", 100)
for row in result:
        handle(row.get("name"), row.get("score"))

# Stopping early: the with block closes the result set
with db.query("sql", "SELECT name, score FROM Item WHERE score > ?", 100) as result:
    for row in result:
        if row.get("score") > 1000:
            break

# Bulk materialization as dicts (~5.5x faster than to_list on a wide scan):
# rows are JSON-serialized in batches on the Java side. Values carry
# JSON-native types (temporals arrive as ISO strings, not datetime).
rows = db.query("sql", "SELECT FROM Item").to_json_list()

# Materialize with full Python-type fidelity (datetime, Decimal, ...)
result = db.query("sql", "SELECT name, score FROM Item WHERE score > ?", 100)
payload = result.to_list()

# For wrappers, prefer field access over full dict conversion in large loops
for doc in db.query("sql", "SELECT FROM Person"):
        process(doc.get("name"), doc.get("city"))
```

## OpenCypher

OpenCypher provides expressive graph pattern matching.

### Basic Traversals

```python
# Get vertex property values
result = db.query("opencypher", "MATCH (p:Person) RETURN p.name as name")
names = [record.get("name") for record in result]
assert "Alice" in names or "Bob" in names

# Count vertices
result = db.query("opencypher", "MATCH (p:Person) RETURN count(p) as count")
results = list(result)
count = results[0].get("count") if results else 0
```

Bind values in Cypher as `$name` parameters with a dict, exactly as in SQL; the
same reasons apply (see [Parameters](#parameters)):

```python
result = db.query(
    "opencypher",
    "MATCH (p:Person {name: $name}) RETURN p.age AS age",
    {"name": "Alice"},
)
```

### Writing nodes

Write in batches, as the SQL section does: one `UNWIND $rows` statement per transaction of a
few thousand rows, with the values bound as a parameter.

```python
rows = [{"id": i, "name": f"n{i}"} for i in range(start, start + 5_000)]
with db.transaction():
    db.command("opencypher",
               "UNWIND $rows AS r MERGE (p:Person {id: r.id}) SET p.name = r.name",
               {"rows": rows})
```

Give a new node its properties in the statement that creates it, as plain property
assignments. From 26.10.1, `CREATE (n ...) SET n.p = ...`, `MERGE ... SET n.p = ...`, and
`MERGE ... ON CREATE SET n.p = ...` apply the assignments before the node's first write. A
`SET` that assigns a map (`SET n += r`), sets a label, or reads the new node still writes it
a second time, and that second write, which grows the record inside its page, costs about as
much as creating it. At 200,000 new vertices, 1,000 per transaction, on a 26.10.1 snapshot:
`CREATE ... SET n.name = r.name` about 95,000 vertices per second against about 50,000 for
`SET n += {name: r.name}`, and `MERGE ... SET n.name = r.name` about 60,000 against about
39,000 (ArcadeDB [#8735](https://github.com/ArcadeData/arcadedb/issues/8735)). A record made
through the Python API follows the same rule: set every property before its first `save()`.

### Graph Traversals

```python
# Complex projection with aggregation
query = """
    MATCH (q:Question)
    OPTIONAL MATCH (q)-[:HAS_ANSWER]->(a:Answer)
    RETURN q.Title as title, count(a) as answer_count, q.Score as score
    ORDER BY answer_count DESC
    LIMIT 5
"""

results = list(db.query("opencypher", query))

for i, result in enumerate(results, 1):
    title = result.get("title") or "Unknown"
    answer_count = result.get("answer_count") or 0
    score = result.get("score") or 0
    print(f"[{i}] Answers: {answer_count}, Score: {score}")
    print(f"    {title[:70]}...")
```

### Processing Results

```python
# Simple value extraction
result = db.query("opencypher", "MATCH (p:Person) RETURN p.name as name")
names = [record.get("name") for record in result]

# Project returns named keys directly
query = """
    MATCH (q:Question)
    RETURN q.Title as title, q.Score as score
    LIMIT 5
"""
results = list(db.query("opencypher", query))
for result in results:
    title = result.get("title")
    score = result.get("score")
```
