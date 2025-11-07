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
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small
"""

import argparse
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pyarcade import ArcadeDatabase


class StackOverflowDatabase:
    """Main orchestrator for the Stack Overflow multi-model database."""

    DATASET_PATHS = {
        "stackoverflow-small": (
            Path.home() / "data" / "stackexchange" / "cs.stackexchange.com"
        ),
        "stackoverflow-medium": (
            Path.home() / "data" / "stackexchange" / "stats.stackexchange.com"
        ),
        "stackoverflow-large": (
            Path.home() / "data" / "stackexchange" / "stackoverflow.com-Posts"
        ),
    }

    def __init__(self, db_path: str, dataset: str):
        """Initialize the database connection.

        Args:
            db_path: Path to the ArcadeDB database directory
            dataset: Dataset size ('small', 'medium', or 'large')
        """
        self.db_path = db_path
        self.dataset = dataset
        self.dataset_path = self.DATASET_PATHS[dataset]
        self.db = None

        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found at {self.dataset_path}. "
                f"Please download the Stack Exchange data dump first."
            )

    def __enter__(self):
        """Context manager entry: open database connection."""
        self.db = ArcadeDatabase(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit: close database connection."""
        if self.db:
            self.db.close()

    def execute_phase_1(self, schema_path: Optional[str] = None):
        """Execute Phase 1: Import XML data as documents.

        Args:
            schema_path: Path to schema JSON file (optional)
        """
        print("=" * 80)
        print("PHASE 1: DOCUMENTS")
        print("=" * 80)
        print(f"Dataset: {self.dataset}")
        print(f"Path: {self.dataset_path}")
        print()

        # Step 1: Build schema
        builder = SchemaBuilder(self.db, schema_path)
        builder.create_document_types()

        # Step 2: Import documents
        importer = DocumentImporter(self.db, self.dataset_path)
        importer.import_all_documents()

        # Step 3: Create indexes (after import for performance)
        builder.create_indexes()

        print()
        print("Phase 1 complete! Documents imported and indexed.")

    def execute_phase_2(self):
        """Execute Phase 2: Build graph from documents."""
        print("=" * 80)
        print("PHASE 2: GRAPH")
        print("=" * 80)
        print("Building graph vertices and edges from documents...")
        print()

        # TODO: Implement Phase 2
        print("Phase 2 not yet implemented.")

    def execute_phase_3(self):
        """Execute Phase 3: Add vector embeddings."""
        print("=" * 80)
        print("PHASE 3: VECTORS")
        print("=" * 80)
        print("Generating embeddings and creating HNSW indexes...")
        print()

        # TODO: Implement Phase 3
        print("Phase 3 not yet implemented.")


class SchemaBuilder:
    """Builds the document schema for Stack Overflow data."""

    # Type conflict handling: Fields that have mixed types should use STRING
    # (discovered from schema analysis - see stackoverflow_schema-*.json)
    STRING_FALLBACK_FIELDS = {
        "Comment": ["Id", "PostId", "UserId"],  # INTEGER + DATETIME conflicts
        "Vote": ["Id", "PostId", "UserId"],
        "Badge": ["UserId"],
        "PostHistory": ["UserId", "PostId"],
    }

    # Schema definitions for all 8 document types
    DOCUMENT_SCHEMAS = {
        "Post": {
            "Id": "INTEGER",
            "PostTypeId": "INTEGER",  # 1=Question, 2=Answer
            "ParentId": "INTEGER",  # For answers, link to question
            "AcceptedAnswerId": "INTEGER",
            "CreationDate": "DATETIME",
            "Score": "INTEGER",
            "ViewCount": "INTEGER",
            "Body": "STRING",
            "OwnerUserId": "INTEGER",
            "OwnerDisplayName": "STRING",
            "LastEditorUserId": "INTEGER",
            "LastEditorDisplayName": "STRING",
            "LastEditDate": "DATETIME",
            "LastActivityDate": "DATETIME",
            "Title": "STRING",
            "Tags": "STRING",  # Pipe-delimited: <tag1>|<tag2>|<tag3>
            "AnswerCount": "INTEGER",
            "CommentCount": "INTEGER",
            "FavoriteCount": "INTEGER",
            "ClosedDate": "DATETIME",
            "CommunityOwnedDate": "DATETIME",
            "ContentLicense": "STRING",
        },
        "User": {
            "Id": "INTEGER",
            "Reputation": "INTEGER",
            "CreationDate": "DATETIME",
            "DisplayName": "STRING",
            "LastAccessDate": "DATETIME",
            "WebsiteUrl": "STRING",
            "Location": "STRING",
            "AboutMe": "STRING",
            "Views": "INTEGER",
            "UpVotes": "INTEGER",
            "DownVotes": "INTEGER",
            "AccountId": "INTEGER",
            "ProfileImageUrl": "STRING",
        },
        "Tag": {
            "Id": "INTEGER",
            "TagName": "STRING",
            "Count": "INTEGER",
            "ExcerptPostId": "INTEGER",
            "WikiPostId": "INTEGER",
        },
        "Comment": {
            "Id": "STRING",  # Type conflict: INTEGER + DATETIME
            "PostId": "STRING",  # Type conflict: INTEGER + DATETIME
            "Score": "INTEGER",
            "Text": "STRING",
            "CreationDate": "DATETIME",
            "UserId": "STRING",  # Type conflict: INTEGER + DATETIME
            "UserDisplayName": "STRING",
            "ContentLicense": "STRING",
        },
        "Vote": {
            "Id": "STRING",  # Type conflict: INTEGER + DATETIME
            "PostId": "STRING",  # Type conflict: INTEGER + DATETIME
            "VoteTypeId": "INTEGER",
            "CreationDate": "DATETIME",
            "UserId": "STRING",  # Type conflict: INTEGER + DATETIME
            "BountyAmount": "INTEGER",
        },
        "Badge": {
            "Id": "INTEGER",
            "UserId": "STRING",  # Type conflict in large dataset
            "Name": "STRING",
            "Date": "DATETIME",
            "Class": "INTEGER",
            "TagBased": "BOOLEAN",
        },
        "PostLink": {
            "Id": "INTEGER",
            "CreationDate": "DATETIME",
            "PostId": "INTEGER",
            "RelatedPostId": "INTEGER",
            "LinkTypeId": "INTEGER",
        },
        "PostHistory": {
            "Id": "INTEGER",
            "PostHistoryTypeId": "INTEGER",
            "PostId": "STRING",  # Type conflict in large dataset
            "RevisionGUID": "STRING",
            "CreationDate": "DATETIME",
            "UserId": "STRING",  # Type conflict in large dataset
            "UserDisplayName": "STRING",
            "Comment": "STRING",
            "Text": "STRING",
            "ContentLicense": "STRING",
        },
    }

    # Index definitions: Create after import for performance
    INDEX_DEFINITIONS = {
        # Primary key indexes (UNIQUE)
        "Post": [("Id", True)],
        "User": [("Id", True)],
        "Tag": [("TagName", True)],
        "Comment": [("Id", True)],
        "Vote": [("Id", True)],
        "Badge": [("Id", True)],
        "PostLink": [("Id", True)],
        "PostHistory": [("Id", True)],
        # Foreign key indexes (NOTUNIQUE) - for graph building
        "Post_OwnerUserId": ("Post", "OwnerUserId", False),
        "Post_ParentId": ("Post", "ParentId", False),
        "Post_AcceptedAnswerId": ("Post", "AcceptedAnswerId", False),
        "Comment_PostId": ("Comment", "PostId", False),
        "Comment_UserId": ("Comment", "UserId", False),
        "Vote_PostId": ("Vote", "PostId", False),
        "Vote_UserId": ("Vote", "UserId", False),
        "Badge_UserId": ("Badge", "UserId", False),
        "PostLink_PostId": ("PostLink", "PostId", False),
        "PostLink_RelatedPostId": ("PostLink", "RelatedPostId", False),
        "PostHistory_PostId": ("PostHistory", "PostId", False),
        "PostHistory_UserId": ("PostHistory", "UserId", False),
        # Temporal indexes (for time-based queries)
        "Post_CreationDate": ("Post", "CreationDate", False),
        "User_CreationDate": ("User", "CreationDate", False),
        "Comment_CreationDate": ("Comment", "CreationDate", False),
        # Scoring indexes (for ranking queries)
        "User_Reputation": ("User", "Reputation", False),
        "Post_Score": ("Post", "Score", False),
    }

    def __init__(self, db: ArcadeDatabase, schema_path: Optional[str] = None):
        """Initialize the schema builder.

        Args:
            db: ArcadeDB database connection
            schema_path: Optional path to schema JSON file (for validation)
        """
        self.db = db
        self.schema_path = schema_path
        self.schema_data = None

        if schema_path and Path(schema_path).exists():
            with open(schema_path, "r") as f:
                self.schema_data = json.load(f)
            print(f"Loaded schema metadata from {schema_path}")

    def create_document_types(self):
        """Create all document types with properties."""
        print("Creating document types...")

        for doc_type, properties in self.DOCUMENT_SCHEMAS.items():
            # Check if type already exists
            try:
                result = self.db.query(
                    f"SELECT FROM schema:types WHERE name = '{doc_type}'"
                )
                if result:
                    print(f"  ✓ {doc_type} (already exists)")
                    continue
            except Exception:
                pass  # Type doesn't exist, create it

            # Create document type
            self.db.command(f"CREATE DOCUMENT TYPE {doc_type}")
            print(f"  ✓ {doc_type}")

            # Create properties
            for prop_name, prop_type in properties.items():
                self.db.command(f"CREATE PROPERTY {doc_type}.{prop_name} {prop_type}")

        print(f"Created {len(self.DOCUMENT_SCHEMAS)} document types.")
        print()

    def create_indexes(self):
        """Create all indexes after import."""
        print("Creating indexes...")
        start_time = time.time()

        index_count = 0

        # Primary and foreign key indexes
        for doc_type, indexes in self.INDEX_DEFINITIONS.items():
            if isinstance(indexes, list):
                # Primary key indexes
                for prop_name, unique in indexes:
                    index_name = f"{doc_type}_{prop_name}"
                    index_type = "UNIQUE" if unique else "NOTUNIQUE"

                    try:
                        self.db.command(
                            f"CREATE INDEX `{index_name}` ON {doc_type} ({prop_name}) {index_type}"
                        )
                        print(f"  ✓ {index_name} ({index_type})")
                        index_count += 1
                    except Exception as e:
                        print(f"  ✗ {index_name}: {e}")

            elif isinstance(indexes, tuple):
                # Foreign key, temporal, or scoring indexes
                type_name, prop_name, unique = indexes
                index_name = doc_type  # Already includes type name
                index_type = "UNIQUE" if unique else "NOTUNIQUE"

                try:
                    self.db.command(
                        f"CREATE INDEX `{index_name}` ON {type_name} ({prop_name}) {index_type}"
                    )
                    print(f"  ✓ {index_name} ({index_type})")
                    index_count += 1
                except Exception as e:
                    print(f"  ✗ {index_name}: {e}")

        elapsed = time.time() - start_time
        print(f"Created {index_count} indexes in {elapsed:.2f}s")
        print()


class DocumentImporter:
    """Imports XML documents into ArcadeDB."""

    ENTITY_ORDER = [
        "Users",  # Import users first (referenced by posts/comments/etc)
        "Tags",  # Import tags second (referenced by posts)
        "Posts",  # Import posts third (referenced by comments/votes/etc)
        "Comments",  # Import comments after posts
        "Votes",  # Import votes after posts
        "Badges",  # Import badges after users
        "PostLinks",  # Import post links after posts
        "PostHistory",  # Import post history after posts
    ]

    def __init__(self, db: ArcadeDatabase, dataset_path: Path, batch_size: int = 10000):
        """Initialize the document importer.

        Args:
            db: ArcadeDB database connection
            dataset_path: Path to the Stack Exchange dataset directory
            batch_size: Number of documents to insert per transaction
        """
        self.db = db
        self.dataset_path = dataset_path
        self.batch_size = batch_size

    def import_all_documents(self):
        """Import all XML files in the correct order."""
        print("Importing documents...")
        print()

        total_start = time.time()
        total_imported = 0

        for entity in self.ENTITY_ORDER:
            xml_file = self.dataset_path / f"{entity}.xml"

            if not xml_file.exists():
                print(f"  ⊗ {entity}: File not found, skipping")
                continue

            count = self.import_xml_file(entity, xml_file)
            total_imported += count

        total_elapsed = time.time() - total_start
        print()
        print(f"Total imported: {total_imported:,} documents in {total_elapsed:.2f}s")
        print(f"Average throughput: {total_imported / total_elapsed:.2f} docs/sec")
        print()

    def import_xml_file(self, entity: str, xml_file: Path) -> int:
        """Import a single XML file.

        Args:
            entity: Entity name (e.g., 'Posts', 'Users')
            xml_file: Path to the XML file

        Returns:
            Number of documents imported
        """
        # Determine document type name (singular form)
        doc_type = entity.rstrip("s") if entity.endswith("s") else entity

        print(f"  → {entity} ({xml_file.name})")

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

                    # Progress update every 10 batches
                    if count % (self.batch_size * 10) == 0:
                        elapsed = time.time() - start_time
                        rate = count / elapsed
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
        schema = SchemaBuilder.DOCUMENT_SCHEMAS[doc_type]
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
                if expected_type == "INTEGER":
                    doc[key] = int(value)
                elif expected_type == "LONG":
                    doc[key] = int(value)
                elif expected_type == "DOUBLE":
                    doc[key] = float(value)
                elif expected_type == "BOOLEAN":
                    doc[key] = value.lower() in ("true", "1", "yes")
                elif expected_type == "DATETIME":
                    # Stack Exchange uses ISO format: 2021-01-01T00:00:00.000
                    doc[key] = value  # ArcadeDB handles ISO datetime strings
                else:  # STRING
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

        # Build batch insert statement
        # INSERT INTO Post CONTENT [{'Id': 1, ...}, {'Id': 2, ...}]
        self.db.command(f"INSERT INTO {doc_type} CONTENT {json.dumps(batch)}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Stack Overflow Multi-Model Database Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import and process Stack Overflow data (runs all available phases)
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-small

  # Use medium dataset
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-medium

  # Use large dataset (requires significant disk space and memory)
  python 07_stackoverflow_multimodel.py --dataset stackoverflow-large
        """,
    )

    parser.add_argument(
        "--dataset",
        choices=["stackoverflow-small", "stackoverflow-medium", "stackoverflow-large"],
        default="stackoverflow-small",
        help="Dataset size to use (default: stackoverflow-small)",
    )

    parser.add_argument(
        "--db-path",
        default="databases/stackoverflow",
        help="Database directory path (default: databases/stackoverflow)",
    )

    parser.add_argument("--schema", help="Path to schema JSON file (optional)")

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Batch size for document import (default: 10000)",
    )

    args = parser.parse_args()

    # Create database instance and run all phases
    with StackOverflowDatabase(args.db_path, args.dataset) as db:
        # Phase 1: Documents (implemented)
        db.execute_phase_1(args.schema)

        # Phase 2: Graph (not yet implemented)
        db.execute_phase_2()

        # Phase 3: Vectors (not yet implemented)
        db.execute_phase_3()

    print("Done!")


if __name__ == "__main__":
    main()
