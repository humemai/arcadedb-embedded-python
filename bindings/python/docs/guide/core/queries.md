# Query Languages Guide

ArcadeDB Python bindings support two approaches:

1. **Pythonic API (Recommended)**: Use the Java embedded API directly -
   `db.new_document()`, `vertex.set()`, `vertex.save()`
2. **SQL/OpenCypher**: Traditional query languages for complex queries and analytics

## Best Practice: Use Pythonic API for CRUD

For creating, updating, and managing data, use the embedded API methods instead of SQL:

### Creating Documents

```python
# Create schema
db.schema.create_document_type("Task")
db.schema.create_property("Task", "title", "STRING")
db.schema.create_property("Task", "completed", "BOOLEAN")

# Insert using Pythonic API (RECOMMENDED)
with db.transaction():
    task = db.new_document("Task")
    task.set("title", "Buy groceries")
    task.set("completed", False)
    task.set("tags", ["shopping", "urgent"])
    task.save()
```

### Creating Vertices

```python
# Create schema
db.schema.create_vertex_type("Person")
db.schema.create_edge_type("Knows")

# Insert using Pythonic API (RECOMMENDED)
with db.transaction():
    alice = db.new_vertex("Person")
    alice.set("name", "Alice")
    alice.set("age", 30)
    alice.save()

    bob = db.new_vertex("Person")
    bob.set("name", "Bob")
    bob.save()
```

### Bulk Inserts (preferred: chunked transactions)

```python
# Efficient bulk insertion (embedded-friendly): use chunked transactions
chunk_size = 500
for start in range(0, len(people_data), chunk_size):
    with db.transaction():
        for name, age, city in people_data[start : start + chunk_size]:
            person = db.new_vertex("Person")
            person.set("name", name)
            person.set("age", age)
            person.set("city", city)
            person.save()

# If you specifically need the Java batching API (e.g., remote/server workflows),
# you can still use db.batch_context(...), but embedded users should prefer
# explicit chunked transactions to avoid batch_context overhead.
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

result = db.command("sqlscript", script)
last = result.first()
assert last.get("operation") == "ALTER TYPE"
assert last.get("typeName") == "SqlScriptVertex"
```

### Updating Data

**Prefer Pythonic API for updates:**

```python
# RECOMMENDED: Update using Pythonic API with .modify()
result = db.query("sql", "SELECT FROM Movie WHERE movieId = '1'")
with db.transaction():
    for movie_result in result:
        movie = movie_result.get_vertex()  # or .get_document()
        mutable_vertex = movie.modify()  # Get mutable version
        mutable_vertex.set("embedding", java_embedding)
        mutable_vertex.set("vector_id", "movie_1")
        mutable_vertex.save()

# Alternative: SQL UPDATE (for bulk operations)
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
doc_type = db.schema.create_document_type("BucketDoc", buckets=1)
bucket_name = doc_type.getBuckets(False)[0].getName()

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
db.schema.create_document_type("Article")
db.schema.create_property("Article", "content", "STRING")
db.schema.create_index("Article", ["content"], index_type="FULL_TEXT")

# Query with SEARCH_FIELDS and $score
result = db.query(
    "sql",
    "SELECT content, $score FROM Article WHERE SEARCH_FIELDS(['content'], 'database') = true ORDER BY $score DESC",
)
for row in result:
    print(row.get("content"), row.get("$score"))
```

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
