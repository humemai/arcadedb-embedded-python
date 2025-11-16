#!/usr/bin/env python3
"""
Example 07: Stack Overflow Multi-Model Database
================================================

This example demonstrates ArcadeDB's multi-model capabilities by progressively
building a Stack Overflow dataset through three phases:
  1. Documents: Import XML data into typed document collections
  2. Graph: Transform documents into vertices and edges for relationship queries
  3. Vectors: Add semantic search capabilities with embeddings and HNSW indexes

Dataset: Stack Exchange Data Dump (https://archive.org/details/stackexchange)
- stackoverflow-small: cs.stackexchange.com (~650MB, 1.4M records)
- stackoverflow-medium: stats.stackexchange.com (~2.5GB, 5M records)
- stackoverflow-large: stackoverflow.com (~325GB, 350M records)

Usage:
    # Run all phases (default)
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small

    # Run specific phase
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phase 1
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phase 2

IMPORTANT - If Something Goes Wrong:
    ====================================
    If Phase 1 fails (data import errors, index creation failures, corruption, etc.),
    DO NOT try to fix it programmatically. The safest approach is:

    1. Delete the database directory:
       rm -rf my_test_databases/stackoverflow_*_db

    2. Re-run Phase 1 from scratch:
       python 07_stackoverflow_multimodel.py --dataset <name> --phase 1

    This takes ~40 minutes for stackoverflow-small, but guarantees a clean database.
    ArcadeDB's index management is fragile - attempting to drop/recreate indexes
    or fix corruption can make things worse.

Phase Dependencies:
    - Phase 1 (Documents + Indexes): Standalone, imports XML data and creates indexes
    - Phase 2 (Graph): Requires Phase 1 complete (validates document counts + indexes)
    - Phase 3 (Vectors): Requires Phase 1 + 2 complete
"""

import argparse
import os
import re
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

import arcadedb_embedded as arcadedb


class StackOverflowDatabase:
    """Main orchestrator for the Stack Overflow multi-model database."""

    DATASET_PATHS = {
        "stackoverflow-small": Path(__file__).parent / "data" / "stackoverflow-small",
        "stackoverflow-medium": (
            Path(__file__).parent / "data" / "stackoverflow-medium"
        ),
        "stackoverflow-large": Path(__file__).parent / "data" / "stackoverflow-large",
    }

    # Expected document counts per dataset (for phase validation)
    EXPECTED_COUNTS = {
        "stackoverflow-small": {
            "Badge": 182_975,
            "Comment": 195_781,
            "Post": 105_373,
            "PostHistory": 360_340,
            "PostLink": 11_005,
            "Tag": 668,
            "User": 138_727,
            "Vote": 411_166,
        },
        "stackoverflow-medium": {
            "Badge": 612_258,
            "Comment": 819_648,
            "Post": 425_735,
            "PostHistory": 1_525_713,
            "PostLink": 86_919,
            "Tag": 1_612,
            "User": 345_754,
            "Vote": 1_747_225,
        },
        "stackoverflow-large": {
            "Badge": 51_289_973,
            "Comment": 90_380_323,
            "Post": 59_819_048,
            "PostHistory": 160_790_317,
            "PostLink": 6_552_590,
            "Tag": 65_675,
            "User": 22_484_235,
            "Vote": 238_984_011,
        },
    }

    # Index definitions for Phase 1 (Document Model)
    # Format: (type_name, property_name, index_type, unique)
    #
    # STRATEGY: Minimal indexes for Phase 2 graph construction
    # Documents are temporary - only create indexes needed for edge creation
    PHASE_1_INDEXES = [
        # ========================================================================
        # PRIMARY KEY indexes (UNIQUE) - REQUIRED for Phase 2 graph building
        # ========================================================================
        # These enable O(log n) lookups when creating edges
        # Example: "Find User with Id=123" → Use UNIQUE index, not scan
        ("User", "Id", "LSM_TREE", True),
        ("Post", "Id", "LSM_TREE", True),
        ("Comment", "Id", "LSM_TREE", True),
        ("Badge", "Id", "LSM_TREE", True),
        ("Vote", "Id", "LSM_TREE", True),
        ("Tag", "Id", "LSM_TREE", True),
        ("PostHistory", "Id", "LSM_TREE", True),
        ("PostLink", "Id", "LSM_TREE", True),
        # ========================================================================
        # FOREIGN KEY indexes (NOTUNIQUE) - RECOMMENDED for Phase 2 batching
        # ========================================================================
        # Enable efficient "group by" patterns for edge creation
        # Example: "Find all Comments with UserId=123" → Process user's
        #          comments as batch
        # Without these: Still works, but slower (process one document at a time)
        ("Badge", "UserId", "LSM_TREE", False),
        ("Comment", "UserId", "LSM_TREE", False),
        ("Comment", "PostId", "LSM_TREE", False),
        ("Post", "OwnerUserId", "LSM_TREE", False),
        ("Post", "LastEditorUserId", "LSM_TREE", False),
        ("Post", "ParentId", "LSM_TREE", False),  # Answer → Question
        ("Post", "AcceptedAnswerId", "LSM_TREE", False),
        ("PostHistory", "UserId", "LSM_TREE", False),
        ("PostHistory", "PostId", "LSM_TREE", False),
        ("PostLink", "PostId", "LSM_TREE", False),
        ("PostLink", "RelatedPostId", "LSM_TREE", False),
        ("Tag", "WikiPostId", "LSM_TREE", False),
        ("Tag", "ExcerptPostId", "LSM_TREE", False),
        ("Vote", "UserId", "LSM_TREE", False),
        ("Vote", "PostId", "LSM_TREE", False),
        # ========================================================================
        # OPTIONAL: Performance indexes for Phase 1 document queries
        # ========================================================================
        # These are NOT needed for Phase 2 graph construction
        # Uncomment if you want to benchmark document query performance
        # But if documents are temporary, these add ~20-30 minutes to Phase 1
        # with no benefit for Phase 2
        #
        # ("Post", "Score", "LSM_TREE", False),
        # ("Post", "ViewCount", "LSM_TREE", False),
        # ("Post", "AnswerCount", "LSM_TREE", False),
        # ("Post", "CommentCount", "LSM_TREE", False),
        # ("PostHistory", "CreationDate", "LSM_TREE", False),
        # ("PostHistory", "PostHistoryTypeId", "LSM_TREE", False),
        # ("Vote", "CreationDate", "LSM_TREE", False),
        # ("Vote", "VoteTypeId", "LSM_TREE", False),
        # ("User", "Reputation", "LSM_TREE", False),
        # ("User", "CreationDate", "LSM_TREE", False),
        # ("Comment", "Score", "LSM_TREE", False),
        # ("Comment", "CreationDate", "LSM_TREE", False),
        # ("Badge", "Date", "LSM_TREE", False),
        # ("Badge", "Name", "LSM_TREE", False),
        # ("PostLink", "LinkTypeId", "LSM_TREE", False),
        # ("PostLink", "CreationDate", "LSM_TREE", False),
        # ("Tag", "Count", "LSM_TREE", False),
        # ("Post", "Body", "FULL_TEXT", False),
        # ("Post", "Title", "FULL_TEXT", False),
        # ("Post", "Tags", "FULL_TEXT", False),
        # ("Comment", "Text", "FULL_TEXT", False),
    ]

    def __init__(self, db_path: str, dataset: str):
        """Initialize the database connection.

        Args:
            db_path: Path to the ArcadeDB database directory
            dataset: Dataset size ('stackoverflow-small', 'stackoverflow-medium',
                    or 'stackoverflow-large')
        """
        self.db_path = db_path
        self.dataset = dataset
        self.dataset_path = self.DATASET_PATHS[dataset]
        self.db = None
        # Store query results for before/after comparison
        self.baseline_results = None
        self.indexed_results = None

        if not self.dataset_path.exists():
            print(f"Dataset not found at {self.dataset_path}")
            print("\nTo download the dataset, run:")
            print(f"  python download_data.py {dataset}")
            print("\nOr download manually from:")
            print("  https://archive.org/details/stackexchange")
            raise FileNotFoundError(
                f"Dataset not found at {self.dataset_path}. "
                f"Run: python download_data.py {dataset}"
            )

    def __enter__(self):
        """Context manager entry: open database connection."""
        # Clean up any existing database from previous runs
        if os.path.exists(self.db_path):
            shutil.rmtree(self.db_path)

        # Clean up log directory from previous runs
        if os.path.exists("./log"):
            shutil.rmtree("./log")

        self.db = arcadedb.create_database(self.db_path)
        return self

    def __enter_existing__(self):
        """Context manager entry: open existing database (for retry/rebuild)."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                f"Cannot open non-existent database."
            )
        self.db = arcadedb.open_database(self.db_path)
        return self

    def open_existing(self):
        """Open existing database without cleanup (for phase 2/3 or rebuild)."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. "
                f"Run Phase 1 first to create the database."
            )
        self.db = arcadedb.open_database(self.db_path)
        return self

    def validate_phase_1_complete(self) -> bool:
        """Validate that Phase 1 completed successfully by checking document counts.

        Returns:
            True if Phase 1 appears complete, False otherwise
        """
        if not os.path.exists(self.db_path):
            return False

        expected = self.EXPECTED_COUNTS.get(self.dataset)
        if not expected:
            print(f"⚠️  No expected counts defined for {self.dataset}")
            return False

        print("🔍 Validating Phase 1 completion...")

        # Check if all expected document types exist with correct counts
        all_valid = True
        for doc_type, expected_count in expected.items():
            if not self.db.schema.exists_type(doc_type):
                print(f"  ❌ {doc_type}: Type not found")
                all_valid = False
                continue

            # Count documents
            query = f"SELECT count(*) as count FROM {doc_type}"
            result = self.db.query("sql", query)
            # Convert ResultSet to list to access first record
            records = list(result)
            actual_count = records[0].get_property("count") if records else 0

            # Allow 1% tolerance for count differences (in case of data variations)
            tolerance = max(1, int(expected_count * 0.01))
            if abs(actual_count - expected_count) > tolerance:
                print(
                    f"  ⚠️  {doc_type}: Expected ~{expected_count:,} documents, "
                    f"found {actual_count:,}"
                )
                all_valid = False
            else:
                print(f"  ✓ {doc_type}: {actual_count:,} documents")

        if all_valid:
            print("✅ Phase 1 validation passed")
        else:
            print("❌ Phase 1 validation failed - run Phase 1 first")

        return all_valid

    def get_indexes_for_existing_types(
        self, index_definitions: List[tuple]
    ) -> List[tuple]:
        """Filter index definitions to only include types that exist in the database.

        Args:
            index_definitions: List of (type_name, property_name, index_type,
                unique) tuples

        Returns:
            Filtered list of index definitions for existing types
        """
        filtered_indexes = []
        for definition in index_definitions:
            type_name = definition[0]
            if self.db.schema.exists_type(type_name):
                filtered_indexes.append(definition)
        return filtered_indexes

    def validate_indexes_exist(self, index_definitions: List[tuple]) -> bool:
        """Validate that all required indexes exist in the database.

        Args:
            index_definitions: List of (type_name, property_name, index_type,
                unique) tuples

        Returns:
            True if all indexes exist, False otherwise
        """
        print("🔍 Validating indexes...")

        # Get all existing indexes
        all_indexes = self.db.schema.get_indexes()

        # Build a set of (type_name, property_name) for quick lookup
        existing_indexes = set()
        for idx in all_indexes:
            try:
                type_name = idx.getTypeName()
                property_names_raw = idx.getPropertyNames()

                # Skip bucket indexes (None property names)
                if property_names_raw is None:
                    continue

                property_names = list(property_names_raw)

                # Add each property to the set
                for prop in property_names:
                    existing_indexes.add((type_name, prop))
            except Exception:
                continue

        # Filter to only check indexes for existing types
        filtered_indexes = self.get_indexes_for_existing_types(index_definitions)

        # Check each required index
        missing_indexes = []
        for definition in filtered_indexes:
            type_name, property_name = definition[0], definition[1]
            if (type_name, property_name) not in existing_indexes:
                index_type = definition[2]
                missing_indexes.append((type_name, property_name, index_type))
                print(f"  ❌ Missing: {type_name}[{property_name}] ({index_type})")
            else:
                print(f"  ✓ Found: {type_name}[{property_name}]")

        if missing_indexes:
            print(f"\n❌ {len(missing_indexes)} indexes missing")
            return False
        else:
            print(f"\n✅ All {len(filtered_indexes)} required indexes exist")
            return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: close database connection."""
        if self.db:
            self.db.close()

    def close_with_wait(self):
        """Close database after waiting for all background compactions."""
        if not self.db:
            return

        print()
        print("⏳ Waiting for background compactions to complete...")
        try:
            async_exec = self.db.async_executor()
            # Wait indefinitely (None = no timeout)
            async_exec.wait_completion()
            print("  ✓ All compactions complete - safe to close")
        except Exception as e:
            print(f"  ⚠️  Could not verify compaction status: {e}")
            print("     Proceeding with database close...")

        self.__exit__(None, None, None)
        print("  ✓ Database closed")

    def execute_phase_1(
        self, analysis_limit: int = 1_000_000, batch_size: int = 50_000
    ):
        """Execute Phase 1: Import XML data as documents.

        Args:
            analysis_limit: Number of rows to analyze per file for schema inference
            batch_size: Number of documents to insert per transaction
        """
        print("=" * 80)
        print("PHASE 1: DOCUMENTS")
        print("=" * 80)
        print(f"Dataset: {self.dataset}")
        print(f"Path: {self.dataset_path}")
        print(f"Analysis limit: {analysis_limit:,} rows per file")
        print(f"Batch size: {batch_size:,} documents per transaction")
        print()

        # Step 1: Analyze XML files and infer schemas
        print("🔍 Step 1: Analyzing XML files to infer schemas...")
        analyzer = SchemaAnalyzer(analysis_limit=analysis_limit)

        xml_files = sorted(self.dataset_path.glob("*.xml"))
        for xml_file in xml_files:
            entity = xml_file.stem
            doc_type = entity.rstrip("s") if entity.endswith("s") else entity
            analyzer.analyze_xml_file(xml_file, doc_type)

        print(f"\n✅ Analyzed {len(analyzer.schemas)} XML files")

        # Step 2: Create document types from inferred schemas
        print("\n📝 Step 2: Creating document types...")
        builder = SchemaBuilder(self.db, analyzer.schemas)
        builder.create_document_types()

        # Step 3: Import all documents
        print("📥 Step 3: Importing documents...")
        importer = DocumentImporter(
            self.db, self.dataset_path, analyzer.schemas, batch_size=batch_size
        )
        importer.import_all_documents()

        print()
        print("✅ Documents imported.")
        print()

        # Step 4: Create indexes for Phase 2 graph construction
        print("📇 Step 4: Creating indexes for Phase 2 (PK + FK indexes)...")
        self.create_phase_1_indexes()
        print()

        # Step 5: Run validation queries to test indexes
        print("🔍 Step 5: Running validation queries (testing indexes)...")
        self.run_phase_1_queries()
        print()

        print("✅ Phase 1 complete!")
        print()

    def run_phase_1_queries(self):
        """Run minimal validation queries to test indexes for Phase 2.

        Phase 1 is just data import + indexes for Phase 2.
        These queries validate:
        1. Data was imported correctly (counts)
        2. Primary key indexes work (lookup by Id)
        3. Foreign key indexes work (lookup by UserId/PostId)

        Returns:
            List of query results with timing information
        """
        print()
        print("=" * 80)
        print("VALIDATION QUERIES - Phase 1: Document Model")
        print("=" * 80)
        print("Testing indexes for Phase 2 graph construction")
        print()

        # Get list of document types that were created
        # Note: ArcadeDB may not support NOT LIKE, so we filter in Python
        query = "SELECT name FROM schema:types ORDER BY name"
        doc_types_result = self.db.query("sql", query)
        doc_types = [
            record.get_property("name")
            for record in doc_types_result
            if not record.get_property("name").startswith("schema:")
        ]

        print(f"📊 Document types created: {', '.join(doc_types)}")
        print()

        # Check which types exist for targeted queries
        doc_type_set = set(doc_types)

        # Build minimal validation queries to test indexes
        queries = []

        # Q1: Always include document counts (validates data import)
        queries.append(
            (
                "Count documents by type",
                "COUNT_BY_TYPE",
                doc_types,
            )
        )

        # Q2-Q9: Test PRIMARY KEY indexes (UNIQUE) - one per type
        # These test O(log n) lookups by Id (critical for Phase 2 edge creation)
        if "User" in doc_type_set:
            queries.append(
                (
                    "Lookup User by Id [PK index test]",
                    "SELECT FROM User WHERE Id = 1 LIMIT 1",
                    "User",
                )
            )

        if "Post" in doc_type_set:
            queries.append(
                (
                    "Lookup Post by Id [PK index test]",
                    "SELECT FROM Post WHERE Id = 1 LIMIT 1",
                    "Post",
                )
            )

        if "Comment" in doc_type_set:
            queries.append(
                (
                    "Lookup Comment by Id [PK index test]",
                    "SELECT FROM Comment WHERE Id = 1 LIMIT 1",
                    "Comment",
                )
            )

        if "Badge" in doc_type_set:
            queries.append(
                (
                    "Lookup Badge by Id [PK index test]",
                    "SELECT FROM Badge WHERE Id = 1 LIMIT 1",
                    "Badge",
                )
            )

        if "Vote" in doc_type_set:
            queries.append(
                (
                    "Lookup Vote by Id [PK index test]",
                    "SELECT FROM Vote WHERE Id = 1 LIMIT 1",
                    "Vote",
                )
            )

        if "Tag" in doc_type_set:
            queries.append(
                (
                    "Lookup Tag by Id [PK index test]",
                    "SELECT FROM Tag WHERE Id = 1 LIMIT 1",
                    "Tag",
                )
            )

        if "PostHistory" in doc_type_set:
            queries.append(
                (
                    "Lookup PostHistory by Id [PK index test]",
                    "SELECT FROM PostHistory WHERE Id = 1 LIMIT 1",
                    "PostHistory",
                )
            )

        if "PostLink" in doc_type_set:
            queries.append(
                (
                    "Lookup PostLink by Id [PK index test]",
                    "SELECT FROM PostLink WHERE Id = 1 LIMIT 1",
                    "PostLink",
                )
            )

        # Q10-Q17: Test FOREIGN KEY indexes (NOTUNIQUE)
        # These test batch lookup patterns (find all X for user/post Y)
        if "Badge" in doc_type_set:
            queries.append(
                (
                    "Find Badges by UserId [FK index test]",
                    "SELECT FROM Badge WHERE UserId = 1 LIMIT 10",
                    "Badge",
                )
            )

        if "Comment" in doc_type_set:
            queries.extend(
                [
                    (
                        "Find Comments by UserId [FK index test]",
                        "SELECT FROM Comment WHERE UserId = 1 LIMIT 10",
                        "Comment",
                    ),
                    (
                        "Find Comments by PostId [FK index test]",
                        "SELECT FROM Comment WHERE PostId = 1 LIMIT 10",
                        "Comment",
                    ),
                ]
            )

        if "Post" in doc_type_set:
            queries.extend(
                [
                    (
                        "Find Posts by OwnerUserId [FK index test]",
                        "SELECT FROM Post WHERE OwnerUserId = 1 LIMIT 10",
                        "Post",
                    ),
                    (
                        "Find Answers by ParentId [FK index test]",
                        "SELECT FROM Post WHERE ParentId IS NOT NULL LIMIT 10",
                        "Post",
                    ),
                ]
            )

        if "PostHistory" in doc_type_set:
            queries.extend(
                [
                    (
                        "Find PostHistory by UserId [FK index test]",
                        "SELECT FROM PostHistory WHERE UserId = 1 LIMIT 10",
                        "PostHistory",
                    ),
                    (
                        "Find PostHistory by PostId [FK index test]",
                        "SELECT FROM PostHistory WHERE PostId = 1 LIMIT 10",
                        "PostHistory",
                    ),
                ]
            )

        if "Vote" in doc_type_set:
            queries.extend(
                [
                    (
                        "Find Votes by UserId [FK index test]",
                        "SELECT FROM Vote WHERE UserId = 1 LIMIT 10",
                        "Vote",
                    ),
                    (
                        "Find Votes by PostId [FK index test]",
                        "SELECT FROM Vote WHERE PostId = 1 LIMIT 10",
                        "Vote",
                    ),
                ]
            )

        # Run all queries and time them
        print(f"Running {len(queries)} validation queries...")
        print("-" * 80)
        query_results = []

        for query_num, (query_name, query_sql, query_data) in enumerate(queries, 1):
            try:
                # Special handling for COUNT_BY_TYPE
                if query_sql == "COUNT_BY_TYPE":
                    print(f"\nQ{query_num}: {query_name} [Multiple]")
                    print("-" * 40)
                    total_time = 0
                    for doc_type in query_data:
                        sql = f"SELECT count(*) as count FROM {doc_type}"
                        start = time.time()
                        result = self.db.query("sql", sql).first()
                        elapsed = time.time() - start
                        total_time += elapsed
                        count = result.get_property("count")
                        print(f"  {doc_type}: {count:,} documents " f"({elapsed:.3f}s)")

                    query_results.append(
                        {
                            "name": f"Q{query_num}: {query_name}",
                            "sql": "Multiple COUNT queries",
                            "count": len(query_data),
                            "time_s": total_time,
                        }
                    )
                    continue

                # Regular query execution
                start = time.time()
                result = self.db.query("sql", query_sql)
                records = list(result)
                elapsed = time.time() - start

                query_results.append(
                    {
                        "name": f"Q{query_num}: {query_name}",
                        "sql": query_sql,
                        "count": len(records),
                        "time_s": elapsed,
                        "records": records[:5],  # Keep first 5 for display
                        "doc_type": query_data,
                    }
                )

                print(f"\nQ{query_num}: {query_name} [{query_data}]")
                print(f"  Time: {elapsed:.3f}s | Results: {len(records)}")

                # Show sample results
                for i, record in enumerate(records[:3], 1):
                    props = {}
                    for prop_name in record.get_property_names():
                        value = record.get_property(prop_name)
                        # Truncate long strings
                        if isinstance(value, str) and len(value) > 60:
                            value = value[:57] + "..."
                        props[prop_name] = value
                    print(f"  {i}. {props}")

            except Exception as e:
                doc_type_label = (
                    query_data if query_sql != "COUNT_BY_TYPE" else "Multiple"
                )
                print(f"\nQ{query_num}: {query_name} [{doc_type_label}]")
                print(f"  ⚠️  Error: {e}")
                query_results.append(
                    {
                        "name": f"Q{query_num}: {query_name}",
                        "sql": (
                            query_sql if query_sql != "COUNT_BY_TYPE" else "Multiple"
                        ),
                        "error": str(e),
                        "doc_type": doc_type_label,
                    }
                )

        print()
        print("-" * 80)
        print("Query Summary:")
        print("-" * 80)
        for result in query_results:
            if "error" not in result:
                print(
                    f"{result['name']}: {result['time_s']:.3f}s "
                    f"({result['count']} results)"
                )
            else:
                print(f"{result['name']}: ERROR")

        print()
        print("=" * 80)

        return query_results

    def create_phase_1_indexes(self):
        """Create indexes needed for Phase 2 graph construction.

        Creates:
        - PRIMARY KEY indexes (UNIQUE) on Id fields for fast vertex lookups
        - FOREIGN KEY indexes (NOTUNIQUE) for efficient batch edge creation
        """
        # Set generous retry limits for all datasets
        max_retries = 360  # 18 hours max per index (360 × 180s)
        retry_delay = 180  # Wait 180 seconds (3 mins) between retries

        # Check for background async tasks before starting index creation
        print("Checking background task status...")
        try:
            async_exec = self.db.async_executor()
            async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
            print("  ✓ No background tasks running")
        except TimeoutError:
            print("  ℹ️  Background tasks still running (this is normal)")
        except Exception as e:
            print(f"  ℹ️  Could not check async status: {e}")
        print()

        # Get indexes to create based on existing types
        indexes_to_create = self.get_indexes_for_existing_types(self.PHASE_1_INDEXES)

        print(f"Creating {len(indexes_to_create)} indexes with retry logic...")
        print()

        # Create indexes with retry logic for compaction conflicts
        success_count = 0
        failed_indexes = []
        total_index_start = time.time()

        for idx, definition in enumerate(indexes_to_create, 1):
            type_name, property_name, index_type, unique = definition
            created = False
            index_start = time.time()
            retry_time = 0

            for attempt in range(1, max_retries + 1):
                try:
                    with self.db.transaction():
                        if index_type == "FULL_TEXT":
                            self.db.schema.create_index(
                                type_name, [property_name], index_type=index_type
                            )
                        else:
                            self.db.schema.create_index(
                                type_name,
                                [property_name],
                                unique=unique,
                                index_type=index_type,
                            )
                    total_time = time.time() - index_start
                    unique_label = " [UNIQUE]" if unique else ""
                    print(
                        f"  ✓ [{idx}/{len(indexes_to_create)}] "
                        f"{type_name}[{property_name}] ({index_type}{unique_label}) "
                        f"- {total_time:.2f}s"
                    )
                    created = True
                    success_count += 1
                    break
                except Exception as e:
                    error_msg = str(e)

                    # Check if retryable (compaction or index conflicts)
                    is_compaction_error = (
                        "NeedRetryException" in error_msg
                        and "asynchronous tasks" in error_msg
                    )
                    is_index_error = (
                        "IndexException" in error_msg
                        and "Error on creating index" in error_msg
                    )

                    if is_compaction_error or is_index_error:
                        if attempt < max_retries:
                            elapsed = attempt * retry_delay
                            reason = (
                                "compaction running"
                                if is_compaction_error
                                else "index conflict"
                            )
                            print(
                                f"  ⏳ [{idx}/{len(indexes_to_create)}] "
                                f"Waiting for {reason} "
                                f"(attempt {attempt}/{max_retries}, "
                                f"{elapsed}s elapsed)..."
                            )
                            time.sleep(retry_delay)
                            retry_time += retry_delay
                        else:
                            print(
                                f"  ❌ [{idx}/{len(indexes_to_create)}] "
                                f"Failed after {max_retries} retries: "
                                f"{type_name}[{property_name}]"
                            )
                            failed_indexes.append((type_name, property_name, error_msg))
                            break
                    else:
                        # Non-retryable error
                        print(
                            f"  ❌ [{idx}/{len(indexes_to_create)}] "
                            f"Failed: {type_name}[{property_name}]: {error_msg}"
                        )
                        failed_indexes.append((type_name, property_name, error_msg))
                        break

            if not created:
                print(f"  ⚠️  Skipping index {type_name}[{property_name}]")

        total_index_elapsed = time.time() - total_index_start

        print()
        print(
            f"✅ Created {success_count}/{len(indexes_to_create)} indexes "
            f"in {total_index_elapsed:.2f}s"
        )
        if failed_indexes:
            print(f"⚠️  {len(failed_indexes)} indexes failed")

        # Wait for final compactions triggered by index creation
        print()
        print("⏳ Waiting for background compactions...")
        try:
            async_exec = self.db.async_executor()
            async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
            print("  ✓ All compactions complete")
        except TimeoutError:
            print("  ℹ️  Compactions still running (normal for large datasets)")
            print("     Database is functional, will finish in background")
        except Exception as e:
            print(f"  ℹ️  Could not check async status: {e}")

    def create_indexes_and_compare(self):
        """Create indexes on frequently queried fields and compare performance."""
        # Set generous retry limits for all datasets
        max_retries = 360  # 18 hours max per index (360 × 180s)
        retry_delay = 180  # Wait 180 seconds (3 mins) between retries

        print()
        print()
        print("=" * 80)
        print("CREATING INDEXES FOR PERFORMANCE COMPARISON")
        print("=" * 80)
        print()

        # Check for background async tasks before starting index creation
        print("Checking background task status...")
        try:
            async_exec = self.db.async_executor()
            async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
            print("  ✓ No background tasks running")
        except TimeoutError:
            print("  ℹ️  Background tasks detected (will proceed anyway)")
        except Exception as e:
            print(f"  ℹ️  Could not check async status: {e}")
        print()

        print("Creating indexes on frequently queried fields...")
        print()

        # Get indexes to create based on existing types
        indexes_to_create = self.get_indexes_for_existing_types(self.PHASE_1_INDEXES)

        print(f"Creating {len(indexes_to_create)} indexes with retry logic...")
        print()

        # Create indexes with retry logic for compaction conflicts
        success_count = 0
        failed_indexes = []
        index_times = []  # Track (type_name, property, index_type, time)
        total_index_start = time.time()

        for idx, definition in enumerate(indexes_to_create, 1):
            type_name, property_name, index_type, unique = definition
            created = False
            index_start = time.time()
            retry_time = 0  # Track time spent waiting in retries

            for attempt in range(1, max_retries + 1):
                try:
                    attempt_start = time.time()
                    with self.db.transaction():
                        # FULL_TEXT indexes don't use the unique parameter
                        if index_type == "FULL_TEXT":
                            self.db.schema.create_index(
                                type_name, [property_name], index_type=index_type
                            )
                        else:
                            self.db.schema.create_index(
                                type_name,
                                [property_name],
                                unique=unique,
                                index_type=index_type,
                            )
                    creation_time = time.time() - attempt_start
                    total_time = time.time() - index_start
                    index_times.append(
                        (type_name, property_name, index_type, total_time)
                    )
                    unique_label = " [UNIQUE]" if unique else ""
                    print(
                        f"\n  ✓ [{idx}/{len(indexes_to_create)}] "
                        f"Created index on {type_name}[{property_name}] "
                        f"({index_type}{unique_label}) in {total_time:.2f}s "
                        f"(creation: {creation_time:.2f}s, "
                        f"retries: {retry_time:.0f}s)"
                    )
                    created = True
                    success_count += 1
                    break
                except Exception as e:
                    error_msg = str(e)

                    # Check if retryable (compaction or index conflicts)
                    is_compaction_error = (
                        "NeedRetryException" in error_msg
                        and "asynchronous tasks" in error_msg
                    )
                    is_index_error = (
                        "IndexException" in error_msg
                        and "Error on creating index" in error_msg
                    )

                    if is_compaction_error or is_index_error:
                        if attempt < max_retries:
                            elapsed = attempt * retry_delay
                            reason = (
                                "compaction running"
                                if is_compaction_error
                                else "index conflict"
                            )
                            print(
                                f"  ⏳ [{idx}/{len(indexes_to_create)}] "
                                f"Waiting for {reason} "
                                f"(attempt {attempt}/{max_retries}, "
                                f"{elapsed}s elapsed)..."
                            )
                            time.sleep(retry_delay)
                            retry_time += retry_delay
                        else:
                            print(
                                f"  ❌ [{idx}/{len(indexes_to_create)}] "
                                f"Failed to create index on "
                                f"{type_name}[{property_name}] "
                                f"after {max_retries} retries"
                            )
                            failed_indexes.append((type_name, property_name, error_msg))
                            break
                    else:
                        # Non-retryable error
                        print(
                            f"  ❌ [{idx}/{len(indexes_to_create)}] "
                            f"Failed to create index on "
                            f"{type_name}[{property_name}]: {error_msg}"
                        )
                        failed_indexes.append((type_name, property_name, error_msg))
                        break

            if not created:
                print(f"  ⚠️  Skipping index {type_name}[{property_name}]")

        total_index_elapsed = time.time() - total_index_start

        print()
        print(f"✅ Created {success_count}/{len(indexes_to_create)} indexes")
        if failed_indexes:
            print(f"⚠️  Failed to create {len(failed_indexes)} indexes:")
            for type_name, property_name, error in failed_indexes:
                print(f"   - {type_name}[{property_name}]: {error[:80]}...")

        # Print timing summary
        print()
        print("⏱️  Index Creation Timing Summary:")
        print(f"   Total time: {total_index_elapsed:.2f}s")

        if index_times:
            # Calculate statistics by index type
            lsm_times = [t for _, _, itype, t in index_times if itype == "LSM_TREE"]
            fulltext_times = [
                t for _, _, itype, t in index_times if itype == "FULL_TEXT"
            ]

            if lsm_times:
                avg_lsm = sum(lsm_times) / len(lsm_times)
                max_lsm = max(lsm_times)
                total_lsm = sum(lsm_times)
                print(
                    f"   LSM_TREE indexes ({len(lsm_times)}): "
                    f"avg={avg_lsm:.2f}s, max={max_lsm:.2f}s, "
                    f"total={total_lsm:.2f}s"
                )

            if fulltext_times:
                avg_ft = sum(fulltext_times) / len(fulltext_times)
                max_ft = max(fulltext_times)
                total_ft = sum(fulltext_times)
                print(
                    f"   FULL_TEXT indexes ({len(fulltext_times)}): "
                    f"avg={avg_ft:.2f}s, max={max_ft:.2f}s, "
                    f"total={total_ft:.2f}s"
                )

            # Show top 5 slowest indexes
            print()
            print("   Top 5 slowest indexes:")
            sorted_times = sorted(index_times, key=lambda x: x[3], reverse=True)
            for i, (tname, pname, itype, t) in enumerate(sorted_times[:5], 1):
                print(f"     {i}. {tname}[{pname}] ({itype}): {t:.2f}s")

        print()
        print("=" * 80)
        print()

        # Wait for final compactions triggered by index creation
        # Note: On large datasets, compaction can take hours
        print("⏳ Checking for background compactions...")
        try:
            async_exec = self.db.async_executor()
            # Quick check - don't block for hours
            async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
            print("  ✓ All background compactions completed")
        except TimeoutError:
            print("  ℹ️  Background compactions still running")
            print("     (This is normal and can take hours on large datasets)")
            print("     Indexes are functional and queries will work.")
        except Exception as e:
            print(f"  ℹ️  Could not check async status: {e}")
        print()

        # Rerun queries with indexes
        print("🔍 Re-running queries WITH indexes for comparison...")
        print("    Note: Performance may improve further as compactions complete")
        print()
        self.indexed_results = self.run_phase_1_queries()

        # Create comparison table
        self.print_performance_comparison()

    def print_performance_comparison(self):
        """Print a table comparing query performance before and after indexing."""
        if not self.baseline_results or not self.indexed_results:
            print("⚠️  Cannot create comparison - missing baseline or indexed results")
            return

        print()
        print("=" * 80)
        print("PERFORMANCE COMPARISON: WITHOUT vs WITH INDEXES")
        print("=" * 80)
        print()

        # Table header
        print(f"{'Query':<50} {'Before':<12} {'After':<12} {'Speedup':<12}")
        print("-" * 86)

        total_before = 0
        total_after = 0

        for baseline, indexed in zip(self.baseline_results, self.indexed_results):
            if "error" in baseline or "error" in indexed:
                continue

            query_name = baseline["name"]
            time_before = baseline["time_s"]
            time_after = indexed["time_s"]

            total_before += time_before
            total_after += time_after

            # Calculate speedup
            if time_after > 0:
                speedup = time_before / time_after
                speedup_str = f"{speedup:.1f}x"
            else:
                speedup_str = "N/A"

            # Truncate query name if too long
            if len(query_name) > 48:
                query_name = query_name[:45] + "..."

            print(
                f"{query_name:<50} {time_before:>10.3f}s {time_after:>10.3f}s "
                f"{speedup_str:>10}"
            )

        print("-" * 86)

        # Calculate overall speedup
        if total_after > 0:
            overall_speedup = total_before / total_after
            speedup_str = f"{overall_speedup:.1f}x"
        else:
            speedup_str = "N/A"

        print(
            f"{'TOTAL':<50} {total_before:>10.3f}s {total_after:>10.3f}s "
            f"{speedup_str:>10}"
        )

        print()
        print("=" * 80)
        print()

    def execute_phase_2(self):
        """Execute Phase 2: Build graph from documents."""
        print("=" * 80)
        print("PHASE 2: GRAPH")
        print("=" * 80)
        print(f"Dataset: {self.dataset}")
        print()

        # Step 1: Validate Phase 1 is complete (data + indexes)
        print("🔍 Step 1: Validating Phase 1 prerequisites...")
        print()

        # Check document counts
        if not self.validate_phase_1_complete():
            print()
            print("❌ Phase 1 data validation failed!")
            print("   Please run Phase 1 first:")
            print(
                f"   python 07_stackoverflow_multimodel.py "
                f"--dataset {self.dataset} --phase 1"
            )
            return

        print()

        # Check indexes
        if not self.validate_indexes_exist(self.PHASE_1_INDEXES):
            print()
            print("❌ Phase 1 indexes validation failed!")
            print("   Some required indexes are missing.")
            print()
            print("   Solution: Delete database and re-run Phase 1 from scratch")
            print(f"   rm -rf {self.db_path}")
            print(
                f"   python 07_stackoverflow_multimodel.py "
                f"--dataset {self.dataset} --phase 1"
            )
            return

        print()
        print("✅ Phase 1 prerequisites validated!")
        print()

        # TODO: Implement Phase 2 graph building
        print("⚠️  Phase 2 graph building not yet implemented.")
        print("    Will transform documents into graph vertices and edges")
        print("    for relationship queries.")
        print()

    def execute_phase_3(self):
        """Execute Phase 3: Add vector embeddings."""
        print("Generating embeddings and creating HNSW indexes...")
        print()

        # TODO: Implement Phase 3
        print("⚠️  Phase 3 not yet implemented.")
        print("    Will add semantic search capabilities with embeddings")
        print("    and HNSW indexes.")
        print()


class SchemaAnalyzer:
    """Analyzes XML files to infer schema automatically."""

    # Datetime/date patterns commonly found in Stack Exchange data
    DATETIME_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$",  # ISO with millis
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",  # ISO without millis
    ]
    DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"  # Date only (YYYY-MM-DD)

    # Integer range limits for type selection
    BYTE_MIN, BYTE_MAX = -128, 127
    SHORT_MIN, SHORT_MAX = -32768, 32767
    INTEGER_MIN, INTEGER_MAX = -2147483648, 2147483647

    def __init__(self, analysis_limit: int = 1_000_000):
        """Initialize the schema analyzer.

        Args:
            analysis_limit: Number of rows to analyze per file (default: 1M)
        """
        self.analysis_limit = analysis_limit
        self.schemas = {}  # doc_type -> {attr -> inferred_type}
        self.attr_stats = {}  # doc_type -> {attr -> {min, max, has_decimal}}

    def analyze_xml_file(self, xml_file: Path, doc_type: str) -> Dict[str, str]:
        """Analyze XML file and infer schema.

        Args:
            xml_file: Path to XML file
            doc_type: Document type name

        Returns:
            Dictionary mapping attribute names to inferred types
        """
        print(f"  📊 Analyzing {xml_file.name} (up to {self.analysis_limit:,} rows)...")

        # Track type candidates for each attribute
        attr_types = {}  # attr -> set of observed types
        attr_samples = {}  # attr -> list of sample values
        attr_numeric_values = {}  # attr -> list of numeric values for range analysis
        row_count = 0

        # Stream parse XML
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row_count += 1

                for attr_name, attr_value in elem.attrib.items():
                    if attr_name not in attr_types:
                        attr_types[attr_name] = set()
                        attr_samples[attr_name] = []
                        attr_numeric_values[attr_name] = []

                    # Skip empty/whitespace values
                    if not attr_value or attr_value.isspace():
                        continue

                    # Infer type from value
                    inferred = self._infer_type(attr_value, attr_name)
                    attr_types[attr_name].add(inferred)

                    # Track numeric values for range-based type selection
                    if inferred in ("BYTE", "SHORT", "INTEGER", "LONG"):
                        try:
                            numeric_val = int(attr_value)
                            attr_numeric_values[attr_name].append(numeric_val)
                        except ValueError:
                            pass

                    # Keep sample values (up to 10)
                    if len(attr_samples[attr_name]) < 10:
                        attr_samples[attr_name].append(attr_value)

                # Clear element to free memory
                elem.clear()
                root.clear()

                if row_count >= self.analysis_limit:
                    break

        # Determine final type for each attribute
        schema = {}
        for attr_name, type_set in attr_types.items():
            # If multiple types detected, use STRING as fallback
            if len(type_set) > 1:
                # Special case: numeric types can be unified
                if type_set.issubset({"BYTE", "SHORT", "INTEGER", "LONG"}):
                    # Use the largest numeric type needed
                    if "LONG" in type_set:
                        schema[attr_name] = "LONG"
                    elif "INTEGER" in type_set:
                        schema[attr_name] = "INTEGER"
                    elif "SHORT" in type_set:
                        schema[attr_name] = "SHORT"
                    else:
                        schema[attr_name] = "BYTE"
                    print(
                        f"      • {attr_name}: {schema[attr_name]} "
                        f"(unified from {type_set})"
                    )
                elif type_set.issubset({"FLOAT", "DOUBLE", "DECIMAL"}):
                    # Use DOUBLE for mixed decimal types (safe default)
                    schema[attr_name] = "DOUBLE"
                    print(f"      • {attr_name}: DOUBLE (unified from {type_set})")
                else:
                    schema[attr_name] = "STRING"
                    print(f"      • {attr_name}: STRING (type conflict: {type_set})")
            else:
                inferred_type = list(type_set)[0]

                # For numeric types, refine based on actual value ranges
                if (
                    inferred_type in ("BYTE", "SHORT", "INTEGER", "LONG")
                    and attr_numeric_values[attr_name]
                ):
                    min_val = min(attr_numeric_values[attr_name])
                    max_val = max(attr_numeric_values[attr_name])

                    # Choose smallest type that fits the range
                    if (
                        self.BYTE_MIN <= min_val <= self.BYTE_MAX
                        and self.BYTE_MIN <= max_val <= self.BYTE_MAX
                    ):
                        schema[attr_name] = "BYTE"
                    elif (
                        self.SHORT_MIN <= min_val <= self.SHORT_MAX
                        and self.SHORT_MIN <= max_val <= self.SHORT_MAX
                    ):
                        schema[attr_name] = "SHORT"
                    elif (
                        self.INTEGER_MIN <= min_val <= self.INTEGER_MAX
                        and self.INTEGER_MIN <= max_val <= self.INTEGER_MAX
                    ):
                        schema[attr_name] = "INTEGER"
                    else:
                        schema[attr_name] = "LONG"

                    print(
                        f"      • {attr_name}: {schema[attr_name]} "
                        f"(range: {min_val} to {max_val})"
                    )
                else:
                    schema[attr_name] = inferred_type
                    print(f"      • {attr_name}: {schema[attr_name]}")

        print(f"      Analyzed {row_count:,} rows, found {len(schema)} attributes")

        self.schemas[doc_type] = schema
        return schema

    def _infer_type(self, value: str, attr_name: str = "") -> str:
        """Infer ArcadeDB type from a string value.

        Args:
            value: String value to analyze
            attr_name: Attribute name (for context-aware heuristics)

        Returns:
            Inferred ArcadeDB type name
        """
        # Check for datetime with time component
        for pattern in self.DATETIME_PATTERNS:
            if re.match(pattern, value):
                return "DATETIME"

        # Check for date-only pattern (YYYY-MM-DD)
        if re.match(self.DATE_PATTERN, value):
            return "DATE"

        # Try integer BEFORE boolean check
        # (to avoid classifying "0" and "1" as boolean when they're actually IDs)
        try:
            int(value)
            # Initial classification as INTEGER
            # Range analysis in analyze_xml_file() will refine to BYTE/SHORT/LONG
            return "INTEGER"
        except ValueError:
            pass

        # Check for boolean (only for non-numeric values)
        if value.lower() in ("true", "false", "yes", "no"):
            return "BOOLEAN"

        # Try float/decimal
        try:
            float(value)
            # Check if it's a decimal value requiring precision
            # Heuristic: if has decimal point and more than 6 decimal places,
            # or attribute name suggests currency/precision, use DECIMAL
            if "." in value:
                decimal_places = len(value.split(".")[1])
                if decimal_places > 6 or any(
                    keyword in attr_name.lower()
                    for keyword in ["price", "amount", "currency", "balance"]
                ):
                    return "DECIMAL"
                # For 1-6 decimal places, distinguish FLOAT vs DOUBLE
                # Use FLOAT for smaller precision, DOUBLE for higher
                elif decimal_places <= 3:
                    return "FLOAT"
                else:
                    return "DOUBLE"
            else:
                # No decimal point but parses as float (e.g., "1e10")
                return "DOUBLE"
        except ValueError:
            pass

        # TODO: Detect LIST type (XML elements with multiple child elements)
        # This would require analyzing XML structure, not just values

        # Default to STRING
        return "STRING"


class SchemaBuilder:
    """Builds document types from inferred schemas."""

    def __init__(self, db: Any, schemas: Dict[str, Dict[str, str]]):
        """Initialize the schema builder.

        Args:
            db: ArcadeDB database connection
            schemas: Dictionary of doc_type -> {attr -> type}
        """
        self.db = db
        self.schemas = schemas

    def create_document_types(self):
        """Create all document types with properties."""
        print("\n📝 Creating document types...")

        with self.db.transaction():
            for doc_type, properties in self.schemas.items():
                # Check if type already exists
                if self.db.schema.exists_type(doc_type):
                    print(f"  ✓ {doc_type} (already exists)")
                    continue

                # Create document type
                self.db.schema.create_document_type(doc_type)

                # Create properties
                for prop_name, prop_type in properties.items():
                    self.db.schema.create_property(doc_type, prop_name, prop_type)

                print(f"  ✓ {doc_type} ({len(properties)} properties)")

        print(f"\nCreated {len(self.schemas)} document types.")
        print()


class DocumentImporter:
    """Imports XML documents into ArcadeDB."""

    def __init__(
        self,
        db: Any,
        dataset_path: Path,
        schemas: Dict[str, Dict[str, str]],
        batch_size: int = 10000,
    ):
        """Initialize the document importer.

        Args:
            db: ArcadeDB database connection
            dataset_path: Path to the Stack Exchange dataset directory
            schemas: Dictionary of doc_type -> {attr -> type}
            batch_size: Number of documents to insert per transaction
        """
        self.db = db
        self.dataset_path = dataset_path
        self.schemas = schemas
        self.batch_size = batch_size

    def import_all_documents(self):
        """Import all XML files (no assumed order)."""
        print("\n📥 Importing documents...")
        print()

        total_start = time.time()
        total_imported = 0

        # Process files in alphabetical order (no assumptions about relationships)
        xml_files = sorted(self.dataset_path.glob("*.xml"))

        for xml_file in xml_files:
            # Get document type from filename (Posts.xml -> Post)
            entity = xml_file.stem
            doc_type = entity.rstrip("s") if entity.endswith("s") else entity

            # Skip if we don't have schema for this file
            if doc_type not in self.schemas:
                print(f"  ⊗ {entity}: No schema found, skipping")
                continue

            count = self.import_xml_file(entity, doc_type, xml_file)
            total_imported += count

        total_elapsed = time.time() - total_start
        print()
        print(f"Total imported: {total_imported:,} documents in {total_elapsed:.2f}s")
        if total_elapsed > 0:
            print(f"Average throughput: {total_imported / total_elapsed:.2f} docs/sec")
        print()

    def import_xml_file(self, entity: str, doc_type: str, xml_file: Path) -> int:
        """Import a single XML file.

        Args:
            entity: Entity name (e.g., 'Posts', 'Users')
            doc_type: Document type name (e.g., 'Post', 'User')
            xml_file: Path to the XML file

        Returns:
            Number of documents imported
        """
        # Get file size for progress tracking
        file_size_mb = xml_file.stat().st_size / (1024 * 1024)
        print(f"  → {entity} ({xml_file.name}, {file_size_mb:.1f} MB)")

        start_time = time.time()
        count = 0
        batch = []

        # Stream parse XML file
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)  # Get root element

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                # Convert XML attributes to document
                doc = self._xml_to_document(doc_type, elem.attrib)
                batch.append(doc)
                count += 1

                # Insert batch when full
                if len(batch) >= self.batch_size:
                    self._insert_batch(doc_type, batch)
                    batch = []

                    # Progress update after every batch
                    current_time = time.time()
                    elapsed = current_time - start_time
                    rate = count / elapsed if elapsed > 0 else 0

                    print(f"    {count:,} documents ({rate:.0f} docs/sec)")

                # Clear element to free memory
                elem.clear()
                root.clear()

        # Insert remaining batch
        if batch:
            self._insert_batch(doc_type, batch)

        elapsed = time.time() - start_time
        rate = count / elapsed if elapsed > 0 else 0
        print(f"    ✓ {count:,} documents in {elapsed:.2f}s ({rate:.0f} docs/sec)")

        return count

    def _xml_to_document(self, doc_type: str, attrib: Dict[str, str]) -> Dict[str, Any]:
        """Convert XML attributes to a document with proper types.

        Args:
            doc_type: Document type name
            attrib: XML element attributes

        Returns:
            Document dictionary with typed values
        """
        schema = self.schemas[doc_type]
        doc = {}

        for key, value in attrib.items():
            if key not in schema:
                continue  # Skip unknown attributes

            expected_type = schema[key]

            # Handle NULL values (empty strings)
            if not value or value.isspace():
                doc[key] = None
                continue

            # Type conversion
            try:
                if expected_type in ("BYTE", "SHORT", "INTEGER"):
                    doc[key] = int(value)
                elif expected_type == "LONG":
                    doc[key] = int(value)
                elif expected_type == "FLOAT":
                    doc[key] = float(value)
                elif expected_type == "DOUBLE":
                    doc[key] = float(value)
                elif expected_type == "DECIMAL":
                    # For DECIMAL, keep as string to preserve precision
                    # ArcadeDB will handle the conversion
                    doc[key] = value
                elif expected_type == "BOOLEAN":
                    doc[key] = value.lower() in ("true", "1", "yes")
                elif expected_type == "DATE":
                    # ISO date format: YYYY-MM-DD
                    doc[key] = value
                elif expected_type == "DATETIME":
                    # ISO datetime format: 2021-01-01T00:00:00.000
                    doc[key] = value
                else:  # STRING or other types
                    doc[key] = value
            except (ValueError, TypeError):
                # Type conversion failed, store as string
                doc[key] = value

        return doc

    def _insert_batch(self, doc_type: str, batch: List[Dict[str, Any]]):
        """Insert a batch of documents.

        Args:
            doc_type: Document type name
            batch: List of documents to insert
        """
        if not batch:
            return

        # Use transaction context for batch insert
        with self.db.transaction():
            for doc_data in batch:
                doc = self.db.new_document(doc_type)
                for key, value in doc_data.items():
                    doc.set(key, value)
                doc.save()


def main():
    """Main entry point."""
    # Track overall timing
    script_start_time = time.time()

    parser = argparse.ArgumentParser(
        description="Stack Overflow Multi-Model Database Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all phases (1, 2, 3) - default behavior
  ARCADEDB_JVM_MAX_HEAP="2g" ARCADEDB_JVM_ARGS="-Xms2g"
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small

  # Run specific phase (Phase 2 requires Phase 1, Phase 3 requires 1+2)
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phase 1
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phase 2
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phase 3

  # Medium dataset: 3 GB XML → ~5M records
  ARCADEDB_JVM_MAX_HEAP="8g" ARCADEDB_JVM_ARGS="-Xms8g"
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-medium

  # Large dataset: 325 GB XML → ~350M records (REQUIRES 32GB+ RAM)
  ARCADEDB_JVM_MAX_HEAP="32g" ARCADEDB_JVM_ARGS="-Xms32g"
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-large --batch-size 5000

  # Phase 1 only: Force rebuild indexes on existing database (after failures)
  ARCADEDB_JVM_MAX_HEAP="32g" ARCADEDB_JVM_ARGS="-Xms32g"
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-large \\
      --phase 1 --force-rebuild-indexes
        """,
    )

    parser.add_argument(
        "--dataset",
        choices=["stackoverflow-small", "stackoverflow-medium", "stackoverflow-large"],
        default="stackoverflow-small",
        help="Dataset size to use (default: stackoverflow-small)",
    )

    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "all"],
        default="all",
        help=(
            "Which phase to run: 1 (Documents+Indexes), 2 (Graph), 3 (Vectors), "
            "or all (default: all). Phase 2 requires Phase 1, Phase 3 requires 1+2."
        ),
    )

    parser.add_argument(
        "--db-path",
        default=None,
        help=(
            "Database directory path "
            "(default: my_test_databases/stackoverflow_{size}_db)"
        ),
    )

    parser.add_argument(
        "--analysis-limit",
        type=int,
        default=1_000_000,
        help="Number of rows to analyze per file for schema inference (default: 1M)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50_000,
        help="Batch size for document import (default: 50000)",
    )

    args = parser.parse_args()

    # Set default database path with dataset size if not provided
    if args.db_path is None:
        # Extract size from dataset name (e.g., "stackoverflow-small" -> "small")
        size = args.dataset.split("-")[-1]
        args.db_path = f"my_test_databases/stackoverflow_{size}_db"

    # Determine which phases to run
    phases_to_run = []
    if args.phase == "all":
        phases_to_run = [1, 2, 3]
    else:
        phases_to_run = [int(args.phase)]

    # Run selected phases
    db_instance = StackOverflowDatabase(args.db_path, args.dataset)

    try:
        # Phase 1: Documents + Indexes
        if 1 in phases_to_run:
            # Create new database
            db_instance.__enter__()

            print("=" * 80)
            print("PHASE 1: DOCUMENTS + INDEXES")
            print("=" * 80)
            print()

            # Import documents and create indexes
            db_instance.execute_phase_1(
                analysis_limit=args.analysis_limit, batch_size=args.batch_size
            )

            # Final check (don't block for hours waiting for compaction)
            print()
            print("⏳ Final check: background compaction status...")
            try:
                async_exec = db_instance.db.async_executor()
                async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
                print("  ✓ All background operations completed")
            except TimeoutError:
                print("  ℹ️  Background compactions still running")
                print("     This is expected on large datasets and can take hours.")
                print("     The database is fully functional. Compactions will")
                print("     complete in background, improving performance over time.")
            except Exception as e:
                print(f"  ℹ️  Could not check async status: {e}")

            print()
            print("✅ Phase 1 complete!")
            print()

        # Phase 2: Graph (requires Phase 1)
        if 2 in phases_to_run:
            # If Phase 1 wasn't just run, open existing database and validate
            if 1 not in phases_to_run:
                db_instance.open_existing()

                if not db_instance.validate_phase_1_complete():
                    print("\n❌ Cannot run Phase 2 - Phase 1 is not complete")
                    print("   Run Phase 1 first")
                    return
                print()

            print("=" * 80)
            print("PHASE 2: GRAPH")
            print("=" * 80)
            print()

            db_instance.execute_phase_2()

            print()
            print("✅ Phase 2 complete!")
            print()

        # Phase 3: Vectors (requires Phase 1 + 2)
        if 3 in phases_to_run:
            # If previous phases weren't just run, open existing database
            if 1 not in phases_to_run and 2 not in phases_to_run:
                db_instance.open_existing()

                if not db_instance.validate_phase_1_complete():
                    print("\n❌ Cannot run Phase 3 - Phase 1 is not complete")
                    print("   Run Phase 1 first")
                    return

                # TODO: Add Phase 2 validation once implemented
                print()

            print("=" * 80)
            print("PHASE 3: VECTORS")
            print("=" * 80)
            print()

            db_instance.execute_phase_3()

            print()
            print("✅ Phase 3 complete!")
            print()

    finally:
        db_instance.close_with_wait()

    # Overall timing summary
    script_elapsed = time.time() - script_start_time
    print("\n" + "=" * 80)
    print("OVERALL TIMING")
    print("=" * 80)
    minutes = script_elapsed / 60
    print(f"Total script execution time: {script_elapsed:.2f}s ({minutes:.1f} min)")
    print("=" * 80)
    print()

    print("Done!")


if __name__ == "__main__":
    main()
