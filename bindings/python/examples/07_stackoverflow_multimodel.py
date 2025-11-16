#!/usr/bin/env python3
"""
Example 07: Stack Overflow Multi-Model Database

Demonstrates a complete multi-model workflow:
- Phase 1: XML → Documents + Indexes
- Phase 2: Documents → Graph (vertices + edges)
- Phase 3: Graph → Embeddings + HNSW

This example uses Stack Overflow data dump (Users, Posts, Comments, etc.)
to build a comprehensive knowledge graph with semantic search capabilities.

Dataset Options (disk size → recommended JVM heap):
- stackoverflow-tiny: ~34 MB → 2 GB (ARCADEDB_JVM_MAX_HEAP='2g' ARCADEDB_JVM_ARGS='-Xms2g')
- stackoverflow-small: ~642 MB → 4 GB (ARCADEDB_JVM_MAX_HEAP='4g' ARCADEDB_JVM_ARGS='-Xms4g')
- stackoverflow-medium: ~2.9 GB → 8 GB (ARCADEDB_JVM_MAX_HEAP='8g' ARCADEDB_JVM_ARGS='-Xms8g')
- stackoverflow-large: ~323 GB → 32+ GB (ARCADEDB_JVM_MAX_HEAP='32g' ARCADEDB_JVM_ARGS='-Xms32g')

Usage:
    # Phase 1 only (import + index)
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small

    # Analyze schema before importing (understand data structure and nullable fields)
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-tiny --analyze-only

    # All phases
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --phases 1 2 3

    # Custom batch size
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-medium --batch-size 10000

Requirements:
- arcadedb-embedded
- lxml (for XML parsing)
- Stack Overflow data dump in data/stackoverflow-{dataset}/ directory
"""

import argparse
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

import arcadedb_embedded as arcadedb
from lxml import etree

# =============================================================================
# Validation Module - Reusable Across All Phases
# =============================================================================


class StackOverflowValidator:
    """Standalone validator for Stack Overflow database phases.

    This class provides reusable validation methods that can be called
    from any phase (Phase 1, 2, 3) or standalone.
    """

    # Expected record counts for each dataset size
    EXPECTED_COUNTS = {
        "stackoverflow-tiny": {
            "User": 10_000,
            "Post": 10_000,
            "Comment": 10_000,
            "Badge": 10_000,
            "Vote": 10_000,
            "PostLink": 10_000,
            "Tag": 668,
            "PostHistory": 10_000,
            "total": 70_668,
        },
        "stackoverflow-small": {
            "User": 138_727,
            "Post": 105_373,
            "Comment": 195_781,
            "Badge": 182_975,
            "Vote": 411_166,
            "PostLink": 11_005,
            "Tag": 668,
            "PostHistory": 360_340,
            "total": 1_406_035,
        },
        "stackoverflow-medium": {
            "User": 345_754,
            "Post": 425_735,
            "Comment": 819_648,
            "Badge": 612_258,
            "Vote": 1_747_225,
            "PostLink": 86_919,
            "Tag": 1_612,
            "PostHistory": 1_525_713,
            "total": 5_564_864,
        },
        # Large dataset counts will be added once import completes
        "stackoverflow-large": {
            "User": 22_484_235,
            "Post": 59_819_048,
            "Comment": 90_380_323,
            "Badge": 51_289_973,
            "Vote": 238_984_011,
            "PostLink": 6_552_590,
            "Tag": 65_675,
            "PostHistory": 160_790_317,
            "total": 630_366_172,
        },
    }

    @staticmethod
    def get_phase1_validation_queries(random_user_id: int, random_post_id: int) -> list:
        """Get validation queries for Phase 1 document database.

        Args:
            random_user_id: Random user ID to use in queries
            random_post_id: Random post ID to use in queries

        Returns:
            List of tuples: (name, sql, validator_function)
        """
        return [
            (
                "Count users",
                "SELECT count(*) as count FROM User",
                lambda r: r[0].get_property("count") > 0,
            ),
            (
                "Count posts",
                "SELECT count(*) as count FROM Post",
                lambda r: r[0].get_property("count") > 0,
            ),
            (
                "Count comments",
                "SELECT count(*) as count FROM Comment",
                lambda r: r[0].get_property("count") > 0,
            ),
            (
                "Find user by ID",
                f"SELECT DisplayName FROM User WHERE Id = {random_user_id} LIMIT 1",
                lambda r: len(r) > 0,
            ),
            (
                "Count post types",
                "SELECT PostTypeId, count(*) as count FROM Post GROUP BY PostTypeId",
                lambda r: len(r) > 0,
            ),
            (
                "Find post by ID",
                f"SELECT Id FROM Post WHERE Id = {random_post_id} LIMIT 1",
                lambda r: len(r) > 0,
            ),
            (
                "Count badges",
                "SELECT count(*) as count FROM Badge",
                lambda r: r[0].get_property("count") > 0,
            ),
            (
                "Count votes",
                "SELECT count(*) as count FROM Vote",
                lambda r: r[0].get_property("count") > 0,
            ),
            (
                "Count tags",
                "SELECT count(*) as count FROM Tag",
                lambda r: r[0].get_property("count") > 0,
            ),
            (
                "Count post links",
                "SELECT count(*) as count FROM PostLink",
                lambda r: r[0].get_property("count") > 0,
            ),
        ]

    @staticmethod
    def get_phase1_expected_indexes() -> set:
        """Get expected Phase 1 indexes.

        28 total: 8 unique primary keys + 20 non-unique foreign keys.

        Returns:
            Set of tuples: (entity_name, field_name, is_unique)
        """
        return {
            # Primary key indexes (UNIQUE)
            ("User", "Id", True),
            ("Post", "Id", True),
            ("Comment", "Id", True),
            ("Badge", "Id", True),
            ("Vote", "Id", True),
            ("PostLink", "Id", True),
            ("Tag", "Id", True),
            ("PostHistory", "Id", True),
            # Foreign key indexes (NOTUNIQUE)
            ("User", "AccountId", False),
            ("Post", "AcceptedAnswerId", False),
            ("Post", "LastEditorUserId", False),
            ("Post", "ParentId", False),
            ("Post", "OwnerUserId", False),
            ("Post", "PostTypeId", False),
            ("Comment", "PostId", False),
            ("Comment", "UserId", False),
            ("Badge", "UserId", False),
            ("Vote", "PostId", False),
            ("Vote", "UserId", False),
            ("Vote", "VoteTypeId", False),
            ("PostLink", "PostId", False),
            ("PostLink", "LinkTypeId", False),
            ("PostLink", "RelatedPostId", False),
            ("Tag", "ExcerptPostId", False),
            ("Tag", "WikiPostId", False),
            ("PostHistory", "PostHistoryTypeId", False),
            ("PostHistory", "PostId", False),
            ("PostHistory", "UserId", False),
        }

    @staticmethod
    def verify_phase1_document_counts(
        db, entities: list = None, indent: str = "     ", dataset_size: str = None
    ) -> dict:
        """Verify document counts in Phase 1 database.

        Args:
            db: Database instance
            entities: List of entity names (default: all Phase 1 entities)
            indent: Indentation string for output formatting
            dataset_size: Dataset size name (e.g., 'stackoverflow-tiny')
                         for validation against expected counts

        Returns:
            Dict of {entity_name: count}
        """
        if entities is None:
            entities = [
                "User",
                "Post",
                "Comment",
                "Badge",
                "Vote",
                "PostLink",
                "Tag",
                "PostHistory",
            ]

        counts = {}
        total_count = 0
        mismatches = []

        # Get expected counts if dataset_size is provided
        expected = None
        if dataset_size and dataset_size in StackOverflowValidator.EXPECTED_COUNTS:
            expected = StackOverflowValidator.EXPECTED_COUNTS[dataset_size]

        for entity in entities:
            result = list(db.query("sql", f"SELECT count(*) as count FROM {entity}"))
            count = result[0].get_property("count")
            counts[entity] = count
            total_count += count

            # Check against expected counts
            status = ""
            if expected and expected.get(entity) is not None:
                expected_count = expected[entity]
                if count == expected_count:
                    status = " ✓"
                else:
                    status = f" ❌ (expected {expected_count:,})"
                    mismatches.append(
                        f"{entity}: got {count:,}, expected {expected_count:,}"
                    )

            print(f"{indent}• {entity:12} {count:>9,} documents{status}")

        print(f"{indent}{'─' * 40}")

        # Check total
        total_status = ""
        if expected and expected.get("total") is not None:
            expected_total = expected["total"]
            if total_count == expected_total:
                total_status = " ✓"
            else:
                total_status = f" ❌ (expected {expected_total:,})"
                mismatches.append(
                    f"Total: got {total_count:,}, " f"expected {expected_total:,}"
                )

        print(f"{indent}• {'Total':12} {total_count:>9,} documents{total_status}")

        # Report issues
        issues = []
        for entity, count in counts.items():
            if count == 0:
                issues.append(f"{entity} has 0 documents")

        if mismatches:
            print()
            print(f"{indent}❌ Count mismatches found:")
            for mismatch in mismatches:
                print(f"{indent}   • {mismatch}")

        if issues:
            print()
            print(f"{indent}⚠️  Issues found:")
            for issue in issues:
                print(f"{indent}   • {issue}")

        return counts

    @staticmethod
    def verify_phase1_indexes(
        db, expected_indexes: set = None, indent: str = "     "
    ) -> bool:
        """Verify all expected Phase 1 indexes exist in database.

        Args:
            db: Database instance
            expected_indexes: Set of (entity, field, is_unique) tuples
            indent: Indentation string for output formatting

        Returns:
            True if all expected indexes are found
        """
        if expected_indexes is None:
            expected_indexes = StackOverflowValidator.get_phase1_expected_indexes()

        # Get actual indexes from database
        indexes = db.schema.get_indexes()

        # Parse actual index names and build set
        actual_indexes = set()
        for idx in indexes:
            idx_name = str(idx.getName())  # Convert to Python string
            is_unique = idx.isUnique()

            # Parse index name format: "EntityName[FieldName]"
            if "[" in idx_name and "]" in idx_name:
                # Use Python string methods, not Java regex split
                bracket_start = idx_name.index("[")
                bracket_end = idx_name.index("]")
                entity = idx_name[:bracket_start]
                field = idx_name[bracket_start + 1 : bracket_end]
                actual_indexes.add((entity, field, is_unique))

        # Find missing and extra indexes
        missing = expected_indexes - actual_indexes
        extra_named = actual_indexes - expected_indexes

        print(f"{indent}• Total indexes in DB: {len(indexes)}")
        print(f"{indent}• Expected named indexes: {len(expected_indexes)}")
        print(f"{indent}• Found named indexes: {len(actual_indexes)}")

        if missing:
            print()
            print(f"{indent}❌ Missing {len(missing)} expected indexes:")
            for entity, field, unique in sorted(missing):
                idx_type = "UNIQUE" if unique else "NOTUNIQUE"
                print(f"{indent}   • {entity}[{field}] ({idx_type})")

        if extra_named:
            print()
            print(f"{indent}ℹ️  Found {len(extra_named)} unexpected named indexes:")
            for entity, field, unique in sorted(extra_named):
                idx_type = "UNIQUE" if unique else "NOTUNIQUE"
                print(f"{indent}   • {entity}[{field}] ({idx_type})")

        if not missing:
            print(f"{indent}✅ All {len(expected_indexes)} expected indexes present")
            return True
        else:
            return False

    @staticmethod
    def run_phase1_validation_queries(
        db, random_user_id: int, random_post_id: int, indent: str = "     "
    ) -> bool:
        """Run validation queries on Phase 1 database.

        Args:
            db: Database instance
            random_user_id: Random user ID for queries
            random_post_id: Random post ID for queries
            indent: Indentation string for output formatting

        Returns:
            True if all queries pass
        """
        queries = StackOverflowValidator.get_phase1_validation_queries(
            random_user_id, random_post_id
        )

        all_passed = True
        for name, sql, validator in queries:
            try:
                start = time.time()
                results = list(db.query("sql", sql))
                elapsed = time.time() - start

                if validator(results):
                    print(f"{indent}   ✓ {name}: {len(results)} rows ({elapsed:.4f}s)")
                else:
                    print(f"{indent}   ❌ {name}: Validation failed")
                    all_passed = False
            except Exception as e:
                print(f"{indent}   ❌ {name}: {e}")
                all_passed = False

        return all_passed

    @staticmethod
    def validate_phase1(
        db_path: Path, dataset_size: str = None, verbose: bool = True, indent: str = ""
    ) -> tuple[bool, dict]:
        """Complete Phase 1 validation (standalone entry point).

        Args:
            db_path: Path to Phase 1 database
            dataset_size: Dataset size name for count validation
            verbose: Print detailed output
            indent: Indentation for output

        Returns:
            Tuple of (validation_passed, counts_dict)
        """
        import random

        if verbose:
            print(f"{indent}📊 Validating Phase 1 Database")
            if dataset_size:
                print(f"{indent}   Dataset: {dataset_size}")
            print(f"{indent}{'=' * 70}")
            print()

        validation_passed = True
        counts = {}

        with arcadedb.open_database(str(db_path)) as db:
            # Verify document counts
            if verbose:
                print(f"{indent}  Document Counts:")
            counts = StackOverflowValidator.verify_phase1_document_counts(
                db, indent=f"{indent}     ", dataset_size=dataset_size
            )
            if verbose:
                print()

            # Verify indexes
            if verbose:
                print(f"{indent}  Index Verification:")
            indexes_valid = StackOverflowValidator.verify_phase1_indexes(
                db, indent=f"{indent}     "
            )
            validation_passed = validation_passed and indexes_valid
            if verbose:
                print()

            # Run validation queries
            if verbose:
                print(f"{indent}  Validation Queries:")

            # Sample random IDs
            random.seed(42)
            user_sample = list(db.query("sql", "SELECT Id FROM User LIMIT 100"))
            post_sample = list(db.query("sql", "SELECT Id FROM Post LIMIT 100"))

            if user_sample and post_sample:
                random_user_id = random.choice(user_sample).get_property("Id")
                random_post_id = random.choice(post_sample).get_property("Id")

                queries_valid = StackOverflowValidator.run_phase1_validation_queries(
                    db, random_user_id, random_post_id, indent=f"{indent}     "
                )
                validation_passed = validation_passed and queries_valid
            else:
                if verbose:
                    print(f"{indent}     ⚠️  Insufficient data for queries")
                validation_passed = False

            if verbose:
                print()

        if verbose:
            print(f"{indent}{'=' * 70}")
            if validation_passed:
                print(f"{indent}✅ Phase 1 validation passed")
            else:
                print(f"{indent}❌ Phase 1 validation failed")
            print(f"{indent}{'=' * 70}")
            print()

        return validation_passed, counts


# =============================================================================
# Schema Analysis Classes
# =============================================================================


@dataclass
class FieldStats:
    """Statistics for a single field."""

    type_name: str
    count: int
    null_count: int = 0
    sample_values: List[str] = field(default_factory=list)
    avg_length: float = 0.0
    avg_tokens: float = 0.0
    min_value: int = None
    max_value: int = None


@dataclass
class EntitySchema:
    """Schema information for an entity (document type)."""

    name: str
    source_file: Path
    fields: Dict[str, FieldStats]
    row_count: int
    has_primary_key: bool


class SchemaAnalyzer:
    """Analyzes data files to infer types and statistics."""

    # Datetime/date patterns
    DATETIME_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$",  # ISO with millis
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",  # ISO without millis
    ]
    DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"

    # Integer ranges
    BYTE_MIN, BYTE_MAX = -128, 127
    SHORT_MIN, SHORT_MAX = -32768, 32767
    INTEGER_MIN, INTEGER_MAX = -2147483648, 2147483647

    def __init__(self, analysis_limit: int = 1_000_000):
        """Initialize analyzer.

        Args:
            analysis_limit: Max rows to analyze per file (for performance)
        """
        self.analysis_limit = analysis_limit

    def analyze_xml_file(self, xml_file: Path) -> EntitySchema:
        """Analyze XML file and infer schema.

        Args:
            xml_file: Path to XML file

        Returns:
            EntitySchema with inferred types and statistics
        """
        entity_name = xml_file.stem.rstrip("s")  # Users.xml → User

        print(f"  📊 Analyzing {xml_file.name}...")
        print(f"      (sampling up to {self.analysis_limit:,} rows)")

        # Track field statistics
        field_types = defaultdict(set)  # field → set of observed types
        field_values = defaultdict(list)  # field → list of values
        field_null_counts = defaultdict(int)
        all_fields_seen = set()
        row_count = 0

        # Stream parse XML
        context = etree.iterparse(str(xml_file), events=("end",))

        for event, elem in context:
            if elem.tag == "row":
                row_count += 1

                # Track which fields exist in this row
                row_fields = set(elem.attrib.keys())
                all_fields_seen.update(row_fields)

                for attr_name, attr_value in elem.attrib.items():
                    # Track value for statistics
                    field_values[attr_name].append(attr_value)

                    # Infer type
                    inferred_type = self._infer_type(attr_value, attr_name)
                    field_types[attr_name].add(inferred_type)

                # Track which fields are missing (nulls)
                for missing_field in all_fields_seen - row_fields:
                    field_null_counts[missing_field] += 1

                # Clear element to save memory
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

                # Limit analysis for large files
                if row_count >= self.analysis_limit:
                    break

        # Build field statistics
        fields = {}
        for field_name in all_fields_seen:
            type_set = field_types.get(field_name, {"STRING"})
            values = field_values.get(field_name, [])

            # Choose most specific type
            final_type = self._resolve_type(type_set, values)

            # Calculate statistics
            stats = FieldStats(
                type_name=final_type,
                count=len(values),
                null_count=field_null_counts.get(field_name, 0),
                sample_values=values[:5] if values else [],
            )

            # String length stats
            if final_type in ["STRING", "TEXT"]:
                lengths = [len(str(v)) for v in values if v]
                stats.avg_length = sum(lengths) / len(lengths) if lengths else 0
                # Estimate tokens: ~1 token per 4 chars (English text heuristic)
                stats.avg_tokens = stats.avg_length / 4.0 if stats.avg_length else 0

            # Numeric range stats
            if final_type in ["BYTE", "SHORT", "INTEGER", "LONG"]:
                numeric_values = [int(v) for v in values if v]
                if numeric_values:
                    stats.min_value = min(numeric_values)
                    stats.max_value = max(numeric_values)

            fields[field_name] = stats

        print(f"      → {row_count:,} rows, {len(fields)} fields")

        return EntitySchema(
            name=entity_name,
            source_file=xml_file,
            fields=fields,
            row_count=row_count,
            has_primary_key="Id" in fields,
        )

    def _infer_type(self, value: str, field_name: str = "") -> str:
        """Infer ArcadeDB type from string value."""
        if not value:
            return "STRING"

        # Check datetime patterns
        for pattern in self.DATETIME_PATTERNS:
            if re.match(pattern, value):
                return "DATETIME"

        if re.match(self.DATE_PATTERN, value):
            return "DATE"

        # Try numeric types
        try:
            num = int(value)
            if self.BYTE_MIN <= num <= self.BYTE_MAX:
                return "BYTE"
            elif self.SHORT_MIN <= num <= self.SHORT_MAX:
                return "SHORT"
            elif self.INTEGER_MIN <= num <= self.INTEGER_MAX:
                return "INTEGER"
            else:
                return "LONG"
        except ValueError:
            pass

        # Try float
        try:
            float(value)
            return "FLOAT"
        except ValueError:
            pass

        # Try boolean
        if value.lower() in ["true", "false"]:
            return "BOOLEAN"

        # Default to string
        return "STRING"

    def _resolve_type(self, type_set: Set[str], values: List[str]) -> str:
        """Resolve final type when multiple types observed."""
        if len(type_set) == 1:
            return next(iter(type_set))

        # If multiple types, use most general
        type_hierarchy = ["BYTE", "SHORT", "INTEGER", "LONG", "FLOAT", "STRING"]

        for general_type in reversed(type_hierarchy):
            if general_type in type_set:
                return general_type

        return "STRING"


# =============================================================================
# Helper Functions
# =============================================================================


def get_retry_config(dataset_size):
    """Get retry configuration based on dataset size.

    Args:
        dataset_size: Full dataset name (e.g., 'stackoverflow-tiny')
    """
    # Extract size suffix (tiny, small, medium, large)
    size = dataset_size.split("-")[-1] if "-" in dataset_size else dataset_size

    configs = {
        "tiny": {"retry_delay": 10, "max_retries": 60},  # 10 min max
        "small": {"retry_delay": 60, "max_retries": 120},  # 2 hours max
        "medium": {"retry_delay": 180, "max_retries": 200},  # 10 hours max
        "large": {"retry_delay": 300, "max_retries": 200},  # 16.7 hours max
    }
    return configs.get(size, configs["tiny"])


def print_batch_stats(
    count: int,
    embed_time: float = None,
    query_time: float = None,
    db_time: float = None,
    total_time: float = None,
    item_name: str = "items",
):
    """Print per-batch statistics in a consistent format.

    Args:
        count: Number of items in batch
        embed_time: Time spent on embeddings (optional)
        query_time: Time spent on queries (optional, for edges)
        db_time: Time spent on database operations
        total_time: Total batch time
        item_name: Name for items (e.g., "users", "edges", "v", "e")
    """
    rate = count / total_time if total_time and total_time > 0 else 0

    parts = [f"    → Batch: {count:,} {item_name} |"]

    if embed_time is not None:
        parts.append(f"embed: {embed_time:.1f}s |")
    if query_time is not None:
        parts.append(f"query: {query_time:.1f}s |")
    if db_time is not None:
        parts.append(f"db: {db_time:.1f}s |")
    if total_time is not None:
        parts.append(f"total: {total_time:.1f}s ({rate:.0f} /s)")

    print(" ".join(parts))


def print_summary_stats(
    total_count: int,
    elapsed: float,
    batch_times: List[tuple],
    item_name: str = "items",
    has_embed: bool = False,
    has_query: bool = False,
):
    """Print summary statistics with averages.

    Args:
        total_count: Total number of items created
        elapsed: Total elapsed time
        batch_times: List of tuples (count, [embed_t], [query_t], db_t, total_t)
        item_name: Name for items (e.g., "users", "edges")
        has_embed: Whether batches have embedding time
        has_query: Whether batches have query time (for edges)
    """
    if not batch_times:
        rate = total_count / elapsed if elapsed > 0 else 0
        print(
            f"    ✓ Created {total_count:,} {item_name} in "
            f"{elapsed:.1f}s ({rate:.0f} /s)"
        )
        return

    avg_rate = total_count / elapsed if elapsed > 0 else 0
    parts = [f"    ✓ Summary: {total_count:,} {item_name} in " f"{elapsed:.1f}s |"]

    if has_embed:
        # batch_times format: (count, embed_t, db_t, total_t)
        total_embed = sum(t[1] for t in batch_times)
        total_db = sum(t[2] for t in batch_times)
        avg_embed = total_embed / len(batch_times)
        avg_db = total_db / len(batch_times)
        parts.append(f"avg embed: {avg_embed:.1f}s |")
        parts.append(f"avg db: {avg_db:.1f}s |")
    elif has_query:
        # batch_times format: (count, query_t, db_t, total_t)
        total_query = sum(t[1] for t in batch_times)
        total_db = sum(t[2] for t in batch_times)
        avg_query = total_query / len(batch_times)
        avg_db = total_db / len(batch_times)
        parts.append(f"avg query: {avg_query:.1f}s |")
        # Only show db time if it's significant
        if avg_db > 0.01:
            parts.append(f"avg db: {avg_db:.1f}s |")
    else:
        # batch_times format: (count, db_t)
        total_db = sum(t[1] for t in batch_times)
        avg_db = total_db / len(batch_times)
        parts.append(f"avg db: {avg_db:.1f}s |")

    parts.append(f"avg rate: {avg_rate:.0f} /s")
    print(" ".join(parts))


def create_indexes(db, indexes, retry_delay=10, max_retries=60, verbose=True):
    """
    Create indexes with retry logic for compaction conflicts.

    Args:
        db: Database instance
        indexes: List of (table, column, uniqueness) tuples
        retry_delay: Seconds to wait between retries
        max_retries: Maximum number of retry attempts
        verbose: If True, print progress messages

    Returns:
        tuple: (success_count, failed_indexes)
    """
    if verbose:
        print(f"\n  Creating {len(indexes)} indexes with retry logic...")
        print(f"    Retry: {retry_delay}s delay, {max_retries} max attempts")

    success_count = 0
    failed_indexes = []

    for idx, (table, column, uniqueness) in enumerate(indexes, 1):
        created = False

        for attempt in range(1, max_retries + 1):
            try:
                with db.transaction():
                    if uniqueness == "UNIQUE":
                        db.schema.create_index(table, [column], unique=True)
                    elif uniqueness == "FULL_TEXT":
                        db.schema.create_index(table, [column], index_type="FULL_TEXT")
                    else:  # NOTUNIQUE
                        db.schema.create_index(table, [column], unique=False)

                if verbose:
                    print(
                        f"\n    ✅ [{idx}/{len(indexes)}] {table}[{column}] {uniqueness}"
                    )

                created = True
                success_count += 1
                break

            except Exception as e:
                error_msg = str(e)

                # Check if retryable
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
                            "compaction" if is_compaction_error else "index conflict"
                        )
                        if verbose:
                            print(
                                f"    ⏳ [{idx}/{len(indexes)}] Waiting for {reason} "
                                f"(attempt {attempt}/{max_retries}, {elapsed}s elapsed)..."
                            )
                        time.sleep(retry_delay)
                    else:
                        if verbose:
                            print(
                                f"    ❌ [{idx}/{len(indexes)}] Failed after {max_retries} retries: "
                                f"{table}[{column}]"
                            )
                        failed_indexes.append((table, column, error_msg))
                        break
                else:
                    # Non-retryable error
                    if verbose:
                        print(
                            f"    ❌ [{idx}/{len(indexes)}] {table}[{column}]: {error_msg}"
                        )
                    failed_indexes.append((table, column, error_msg))
                    break

        if not created and verbose:
            print(f"    ⚠️  Skipped {table}[{column}]")

    # Wait for all background index building to complete
    if success_count > 0 and verbose:
        print("\n  ⏳ Waiting for all index builds to complete...")

    try:
        async_exec = db.async_executor()
        async_exec.wait_completion()
        if success_count > 0 and verbose:
            print("  ✅ All index builds complete")
    except Exception as e:
        if verbose:
            print(f"  ⚠️  Could not verify index build completion: {e}")
            print("     Indexes may still be building in background...")

    return success_count, failed_indexes


def close_database_safely(db, verbose=True):
    """Close database after waiting for all background compactions."""
    if verbose:
        print("\n  Finalizing database...")
        print("    ⏳ Waiting for background compactions to complete...")

    try:
        async_exec = db.async_executor()
        async_exec.wait_completion()
        if verbose:
            print("    ✅ All compactions complete - safe to close")
    except Exception as e:
        if verbose:
            print(f"    ⚠️  Could not verify compaction status: {e}")
            print("       Proceeding with database close...")

    db.close()
    if verbose:
        print("    ✅ Database closed cleanly")


# =============================================================================
# Phase 1: XML → Documents + Indexes
# =============================================================================


class Phase1XMLImporter:
    """Handles Phase 1: Import XMLs → Documents → Create Indexes."""

    def __init__(
        self, db_path, data_dir, batch_size, dataset_size, analysis_limit=1_000_000
    ):
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir)
        self.batch_size = batch_size
        self.dataset_size = dataset_size
        self.analysis_limit = analysis_limit
        self.db = None
        self.schemas = {}  # Store discovered schemas

    def run(self):
        """Execute Phase 1: XML import and index creation."""
        print("=" * 80)
        print("PHASE 1: XML → Documents + Indexes")
        print("=" * 80)
        print(f"Dataset: {self.dataset_size}")
        print(f"Batch size: {self.batch_size} records/commit")
        print(f"Data directory: {self.data_dir}")
        print(f"Database path: {self.db_path}")
        print()

        phase_start = time.time()

        try:
            # Step 0: Analyze schemas (fast, discovers all attributes)
            print("Step 0: Analyzing XML schemas...")
            analysis_start = time.time()

            analyzer = SchemaAnalyzer(analysis_limit=self.analysis_limit)
            xml_files = [
                "Users.xml",
                "Posts.xml",
                "Comments.xml",
                "Badges.xml",
                "Votes.xml",
                "PostLinks.xml",
                "Tags.xml",
                "PostHistory.xml",
            ]

            for xml_file in xml_files:
                xml_path = self.data_dir / xml_file
                if xml_path.exists():
                    schema = analyzer.analyze_xml_file(xml_path)
                    self.schemas[schema.name] = schema

            print(f"  ✅ Analyzed {len(self.schemas)} XML files")
            print(f"  ⏱️  Time: {time.time() - analysis_start:.2f}s")
            print()

            # Step 1: Create database
            print("Step 1: Creating database...")
            step_start = time.time()

            # Clean up existing database
            if self.db_path.exists():
                shutil.rmtree(self.db_path)

            # Clean up log directory
            log_dir = Path("./log")
            if log_dir.exists():
                shutil.rmtree(log_dir)

            self.db = arcadedb.create_database(str(self.db_path))

            print(f"  ✅ Database created")
            print(f"  ⏱️  Time: {time.time() - step_start:.2f}s")
            print()

            # Step 2: Create document types from discovered schemas
            print("Step 2: Creating document types...")
            step_start = time.time()

            self._create_document_types()

            print(f"  ✅ Created {len(self.schemas)} document types")
            print(f"  ⏱️  Time: {time.time() - step_start:.2f}s")
            print()

            # Step 3: Import XML files using discovered schemas
            print("Step 3: Importing XML files...")
            import_start = time.time()

            import_stats = []  # Collect statistics from each import

            for xml_file in xml_files:
                xml_path = self.data_dir / xml_file
                if xml_path.exists():
                    entity_name = xml_path.stem.rstrip("s")  # Users.xml → User
                    if entity_name in self.schemas:
                        stats = self._import_xml_generic(xml_path, entity_name)
                        import_stats.append(stats)

            # Print aggregate statistics
            total_records = sum(s["count"] for s in import_stats)
            total_time = time.time() - import_start
            overall_rate = total_records / total_time if total_time > 0 else 0

            # Calculate timing aggregates
            total_db_time = sum(s["db_time"] for s in import_stats)
            total_embed_time = sum(s["embed_time"] for s in import_stats)
            total_query_time = sum(s["query_time"] for s in import_stats)

            print("\n  ✅ All XML files imported")
            print(f"  📊 Total records: {total_records:,}")
            print(f"  ⏱️  Total import time: {total_time:.2f}s")
            print(f"  ⚡ Overall rate: {overall_rate:,.0f} records/sec")
            print()

            # Print timing breakdown
            print("  ⏱️  Timing breakdown:")
            print(
                f"     • DB operations:    {total_db_time:>8.2f}s ({total_db_time/total_time*100:>5.1f}%)"
            )
            if total_embed_time > 0:
                print(
                    f"     • Embedding gen:    {total_embed_time:>8.2f}s ({total_embed_time/total_time*100:>5.1f}%)"
                )
            if total_query_time > 0:
                print(
                    f"     • Queries:    {total_query_time:>8.2f}s ({total_query_time/total_time*100:>5.1f}%)"
                )
            overhead = total_time - (
                total_db_time + total_embed_time + total_query_time
            )
            print(
                f"     • Overhead (I/O):   {overhead:>8.2f}s ({overhead/total_time*100:>5.1f}%)"
            )
            print()

            # Print per-entity breakdown
            print("  📋 Import breakdown by entity:")
            for stats in import_stats:
                pct = (stats["count"] / total_records * 100) if total_records > 0 else 0
                db_pct = (
                    (stats["db_time"] / total_db_time * 100) if total_db_time > 0 else 0
                )
                print(
                    f"     • {stats['entity_name']:12} "
                    f"{stats['count']:>7,} records "
                    f"({pct:>5.1f}%) | "
                    f"{stats['avg_rate']:>7,.0f} rec/s | "
                    f"{stats['db_time']:>6.2f}s db ({db_pct:>5.1f}%)"
                )
            print()

            # Step 4: Create indexes
            print("Step 4: Creating indexes...")
            index_start = time.time()

            indexes = self._get_indexes()

            # Show what indexes will be created
            self._print_index_plan(indexes)

            retry_config = get_retry_config(self.dataset_size)

            success, failed = create_indexes(
                self.db,
                indexes,
                retry_delay=retry_config["retry_delay"],
                max_retries=retry_config["max_retries"],
                verbose=True,
            )

            if failed:
                raise RuntimeError(f"Failed to create {len(failed)} indexes")

            print(f"\n  ✅ All {success} indexes created")
            print(f"  ⏱️  Index creation time: {time.time() - index_start:.2f}s")
            print()

            # Step 5: Run validation queries (sanity check)
            print("Step 5: Running validation queries (sanity check)...")
            query_start = time.time()

            self._run_validation_queries()

            print(f"  ⏱️  Query time: {time.time() - query_start:.2f}s")
            print()

            # Step 6: Close database safely
            print("Step 6: Closing database...")
            close_start = time.time()

            close_database_safely(self.db, verbose=True)

            print(f"  ⏱️  Close time: {time.time() - close_start:.2f}s")
            print()

            # Step 7: Print schema summary
            print("Step 7: Schema summary...")
            self._print_schema_summary()

            # Phase 1 complete
            phase_elapsed = time.time() - phase_start
            print("=" * 80)
            print("✅ PHASE 1 COMPLETE")
            print("=" * 80)
            print(
                f"Total time: {phase_elapsed:.2f}s ({phase_elapsed / 60:.1f} minutes)"
            )
            print("=" * 80)
            print()

        except Exception as e:
            print(f"\n❌ Phase 1 failed: {e}")
            if self.db:
                self.db.close()
            raise

    def _create_document_types(self):
        """Create document types with properties based on discovered schemas."""
        with self.db.transaction():
            for entity_name, schema in self.schemas.items():
                # Create document type
                self.db.schema.create_document_type(entity_name)

                # Define all properties with their types
                for field_name, field_stats in schema.fields.items():
                    self.db.schema.create_property(
                        entity_name, field_name, field_stats.type_name
                    )

                prop_count = len(schema.fields)
                print(f"    ✓ Created {entity_name} ({prop_count} properties)")

    def _import_xml_generic(self, xml_path: Path, entity_name: str):
        """Generic XML importer using discovered schema.

        Returns:
            dict: Statistics with keys: count, elapsed, avg_rate, db_time,
                  embed_time, query_time, entity_name
        """
        print(f"\n  Importing {xml_path.name}...")

        schema = self.schemas.get(entity_name)
        if not schema:
            print(f"    ⚠️  No schema found for {entity_name}, skipping")
            return {
                "count": 0,
                "elapsed": 0,
                "avg_rate": 0,
                "db_time": 0,
                "embed_time": 0,
                "query_time": 0,
                "entity_name": entity_name,
            }

        # Get field info from schema
        fields = schema.fields
        integer_fields = {
            name
            for name, stats in fields.items()
            if stats.type_name in ["BYTE", "SHORT", "INTEGER", "LONG"]
        }

        batch = []
        total_count = 0
        batch_times = []
        total_db_time = 0
        total_embed_time = 0  # For future use (Phase 3)
        total_query_time = 0  # For future use (Phase 2)
        start_time = time.time()

        context = etree.iterparse(str(xml_path), events=("end",), tag="row")

        for _, elem in context:
            # Build document from ALL discovered attributes
            doc_data = {}

            for attr_name in fields.keys():
                attr_value = elem.get(attr_name)

                if attr_value is not None:
                    # Convert integers
                    if attr_name in integer_fields:
                        try:
                            doc_data[attr_name] = int(attr_value)
                        except ValueError:
                            # Skip invalid integers
                            pass
                    else:
                        doc_data[attr_name] = attr_value

            batch.append(doc_data)

            if len(batch) >= self.batch_size:
                batch_start = time.time()
                db_time = self._insert_batch(entity_name, batch)
                total_time = time.time() - batch_start

                total_count += len(batch)
                total_db_time += db_time  # Accumulate database time
                batch_times.append((len(batch), db_time))

                print_batch_stats(
                    count=len(batch),
                    db_time=db_time,
                    total_time=total_time,
                    item_name=entity_name.lower(),
                )
                batch = []

            # Memory cleanup
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

        # Final batch
        if batch:
            batch_start = time.time()
            db_time = self._insert_batch(entity_name, batch)
            total_time = time.time() - batch_start

            total_count += len(batch)
            total_db_time += db_time  # Accumulate database time
            batch_times.append((len(batch), db_time))

            print_batch_stats(
                count=len(batch),
                db_time=db_time,
                total_time=total_time,
                item_name=entity_name.lower(),
            )

        elapsed = time.time() - start_time

        # Calculate average rate
        avg_rate = total_count / elapsed if elapsed > 0 else 0

        # Print summary statistics
        print_summary_stats(
            total_count=total_count,
            elapsed=elapsed,
            batch_times=batch_times,
            item_name=entity_name.lower(),
            has_embed=False,
            has_query=False,
        )

        del context

        # Return statistics for aggregation
        return {
            "count": total_count,
            "elapsed": elapsed,
            "avg_rate": avg_rate,
            "db_time": total_db_time,
            "embed_time": total_embed_time,
            "query_time": total_query_time,
            "entity_name": entity_name,
        }

    def _print_schema_summary(self):
        """Print summary of imported schemas."""
        print("\n" + "=" * 80)
        print("📊 IMPORTED SCHEMA SUMMARY")
        print("=" * 80)
        print()

        for entity_name, schema in sorted(self.schemas.items()):
            print(f"📄 {entity_name}")
            print(f"   Total fields: {len(schema.fields)}")
            print(f"   Fields: {', '.join(sorted(schema.fields.keys()))}")

            # Show nullable fields
            nullable = [
                (name, stats.null_count, schema.row_count)
                for name, stats in schema.fields.items()
                if stats.null_count > 0
            ]

            if nullable:
                print(f"   Nullable fields: {len(nullable)}")
                for name, null_count, total in sorted(
                    nullable, key=lambda x: x[1], reverse=True
                )[:5]:
                    pct = (null_count / total) * 100
                    print(f"     - {name}: {pct:.1f}% nulls")
                if len(nullable) > 5:
                    print(f"     ... and {len(nullable) - 5} more")
            print()

        print("=" * 80)
        print()

    # ========================================================================
    # Database Helper Methods
    # ========================================================================

    def _insert_batch(self, type_name, records):
        """Insert a batch of records using transaction.

        Returns:
            float: Time elapsed in seconds for the database operation
        """
        batch_start = time.time()
        with self.db.transaction():
            for record in records:
                doc = self.db.new_document(type_name)
                for key, value in record.items():
                    doc.set(key, value)
                doc.save()
        return time.time() - batch_start

    def _run_validation_queries(self):
        """Run validation queries using StackOverflowValidator."""
        import random

        random.seed(42)

        print("\n  📊 Running validation queries...\n")

        # Sample random IDs
        try:
            user_sample = list(self.db.query("sql", "SELECT Id FROM User LIMIT 100"))
            random_user_id = (
                random.choice(user_sample).get_property("Id") if user_sample else 1
            )

            post_sample = list(self.db.query("sql", "SELECT Id FROM Post LIMIT 100"))
            random_post_id = (
                random.choice(post_sample).get_property("Id") if post_sample else 1
            )
        except Exception:
            random_user_id = 1
            random_post_id = 1

        # Use the reusable validator
        queries = StackOverflowValidator.get_phase1_validation_queries(
            random_user_id, random_post_id
        )

        for i, (query_name, query, validator) in enumerate(queries, 1):
            try:
                start_time = time.time()
                result = list(self.db.query("sql", query))
                elapsed = time.time() - start_time

                passed = validator(result)
                status = "✓" if passed else "❌"

                print(f"  [{i}/{len(queries)}] {query_name}")
                print(f"          Results: {len(result)} rows")
                print(f"          Time: {elapsed:.4f}s")
                print(f"          Status: {status}")
                print()

            except Exception as e:
                print(f"  [{i}/{len(queries)}] {query_name}")
                print(f"          ❌ Error: {e}")
                print()

    def _get_indexes(self):
        """Auto-generate indexes from discovered schema.

        Phase 2 will convert documents → graph with edges. For edge creation,
        we need to lookup vertices efficiently using queries like:
            SELECT FROM User WHERE userId IN [1, 2, 3, ...]
            SELECT FROM Post WHERE Id IN [100, 200, 300, ...]

        Therefore we need indexes on:
        1. PRIMARY KEYS (Id fields) - for direct vertex lookups
        2. FOREIGN KEYS (OwnerUserId, PostId, etc.) - for batch vertex cache
           queries during edge creation (see example 05's _build_vertex_cache)

        Returns:
            List of tuples: (entity_name, field_name, index_type)
        """
        indexes = []

        # Entity name mapping (schema key -> document type name)
        entity_map = {
            "User": "User",
            "Post": "Post",
            "Comment": "Comment",
            "Badge": "Badge",
            "Vote": "Vote",
            "PostLink": "PostLink",
            "Tag": "Tag",
            "PostHistory": "PostHistory",
        }

        for entity_key, schema in self.schemas.items():
            entity_name = entity_map.get(entity_key, entity_key)

            # Add primary key index (Id field) - UNIQUE
            if "Id" in schema.fields:
                indexes.append((entity_name, "Id", "UNIQUE"))

            # Add foreign key indexes (for Phase 2 vertex cache queries)
            # Pattern: any field ending with 'Id' (except primary key 'Id')
            for field_name in schema.fields.keys():
                # Skip the primary key 'Id', but index foreign keys like
                # 'UserId', 'PostId', 'OwnerUserId', 'ParentId', etc.
                if field_name != "Id" and field_name.endswith("Id"):
                    indexes.append((entity_name, field_name, "NOTUNIQUE"))

        return indexes

    def _print_index_plan(self, indexes):
        """Print the index creation plan for verification."""
        unique = [idx for idx in indexes if idx[2] == "UNIQUE"]
        notunique = [idx for idx in indexes if idx[2] == "NOTUNIQUE"]

        print(f"\n  📋 Index Plan: {len(indexes)} total indexes")
        print(f"     • {len(unique)} UNIQUE (primary keys)")
        print(
            f"     • {len(notunique)} NOTUNIQUE "
            f"(foreign keys for Phase 2 vertex cache)"
        )
        print()

        if unique:
            print("  🔑 Primary Key Indexes:")
            for entity, field_name, _ in sorted(unique):
                print(f"     • {entity}.{field_name}")

        if notunique:
            print(
                "\n  🔗 Foreign Key Indexes "
                "(enables fast vertex lookups in Phase 2):"
            )
            for entity, field_name, _ in sorted(notunique):
                print(f"     • {entity}.{field_name}")
        print()


# =============================================================================
# Phase 2: Documents → Graph (Vertices + Edges)
# =============================================================================


class Phase2GraphConverter:
    """Converts Phase 1 document database to Phase 2 graph database.

    Phase 2 Steps:
    1. Verify Phase 1 database (counts, indexes, validation queries)
    2. Create new graph database with vertex/edge schema
    3. Convert documents to vertices (User, Question, Answer, Tag, Badge, Comment)
    4. Create edges (ASKED, ANSWERED, HAS_ANSWER, etc.)
    5. Aggregate vote counts into Question/Answer properties
    6. Run graph validation queries
    """

    def __init__(
        self,
        doc_db_path: Path,
        graph_db_path: Path,
        batch_size: int = 10000,
        dataset_size: str = "stackoverflow-small",
    ):
        self.doc_db_path = doc_db_path
        self.graph_db_path = graph_db_path
        self.batch_size = batch_size
        self.dataset_size = dataset_size
        self.doc_db = None
        self.graph_db = None

        # Expected counts from Phase 1 (will be verified)
        self.expected_counts = {}
        self.expected_indexes = 28  # From Phase 1

    def run(self):
        """Execute Phase 2: Document to Graph conversion."""
        print("=" * 80)
        print("PHASE 2: Documents → Graph")
        print("=" * 80)
        print(f"Source DB (Phase 1): {self.doc_db_path}")
        print(f"Target DB (Phase 2): {self.graph_db_path}")
        print(f"Batch size: {self.batch_size:,} records/commit")
        print()

        phase_start = time.time()

        try:
            # Step 1: Verify Phase 1 database
            print("Step 1: Verifying Phase 1 database...")
            start_time = time.time()
            self._verify_phase1()
            print(f"  ⏱️  Time: {time.time() - start_time:.2f}s")
            print()

            # Step 2: Create graph schema
            print("Step 2: Creating graph schema...")
            step_start = time.time()
            self._create_graph_schema()
            print(f"  ⏱️  Time: {time.time() - step_start:.2f}s")
            print()

            # Step 3: Convert to vertices
            print("Step 3: Converting documents to vertices...")
            step_start = time.time()
            self._convert_to_vertices()
            print(f"  ⏱️  Time: {time.time() - step_start:.2f}s")
            print()

            # Step 4: Create edges
            print("Step 4: Creating edges...")
            print("⚠️  Not yet implemented")
            print()

            # Step 5: Run graph validation
            print("Step 5: Running graph validation queries...")
            print("⚠️  Not yet implemented")
            print()

            # Phase 2 complete
            phase_elapsed = time.time() - phase_start
            print("=" * 80)
            print("✅ PHASE 2 COMPLETE")
            print("=" * 80)
            print(
                f"Total time: {phase_elapsed:.2f}s ({phase_elapsed / 60:.1f} minutes)"
            )
            print("=" * 80)
            print()

        except Exception as e:
            print(f"\n❌ Phase 2 failed: {e}")
            raise

    def _verify_phase1(self):
        """Verify Phase 1 database using StackOverflowValidator."""
        print("  Verifying Phase 1 database...")
        print()

        # Use the reusable standalone validator
        validation_passed, counts = StackOverflowValidator.validate_phase1(
            self.doc_db_path, dataset_size=self.dataset_size, verbose=True, indent="  "
        )

        if not validation_passed:
            raise RuntimeError("Phase 1 verification failed!")

        # Store counts for reference
        self.expected_counts = counts

        print("  ✅ Phase 1 verification complete!")

    def _create_graph_schema(self):
        """Create graph database with vertex and edge types.

        Vertex types (6):
        - User: Stack Overflow users
        - Question: Posts where PostTypeId=1
        - Answer: Posts where PostTypeId=2
        - Tag: Tags for categorizing questions
        - Badge: User achievements
        - Comment: Comments on posts

        Edge types (8):
        - ASKED: User -> Question
        - ANSWERED: User -> Answer
        - HAS_ANSWER: Question -> Answer
        - ACCEPTED_ANSWER: Question -> Answer (accepted)
        - TAGGED_WITH: Question -> Tag
        - COMMENTED_ON: Comment -> Post (Question or Answer)
        - EARNED: User -> Badge
        - LINKED_TO: Post -> Post (via PostLink)
        """
        print("  Creating graph database...")

        # Clean up existing graph database
        if self.graph_db_path.exists():
            shutil.rmtree(self.graph_db_path)
            print("    • Cleaned up existing graph database")

        # Create new graph database
        self.graph_db = arcadedb.create_database(str(self.graph_db_path))
        print(f"    • Created graph database: {self.graph_db_path.name}")

        with self.graph_db.transaction():
            # Create vertex types
            print("\n  Creating vertex types...")

            # User vertex
            self.graph_db.schema.create_vertex_type("User")
            self.graph_db.schema.create_property("User", "Id", "INTEGER")
            self.graph_db.schema.create_property("User", "DisplayName", "STRING")
            self.graph_db.schema.create_property("User", "Reputation", "INTEGER")
            self.graph_db.schema.create_property("User", "CreationDate", "DATETIME")
            self.graph_db.schema.create_property("User", "Views", "INTEGER")
            self.graph_db.schema.create_property("User", "UpVotes", "INTEGER")
            self.graph_db.schema.create_property("User", "DownVotes", "INTEGER")
            print("    ✓ User (Id, DisplayName, Reputation, ...)")

            # Question vertex (Post where PostTypeId=1)
            self.graph_db.schema.create_vertex_type("Question")
            self.graph_db.schema.create_property("Question", "Id", "INTEGER")
            self.graph_db.schema.create_property("Question", "Title", "STRING")
            self.graph_db.schema.create_property("Question", "Body", "STRING")
            self.graph_db.schema.create_property("Question", "Score", "INTEGER")
            self.graph_db.schema.create_property("Question", "ViewCount", "INTEGER")
            self.graph_db.schema.create_property("Question", "CreationDate", "DATETIME")
            self.graph_db.schema.create_property("Question", "AnswerCount", "INTEGER")
            self.graph_db.schema.create_property("Question", "CommentCount", "INTEGER")
            self.graph_db.schema.create_property("Question", "FavoriteCount", "INTEGER")
            # Vote aggregates (from Vote documents)
            self.graph_db.schema.create_property("Question", "UpVotes", "INTEGER")
            self.graph_db.schema.create_property("Question", "DownVotes", "INTEGER")
            self.graph_db.schema.create_property("Question", "BountyAmount", "INTEGER")
            print("    ✓ Question (Id, Title, Body, Score, Vote aggregates, ...)")

            # Answer vertex (Post where PostTypeId=2)
            self.graph_db.schema.create_vertex_type("Answer")
            self.graph_db.schema.create_property("Answer", "Id", "INTEGER")
            self.graph_db.schema.create_property("Answer", "Body", "STRING")
            self.graph_db.schema.create_property("Answer", "Score", "INTEGER")
            self.graph_db.schema.create_property("Answer", "CreationDate", "DATETIME")
            self.graph_db.schema.create_property("Answer", "CommentCount", "INTEGER")
            # Vote aggregates (from Vote documents)
            self.graph_db.schema.create_property("Answer", "UpVotes", "INTEGER")
            self.graph_db.schema.create_property("Answer", "DownVotes", "INTEGER")
            print("    ✓ Answer (Id, Body, Score, Vote aggregates, ...)")

            # Tag vertex
            self.graph_db.schema.create_vertex_type("Tag")
            self.graph_db.schema.create_property("Tag", "Id", "INTEGER")
            self.graph_db.schema.create_property("Tag", "TagName", "STRING")
            self.graph_db.schema.create_property("Tag", "Count", "INTEGER")
            print("    ✓ Tag (Id, TagName, Count)")

            # Badge vertex
            self.graph_db.schema.create_vertex_type("Badge")
            self.graph_db.schema.create_property("Badge", "Id", "INTEGER")
            self.graph_db.schema.create_property("Badge", "Name", "STRING")
            self.graph_db.schema.create_property("Badge", "Date", "DATETIME")
            self.graph_db.schema.create_property("Badge", "Class", "INTEGER")
            print("    ✓ Badge (Id, Name, Date, Class)")

            # Comment vertex
            self.graph_db.schema.create_vertex_type("Comment")
            self.graph_db.schema.create_property("Comment", "Id", "INTEGER")
            self.graph_db.schema.create_property("Comment", "Text", "STRING")
            self.graph_db.schema.create_property("Comment", "Score", "INTEGER")
            self.graph_db.schema.create_property("Comment", "CreationDate", "DATETIME")
            print("    ✓ Comment (Id, Text, Score, CreationDate)")

            # Create edge types
            print("\n  Creating edge types...")

            # User -> Question (ASKED)
            self.graph_db.schema.create_edge_type("ASKED")
            print("    ✓ ASKED (User -> Question)")

            # User -> Answer (ANSWERED)
            self.graph_db.schema.create_edge_type("ANSWERED")
            print("    ✓ ANSWERED (User -> Answer)")

            # Question -> Answer (HAS_ANSWER)
            self.graph_db.schema.create_edge_type("HAS_ANSWER")
            print("    ✓ HAS_ANSWER (Question -> Answer)")

            # Question -> Answer (ACCEPTED_ANSWER, specific answer)
            self.graph_db.schema.create_edge_type("ACCEPTED_ANSWER")
            print("    ✓ ACCEPTED_ANSWER (Question -> Answer)")

            # Question -> Tag (TAGGED_WITH)
            self.graph_db.schema.create_edge_type("TAGGED_WITH")
            print("    ✓ TAGGED_WITH (Question -> Tag)")

            # Comment -> Post (COMMENTED_ON, to Question or Answer)
            self.graph_db.schema.create_edge_type("COMMENTED_ON")
            print("    ✓ COMMENTED_ON (Comment -> Question/Answer)")

            # User -> Badge (EARNED)
            self.graph_db.schema.create_edge_type("EARNED")
            print("    ✓ EARNED (User -> Badge)")

            # Post -> Post (LINKED_TO, via PostLink)
            self.graph_db.schema.create_edge_type("LINKED_TO")
            self.graph_db.schema.create_property("LINKED_TO", "LinkTypeId", "INTEGER")
            print("    ✓ LINKED_TO (Post -> Post, with LinkTypeId)")

        print("\n  ✅ Vertex and edge types created")
        print("     • 6 vertex types: User, Question, Answer, Tag, Badge, Comment")
        print("     • 8 edge types: ASKED, ANSWERED, HAS_ANSWER, ACCEPTED_ANSWER,")
        print("                     TAGGED_WITH, COMMENTED_ON, EARNED, LINKED_TO")

        # Create indexes on Id fields for fast lookups (outside transaction, with retry logic)
        print("\n  Creating indexes on vertex Id fields...")

        indexes = [
            ("User", "Id", "UNIQUE"),
            ("Question", "Id", "UNIQUE"),
            ("Answer", "Id", "UNIQUE"),
            ("Tag", "Id", "UNIQUE"),
            ("Badge", "Id", "UNIQUE"),
            ("Comment", "Id", "UNIQUE"),
        ]

        retry_config = get_retry_config(self.dataset_size)
        success, failed = create_indexes(
            self.graph_db,
            indexes,
            retry_delay=retry_config["retry_delay"],
            max_retries=retry_config["max_retries"],
            verbose=True,
        )

        if failed:
            raise RuntimeError(f"Failed to create {len(failed)} vertex indexes")

        print(f"\n  ✅ Graph schema complete with {success} indexes")
        print("     • 6 vertex types: User, Question, Answer, Tag, Badge, Comment")
        print("     • 8 edge types: ASKED, ANSWERED, HAS_ANSWER, ACCEPTED_ANSWER,")
        print("                     TAGGED_WITH, COMMENTED_ON, EARNED, LINKED_TO")
        print("     • 6 indexes on Id fields for fast lookups")

    def _convert_to_vertices(self):
        """Convert Phase 1 documents to Phase 2 graph vertices.

        Conversions:
        - User documents → User vertices
        - Post documents (PostTypeId=1) → Question vertices
        - Post documents (PostTypeId=2) → Answer vertices
        - Tag documents → Tag vertices
        - Badge documents → Badge vertices
        - Comment documents → Comment vertices
        - Vote documents → Aggregate into Question/Answer properties
        """
        print("  Opening Phase 1 database (read-only)...")
        doc_db = arcadedb.open_database(str(self.doc_db_path))

        try:
            # Step 3.1: Convert Users
            print("\n  Converting User documents → User vertices...")
            self._convert_users(doc_db)

            # Step 3.2: Convert Posts (split into Questions and Answers)
            print("\n  Converting Post documents → Question/Answer vertices...")
            self._convert_posts(doc_db)

            # Step 3.3: Aggregate Votes into Question/Answer properties
            print("\n  Aggregating Vote counts into Question/Answer vertices...")
            self._aggregate_votes(doc_db)

            # Step 3.4: Convert Tags
            print("\n  Converting Tag documents → Tag vertices...")
            self._convert_tags(doc_db)

            # Step 3.5: Convert Badges
            print("\n  Converting Badge documents → Badge vertices...")
            self._convert_badges(doc_db)

            # Step 3.6: Convert Comments
            print("\n  Converting Comment documents → Comment vertices...")
            self._convert_comments(doc_db)

            print("\n  ✅ All documents converted to vertices")

        finally:
            doc_db.close()
            print("  ✅ Closed Phase 1 database")

    def _convert_users(self, doc_db):
        """Convert User documents to User vertices with pagination."""
        batch = []
        count = 0
        start = time.time()
        batch_times = []

        # Use @rid pagination for large datasets
        last_rid = "#-1:-1"
        while True:
            batch_start = time.time()

            # Query with timing
            query_start = time.time()
            query = f"""
                SELECT *, @rid as rid FROM User
                WHERE @rid > {last_rid}
                ORDER BY @rid
                LIMIT {self.batch_size}
            """
            chunk = list(doc_db.query("sql", query))
            query_time = time.time() - query_start

            if not chunk:
                break

            for user in chunk:
                # Extract properties
                vertex_data = {
                    "Id": user.get_property("Id"),
                    "DisplayName": user.get_property("DisplayName"),
                    "Reputation": user.get_property("Reputation"),
                    "CreationDate": user.get_property("CreationDate"),
                    "Views": user.get_property("Views"),
                    "UpVotes": user.get_property("UpVotes"),
                    "DownVotes": user.get_property("DownVotes"),
                }

                batch.append(vertex_data)
                count += 1

            # Insert batch and track time
            db_time = self._insert_vertex_batch("User", batch)
            batch_time = time.time() - batch_start
            batch_times.append((len(batch), query_time, db_time, batch_time))

            # Print batch stats
            print_batch_stats(
                count=len(batch),
                query_time=query_time,
                db_time=db_time,
                total_time=batch_time,
                item_name="users",
            )
            batch = []

            # Update pagination cursor
            last_rid = chunk[-1].get_property("rid")

        elapsed = time.time() - start

        # Print summary stats
        print_summary_stats(
            total_count=count,
            elapsed=elapsed,
            batch_times=batch_times,
            item_name="User vertices",
            has_embed=False,
            has_query=True,
        )

    def _convert_posts(self, doc_db):
        """Convert Post documents to Question/Answer vertices with pagination."""
        question_batch = []
        answer_batch = []
        question_count = 0
        answer_count = 0
        start = time.time()
        question_times = []
        answer_times = []
        total_query_time = 0
        query_count = 0

        # Use @rid pagination for large datasets
        last_rid = "#-1:-1"
        while True:
            batch_start = time.time()

            # Query with timing
            query_start = time.time()
            query = f"""
                SELECT *, @rid as rid FROM Post
                WHERE @rid > {last_rid}
                ORDER BY @rid
                LIMIT {self.batch_size}
            """
            chunk = list(doc_db.query("sql", query))
            query_time = time.time() - query_start
            total_query_time += query_time
            query_count += 1

            if not chunk:
                break

            for post in chunk:
                post_type_id = post.get_property("PostTypeId")

                if post_type_id == 1:  # Question
                    vertex_data = {
                        "Id": post.get_property("Id"),
                        "Title": post.get_property("Title"),
                        "Body": post.get_property("Body"),
                        "Score": post.get_property("Score"),
                        "ViewCount": post.get_property("ViewCount"),
                        "CreationDate": post.get_property("CreationDate"),
                        "AnswerCount": post.get_property("AnswerCount"),
                        "CommentCount": post.get_property("CommentCount"),
                        "FavoriteCount": post.get_property("FavoriteCount"),
                        # Vote aggregates will be added later
                        "UpVotes": 0,
                        "DownVotes": 0,
                        "BountyAmount": 0,
                    }

                    question_batch.append(vertex_data)
                    question_count += 1

                    if len(question_batch) >= self.batch_size:
                        q_db_time = self._insert_vertex_batch(
                            "Question", question_batch
                        )
                        batch_time = time.time() - batch_start
                        question_times.append(
                            (len(question_batch), query_time, q_db_time, batch_time)
                        )

                        print_batch_stats(
                            count=len(question_batch),
                            query_time=query_time,
                            db_time=q_db_time,
                            total_time=batch_time,
                            item_name="questions",
                        )
                        question_batch = []
                        batch_start = time.time()  # Reset for next batch

                elif post_type_id == 2:  # Answer
                    vertex_data = {
                        "Id": post.get_property("Id"),
                        "Body": post.get_property("Body"),
                        "Score": post.get_property("Score"),
                        "CreationDate": post.get_property("CreationDate"),
                        "CommentCount": post.get_property("CommentCount"),
                        # Vote aggregates will be added later
                        "UpVotes": 0,
                        "DownVotes": 0,
                    }

                    answer_batch.append(vertex_data)
                    answer_count += 1

                    if len(answer_batch) >= self.batch_size:
                        a_db_time = self._insert_vertex_batch("Answer", answer_batch)
                        batch_time = time.time() - batch_start
                        answer_times.append(
                            (len(answer_batch), query_time, a_db_time, batch_time)
                        )

                        print_batch_stats(
                            count=len(answer_batch),
                            query_time=query_time,
                            db_time=a_db_time,
                            total_time=batch_time,
                            item_name="answers",
                        )
                        answer_batch = []
                        batch_start = time.time()  # Reset for next batch

            # Update pagination cursor
            last_rid = chunk[-1].get_property("rid")

        # Final batches
        if question_batch:
            db_time = self._insert_vertex_batch("Question", question_batch)
            batch_time = time.time() - batch_start
            # Use average query time for final batch
            avg_query = total_query_time / query_count if query_count > 0 else 0
            question_times.append((len(question_batch), avg_query, db_time, batch_time))
        if answer_batch:
            db_time = self._insert_vertex_batch("Answer", answer_batch)
            batch_time = time.time() - batch_start
            avg_query = total_query_time / query_count if query_count > 0 else 0
            answer_times.append((len(answer_batch), avg_query, db_time, batch_time))

        elapsed = time.time() - start

        # Print summary for Questions
        if question_times:
            print_summary_stats(
                total_count=question_count,
                elapsed=elapsed,
                batch_times=question_times,
                item_name="Question vertices",
                has_embed=False,
                has_query=True,
            )

        # Print summary for Answers
        if answer_times:
            print_summary_stats(
                total_count=answer_count,
                elapsed=elapsed,
                batch_times=answer_times,
                item_name="Answer vertices",
                has_embed=False,
                has_query=True,
            )

        # Print combined summary
        total_rate = (question_count + answer_count) / elapsed if elapsed > 0 else 0
        print(
            f"    ✓ Total: {question_count + answer_count:,} vertices | total: {elapsed:.2f}s | avg rate: {total_rate:,.0f} v/s"
        )

    def _aggregate_votes(self, doc_db):
        """Aggregate Vote counts into Question/Answer vertex properties.

        Uses pagination to avoid loading all votes into memory at once.
        """
        overall_start = time.time()

        # Phase 1: Query and aggregate votes
        print("    Phase 1: Querying and aggregating votes...")
        post_votes = {}
        total_votes_processed = 0
        last_rid = "#-1:-1"
        query_batch_times = []

        while True:
            batch_start = time.time()

            # Read votes in batches using @rid pagination
            query_start = time.time()
            vote_query = f"""
                SELECT *, @rid as rid
                FROM Vote
                WHERE PostId IS NOT NULL AND @rid > {last_rid}
                ORDER BY @rid
                LIMIT {self.batch_size}
            """
            chunk = list(doc_db.query("sql", vote_query))
            query_time = time.time() - query_start

            if not chunk:
                break

            # Aggregate votes from this chunk (in-memory processing)
            for vote in chunk:
                post_id = vote.get_property("PostId")
                vote_type = vote.get_property("VoteTypeId")
                bounty = vote.get_property("BountyAmount") or 0

                if post_id not in post_votes:
                    post_votes[post_id] = {"up": 0, "down": 0, "bounty": 0}

                # VoteTypeId: 2=UpVote, 3=DownVote, 8=Bounty
                if vote_type == 2:
                    post_votes[post_id]["up"] += 1
                elif vote_type == 3:
                    post_votes[post_id]["down"] += 1

                if bounty > 0:
                    post_votes[post_id]["bounty"] += bounty

            batch_time = time.time() - batch_start
            total_votes_processed += len(chunk)
            # Format: (count, query_t, db_t, total_t) for has_query=True
            # Since this is just query+aggregation, db_t is 0
            query_batch_times.append((len(chunk), query_time, 0, batch_time))

            # Print batch stats
            print_batch_stats(
                count=len(chunk),
                query_time=query_time,
                total_time=batch_time,
                item_name="votes",
            )

            # Update pagination cursor
            last_rid = chunk[-1].get_property("rid")

        query_phase_time = time.time() - overall_start

        # Print query phase summary
        print_summary_stats(
            total_count=total_votes_processed,
            elapsed=query_phase_time,
            batch_times=query_batch_times,
            item_name="votes",
            has_embed=False,
            has_query=True,
        )

        print(f"    → Found vote data for {len(post_votes):,} unique posts")
        print()

        # Phase 2: Update vertices with aggregated vote counts
        print("    Phase 2: Updating Question/Answer vertices...")
        update_start = time.time()
        post_ids = list(post_votes.keys())
        q_updated = 0
        a_updated = 0
        update_batch_times = []

        for i in range(0, len(post_ids), self.batch_size):
            batch_start = time.time()
            batch_ids = post_ids[i : i + self.batch_size]

            # Database updates in transaction
            db_start = time.time()
            with self.graph_db.transaction():
                # Update Questions in batch
                for post_id in batch_ids:
                    votes = post_votes[post_id]
                    # surprisingly, trying to use java api here instead of the sql query
                    # results in slower db performance. This should be investigated further.
                    update_query = f"""
                        UPDATE Question SET
                            UpVotes = {votes["up"]},
                            DownVotes = {votes["down"]},
                            BountyAmount = {votes["bounty"]}
                        WHERE Id = {post_id}
                    """
                    result = list(self.graph_db.command("sql", update_query))
                    if result and len(result) > 0:
                        q_updated += 1

                # Update Answers in same transaction
                for post_id in batch_ids:
                    votes = post_votes[post_id]
                    update_query = f"""
                        UPDATE Answer SET
                            UpVotes = {votes["up"]},
                            DownVotes = {votes["down"]}
                        WHERE Id = {post_id}
                    """
                    result = list(self.graph_db.command("sql", update_query))
                    if result and len(result) > 0:
                        a_updated += 1

            db_time = time.time() - db_start
            batch_time = time.time() - batch_start
            update_batch_times.append((len(batch_ids), db_time))

            # Print batch stats
            print_batch_stats(
                count=len(batch_ids),
                db_time=db_time,
                total_time=batch_time,
                item_name="posts",
            )

        update_phase_time = time.time() - update_start

        # Print update phase summary
        print_summary_stats(
            total_count=len(post_ids),
            elapsed=update_phase_time,
            batch_times=update_batch_times,
            item_name="posts updated",
            has_embed=False,
            has_query=False,
        )

        overall_elapsed = time.time() - overall_start
        print(
            f"    ✓ Updated {q_updated:,} Questions "
            f"and {a_updated:,} Answers with vote counts"
        )
        print(
            f"    ✓ Total time: {overall_elapsed:.2f}s "
            f"(query: {query_phase_time:.2f}s, "
            f"update: {update_phase_time:.2f}s)"
        )

    def _convert_tags(self, doc_db):
        """Convert Tag documents to Tag vertices with pagination."""
        batch = []
        count = 0
        start = time.time()
        batch_times = []

        # Use @rid pagination for large datasets
        last_rid = "#-1:-1"
        while True:
            batch_start = time.time()

            # Query with timing
            query_start = time.time()
            query = f"""
                SELECT *, @rid as rid FROM Tag
                WHERE @rid > {last_rid}
                ORDER BY @rid
                LIMIT {self.batch_size}
            """
            chunk = list(doc_db.query("sql", query))
            query_time = time.time() - query_start

            if not chunk:
                break

            for tag in chunk:
                vertex_data = {
                    "Id": tag.get_property("Id"),
                    "TagName": tag.get_property("TagName"),
                    "Count": tag.get_property("Count"),
                }

                batch.append(vertex_data)
                count += 1

            # Insert batch and track time
            db_time = self._insert_vertex_batch("Tag", batch)
            batch_time = time.time() - batch_start
            batch_times.append((len(batch), query_time, db_time, batch_time))

            # Print batch stats
            print_batch_stats(
                count=len(batch),
                query_time=query_time,
                db_time=db_time,
                total_time=batch_time,
                item_name="tags",
            )
            batch = []

            # Update pagination cursor
            last_rid = chunk[-1].get_property("rid")

        elapsed = time.time() - start

        # Print summary stats
        print_summary_stats(
            total_count=count,
            elapsed=elapsed,
            batch_times=batch_times,
            item_name="Tag vertices",
            has_embed=False,
            has_query=True,
        )

    def _convert_badges(self, doc_db):
        """Convert Badge documents to Badge vertices with pagination."""
        batch = []
        count = 0
        start = time.time()
        batch_times = []

        # Use @rid pagination for large datasets
        last_rid = "#-1:-1"
        while True:
            batch_start = time.time()

            # Query with timing
            query_start = time.time()
            query = f"""
                SELECT *, @rid as rid FROM Badge
                WHERE @rid > {last_rid}
                ORDER BY @rid
                LIMIT {self.batch_size}
            """
            chunk = list(doc_db.query("sql", query))
            query_time = time.time() - query_start

            if not chunk:
                break

            for badge in chunk:
                vertex_data = {
                    "Id": badge.get_property("Id"),
                    "Name": badge.get_property("Name"),
                    "Date": badge.get_property("Date"),
                    "Class": badge.get_property("Class"),
                }

                batch.append(vertex_data)
                count += 1

            # Insert batch and track time
            db_time = self._insert_vertex_batch("Badge", batch)
            batch_time = time.time() - batch_start
            batch_times.append((len(batch), query_time, db_time, batch_time))

            # Print batch stats
            print_batch_stats(
                count=len(batch),
                query_time=query_time,
                db_time=db_time,
                total_time=batch_time,
                item_name="badges",
            )
            batch = []

            # Update pagination cursor
            last_rid = chunk[-1].get_property("rid")

        elapsed = time.time() - start

        # Print summary stats
        print_summary_stats(
            total_count=count,
            elapsed=elapsed,
            batch_times=batch_times,
            item_name="Badge vertices",
            has_embed=False,
            has_query=True,
        )

    def _convert_comments(self, doc_db):
        """Convert Comment documents to Comment vertices with pagination."""
        batch = []
        count = 0
        start = time.time()
        batch_times = []

        # Use @rid pagination for large datasets
        last_rid = "#-1:-1"
        while True:
            batch_start = time.time()

            # Query with timing
            query_start = time.time()
            query = f"""
                SELECT *, @rid as rid FROM Comment
                WHERE @rid > {last_rid}
                ORDER BY @rid
                LIMIT {self.batch_size}
            """
            chunk = list(doc_db.query("sql", query))
            query_time = time.time() - query_start

            if not chunk:
                break

            for comment in chunk:
                vertex_data = {
                    "Id": comment.get_property("Id"),
                    "Text": comment.get_property("Text"),
                    "Score": comment.get_property("Score"),
                    "CreationDate": comment.get_property("CreationDate"),
                }

                batch.append(vertex_data)
                count += 1

            # Insert batch and track time
            db_time = self._insert_vertex_batch("Comment", batch)
            batch_time = time.time() - batch_start
            batch_times.append((len(batch), query_time, db_time, batch_time))

            # Print batch stats
            print_batch_stats(
                count=len(batch),
                query_time=query_time,
                db_time=db_time,
                total_time=batch_time,
                item_name="comments",
            )
            batch = []

            # Update pagination cursor
            last_rid = chunk[-1].get_property("rid")

        elapsed = time.time() - start

        # Print summary stats
        print_summary_stats(
            total_count=count,
            elapsed=elapsed,
            batch_times=batch_times,
            item_name="Comment vertices",
            has_embed=False,
            has_query=True,
        )

    def _insert_vertex_batch(self, vertex_type, batch):
        """Insert a batch of vertices.

        Returns:
            float: Time elapsed in seconds for the database operation
        """
        from datetime import datetime

        batch_start = time.time()
        with self.graph_db.transaction():
            for vertex_data in batch:
                # Convert datetime objects to epoch milliseconds for Java
                converted_data = {}
                for key, value in vertex_data.items():
                    if isinstance(value, datetime):
                        # Convert to epoch milliseconds (Java timestamp format)
                        converted_data[key] = int(value.timestamp() * 1000)
                    else:
                        converted_data[key] = value

                self.graph_db.new_vertex(vertex_type).set(converted_data).save()

        return time.time() - batch_start


# =============================================================================
# Main Script
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Stack Overflow Multi-Model Database Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all phases with small dataset
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small

  # Run only Phase 1 (documents + indexes)
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-tiny --phases 1

  # Run Phases 1 and 2 (documents + graph)
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-tiny --phases 1 2

  # Custom batch size for Phase 1 operations
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --batch-size 10000

Dataset sizes:
  stackoverflow-tiny   - ~34 MB disk, 2 GB heap recommended
  stackoverflow-small  - ~642 MB disk, 4 GB heap recommended
  stackoverflow-medium - ~2.9 GB disk, 8 GB heap recommended
  stackoverflow-large  - ~323 GB disk, 32+ GB heap recommended

Batch size:
  Default: 10000 records per commit
  Larger batches = faster imports, more memory usage
  Smaller batches = slower imports, less memory usage

Phases:
  1 - XML → Documents + Indexes
  2 - Documents → Graph (vertices + edges)
  3 - Graph → Embeddings + HNSW indexes
        """,
    )

    parser.add_argument(
        "--dataset",
        choices=[
            "stackoverflow-tiny",
            "stackoverflow-small",
            "stackoverflow-medium",
            "stackoverflow-large",
        ],
        default="stackoverflow-small",
        help="Dataset size to use (default: stackoverflow-small)",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Number of records to commit per batch in Phase 1 (default: 10000)",
    )

    parser.add_argument(
        "--phases",
        type=int,
        nargs="+",
        default=[1],
        choices=[1, 2, 3],
        help="Which phases to run (default: 1 only for now)",
    )

    parser.add_argument(
        "--db-name",
        type=str,
        default=None,
        help="Database name (default: stackoverflow_{dataset}_db)",
    )

    parser.add_argument(
        "--analysis-limit",
        type=int,
        default=1_000_000,
        help="Max rows to analyze per file for schema analysis (default: 1 million)",
    )

    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only analyze schema without importing (useful for understanding data structure)",
    )

    args = parser.parse_args()

    # Start overall timer
    script_start_time = time.time()

    print("=" * 80)
    print("Stack Overflow Multi-Model Database")
    print("=" * 80)
    print(f"Dataset: {args.dataset}")
    print(f"Batch size: {args.batch_size} records/commit")
    print(f"Phases: {args.phases}")
    print()

    # Setup paths
    data_dir = Path(__file__).parent / "data" / args.dataset
    db_name = args.db_name or f"{args.dataset.replace('-', '_')}_db"
    db_path = Path("./my_test_databases") / db_name

    # Check dataset exists
    if not data_dir.exists():
        print(f"❌ Dataset not found: {data_dir}")
        print()
        print("Please ensure the Stack Overflow data dump is in the correct location.")
        print(f"Expected: {data_dir}")
        sys.exit(1)

    # Check JVM heap configuration
    jvm_heap = os.environ.get("ARCADEDB_JVM_MAX_HEAP")
    if jvm_heap:
        print(f"💡 JVM Max Heap: {jvm_heap}")
    else:
        print("💡 JVM Max Heap: 4g (default)")
        if args.dataset in ["stackoverflow-medium", "stackoverflow-large"]:
            print("   ⚠️  Consider increasing heap for large datasets:")
            print('      export ARCADEDB_JVM_MAX_HEAP="8g"')
    print()

    # Schema analysis mode
    if args.analyze_only:
        print("=" * 80)
        print("📊 SCHEMA ANALYSIS MODE")
        print("=" * 80)
        print()

        analyzer = SchemaAnalyzer(analysis_limit=args.analysis_limit)

        # Analyze all XML files
        xml_files = [
            "Users.xml",
            "Posts.xml",
            "Comments.xml",
            "Badges.xml",
            "Votes.xml",
            "PostLinks.xml",
            "Tags.xml",
            "PostHistory.xml",
        ]

        schemas = []
        for xml_file in xml_files:
            xml_path = data_dir / xml_file
            if xml_path.exists():
                schema = analyzer.analyze_xml_file(xml_path)
                schemas.append(schema)
            else:
                print(f"  ⚠️  File not found: {xml_file}")

        # Print summary report
        print()
        print("=" * 80)
        print("📊 SCHEMA ANALYSIS SUMMARY")
        print("=" * 80)
        print()

        for schema in schemas:
            print(f"📄 {schema.name} ({schema.source_file.name})")
            print(f"   Total rows: {schema.row_count:,}")
            print(f"   Total fields: {len(schema.fields)}")
            print(f"   Has primary key (Id): {schema.has_primary_key}")
            print()

            # Show top 10 fields by null percentage
            fields_with_nulls = [
                (name, stats)
                for name, stats in schema.fields.items()
                if stats.null_count > 0
            ]
            fields_with_nulls.sort(key=lambda x: x[1].null_count, reverse=True)

            if fields_with_nulls:
                print(f"   Top nullable fields:")
                for name, stats in fields_with_nulls[:10]:
                    null_pct = (stats.null_count / schema.row_count) * 100
                    print(
                        f"     - {name}: {stats.null_count:,} nulls "
                        f"({null_pct:.1f}%) | Type: {stats.type_name}"
                    )
                if len(fields_with_nulls) > 10:
                    print(f"     ... and {len(fields_with_nulls) - 10} more")
            else:
                print("   No nullable fields detected")
            print()

        print("=" * 80)
        print("✅ Schema analysis complete")
        print("=" * 80)
        return

    # Run requested phases
    try:
        if 1 in args.phases:
            phase1 = Phase1XMLImporter(
                db_path=db_path,
                data_dir=data_dir,
                batch_size=args.batch_size,
                dataset_size=args.dataset,
                analysis_limit=args.analysis_limit,
            )
            phase1.run()

        if 2 in args.phases:
            # Phase 2 requires Phase 1 to be complete
            if not db_path.exists():
                print("❌ Phase 1 database not found. Run Phase 1 first.")
                print(f"   Expected: {db_path}")
                sys.exit(1)

            # Create separate graph database path
            graph_db_name = f"{db_path.name}_graph"
            graph_db_path = db_path.parent / graph_db_name

            phase2 = Phase2GraphConverter(
                doc_db_path=db_path,
                graph_db_path=graph_db_path,
                batch_size=args.batch_size,
                dataset_size=args.dataset,
            )
            phase2.run()

        if 3 in args.phases:
            print("⚠️  Phase 3 not yet implemented")
            print()

        # Overall timing
        script_elapsed = time.time() - script_start_time
        print("=" * 80)
        print("✅ ALL PHASES COMPLETED")
        print("=" * 80)
        print(
            f"Total script time: {script_elapsed:.2f}s ({script_elapsed / 60:.1f} minutes)"
        )
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Script failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
