#!/usr/bin/env python3
"""
ArcadeDB Python Bindings - Social Network Graph Example

This example demonstrates how to use ArcadeDB as a graph database to model
a social network with people and friendships. It showcases:

1. Creating vertex and edge types (schema definition)
2. Creating vertices (people) with properties
3. Creating edges (friendships) between vertices
4. Querying the graph using both SQL MATCH and Cypher dialects
5. Finding friends, friends of friends, and mutual connections
6. Comparing SQL vs Cypher syntax for graph operations

Key Concepts:
- Vertices represent entities (Person)
- Edges represent relationships (FRIEND_OF)
- Properties store data on both vertices and edges
- Graph traversal allows complex relationship queries
- Both SQL MATCH and Cypher provide graph querying capabilities

ArcadeDB Query Languages:
- SQL MATCH: ArcadeDB's extended SQL syntax for graph traversal
- Cypher: Neo4j-compatible query language for intuitive graph operations

Requirements:
- Python embedded ArcadeDB (arcadedb_embedded package)

Usage:
- Run this example from the examples/ directory:
  cd bindings/python/examples && python 02_social_network_graph.py
- Database files will be created in ./my_test_databases/social_network_db/
"""

import os
import shutil
import sys
import time

import arcadedb_embedded as arcadedb


def main():
    """Main function demonstrating social network graph operations"""

    # Database connection (using same pattern as 01_simple_document_store.py)
    print("🔌 Creating/connecting to database...")

    step_start = time.time()

    # Create database in a local directory so you can inspect the files
    # This creates: ./my_test_databases/social_network_db/
    db_dir = "./my_test_databases"
    database_path = os.path.join(db_dir, "social_network_db")

    # Clean up any existing database from previous runs
    if os.path.exists(database_path):
        shutil.rmtree(database_path)

    # Clean up log directory from previous runs
    if os.path.exists("./log"):
        shutil.rmtree("./log")

    try:
        # Create/open database using same pattern as working example
        db = arcadedb.create_database(database_path)
        print(f"✅ Database created at: {database_path}")
        print("💡 Using embedded mode - no server needed!")
        print("💡 Database files are kept so you can inspect them!")
        print(f"⏱️  Time: {time.time() - step_start:.3f}s")

        # Create schema
        create_schema(db)

        # Create sample data
        create_sample_data(db)

        # Demonstrate graph queries
        demonstrate_graph_queries(db)

        # Compare SQL vs Cypher approaches
        compare_query_languages(db)

        print("\n✅ Social network graph example completed successfully!")

    except Exception as e:
        print(f"❌ Error in social network example: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    # Close database connection (like 01_simple_document_store.py)
    db.close()
    print("✅ Database connection closed")

    # Note: We're NOT deleting the database directory
    # You can inspect the files in ./my_test_databases/social_network_db/
    print(f"💡 Database files preserved at: {database_path}")
    print("💡 Inspect the database structure and files!")
    print("💡 Re-run this script to recreate the database")


def create_schema(db):
    """Create vertex and edge types for the social network"""
    print("\n📊 Creating social network schema...")

    step_start = time.time()

    try:
        # Create schema in a transaction (like the working example)
        with db.transaction():
            # Create Person vertex type
            db.schema.create_vertex_type("Person")
            print("  ✓ Created Person vertex type")

            # Create properties for Person (various data types, some optional/NULL)
            db.schema.create_property("Person", "name", "STRING")
            db.schema.create_property("Person", "age", "INTEGER")
            db.schema.create_property("Person", "city", "STRING")
            db.schema.create_property("Person", "joined_date", "DATE")
            db.schema.create_property("Person", "email", "STRING")  # Optional
            db.schema.create_property("Person", "phone", "STRING")  # Optional
            db.schema.create_property("Person", "verified", "BOOLEAN")
            db.schema.create_property("Person", "reputation", "FLOAT")  # Optional
            print("  ✓ Created Person properties (including optional fields)")

            # Create FRIEND_OF edge type
            db.schema.create_edge_type("FRIEND_OF")
            print("  ✓ Created FRIEND_OF edge type")

            # Create properties for FRIEND_OF edge
            db.schema.create_property("FRIEND_OF", "since", "DATE")
            db.schema.create_property("FRIEND_OF", "closeness", "STRING")
            print("  ✓ Created FRIEND_OF properties")

            # Create indexes for better performance using Schema API
            db.schema.create_index("Person", ["name"], unique=False)
            print("  ✓ Created index on Person.name")

        print(f"  ⏱️  Time: {time.time() - step_start:.3f}s")

    except Exception as e:
        print(f"  ❌ Error creating schema: {e}")
        raise


def create_sample_data(db):
    """Create sample people and friendships"""
    print("\n👥 Creating sample social network data...")

    step_start = time.time()

    try:
        # Check if data already exists using new count_type() method
        count = db.count_type("Person")

        if count > 0:
            print(f"  ℹ️  Found {count} existing people, skipping data creation")
            print("      💡 Using new count_type() method for efficient counting")
            return

        # Create people with various properties (including NULL values for optional fields)
        # Format: (name, age, city, joined_date, email, phone, verified, reputation)
        people_data = [
            (
                "Alice Johnson",
                28,
                "New York",
                "2020-01-15",
                "alice@example.com",
                "+1-555-0101",
                True,
                4.8,
            ),
            (
                "Bob Smith",
                32,
                "San Francisco",
                "2019-03-20",
                "bob@example.com",
                None,
                True,
                4.5,
            ),  # No phone (NULL)
            (
                "Carol Davis",
                26,
                "Chicago",
                "2021-06-10",
                None,
                "+1-555-0103",
                False,
                None,
            ),  # No email, no reputation (NULLs)
            (
                "David Wilson",
                35,
                "Boston",
                "2018-11-05",
                "david@example.com",
                "+1-555-0104",
                True,
                4.9,
            ),
            (
                "Eve Brown",
                29,
                "Seattle",
                "2020-08-22",
                None,
                None,
                False,
                3.2,
            ),  # No contact info (NULLs)
            (
                "Frank Miller",
                31,
                "Austin",
                "2019-12-14",
                "frank@example.com",
                "+1-555-0106",
                True,
                4.3,
            ),
            (
                "Grace Lee",
                27,
                "Denver",
                "2021-02-28",
                "grace@example.com",
                None,
                True,
                4.7,
            ),  # No phone (NULL)
            (
                "Henry Clark",
                33,
                "Portland",
                "2019-07-18",
                None,
                "+1-555-0108",
                True,
                None,
            ),  # No email, no reputation (NULLs)
        ]

        print("  📝 Creating people...")
        print("  💡 Using BatchContext for efficient bulk insertion")

        # Parse date strings to Java dates once (for reuse)
        from jpype import JClass

        LocalDate = JClass("java.time.LocalDate")

        # Create people using BatchContext for cleaner, more efficient code
        with db.batch_context(batch_size=100, parallel=2) as batch:
            for person in people_data:
                name, age, city, joined_date, email, phone, verified, reputation = (
                    person
                )

                # Parse date string to Java date
                date_obj = LocalDate.parse(joined_date)

                # Create vertex properties dict
                # (BatchContext handles None/NULL automatically)
                properties = {
                    "name": name,
                    "age": age,
                    "city": city,
                    "joined_date": date_obj,
                    "verified": verified,
                }

                # Add optional fields only if present
                if email:
                    properties["email"] = email
                if phone:
                    properties["phone"] = phone
                if reputation is not None:
                    properties["reputation"] = reputation

                # Create vertex using batch context
                # (automatically queued for async insertion)
                batch.create_vertex("Person", **properties)

                # Show which fields are NULL
                null_fields = []
                if not email:
                    null_fields.append("email")
                if not phone:
                    null_fields.append("phone")
                if reputation is None:
                    null_fields.append("reputation")

                null_str = f" (NULL: {', '.join(null_fields)})" if null_fields else ""
                print(f"    ✓ Queued person: {name} ({age}, {city}){null_str}")
        # BatchContext automatically waits for completion on exit

        print("  ✅ All people created successfully")

        # Create friendships with relationship properties
        print("  🤝 Creating friendships...")
        friendships = [
            ("Alice Johnson", "Bob Smith", "2020-05-15", "close"),
            ("Alice Johnson", "Carol Davis", "2021-07-20", "casual"),
            ("Bob Smith", "David Wilson", "2019-08-10", "close"),
            ("Bob Smith", "Frank Miller", "2020-01-25", "work"),
            ("Carol Davis", "Eve Brown", "2021-09-12", "close"),
            ("Carol Davis", "Grace Lee", "2021-08-05", "casual"),
            ("David Wilson", "Henry Clark", "2019-10-30", "old_friends"),
            ("Eve Brown", "Frank Miller", "2020-12-18", "casual"),
            ("Frank Miller", "Grace Lee", "2020-03-22", "work"),
            ("Grace Lee", "Henry Clark", "2021-05-14", "casual"),
            ("Alice Johnson", "Eve Brown", "2021-11-08", "close"),
            ("Bob Smith", "Henry Clark", "2020-06-03", "casual"),
        ]

        # Create friendships using Java API with vertex caching
        with db.transaction():
            # Build vertex cache by name for fast lookups
            person_cache = {}
            for person_wrapper in db.query("sql", "SELECT FROM Person"):
                name = person_wrapper.get_property("name")
                java_vertex = person_wrapper._java_result.getElement().get().asVertex()
                person_cache[name] = java_vertex

            # Create edges using cached vertices
            from jpype import JClass

            LocalDate = JClass("java.time.LocalDate")

            for person1, person2, since_date, closeness in friendships:
                # Get cached vertices
                v1 = person_cache[person1]
                v2 = person_cache[person2]

                # Parse date
                date_obj = LocalDate.parse(since_date)

                # Create bidirectional friendship edges
                edge1 = v1.newEdge(
                    "FRIEND_OF", v2, "since", date_obj, "closeness", closeness
                )
                edge1.save()

                edge2 = v2.newEdge(
                    "FRIEND_OF", v1, "since", date_obj, "closeness", closeness
                )
                edge2.save()

                print(f"    ✓ Connected {person1} ↔ {person2} ({closeness})")

        print(
            f"  ✅ Created {len(people_data)} people and "
            f"{len(friendships) * 2} friendship connections"
        )
        print(f"  ⏱️  Time: {time.time() - step_start:.3f}s")

    except Exception as e:
        print(f"  ❌ Error creating sample data: {e}")
        raise


def demonstrate_graph_queries(db):
    """Demonstrate various graph queries using both SQL and Cypher"""
    print("\n🔍 Demonstrating graph queries...")

    # SQL-based queries
    demonstrate_sql_queries(db)

    # Cypher-based queries
    demonstrate_cypher_queries(db)


def demonstrate_sql_queries(db):
    """Demonstrate graph queries using ArcadeDB's SQL MATCH syntax"""
    print("\n  📊 SQL MATCH Queries:")

    section_start = time.time()

    try:
        # 1. Find all friends of Alice using SQL MATCH
        print("\n    1️⃣ Find all friends of Alice (SQL MATCH):")
        query_start = time.time()
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

        # Using new to_list() for efficient bulk conversion
        friends = result.to_list()
        for friend in friends:
            # Automatic type conversion - no more str() needed!
            print(f"      👥 {friend['name']} from {friend['city']}")
        print(f"      ⏱️  Time: {time.time() - query_start:.3f}s")
        print(f"      💡 Used to_list() - returned {len(friends)} friends as dicts")

        # 2. Find friends of friends (2 degrees) using SQL MATCH
        print("\n    2️⃣ Find friends of friends of Alice (SQL MATCH):")
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

        # Using traditional iteration with automatic type conversion
        for row in result:
            name = row.get_property("name")  # Auto-converted to Python str
            through = row.get_property("through_friend")  # Auto-converted
            print(f"      🔗 {name} (through {through})")

        # 3. Find mutual friends using SQL MATCH
        print("\n    3️⃣ Find mutual friends between Alice and Bob (SQL MATCH):")
        result = db.query(
            "sql",
            """
            MATCH {type: Person, as: alice, where: (name = 'Alice Johnson')}
                  -FRIEND_OF->
                  {type: Person, as: mutual}
                  <-FRIEND_OF-
                  {type: Person, as: bob, where: (name = 'Bob Smith')}
            RETURN mutual.name as mutual_friend
            ORDER BY mutual.name
        """,
        )

        # Using first() to check if any results exist
        first_mutual = result.first()
        if first_mutual:
            print(f"      🤝 {first_mutual.get_property('mutual_friend')}")
            # Continue with rest of results
            for row in result:
                print(f"      🤝 {row.get_property('mutual_friend')}")
        else:
            print("      ℹ️  No mutual friends found")
            print("      💡 Used first() to check for results efficiently")

        # 4. Find friendship statistics using SQL aggregation
        print("\n    4️⃣ Friendship statistics by city (SQL aggregation):")
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

        # Automatic type conversion for all data types
        for row in result:
            city = row.get_property("city")  # Python str
            count = row.get_property("person_count")  # Python int
            avg_age = row.get_property("avg_age")  # Python float
            print(f"      • {city}: {count} people, avg age {avg_age:.1f}")

        # 5. Find people with NULL values (no email)
        print("\n    5️⃣ Find people without email (SQL NULL check):")
        result = db.query(
            "sql", "SELECT name, phone, verified FROM Person WHERE email IS NULL"
        )

        # Convert to list for counting and iteration
        people_without_email = result.to_list()
        for person in people_without_email:
            name = person["name"]  # Auto-converted Python str
            phone = person["phone"]  # None if NULL
            verified = person["verified"]  # Python bool
            phone_str = phone if phone else "No phone"
            verified_str = "✓ Verified" if verified else "Not verified"
            print(f"      • {name}: {phone_str}, {verified_str}")

        if not people_without_email:
            print("      (none found)")
        else:
            print(f"      💡 {len(people_without_email)} people without email")
            print("      💡 NULL values automatically converted to None")

        # 6. Find verified people with reputation scores
        print("\n    6️⃣ Verified people with reputation (exclude NULLs):")
        result = db.query(
            "sql",
            """SELECT name, reputation, city FROM Person
               WHERE verified = true AND reputation IS NOT NULL
               ORDER BY reputation DESC""",
        )

        # Automatic type conversion for floats
        for row in result:
            name = row.get_property("name")  # Python str
            reputation = row.get_property("reputation")  # Python float
            city = row.get_property("city")  # Python str
            stars = "⭐" * int(reputation)
            print(f"      • {name} ({city}): {reputation:.1f} {stars}")

        print(f"  ⏱️  SQL MATCH section: {time.time() - section_start:.3f}s")
        print("\n  💡 NEW features demonstrated in SQL queries:")
        print("      • to_list() - bulk conversion to list of dicts")
        print("      • first() - check if results exist")
        print("      • count_type() - efficient record counting")
        print("      • Automatic type conversion (str, int, float, bool, None)")

    except Exception as e:
        print(f"    ❌ Error in SQL queries: {e}")
        import traceback

        traceback.print_exc()


def demonstrate_cypher_queries(db):
    """Demonstrate graph queries using Cypher dialect"""
    print("\n  🎯 Cypher Queries:")

    section_start = time.time()

    try:
        # 1. Find all friends of Alice using Cypher
        print("\n    1️⃣ Find all friends of Alice (Cypher):")
        result = db.query(
            "cypher",
            """
            MATCH (alice:Person {name: 'Alice Johnson'})-[:FRIEND_OF]->(friend:Person)
            RETURN friend.name as name, friend.city as city
            ORDER BY friend.name
        """,
        )

        for row in result:
            print(
                f"      👥 {row.get_property('name')} from {row.get_property('city')}"
            )

        # 2. Find friends of friends using Cypher
        print("\n    2️⃣ Find friends of friends of Alice (Cypher):")
        result = db.query(
            "cypher",
            """
            MATCH (alice:Person {name: 'Alice Johnson'})
                  -[:FRIEND_OF]->(friend:Person)
                  -[:FRIEND_OF]->(fof:Person)
            WHERE fof.name <> 'Alice Johnson'
            RETURN DISTINCT fof.name as name, friend.name as through_friend
            ORDER BY fof.name
        """,
        )

        for row in result:
            name = row.get_property("name")
            through_friend = row.get_property("through_friend")
            print(f"      🔗 {name} (through {through_friend})")

        # 3. Find mutual friends using Cypher
        print("\n    3️⃣ Find mutual friends between Alice and Bob (Cypher):")
        result = db.query(
            "cypher",
            """
            MATCH (alice:Person {name: 'Alice Johnson'})
                  -[:FRIEND_OF]->(mutual:Person)
                  <-[:FRIEND_OF]-(bob:Person {name: 'Bob Smith'})
            RETURN mutual.name as mutual_friend
            ORDER BY mutual.name
        """,
        )

        mutual_friends = list(result)
        if mutual_friends:
            for row in mutual_friends:
                print(f"      🤝 {row.get_property('mutual_friend')}")
        else:
            print("      ℹ️  No mutual friends found")

        # 4. Find people by friendship closeness using Cypher
        print("\n    4️⃣ Find close friendships (Cypher):")
        result = db.query(
            "cypher",
            """
            MATCH (p1:Person)-[f:FRIEND_OF {closeness: 'close'}]->(p2:Person)
            RETURN p1.name as person1, p2.name as person2, f.since as since
            ORDER BY f.since
        """,
        )

        for row in result:
            person1 = row.get_property("person1")
            person2 = row.get_property("person2")
            since = row.get_property("since")
            print(f"      💙 {person1} → {person2} (since {since})")

        # 5. Find variable length paths using Cypher
        print("\n    5️⃣ Find connections within 3 steps from Alice (Cypher):")
        result = db.query(
            "cypher",
            """
            MATCH (alice:Person {name: 'Alice Johnson'})
                  -[:FRIEND_OF*1..3]-(connected:Person)
            WHERE connected.name <> 'Alice Johnson'
            RETURN DISTINCT connected.name as name, connected.city as city
            ORDER BY connected.name
        """,
        )

        for row in result:
            print(
                f"      🌐 {row.get_property('name')} from "
                f"{row.get_property('city')}"
            )

        print(f"  ⏱️  Cypher section: {time.time() - section_start:.3f}s")

    except Exception as e:
        print(f"    ❌ Error in Cypher queries: {e}")
        import traceback

        traceback.print_exc()


def compare_query_languages(db):
    """Compare SQL MATCH vs Cypher for the same queries"""
    print("\n  🆚 SQL MATCH vs Cypher Comparison:")

    section_start = time.time()

    try:
        print("\n    📝 Same Query, Different Languages:")
        print("    " + "=" * 50)

        # Query: Find friends with their friendship details
        print("\n    Query: Find Alice's friends with friendship details")
        print("    " + "-" * 50)

        print("\n    🔵 SQL MATCH syntax:")
        print(
            """      SELECT name, city FROM Person
      WHERE name IN (
          SELECT p2.name FROM Person p1, FRIEND_OF f, Person p2
          WHERE p1.name = 'Alice Johnson' AND f.out = p1 AND f.in = p2
      )"""
        )

        try:
            result_sql = db.query(
                "sql",
                """
                SELECT name, city FROM Person
                WHERE name IN (
                    SELECT DISTINCT p2.name
                    FROM Person p1, FRIEND_OF f, Person p2
                    WHERE p1.name = 'Alice Johnson'
                      AND f.out = p1 AND f.in = p2
                )
                ORDER BY name
            """,
            )

            sql_results = list(result_sql)
            for row in sql_results:
                name = row.get_property("name")
                city = row.get_property("city")
                print(f"      👥 {name} ({city})")
            sql_count = len(sql_results)
        except Exception:
            print("      💡 SQL query syntax not supported in this ArcadeDB version")
            print("      💡 Concept: Use subqueries to navigate relationships")
            sql_count = 0

        print("\n    🟢 Cypher syntax:")
        print(
            """      MATCH (alice:Person {name: 'Alice Johnson'})
            -[edge:FRIEND_OF]->(friend:Person)
      RETURN friend.name, friend.city, edge.closeness, edge.since"""
        )

        result_cypher = db.query(
            "cypher",
            """
            MATCH (alice:Person {name: 'Alice Johnson'})
                  -[edge:FRIEND_OF]->(friend:Person)
            RETURN friend.name as name, friend.city as city,
                   edge.closeness as closeness, edge.since as since
            ORDER BY friend.name
        """,
        )

        cypher_results = list(result_cypher)
        for row in cypher_results:
            name = row.get_property("name")
            city = row.get_property("city")
            closeness = row.get_property("closeness")
            since = row.get_property("since")
            print(f"      👥 {name} ({city}) - {closeness} since {since}")

        # Compare results if SQL worked
        if sql_count > 0:
            if sql_count == len(cypher_results):
                print(f"\n    ✅ Both queries returned {sql_count} identical results")
            else:
                cypher_count = len(cypher_results)
                print(
                    f"\n    ⚠️  Result count differs: "
                    f"SQL={sql_count}, Cypher={cypher_count}"
                )
        else:
            cypher_count = len(cypher_results)
            print(f"\n    ✅ Cypher query returned {cypher_count} results")
            print("    💡 SQL and Cypher would yield equivalent results")

        # Show syntax differences
        print("\n    🔍 Key Syntax Differences:")
        print("    " + "-" * 30)
        print("    SQL MATCH:")
        print("      • Nodes: {type: Person, as: alias, where: (condition)}")
        print("      • Edges: -EDGE_TYPE-> or -EDGE_TYPE->{as: alias}")
        print("      • Conditions: where: (property = 'value')")
        print("      • More verbose but explicit about types")
        print()
        print("    Cypher:")
        print("      • Nodes: (alias:Label {property: 'value'})")
        print("      • Edges: -[alias:TYPE]-> or -[:TYPE]-")
        print("      • Conditions: WHERE property = 'value'")
        print("      • More concise and intuitive for graph patterns")

        print("\n    💡 When to use each:")
        print("    " + "-" * 20)
        print("    • SQL MATCH: When mixing graph and relational queries")
        print("    • Cypher: For pure graph operations and complex traversals")
        print("    • Both support the same underlying graph operations")

        print(f"  ⏱️  Comparison section: {time.time() - section_start:.3f}s")

    except Exception as e:
        print(f"    ❌ Error in query comparison: {e}")
        import traceback

        traceback.print_exc()


def print_section_header(title, emoji="🔹"):
    """Print a formatted section header"""
    print(f"\n{emoji} {title}")
    print("=" * (len(title) + 4))


if __name__ == "__main__":
    print("🌐 ArcadeDB Python - Social Network Graph Example")
    print("=" * 55)
    main()
