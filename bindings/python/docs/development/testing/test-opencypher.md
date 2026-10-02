# OpenCypher Tests

[View source code]({{ config.repo_url }}/blob/{{ config.extra.version_tag }}/bindings/python/tests/test_cypher.py){ .md-button }

The tests validate OpenCypher query support, common graph patterns, and path-mode
semantics (TRAIL, ACYCLIC, WALK).

They also include regression coverage for planner behavior that matters to the
Python bindings, such as `UNWIND` variables being usable inside `WHERE`
predicates.

Each test first runs `RETURN 1` and skips if the `opencypher` engine
is not available; the CASE/coalesce, collect/UNWIND, and pattern comprehension
tests also skip if the engine rejects that feature.

## OpenCypher

OpenCypher is a declarative graph query language for pattern matching and traversal.

```python
import arcadedb_embedded as arcadedb

with arcadedb.create_database("./opencypher_test_db") as db:
    db.command("sql", "CREATE VERTEX TYPE Person")
    db.command("sql", "CREATE EDGE TYPE Knows")

    with db.transaction():
        alice = db.new_vertex("Person")
        alice.set("name", "Alice").save()

        bob = db.new_vertex("Person")
        bob.set("name", "Bob").save()

        edge = alice.new_edge("Knows", bob)
        edge.save()

    result = db.query("opencypher", """
        MATCH (p:Person)-[:Knows]->(friend:Person)
        RETURN friend.name as name
    """)

    names = [r.get("name") for r in result]
    assert "Bob" in names
```

## Running This Test

```bash
uv run pytest bindings/python/tests/test_cypher.py -v
```

## Test Cases

Most tests seed a `KNOWS` chain of four `Person` vertices (Alice→Bob→Charlie→David)
and a `Company` (Acme) that Alice and Bob work for. The path-mode tests use a `Node`
cycle A→B→C→D→A plus an edge A→E.

### Matching and filtering

- **test_opencypher_basic_match**: `MATCH (p:Person) WHERE p.age > 20` returns exactly Alice, Bob, Charlie, and David.
- **test_opencypher_relationship_properties**: Alice's `KNOWS` edges with `r.since >= 2020` return exactly `[("Bob", 2020)]`.
- **test_opencypher_variable_length_path**: `-[:KNOWS*1..3]->` from Alice returns `["Bob", "Charlie", "David"]` (DISTINCT, ordered).
- **test_opencypher_path_length_and_filter**: the same traversal filtered on `b.age >= 28` returns `["Bob", "David"]`.
- **test_opencypher_id_filter**: `WHERE ID(n) = <Alice's id>` returns only Alice.
- **test_opencypher_optional_match**: `OPTIONAL MATCH` on `WORKS_FOR` returns Acme for Alice and Bob and `None` for Charlie and David.
- **test_opencypher_case_and_coalesce**: a `CASE ... coalesce(...)` over the same optional match returns Acme for Alice and Bob and `"unemployed"` for the others.
- **test_opencypher_subquery_with_exists**: `WHERE EXISTS { MATCH (p)-[:WORKS_FOR]->(:Company) }` returns `["Alice", "Bob"]`.
- **test_opencypher_count_non_existing_label_returns_zero**: `count(n)` over a label that does not exist returns one row with `0`.

### Path modes

- **test_opencypher_trail_is_default_path_mode**: a variable-length match with no mode returns as many rows as `MATCH TRAIL`, and the `TRAIL` result reaches `A` again around the cycle.
- **test_opencypher_acyclic_blocks_vertex_revisit**: `MATCH ACYCLIC` never returns `A` and does reach B, C, D, and E.
- **test_opencypher_walk_produces_more_results_than_trail**: over 1..6 hops on the cycle, `MATCH WALK` returns more rows than `MATCH TRAIL`.
- **test_opencypher_walk_requires_max_hops**: `MATCH WALK` with an unbounded `*` raises an error mentioning `WALK`.

### Aggregation, UNWIND, and projections

- **test_opencypher_aggregation**: counting `WORKS_FOR` edges per company returns Acme with 2 employees as the first row.
- **test_opencypher_collect_and_unwind**: `collect()` then `UNWIND` returns `[("Acme", "Alice"), ("Acme", "Bob")]`.
- **test_opencypher_unwind_where_uses_unwind_variable**: a `WHERE` that references a variable introduced by `UNWIND ['Alice', 'Bob', 'Nobody']` returns `["Alice", "Bob"]`.
- **test_opencypher_pattern_comprehension**: `[(p)-[r:KNOWS]->(b) | r.since]` for Alice returns `[2020]`.
- **test_opencypher_projection_property_order_is_preserved**: `RETURN p.age AS age, p.name AS name, 42 AS marker` gives `property_names` and `to_dict()` keys in the order `age`, `name`, `marker`.

### DDL and constraints

- **test_opencypher_create_index_command**: `CREATE INDEX FOR (n:Event) ON (n.code)` runs, and a lookup on the indexed property returns the created `Event`.
- **test_opencypher_create_index_if_not_exists_command**: the same `CREATE INDEX IF NOT EXISTS` runs twice without error, and the indexed lookup returns `value == 42`.
- **test_opencypher_typed_constraint_command**: `REQUIRE p.email IS TYPED STRING` is accepted, and a `Person` with a string email is created and found.
- **test_opencypher_edge_typed_constraint_command**: `REQUIRE r.since IS TYPED DATE` on `KNOWS` is accepted, and an edge created with `since = date(...)` reads back a non-null `since`.
- **test_opencypher_ddl_auto_creates_vertex_and_edge_types**: `AutoEvent` and `RELATES_TO` do not exist before the Cypher `CREATE INDEX` and `CREATE CONSTRAINT`, do exist after, and an edge created between two `AutoEvent` vertices returns `since == "2026-04-07"`.

### Values and write clauses

- **test_opencypher_is_typed_value_predicate**: `42 IS TYPED INTEGER` and a string `IS TYPED STRING` are `True`; a string `IS TYPED INTEGER` is `False`.
- **test_opencypher_temporal_component_access_on_date_and_datetime**: `.year` and `.month` on a stored `datetime` return 2026 and 4, and `.year` and `.day` on a stored `date` return 2026 and 7.
- **test_opencypher_with_carried_node_survives_anonymous_create_and_merge**: a node carried through `WITH` is still bound after an anonymous `CREATE` and after an anonymous `MERGE`; both queries return `"Alice"`.
- **test_opencypher_set_label_is_idempotent_across_row_fanout**: `SET a:Leader` on a node that appears in two rows returns both rows (Bob, Charlie) with `Leader` in the labels, and afterwards exactly one `Leader` Alice exists.

### Parameters

- **test_opencypher_named_params_on_variable_length_traversal**: `$start_name` and `$min_age` in a variable-length traversal return `["Bob", "David"]`.
- **test_opencypher_named_params_on_traversal_count**: the same parameters with `count(DISTINCT b)` return 2.
- **test_opencypher_nested_parameter_in_match**: `{uuid: $data.uuid}` with `{"data": {"uuid": "u1"}}` returns only `"First"` (#4909).

## Notable Regression Coverage

- Path modes: default `TRAIL`, explicit `ACYCLIC`, and `WALK`
- `WALK` requires an explicit hop bound on cyclic traversals
- `UNWIND` variables can be referenced from `WHERE` clauses during `MATCH`
- Aggregations on missing labels still return a single row with `0`
- Result property order remains stable for projected OpenCypher values

## Path Mode Example

```cypher
MATCH ACYCLIC (a:Node {name: 'A'})-[:LINK*1..5]->(b)
RETURN b.name AS name
```

This coverage is intentionally test-focused: Python already reaches these features
through `db.query("opencypher", ...)`, so the bindings need semantic verification more
than a dedicated wrapper API.

## OpenCypher vs SQL MATCH

| Feature | SQL MATCH | OpenCypher |
|---------|-----------|------------|
| **Style** | SQL-like | Declarative graph patterns |
| **Focus** | Set operations + graph patterns | Pattern matching + paths |
| **Learning curve** | Easier if you know SQL | Easier if you know Cypher |
| **Graph traversal** | Strong | Strong |

### Example Comparison

**SQL MATCH:**
```sql
MATCH {type: Person, as: p}-Knows->{type: Person, as: friend}
RETURN friend.name
```

**OpenCypher:**
```cypher
MATCH (p:Person)-[:Knows]->(friend:Person)
RETURN friend.name
```

## Related Documentation

- [Query Languages](../../guide/core/queries.md)
- [Graph Operations Guide](../../guide/graphs.md)
