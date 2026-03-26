# Query Languages Guide

ArcadeDB Python bindings support two approaches:

1. **SQL/OpenCypher (Recommended)**: Use DSL for schema, CRUD, and graph operations
2. **Language Choice**: Use SQL for relational-style operations and OpenCypher for graph traversals

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
db.command("sql", "CREATE EDGE TYPE Knows UNIDIRECTIONAL")

# Insert using SQL (RECOMMENDED)
with db.transaction():
    db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Alice", 30)
    db.command("sql", "INSERT INTO Person SET name = ?, age = ?", "Bob", 25)
```

### Bulk Inserts (preferred: chunked transactions)

```python
# Efficient bulk insertion (embedded-friendly): use chunked SQL transactions
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

# Prefer SQL/OpenCypher chunked transactions for embedded bulk work.
# There is no separate high-level batch context API in the current Python surface.
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
result = db.query("sql", "SELECT FROM Task WHERE priority = 'high' AND completed = false")
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
    # Query with @rid > last_rid for efficient pagination
    query = f"""
        SELECT *, @rid as rid FROM User
        WHERE @rid > {last_rid}
        LIMIT {batch_size}
    """
    chunk = list(db.query("sql", query))

    if not chunk:
        break  # No more records

    # Process batch
    for user in chunk:
        user_id = user.get("Id")
        name = user.get("DisplayName")
        # Process user...

    # Update cursor to last record's @rid
    last_rid = chunk[-1].get("rid")

# Alternative: OFFSET-based pagination (slower, not recommended for large datasets)
page = 0
page_size = 100
result = db.query("sql", f"SELECT FROM User LIMIT {page_size} SKIP {page * page_size}")
```

### Parameters

Always use parameters to prevent SQL injection:

```python
# Named parameters (recommended)
result = db.query(
    "sql",
    "SELECT FROM Person WHERE name = :name AND age > :min_age",
    {"name": "Alice", "min_age": 25}
)

# Positional parameters
result = db.query(
    "sql",
    "SELECT FROM Person WHERE name = ? AND age > ?",
    ["Alice", 25]
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
        WHERE title = 'Buy groceries'
    """)
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

`HASH` does not imply uniqueness. A non-unique hash index still makes sense when many
records share the same exact-match value, such as `customerId`, `status`, or `country`.

### ResultSet Methods

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
result = db.query("sql", "SELECT FROM Person WHERE name = 'Unknown'")
first_mutual = result.first()
if first_mutual:
    print(f"Found: {first_mutual.get('name')}")
else:
    print("No results found")
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
