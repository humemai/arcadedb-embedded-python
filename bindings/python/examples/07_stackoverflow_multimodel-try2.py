#!/usr/bin/env python3
"""
Example 07: Automated Graph Schema Inference
=============================================

This example demonstrates automatic schema inference for graph databases.
Given a set of data files (XML, CSV, etc.), it automatically:
  1. Detects entities (→ Vertices)
  2. Detects relationships (→ Edges)
  3. Detects text fields (→ Vector embeddings)
  4. Generates import plan
  5. Executes import in one pass

Dataset: Stack Exchange Data Dump (https://archive.org/details/stackexchange)
- stackoverflow-small: cs.stackexchange.com (~650MB XML → 583MB DB, 1.4M records)
- stackoverflow-medium: stats.stackexchange.com (~2.5GB XML → 2.7GB DB, 5M records)
- stackoverflow-large: stackoverflow.com (~325GB XML → 260GB DB, 350M records)

Usage:
    # Analyze files and show inferred schema (dry-run)
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --analyze
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-medium --analyze
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-large --analyze

    # Execute import with inferred schema
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-small --import
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-medium --import
    python 07_stackoverflow_multimodel.py --dataset stackoverflow-large --import

Stack Overflow Graph Schema (based on stackoverflow-small)
===========================================================

Vertex Types (7):
  - UserVertex: Id, DisplayName, Reputation, AboutMe
    Embeddings: AboutMe → 384d (~138K)
  - QuestionVertex: Id, Title, Body, Tags, AcceptedAnswerId
    Embeddings: [Title+Body] → 384d (~64K)
  - AnswerVertex: Id, ParentId, Body | Embeddings: Body → 384d (~41K)
  - CommentVertex: Id, PostId, UserId, Text
    Embeddings: Text → 384d (~196K)
  - BadgeVertex: Id, UserId, Name, Date (~183K)
  - PostHistoryVertex: Id, PostId, UserId, Text
    Embeddings: Text → 384d when not null (~360K)
  - TagVertex: Id, TagName, Count (~668)

Edge Types (18):
  - ASKED: User → Question (Posts.OwnerUserId)
  - ASKED_BY: Question → User (reverse)
  - ANSWERED: User → Answer (Posts.OwnerUserId)
  - ANSWERED_BY: Answer → User (reverse)
  - ANSWERS: Answer → Question (Posts.ParentId)
  - HAS_ANSWER: Question → Answer (reverse)
  - ACCEPTED_ANSWER: Question → Answer (Posts.AcceptedAnswerId)
  - COMMENTED: User → Comment (Comments.UserId)
  - COMMENTED_BY: Comment → User (reverse)
  - COMMENTED_ON: Comment → Q/A (Comments.PostId)
  - EARNED: User → Badge (Badges.UserId)
  - EARNED_BY: Badge → User (reverse)
  - EDITED: User → PostHistory (PostHistory.UserId)
  - EDITED_BY: PostHistory → User (reverse)
  - EDIT_OF: PostHistory → Q/A (PostHistory.PostId)
  - LINKED_TO: Question ↔ Question
    (PostLinks.xml with LinkTypeId, CreationDate)
  - TAGGED_WITH: Question → Tag (Posts.Tags)
  - VOTED_ON: User → Q/A
    (Votes.xml with VoteTypeId, CreationDate, BountyAmount)

Implementation Notes:
  - Two-pass import: Pass 1 creates vertices+embeddings and PostId→Type map
    Pass 2 creates edges
  - Question/Answer split by PostTypeId (1=Question, 2=Answer)
  - Tag parsing: "<python><django>" → ["python", "django"]
  - Deleted users: Skip edge creation when UserId is null
  - Bidirectional edges for easier traversal (ANSWERS/HAS_ANSWER, etc.)

Statistics (stackoverflow-small):
  - Vertices: ~983K (7 types)
  - Edges: ~2.8M (18 types)
  - Embeddings: ~800K vectors (384 dims)
"""

import argparse
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import arcadedb_embedded as arcadedb

# ============================================================================
# Configuration
# ============================================================================

# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class FieldStats:
    """Statistics about a field from data analysis."""

    type_name: str  # Inferred type (STRING, INTEGER, DATETIME, etc.)
    count: int = 0  # Number of non-null values seen
    null_count: int = 0  # Number of null values seen
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    avg_length: Optional[float] = None  # For strings (character length)
    avg_tokens: Optional[float] = None  # For strings (estimated tokens)
    sample_values: List[Any] = field(default_factory=list)


@dataclass
class ForeignKey:
    """Detected foreign key relationship."""

    from_entity: str  # Source entity name
    to_entity: str  # Target entity name
    field_name: str  # FK field name (e.g., "UserId")
    cardinality: str = "many-to-one"  # one-to-one, many-to-one, many-to-many


@dataclass
class EntitySchema:
    """Schema for an entity (potential vertex type)."""

    name: str  # Entity name (e.g., "User")
    source_file: Path  # Source data file
    fields: Dict[str, FieldStats]  # field_name → stats
    row_count: int = 0
    has_primary_key: bool = False
    foreign_keys: List[ForeignKey] = field(default_factory=list)

    @property
    def entity_score(self) -> float:
        """Score indicating how "entity-like" this is (0-1).

        Higher score = more likely to be a vertex.
        Lower score = more likely to be an edge or junction table.
        """
        score = 0.0

        # Has primary key? (+0.3)
        if self.has_primary_key:
            score += 0.3

        # Ratio of descriptive fields to ID fields
        non_id_fields = [f for f in self.fields if not f.endswith("Id")]

        if len(self.fields) > 0:
            # More non-ID fields = more entity-like (+0.4)
            score += 0.4 * (len(non_id_fields) / len(self.fields))

        # Has long text fields? (+0.3)
        has_text = any(
            stats.avg_length and stats.avg_length > 50
            for stats in self.fields.values()
            if stats.type_name in ["STRING", "TEXT"]
        )
        if has_text:
            score += 0.3

        return min(score, 1.0)


@dataclass
class EdgeSchema:
    """Schema for an edge (relationship)."""

    name: str  # Edge type name (e.g., "ASKED")
    from_vertex: str  # Source vertex type
    to_vertex: str  # Target vertex type
    source_entity: str  # Original entity this came from
    foreign_key: str  # FK field used to create edge
    properties: Dict[str, FieldStats] = field(default_factory=dict)  # Edge properties


@dataclass
class EmbeddingConfig:
    """Configuration for a vector embedding field."""

    entity: str  # Entity name
    field: str  # Field to embed
    combined_fields: Optional[List[str]] = None  # If combining multiple fields
    dimension: int = 384  # Embedding dimension (sentence-transformers default)


@dataclass
class ImportPlan:
    """Complete plan for importing data into graph database."""

    vertices: Dict[str, EntitySchema]  # vertex_name → schema
    edges: List[EdgeSchema]  # List of edge types to create
    embeddings: List[EmbeddingConfig]  # Fields to embed

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = []
        lines.append("=" * 80)
        lines.append("AUTOMATED GRAPH SCHEMA INFERENCE")
        lines.append("=" * 80)
        lines.append("")

        # Vertices
        lines.append(f"VERTICES ({len(self.vertices)}):")
        for name, schema in sorted(self.vertices.items()):
            lines.append(f"  - {name}Vertex")
            lines.append(f"      Source: {schema.source_file.name}")
            lines.append(f"      Rows: {schema.row_count:,}")
            lines.append(f"      Fields: {len(schema.fields)}")
            lines.append(f"      Entity Score: {schema.entity_score:.2f}")

            # List properties (non-Id fields)
            properties = [
                f for f in schema.fields.keys() if f != "Id" and not f.endswith("Id")
            ]
            if properties:
                # Show first 8 properties, then "..."
                if len(properties) <= 8:
                    props_str = ", ".join(properties)
                else:
                    props_str = ", ".join(properties[:8]) + ", ..."
                lines.append(f"      Properties ({len(properties)}): {props_str}")

            # List foreign keys (will become edges)
            if schema.foreign_keys:
                fk_str = ", ".join(fk.field_name for fk in schema.foreign_keys)
                lines.append(f"      Foreign Keys: {fk_str}")
        lines.append("")

        # Edges
        lines.append(f"EDGES ({len(self.edges)}):")
        for edge in self.edges:
            arrow = f"{edge.from_vertex} --[{edge.name}]--> {edge.to_vertex}"
            lines.append(f"  - {arrow}")
            lines.append(f"      Source: {edge.source_entity}.{edge.foreign_key}")
            if edge.properties:
                prop_count = len(edge.properties)
                prop_names = ", ".join(edge.properties.keys())
                lines.append(f"      Properties ({prop_count}): {prop_names}")
        lines.append("")

        # Embeddings
        lines.append(f"EMBEDDINGS ({len(self.embeddings)}):")
        for emb in self.embeddings:
            if emb.combined_fields:
                fields = " + ".join(emb.combined_fields)
                lines.append(f"  - {emb.entity}Vertex[{fields}] → {emb.dimension}d")
            else:
                lines.append(f"  - {emb.entity}Vertex.{emb.field} → {emb.dimension}d")
        lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)


# ============================================================================
# Schema Analyzer
# ============================================================================


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
        row_count = 0

        # Stream parse XML
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row_count += 1

                for attr_name, attr_value in elem.attrib.items():
                    # Track value for statistics
                    field_values[attr_name].append(attr_value)

                    # Infer type
                    inferred_type = self._infer_type(attr_value, attr_name)
                    field_types[attr_name].add(inferred_type)

                # Track which fields are missing (nulls)
                all_attrs = set(elem.attrib.keys())
                seen_fields = set(field_values.keys())
                for missing_field in seen_fields - all_attrs:
                    field_null_counts[missing_field] += 1

                # Clear element to save memory
                elem.clear()
                root.clear()

                # Limit analysis for large files
                if row_count >= self.analysis_limit:
                    break

        # Build field statistics
        fields = {}
        for field_name, type_set in field_types.items():
            # Choose most specific type
            final_type = self._resolve_type(type_set, field_values[field_name])

            # Calculate statistics
            values = field_values[field_name]
            stats = FieldStats(
                type_name=final_type,
                count=len(values),
                null_count=field_null_counts.get(field_name, 0),
                sample_values=values[:5],
            )

            # String length stats
            if final_type in ["STRING", "TEXT"]:
                lengths = [len(str(v)) for v in values]
                stats.avg_length = sum(lengths) / len(lengths) if lengths else 0
                # Estimate tokens: ~1 token per 4 chars (English text heuristic)
                # More accurate: tiktoken library, but this is good enough for estimates
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


# ============================================================================
# Graph Schema Inference Engine
# ============================================================================


class GraphSchemaInference:
    """Infers graph schema from analyzed data files."""

    def __init__(self, entity_threshold: float = 0.5):
        """Initialize inference engine.

        Args:
            entity_threshold: Minimum score to consider something a vertex (0-1)
        """
        self.entity_threshold = entity_threshold
        self.entities: Dict[str, EntitySchema] = {}
        self.entity_map: Dict[str, str] = {}  # Handles plural forms (Users → User)

    def add_entity(self, schema: EntitySchema):
        """Add analyzed entity schema."""
        self.entities[schema.name] = schema
        # Map plural forms
        self.entity_map[schema.name] = schema.name
        self.entity_map[schema.name + "s"] = schema.name
        self.entity_map[schema.name.lower()] = schema.name
        self.entity_map[schema.name.lower() + "s"] = schema.name

    def infer_schema(self) -> ImportPlan:
        """Infer complete graph schema from entities."""
        print()
        print("=" * 80)
        print("INFERRING GRAPH SCHEMA")
        print("=" * 80)
        print()

        # Step 1: Detect foreign keys in all entities
        print("🔍 Step 1: Detecting foreign key relationships...")
        self._detect_foreign_keys()

        # Step 2: Classify entities as vertices or edges
        print("\n🔍 Step 2: Classifying entities...")
        vertices, edge_candidates = self._classify_entities()

        # Step 3: Generate edges from foreign keys
        print("\n🔍 Step 3: Generating edge schemas...")
        edges = self._generate_edges(vertices, edge_candidates)

        # Step 4: Detect fields for embeddings
        print("\n🔍 Step 4: Detecting text fields for embeddings...")
        embeddings = self._detect_embeddings(vertices)

        print()
        return ImportPlan(vertices=vertices, edges=edges, embeddings=embeddings)

    def _detect_foreign_keys(self):
        """Detect foreign key relationships in all entities."""
        for entity_name, entity in self.entities.items():
            for field_name in entity.fields:
                # Pattern: {EntityName}Id
                if field_name.endswith("Id") and field_name != "Id":
                    ref_entity_name = field_name[:-2]  # Remove 'Id'

                    # Check if referenced entity exists (handle plural/case)
                    if ref_entity_name in self.entity_map:
                        target = self.entity_map[ref_entity_name]
                        fk = ForeignKey(
                            from_entity=entity_name,
                            to_entity=target,
                            field_name=field_name,
                        )
                        entity.foreign_keys.append(fk)
                        print(f"  ✓ Found FK: {entity_name}.{field_name} → {target}")

    def _classify_entities(self) -> Tuple[Dict[str, EntitySchema], List[EntitySchema]]:
        """Classify entities as vertices or edge candidates."""
        vertices = {}
        edge_candidates = []

        for name, entity in self.entities.items():
            score = entity.entity_score
            print(f"  {name}: score={score:.2f}", end="")

            if score >= self.entity_threshold:
                vertices[name] = entity
                print(" → VERTEX")
            else:
                edge_candidates.append(entity)
                print(" → EDGE CANDIDATE")

        return vertices, edge_candidates

    def _generate_edges(
        self, vertices: Dict[str, EntitySchema], edge_candidates: List[EntitySchema]
    ) -> List[EdgeSchema]:
        """Generate edge schemas from foreign keys."""
        edges = []

        # Edges from vertex foreign keys
        for vertex_name, vertex in vertices.items():
            for fk in vertex.foreign_keys:
                if fk.to_entity in vertices:
                    edge_name = self._generate_edge_name(
                        vertex_name, fk.to_entity, fk.field_name
                    )

                    edge = EdgeSchema(
                        name=edge_name,
                        from_vertex=vertex_name,
                        to_vertex=fk.to_entity,
                        source_entity=vertex_name,
                        foreign_key=fk.field_name,
                    )
                    edges.append(edge)
                    print(f"  ✓ {vertex_name} --[{edge_name}]--> {fk.to_entity}")

        # Edges from junction tables (edge candidates with 2+ FKs)
        for entity in edge_candidates:
            vertex_fks = [fk for fk in entity.foreign_keys if fk.to_entity in vertices]

            if len(vertex_fks) >= 2:
                # Many-to-many relationship
                from_fk, to_fk = vertex_fks[0], vertex_fks[1]
                edge_name = self._generate_edge_name(
                    from_fk.to_entity, to_fk.to_entity, entity.name
                )

                edge = EdgeSchema(
                    name=edge_name,
                    from_vertex=from_fk.to_entity,
                    to_vertex=to_fk.to_entity,
                    source_entity=entity.name,
                    foreign_key=f"{from_fk.field_name}+{to_fk.field_name}",
                )

                # Add edge properties (non-FK fields)
                for field_name, stats in entity.fields.items():
                    if not field_name.endswith("Id"):
                        edge.properties[field_name] = stats

                edges.append(edge)
                print(
                    f"  ✓ {from_fk.to_entity} --[{edge_name}]--> {to_fk.to_entity} "
                    f"(via {entity.name})"
                )

        return edges

    def _generate_edge_name(
        self, from_entity: str, to_entity: str, context: str
    ) -> str:
        """Generate semantic edge name from context."""
        context_lower = context.lower()

        # Common patterns
        if "owner" in context_lower:
            return "OWNS" if from_entity == "User" else "OWNED_BY"
        if "parent" in context_lower:
            return "ANSWER_TO"  # Post.ParentId
        if "accepted" in context_lower:
            return "ACCEPTED"
        if "editor" in context_lower:
            return "EDITED"
        if "wiki" in context_lower:
            return "WIKI_FOR"
        if "excerpt" in context_lower:
            return "EXCERPT_FOR"
        if "related" in context_lower:
            return "RELATED_TO"

        # Entity-based patterns
        if to_entity == "Post" and from_entity == "User":
            return "ASKED"
        if to_entity == "User" and from_entity in ["Comment", "Vote", "Badge"]:
            return f"{from_entity.upper()}_BY"
        if to_entity == "Post" and from_entity == "Comment":
            return "COMMENTED_ON"
        if to_entity == "Post" and from_entity == "Vote":
            return "VOTED_ON"
        if to_entity == "Badge" and from_entity == "User":
            return "EARNED"
        if to_entity == "Tag":
            return "TAGGED_WITH"

        # Default: generic relationship
        return "RELATES_TO"

    def _detect_embeddings(
        self, vertices: Dict[str, EntitySchema]
    ) -> List[EmbeddingConfig]:
        """Detect text fields suitable for embeddings."""
        embeddings = []

        for vertex_name, vertex in vertices.items():
            text_fields = []

            for field_name, stats in vertex.fields.items():
                # Must be text type with sufficient length
                if (
                    stats.type_name in ["STRING", "TEXT"]
                    and stats.avg_length
                    and stats.avg_length >= 50
                ):

                    # Skip fields better for exact matching
                    skip_patterns = ["email", "url", "website", "location"]
                    if any(p in field_name.lower() for p in skip_patterns):
                        continue

                    text_fields.append(field_name)
                    # Show both character length and estimated token count
                    tokens_est = int(stats.avg_tokens) if stats.avg_tokens else 0
                    print(
                        f"  ✓ {vertex_name}.{field_name} "
                        f"(avg_len={stats.avg_length:.0f} chars, "
                        f"~{tokens_est} tokens)"
                    )

            # Create embedding configs
            if len(text_fields) == 1:
                embeddings.append(
                    EmbeddingConfig(entity=vertex_name, field=text_fields[0])
                )
            elif len(text_fields) > 1:
                # Combine multiple text fields
                embeddings.append(
                    EmbeddingConfig(
                        entity=vertex_name,
                        field="combined_text",
                        combined_fields=text_fields,
                    )
                )

        return embeddings


# ============================================================================
# Main Application
# ============================================================================


class StackOverflowGraphBuilder:
    """Main application for automated graph building."""

    DATASET_PATHS = {
        "stackoverflow-tiny": Path(__file__).parent / "data" / "stackoverflow-tiny",
        "stackoverflow-small": Path(__file__).parent / "data" / "stackoverflow-small",
        "stackoverflow-medium": Path(__file__).parent / "data" / "stackoverflow-medium",
        "stackoverflow-large": Path(__file__).parent / "data" / "stackoverflow-large",
    }

    def __init__(
        self,
        dataset: str,
        db_path: str,
        batch_size: int = 50000,
        embedding_batch_size: int = 512,
    ):
        self.dataset = dataset
        self.db_path = db_path
        self.dataset_path = self.DATASET_PATHS[dataset]

        # Hyperparameters
        self.batch_size = batch_size
        self.embedding_batch_size = embedding_batch_size

        if not self.dataset_path.exists():
            print(f"Dataset not found at {self.dataset_path}")
            print(f"\nTo download: python download_data.py {dataset}")
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

    # ========================================================================
    # Batch Statistics Helper Methods
    # ========================================================================

    def _print_batch_stats(
        self,
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

    def _print_summary_stats(
        self,
        total_count: int,
        elapsed: float,
        batch_times: List[Tuple],
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
            parts.append(f"avg db: {avg_db:.1f}s |")
        else:
            # batch_times format: (count, db_t)
            total_db = sum(t[1] for t in batch_times)
            avg_db = total_db / len(batch_times)
            parts.append(f"avg db: {avg_db:.1f}s |")

        parts.append(f"avg rate: {avg_rate:.0f} /s")
        print(" ".join(parts))

    # ========================================================================
    # Main Methods
    # ========================================================================

    def analyze(self, analysis_limit: int = 1_000_000) -> ImportPlan:
        """Analyze data files and infer schema (dry-run)."""
        analyze_start = time.time()

        print("=" * 80)
        print("ANALYZING DATA FILES")
        print("=" * 80)
        print(f"Dataset: {self.dataset}")
        print(f"Path: {self.dataset_path}")
        print(f"Analysis limit: {analysis_limit:,} rows per file")
        print()

        # Step 1: Analyze all XML files
        step1_start = time.time()
        analyzer = SchemaAnalyzer(analysis_limit=analysis_limit)
        xml_files = sorted(self.dataset_path.glob("*.xml"))

        print(f"Found {len(xml_files)} XML files")
        print()

        inference = GraphSchemaInference(entity_threshold=0.5)

        for xml_file in xml_files:
            schema = analyzer.analyze_xml_file(xml_file)
            inference.add_entity(schema)

        step1_elapsed = time.time() - step1_start
        print(f"\n  ✓ Analysis completed in {step1_elapsed:.1f}s")

        # Step 2: Infer graph schema
        step2_start = time.time()
        plan = inference.infer_schema()
        step2_elapsed = time.time() - step2_start
        print(f"  ✓ Inference completed in {step2_elapsed:.1f}s")

        # Print summary
        print()
        print(plan.summary())

        total_analyze = time.time() - analyze_start
        print(f"Total analysis time: {total_analyze:.1f}s")
        print()

        return plan

    def execute_import(self, plan: ImportPlan):
        """Execute the import plan (create graph database).

        Note: This uses a hardcoded Stack Overflow schema based on domain knowledge,
        not the automated inference from the plan. The plan is used for reference only.
        """
        import_start_time = time.time()

        print("=" * 80)
        print("EXECUTING IMPORT (Stack Overflow Production Schema)")
        print("=" * 80)
        print()

        # Check dependencies
        try:
            import numpy as np  # noqa: F401
            from sentence_transformers import SentenceTransformer  # noqa: F401
        except ImportError as e:
            print(f"ERROR: Missing dependency: {e}")
            print("Install: pip install sentence-transformers numpy")
            return

        # Initialize database
        if Path(self.db_path).exists():
            print(f"⚠️  Database already exists: {self.db_path}")
            print("    Deleting existing database...")
            import shutil

            shutil.rmtree(self.db_path)

        print(f"Creating database: {self.db_path}")

        with arcadedb.create_database(self.db_path) as db:
            # Step 1: Create vertex types (Stack Overflow schema)
            step1_time = self._create_so_vertex_types(db)

            # Step 2: Create vertices with embeddings (Pass 1)
            step2_time = self._create_so_vertices(db)

            # Step 3: Create edges (Pass 2)
            step3_time = self._create_so_edges(db)

            # Step 4: Create HNSW indexes
            step4_time, vector_indexes = self._create_so_vector_indexes(db)

            total_elapsed = time.time() - import_start_time

            print()
            print("=" * 80)
            print("✓ IMPORT COMPLETE")
            print("=" * 80)
            print("\nTiming Summary:")
            print(f"  Step 1 (Vertex Types):        {step1_time:8.1f}s")
            print(f"  Step 2 (Vertices+Embeddings): {step2_time:8.1f}s")
            print(f"  Step 3 (Edges):               {step3_time:8.1f}s")
            print(f"  Step 4 (HNSW Indexes):        {step4_time:8.1f}s")
            print(f"  {'─' * 40}")
            print(f"  Total:                        {total_elapsed:8.1f}s")
            print()

            # Run demo queries (pass indexes)
            self.run_demo_queries(db, vector_indexes)

    # ========================================================================
    # Stack Overflow Production Schema Implementation
    # ========================================================================

    def _create_so_vertex_types(self, db):
        """Create Stack Overflow vertex types with properties."""
        step_start = time.time()

        print("\n" + "=" * 80)
        print("STEP 1: Creating Vertex Types (Stack Overflow Schema)")
        print("=" * 80)
        print()

        # Check for background async tasks before starting index creation
        print("Checking background task status...")
        try:
            async_exec = db.async_executor()
            async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
            print("  ✓ No background tasks running")
        except Exception as e:
            # TimeoutError or other exceptions
            error_name = type(e).__name__
            if "TimeoutError" in error_name or "timeout" in str(e).lower():
                print("  ℹ️  Background tasks still running (this is normal)")
            else:
                print(f"  ℹ️  Could not check async status: {e}")
        print()

        # Define schema
        vertex_schemas = {
            "UserVertex": [
                ("Id", "INTEGER"),
                ("DisplayName", "STRING"),
                ("Reputation", "INTEGER"),
                ("CreationDate", "DATETIME"),
                ("LastAccessDate", "DATETIME"),
                ("WebsiteUrl", "STRING"),
                ("Location", "STRING"),
                ("AboutMe", "STRING"),
                ("Views", "INTEGER"),
                ("UpVotes", "INTEGER"),
                ("DownVotes", "INTEGER"),
                ("AccountId", "INTEGER"),
                ("embedding", "FLOAT[]"),
                ("vector_id", "STRING"),
            ],
            "QuestionVertex": [
                ("Id", "INTEGER"),
                ("PostTypeId", "INTEGER"),
                ("Title", "STRING"),
                ("Body", "STRING"),
                ("CreationDate", "DATETIME"),
                ("Score", "INTEGER"),
                ("ViewCount", "INTEGER"),
                ("OwnerUserId", "INTEGER"),
                ("AnswerCount", "INTEGER"),
                ("CommentCount", "INTEGER"),
                ("AcceptedAnswerId", "INTEGER"),
                ("Tags", "STRING"),
                ("LastEditDate", "DATETIME"),
                ("LastActivityDate", "DATETIME"),
                ("embedding", "FLOAT[]"),
                ("vector_id", "STRING"),
            ],
            "AnswerVertex": [
                ("Id", "INTEGER"),
                ("PostTypeId", "INTEGER"),
                ("ParentId", "INTEGER"),
                ("Body", "STRING"),
                ("CreationDate", "DATETIME"),
                ("Score", "INTEGER"),
                ("OwnerUserId", "INTEGER"),
                ("CommentCount", "INTEGER"),
                ("LastEditDate", "DATETIME"),
                ("LastActivityDate", "DATETIME"),
                ("embedding", "FLOAT[]"),
                ("vector_id", "STRING"),
            ],
            "CommentVertex": [
                ("Id", "INTEGER"),
                ("PostId", "INTEGER"),
                ("UserId", "INTEGER"),
                ("Text", "STRING"),
                ("Score", "INTEGER"),
                ("CreationDate", "DATETIME"),
                ("UserDisplayName", "STRING"),
                ("embedding", "FLOAT[]"),
                ("vector_id", "STRING"),
            ],
            "BadgeVertex": [
                ("Id", "INTEGER"),
                ("UserId", "INTEGER"),
                ("Name", "STRING"),
                ("Date", "DATETIME"),
                ("Class", "INTEGER"),
                ("TagBased", "BOOLEAN"),
            ],
            "PostHistoryVertex": [
                ("Id", "INTEGER"),
                ("PostId", "INTEGER"),
                ("UserId", "INTEGER"),
                ("PostHistoryTypeId", "INTEGER"),
                ("RevisionGUID", "STRING"),
                ("CreationDate", "DATETIME"),
                ("Text", "STRING"),
                ("Comment", "STRING"),
                ("UserDisplayName", "STRING"),
                ("ContentLicense", "STRING"),
                ("embedding", "FLOAT[]"),
                ("vector_id", "STRING"),
            ],
            "TagVertex": [
                ("Id", "INTEGER"),
                ("TagName", "STRING"),
                ("Count", "INTEGER"),
                ("ExcerptPostId", "INTEGER"),
                ("WikiPostId", "INTEGER"),
            ],
        }

        with db.transaction():
            for type_name, properties in vertex_schemas.items():
                print(f"  Creating type: {type_name}")
                db.schema.get_or_create_vertex_type(type_name)

                for prop_name, prop_type in properties:
                    db.schema.create_property(type_name, prop_name, prop_type)

                # Create UNIQUE index on Id with retry logic
                if any(p[0] == "Id" for p in properties):
                    print(f"    Creating UNIQUE index on {type_name}[Id]...")
                    success, elapsed, error = self._create_index_with_retry(
                        db, type_name, "Id", index_type="LSM_TREE", unique=True
                    )
                    if success:
                        print(f"      ✓ Index created in {elapsed:.2f}s")
                    else:
                        print(f"      ❌ Failed to create index: {error}")

        # Print schema summary
        print("\n  Schema Summary:")
        print("  " + "-" * 76)
        for type_name, properties in vertex_schemas.items():
            print(f"\n  📊 {type_name}")

            # Separate properties by category
            id_props = []
            text_props = []
            vector_props = []
            other_props = []

            for prop_name, prop_type in properties:
                if prop_name == "Id":
                    id_props.append((prop_name, prop_type))
                elif prop_name in ["embedding", "vector_id"]:
                    vector_props.append((prop_name, prop_type))
                elif (
                    "Text" in prop_name
                    or "Body" in prop_name
                    or "Title" in prop_name
                    or "AboutMe" in prop_name
                ):
                    text_props.append((prop_name, prop_type))
                else:
                    other_props.append((prop_name, prop_type))

            # Print ID
            for prop_name, prop_type in id_props:
                print(f"      🔑 {prop_name}: {prop_type}")

            # Print text fields
            if text_props:
                print(f"      📝 Text fields:")
                for prop_name, prop_type in text_props:
                    print(f"         - {prop_name}: {prop_type}")

            # Print vector fields
            if vector_props:
                print(f"      🎯 Vector fields:")
                for prop_name, prop_type in vector_props:
                    print(f"         - {prop_name}: {prop_type}")

            # Print other properties
            if other_props:
                print(f"      📋 Properties ({len(other_props)}):")
                for prop_name, prop_type in other_props:
                    print(f"         - {prop_name}: {prop_type}")

        print("\n  " + "-" * 76)

        # Create edge types
        print("\n  Creating edge types...")
        edge_types = [
            "ASKED",  # User → Question
            "ASKED_BY",  # Question → User (reverse)
            "ANSWERED",  # User → Answer
            "ANSWERED_BY",  # Answer → User (reverse)
            "ANSWERS",  # Answer → Question
            "HAS_ANSWER",  # Question → Answer (reverse)
            "ACCEPTED_ANSWER",  # Question → Answer
            "COMMENTED",  # User → Comment
            "COMMENTED_BY",  # Comment → User (reverse)
            "COMMENTED_ON",  # Comment → Q/A
            "EARNED",  # User → Badge
            "EARNED_BY",  # Badge → User (reverse)
            "EDITED",  # User → PostHistory
            "EDITED_BY",  # PostHistory → User (reverse)
            "EDIT_OF",  # PostHistory → Q/A
            "LINKED_TO",  # Question ↔ Question
            "TAGGED_WITH",  # Question → Tag
            "VOTED_ON",  # User → Q/A
        ]

        with db.transaction():
            for edge_type in edge_types:
                db.schema.get_or_create_edge_type(edge_type)

        print(f"    ✓ Created {len(edge_types)} edge types")

        # Define properties for edge types that need them
        print("  Creating edge properties...")
        with db.transaction():
            # LINKED_TO edge properties (PostLinks.xml)
            db.schema.create_property("LINKED_TO", "LinkTypeId", "INTEGER")
            db.schema.create_property("LINKED_TO", "CreationDate", "DATETIME")

            # VOTED_ON edge properties (Votes.xml)
            db.schema.create_property("VOTED_ON", "VoteTypeId", "INTEGER")
            db.schema.create_property("VOTED_ON", "CreationDate", "DATETIME")
            db.schema.create_property("VOTED_ON", "BountyAmount", "INTEGER")

        print("    ✓ Created properties for LINKED_TO and VOTED_ON edges")

        # Wait for background compactions triggered by index creation
        print()
        print("  ⏳ Checking for background compactions...")
        try:
            async_exec = db.async_executor()
            async_exec.wait_completion(timeout_ms=10000)  # 10 seconds
            print("    ✓ All compactions complete")
        except Exception as e:
            error_name = type(e).__name__
            if "TimeoutError" in error_name or "timeout" in str(e).lower():
                print("    ℹ️  Compactions still running (normal for large datasets)")
                print("       Database is functional, will finish in background")
            else:
                print(f"    ℹ️  Could not check async status: {e}")

        elapsed = time.time() - step_start
        print(f"\n  ✓ Step 1 completed in {elapsed:.1f}s")
        return elapsed

    def _create_so_vertices(self, db):
        """Create Stack Overflow vertices with embeddings (Pass 1)."""
        step_start = time.time()

        print("\n" + "=" * 80)
        print("STEP 2: Creating Vertices with Embeddings (Pass 1)")
        print("=" * 80)

        # Load embedding model
        print("\n  Loading embedding model: all-MiniLM-L6-v2 (384 dims)")
        model_load_start = time.time()
        from sentence_transformers import SentenceTransformer

        # Detect CUDA availability
        device = "cpu"
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
                print(
                    f"  ✓ CUDA detected: Using GPU ({torch.cuda.get_device_name(0)}) "
                    f"with embedding batch size {self.embedding_batch_size}"
                )
            else:
                print("  Using CPU (CUDA not available)")
        except ImportError:
            print("  Using CPU (PyTorch not installed)")

        model = SentenceTransformer("all-MiniLM-L6-v2", device=device)
        model_load_elapsed = time.time() - model_load_start
        print(f"  ✓ Model loaded in {model_load_elapsed:.1f}s")

        # Store PostId → Type mapping for Pass 2
        self.post_id_map = {}  # PostId → ("Question" | "Answer")

        # Process each XML file
        self._create_users(db, model, device)
        self._create_posts(db, model, device)  # Creates Questions and Answers
        self._create_comments(db, model, device)
        self._create_badges(db)
        self._create_post_history(db, model, device)
        self._create_tags(db)

        elapsed = time.time() - step_start
        print(f"\n  ✓ Step 2 completed in {elapsed:.1f}s")
        return elapsed

    def _process_user_batch(self, db, model, device, batch):
        """Process a batch of users: generate embeddings and create vertices.

        Returns:
            Tuple of (count, embedding_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Extract texts and rows
        rows_data = [row for row, text in batch]
        texts_to_embed = [text for row, text in batch]

        # Generate embeddings for this batch
        emb_start = time.time()
        embeddings = model.encode(
            texts_to_embed,
            batch_size=self.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            device=device,
        )
        emb_time = time.time() - emb_start

        # Create vertices in DB batches
        db_start = time.time()
        db_batch = []

        for i, row in enumerate(rows_data):
            db_batch.append((row, embeddings[i]))

            if len(db_batch) >= self.batch_size:
                with db.transaction():
                    for row_data, embedding in db_batch:
                        vertex = db.new_vertex("UserVertex")

                        # Set properties
                        for field_name, value in row_data.items():
                            if value is not None:
                                vertex.set(field_name, value)

                        # Add embedding
                        java_embedding = arcadedb.to_java_float_array(embedding)
                        vertex.set("embedding", java_embedding)
                        vertex.set("vector_id", row_data.get("Id"))

                        vertex.save()
                db_batch = []

        # Final DB batch
        if db_batch:
            with db.transaction():
                for row_data, embedding in db_batch:
                    vertex = db.new_vertex("UserVertex")

                    # Set properties
                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    # Add embedding
                    java_embedding = arcadedb.to_java_float_array(embedding)
                    vertex.set("embedding", java_embedding)
                    vertex.set("vector_id", row_data.get("Id"))

                    vertex.save()

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        return (len(rows_data), emb_time, db_time, total_time)

    def _create_users(self, db, model, device):
        """Create UserVertex vertices with AboutMe embeddings."""
        xml_file = self.dataset_path / "Users.xml"
        if not xml_file.exists():
            print(f"\n  ⚠️  {xml_file.name} not found, skipping")
            return

        print(f"\n  Processing {xml_file.name} → UserVertex")
        print(f"    Streaming XML with batch_size={self.batch_size:,}")

        start = time.time()
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        batch = []
        total_created = 0
        batch_times = []  # Store (count, emb_time, db_time, total_time)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row = {k: v for k, v in elem.attrib.items()}
                text = row.get("AboutMe", "")
                batch.append((row, text))

                if len(batch) >= self.batch_size:
                    count, emb_t, db_t, total_t = self._process_user_batch(
                        db, model, device, batch
                    )
                    total_created += count
                    batch_times.append((count, emb_t, db_t, total_t))
                    self._print_batch_stats(
                        count,
                        embed_time=emb_t,
                        db_time=db_t,
                        total_time=total_t,
                        item_name="users",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, emb_t, db_t, total_t = self._process_user_batch(
                db, model, device, batch
            )
            total_created += count
            batch_times.append((count, emb_t, db_t, total_t))
            self._print_batch_stats(
                count,
                embed_time=emb_t,
                db_time=db_t,
                total_time=total_t,
                item_name="users",
            )

        elapsed = time.time() - start
        self._print_summary_stats(
            total_created, elapsed, batch_times, item_name="users", has_embed=True
        )

    def _process_question_batch(self, db, model, device, batch):
        """Process a batch of questions: generate embeddings and create vertices.

        Returns:
            Tuple of (count, embedding_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Extract rows and texts
        rows_data = [row for row, text in batch]
        texts_to_embed = [text for row, text in batch]

        # Generate embeddings for this batch
        emb_start = time.time()
        embeddings = model.encode(
            texts_to_embed,
            batch_size=self.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            device=device,
        )
        emb_time = time.time() - emb_start

        # Create vertices in DB batches
        db_start = time.time()
        db_batch = []

        for i, row in enumerate(rows_data):
            db_batch.append((row, embeddings[i]))

            if len(db_batch) >= self.batch_size:
                with db.transaction():
                    for row_data, embedding in db_batch:
                        vertex = db.new_vertex("QuestionVertex")

                        for field_name, value in row_data.items():
                            if value is not None:
                                vertex.set(field_name, value)

                        java_embedding = arcadedb.to_java_float_array(embedding)
                        vertex.set("embedding", java_embedding)
                        vertex.set("vector_id", row_data.get("Id"))

                        vertex.save()
                db_batch = []

        # Final DB batch
        if db_batch:
            with db.transaction():
                for row_data, embedding in db_batch:
                    vertex = db.new_vertex("QuestionVertex")

                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    java_embedding = arcadedb.to_java_float_array(embedding)
                    vertex.set("embedding", java_embedding)
                    vertex.set("vector_id", row_data.get("Id"))

                    vertex.save()

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        return (len(rows_data), emb_time, db_time, total_time)

    def _process_answer_batch(self, db, model, device, batch):
        """Process a batch of answers: generate embeddings and create vertices.

        Returns:
            Tuple of (count, embedding_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Extract rows and texts
        rows_data = [row for row, text in batch]
        texts_to_embed = [text for row, text in batch]

        # Generate embeddings for this batch
        emb_start = time.time()
        embeddings = model.encode(
            texts_to_embed,
            batch_size=self.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            device=device,
        )
        emb_time = time.time() - emb_start

        # Create vertices in DB batches
        db_start = time.time()
        db_batch = []

        for i, row in enumerate(rows_data):
            db_batch.append((row, embeddings[i]))

            if len(db_batch) >= self.batch_size:
                with db.transaction():
                    for row_data, embedding in db_batch:
                        vertex = db.new_vertex("AnswerVertex")

                        for field_name, value in row_data.items():
                            if value is not None:
                                vertex.set(field_name, value)

                        java_embedding = arcadedb.to_java_float_array(embedding)
                        vertex.set("embedding", java_embedding)
                        vertex.set("vector_id", row_data.get("Id"))

                        vertex.save()
                db_batch = []

        # Final DB batch
        if db_batch:
            with db.transaction():
                for row_data, embedding in db_batch:
                    vertex = db.new_vertex("AnswerVertex")

                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    java_embedding = arcadedb.to_java_float_array(embedding)
                    vertex.set("embedding", java_embedding)
                    vertex.set("vector_id", row_data.get("Id"))

                    vertex.save()

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        return (len(rows_data), emb_time, db_time, total_time)

    def _create_posts(self, db, model, device):
        """Create QuestionVertex and AnswerVertex with embeddings."""
        xml_file = self.dataset_path / "Posts.xml"
        if not xml_file.exists():
            print(f"\n  ⚠️  {xml_file.name} not found, skipping")
            return

        print(f"\n  Processing {xml_file.name} → QuestionVertex + AnswerVertex")
        print(f"    Streaming XML with batch_size={self.batch_size:,}")

        start = time.time()
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        question_batch = []
        answer_batch = []
        total_questions = 0
        total_answers = 0
        question_times = []  # (count, emb_time, db_time, total_time)
        answer_times = []

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row = {k: v for k, v in elem.attrib.items()}
                post_type_id = int(row.get("PostTypeId", "0"))
                post_id = row.get("Id")

                if post_type_id == 1:  # Question
                    # Combine Title + Body for embedding
                    title = row.get("Title", "")
                    body = row.get("Body", "")
                    text = f"{title} {body}".strip()
                    question_batch.append((row, text))
                    self.post_id_map[post_id] = "Question"

                    if len(question_batch) >= self.batch_size:
                        count, emb_t, db_t, total_t = self._process_question_batch(
                            db, model, device, question_batch
                        )
                        total_questions += count
                        question_times.append((count, emb_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            embed_time=emb_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="questions",
                        )
                        question_batch = []

                elif post_type_id == 2:  # Answer
                    text = row.get("Body", "")
                    answer_batch.append((row, text))
                    self.post_id_map[post_id] = "Answer"

                    if len(answer_batch) >= self.batch_size:
                        count, emb_t, db_t, total_t = self._process_answer_batch(
                            db, model, device, answer_batch
                        )
                        total_answers += count
                        answer_times.append((count, emb_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            embed_time=emb_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="answers",
                        )
                        answer_batch = []

                elem.clear()
                root.clear()

        # Final batches
        if question_batch:
            count, emb_t, db_t, total_t = self._process_question_batch(
                db, model, device, question_batch
            )
            total_questions += count
            question_times.append((count, emb_t, db_t, total_t))
            self._print_batch_stats(
                count,
                embed_time=emb_t,
                db_time=db_t,
                total_time=total_t,
                item_name="questions",
            )

        if answer_batch:
            count, emb_t, db_t, total_t = self._process_answer_batch(
                db, model, device, answer_batch
            )
            total_answers += count
            answer_times.append((count, emb_t, db_t, total_t))
            self._print_batch_stats(
                count,
                embed_time=emb_t,
                db_time=db_t,
                total_time=total_t,
                item_name="answers",
            )

        elapsed = time.time() - start
        total = total_questions + total_answers

        # Print combined summary
        all_times = question_times + answer_times
        print(f"    ✓ {total_questions:,} questions + {total_answers:,} answers")
        if all_times:
            self._print_summary_stats(
                total, elapsed, all_times, item_name="posts", has_embed=True
            )

    def _process_comment_batch(self, db, model, device, batch):
        """Process a batch of comments: generate embeddings and create vertices.

        Returns:
            Tuple of (count, embedding_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Extract rows and texts
        rows_data = [row for row, text in batch]
        texts_to_embed = [text for row, text in batch]

        # Generate embeddings for this batch
        emb_start = time.time()
        embeddings = model.encode(
            texts_to_embed,
            batch_size=self.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            device=device,
        )
        emb_time = time.time() - emb_start

        # Create vertices in DB batches
        db_start = time.time()
        db_batch = []

        for i, row in enumerate(rows_data):
            db_batch.append((row, embeddings[i]))

            if len(db_batch) >= self.batch_size:
                with db.transaction():
                    for row_data, embedding in db_batch:
                        vertex = db.new_vertex("CommentVertex")

                        for field_name, value in row_data.items():
                            if value is not None:
                                vertex.set(field_name, value)

                        java_embedding = arcadedb.to_java_float_array(embedding)
                        vertex.set("embedding", java_embedding)
                        vertex.set("vector_id", row_data.get("Id"))

                        vertex.save()
                db_batch = []

        # Final DB batch
        if db_batch:
            with db.transaction():
                for row_data, embedding in db_batch:
                    vertex = db.new_vertex("CommentVertex")

                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    java_embedding = arcadedb.to_java_float_array(embedding)
                    vertex.set("embedding", java_embedding)
                    vertex.set("vector_id", row_data.get("Id"))

                    vertex.save()

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        return (len(rows_data), emb_time, db_time, total_time)

    def _create_comments(self, db, model, device):
        """Create CommentVertex with Text embeddings."""
        xml_file = self.dataset_path / "Comments.xml"
        if not xml_file.exists():
            print(f"\n  ⚠️  {xml_file.name} not found, skipping")
            return

        print(f"\n  Processing {xml_file.name} → CommentVertex")
        print(f"    Streaming XML with batch_size={self.batch_size:,}")

        start = time.time()
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        batch = []
        total_created = 0
        batch_times = []

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row = {k: v for k, v in elem.attrib.items()}
                text = row.get("Text", "")
                batch.append((row, text))

                if len(batch) >= self.batch_size:
                    count, emb_t, db_t, total_t = self._process_comment_batch(
                        db, model, device, batch
                    )
                    total_created += count
                    batch_times.append((count, emb_t, db_t, total_t))
                    self._print_batch_stats(
                        count,
                        embed_time=emb_t,
                        db_time=db_t,
                        total_time=total_t,
                        item_name="comments",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, emb_t, db_t, total_t = self._process_comment_batch(
                db, model, device, batch
            )
            total_created += count
            batch_times.append((count, emb_t, db_t, total_t))
            self._print_batch_stats(
                count,
                embed_time=emb_t,
                db_time=db_t,
                total_time=total_t,
                item_name="comments",
            )

        elapsed = time.time() - start
        self._print_summary_stats(
            total_created, elapsed, batch_times, item_name="comments", has_embed=True
        )

    def _create_badges(self, db):
        """Create BadgeVertex (no embeddings)."""
        xml_file = self.dataset_path / "Badges.xml"
        if not xml_file.exists():
            print(f"\n  ⚠️  {xml_file.name} not found, skipping")
            return

        print(f"\n  Processing {xml_file.name} → BadgeVertex")
        print(f"    Streaming XML with batch_size={self.batch_size:,}")

        start = time.time()
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        batch = []
        total_created = 0
        batch_times = []

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row = {k: v for k, v in elem.attrib.items()}
                batch.append(row)

                if len(batch) >= self.batch_size:
                    batch_start = time.time()
                    with db.transaction():
                        for row_data in batch:
                            vertex = db.new_vertex("BadgeVertex")

                            for field_name, value in row_data.items():
                                if value is not None:
                                    vertex.set(field_name, value)

                            vertex.save()
                    batch_time = time.time() - batch_start
                    count = len(batch)
                    total_created += count
                    batch_times.append((count, batch_time))
                    self._print_batch_stats(
                        count,
                        db_time=batch_time,
                        total_time=batch_time,
                        item_name="badges",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            batch_start = time.time()
            with db.transaction():
                for row_data in batch:
                    vertex = db.new_vertex("BadgeVertex")

                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    vertex.save()
            batch_time = time.time() - batch_start
            count = len(batch)
            total_created += count
            batch_times.append((count, batch_time))
            self._print_batch_stats(
                count, db_time=batch_time, total_time=batch_time, item_name="badges"
            )

        elapsed = time.time() - start
        self._print_summary_stats(
            total_created, elapsed, batch_times, item_name="badges", has_embed=False
        )

    def _process_post_history_batch(self, db, model, device, batch):
        """Process a batch of post history: generate embeddings and create vertices.

        Returns:
            Tuple of (count, emb_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Extract rows and texts
        rows_data = [row for row, text in batch]
        texts_to_embed = [text for row, text in batch]

        # Generate embeddings for this batch
        emb_start = time.time()
        embeddings = model.encode(
            texts_to_embed,
            batch_size=self.embedding_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            device=device,
        )
        emb_time = time.time() - emb_start

        # Create vertices in DB batches
        db_start = time.time()
        db_batch = []

        for i, row in enumerate(rows_data):
            db_batch.append((row, embeddings[i]))

            if len(db_batch) >= self.batch_size:
                with db.transaction():
                    for row_data, embedding in db_batch:
                        vertex = db.new_vertex("PostHistoryVertex")

                        for field_name, value in row_data.items():
                            if value is not None:
                                vertex.set(field_name, value)

                        java_embedding = arcadedb.to_java_float_array(embedding)
                        vertex.set("embedding", java_embedding)
                        vertex.set("vector_id", row_data.get("Id"))

                        vertex.save()
                db_batch = []

        # Final DB batch
        if db_batch:
            with db.transaction():
                for row_data, embedding in db_batch:
                    vertex = db.new_vertex("PostHistoryVertex")

                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    java_embedding = arcadedb.to_java_float_array(embedding)
                    vertex.set("embedding", java_embedding)
                    vertex.set("vector_id", row_data.get("Id"))

                    vertex.save()

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        return (len(rows_data), emb_time, db_time, total_time)

    def _create_post_history(self, db, model, device):
        """Create PostHistoryVertex with Text embeddings (when not null)."""
        xml_file = self.dataset_path / "PostHistory.xml"
        if not xml_file.exists():
            print(f"\n  ⚠️  {xml_file.name} not found, skipping")
            return

        print(f"\n  Processing {xml_file.name} → PostHistoryVertex")
        print(f"    Streaming XML with batch_size={self.batch_size:,}")

        start = time.time()
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        batch = []
        total_created = 0
        batch_times = []

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row = {k: v for k, v in elem.attrib.items()}
                text = row.get("Text", "")
                batch.append((row, text))

                if len(batch) >= self.batch_size:
                    count, emb_t, db_t, total_t = self._process_post_history_batch(
                        db, model, device, batch
                    )
                    total_created += count
                    batch_times.append((count, emb_t, db_t, total_t))
                    self._print_batch_stats(
                        count,
                        embed_time=emb_t,
                        db_time=db_t,
                        total_time=total_t,
                        item_name="post history",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, emb_t, db_t, total_t = self._process_post_history_batch(
                db, model, device, batch
            )
            total_created += count
            batch_times.append((count, emb_t, db_t, total_t))
            self._print_batch_stats(
                count,
                embed_time=emb_t,
                db_time=db_t,
                total_time=total_t,
                item_name="post history",
            )

        elapsed = time.time() - start
        self._print_summary_stats(
            total_created,
            elapsed,
            batch_times,
            item_name="post history",
            has_embed=True,
        )

    def _create_tags(self, db):
        """Create TagVertex from Tags.xml (no embeddings)."""
        xml_file = self.dataset_path / "Tags.xml"
        if not xml_file.exists():
            print(f"\n  ⚠️  {xml_file.name} not found, skipping")
            return

        print(f"\n  Processing {xml_file.name} → TagVertex")
        print(f"    Streaming XML with batch_size={self.batch_size:,}")

        start = time.time()
        context = ET.iterparse(xml_file, events=("start", "end"))
        context = iter(context)
        _, root = next(context)

        batch = []
        total_created = 0
        batch_times = []

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                row = {k: v for k, v in elem.attrib.items()}
                batch.append(row)

                if len(batch) >= self.batch_size:
                    batch_start = time.time()
                    with db.transaction():
                        for row_data in batch:
                            vertex = db.new_vertex("TagVertex")

                            for field_name, value in row_data.items():
                                if value is not None:
                                    vertex.set(field_name, value)

                            vertex.save()
                    batch_time = time.time() - batch_start
                    count = len(batch)
                    total_created += count
                    batch_times.append((count, batch_time))
                    self._print_batch_stats(
                        count,
                        db_time=batch_time,
                        total_time=batch_time,
                        item_name="tags",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            batch_start = time.time()
            with db.transaction():
                for row_data in batch:
                    vertex = db.new_vertex("TagVertex")

                    for field_name, value in row_data.items():
                        if value is not None:
                            vertex.set(field_name, value)

                    vertex.save()
            batch_time = time.time() - batch_start
            count = len(batch)
            total_created += count
            batch_times.append((count, batch_time))
            self._print_batch_stats(
                count, db_time=batch_time, total_time=batch_time, item_name="tags"
            )

        elapsed = time.time() - start
        self._print_summary_stats(
            total_created, elapsed, batch_times, item_name="tags", has_embed=False
        )

    def _create_so_edges(self, db):
        """Create Stack Overflow edges (Pass 2).

        Uses cached RIDs from vertex creation for ultra-fast edge creation.
        RID caches eliminate the need for index lookups during edge creation.
        """
        step_start = time.time()

        print("\n" + "=" * 80)
        print("STEP 3: Creating Edges (Pass 2)")
        print("=" * 80)
        print(f"\n  PostId map contains {len(self.post_id_map):,} entries")
        print("  Using per-batch vertex caching (constant memory)")

        # Create all 18 edge types
        self._create_post_ownership_edges(db)  # ASKED, ANSWERED (User → Q/A)
        self._create_answer_edges(db)  # ANSWERS, ACCEPTED_ANSWER
        self._create_comment_edges(db)  # COMMENTED, COMMENTED_ON
        self._create_badge_edges(db)  # EARNED (User → Badge)
        self._create_post_history_edges(db)  # EDITED, EDIT_OF
        self._create_tag_edges(db)  # TAGGED_WITH (Question → Tag)
        self._create_post_link_edges(db)  # LINKED_TO (Question → Question)
        self._create_vote_edges(db)  # VOTED_ON (User → Q/A)

        elapsed = time.time() - step_start
        print(f"\n  ✓ Step 3 completed in {elapsed:.1f}s")
        return elapsed

    def _create_post_ownership_edges(self, db):
        """Create ASKED/ANSWERED edges from Users to Questions/Answers."""
        edge_start = time.time()
        print("\n  Creating Post Ownership edges (ASKED, ANSWERED)...")

        asked_count = 0
        answered_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []  # (count, query_time, db_time, total_time)

        # Parse Posts.xml to create ownership edges
        posts_path = self.dataset_path / "Posts.xml"
        context = ET.iterparse(posts_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                post_id = elem.get("Id")
                owner_id = elem.get("OwnerUserId")
                post_type = elem.get("PostTypeId")

                if owner_id and post_id and post_type:
                    # Determine edge type based on PostTypeId
                    if post_type == "1":  # Question
                        edge_type = "ASKED"
                        from_vertex = f"UserVertex:{owner_id}"
                        to_vertex = f"QuestionVertex:{post_id}"
                        asked_count += 1
                    elif post_type == "2":  # Answer
                        edge_type = "ANSWERED"
                        from_vertex = f"UserVertex:{owner_id}"
                        to_vertex = f"AnswerVertex:{post_id}"
                        answered_count += 1
                    else:
                        elem.clear()
                        continue

                    batch.append((edge_type, from_vertex, to_vertex))

                    if len(batch) >= batch_size:
                        result = self._execute_edge_batch_with_rids(db, batch)
                        count, query_t, db_t, total_t = result
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            result = self._execute_edge_batch_with_rids(db, batch)
            count, query_t, db_t, total_t = result
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        total_edges = asked_count + answered_count

        # Print summary with proper label
        print(f"    ✓ {asked_count:,} ASKED + {answered_count:,} ANSWERED edges")
        self._print_summary_stats(
            total_edges, elapsed, batch_times, item_name="edges", has_query=True
        )

    def _create_answer_edges(self, db):
        """Create ANSWERS/ACCEPTED_ANSWER edges from Answers to Questions."""
        edge_start = time.time()
        print("\n  Creating Answer edges (ANSWERS, ACCEPTED_ANSWER)...")

        answers_count = 0
        accepted_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse Posts.xml for PostTypeId=2 (Answers)
        posts_path = self.dataset_path / "Posts.xml"
        context = ET.iterparse(posts_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                post_id = elem.get("Id")
                post_type = elem.get("PostTypeId")
                parent_id = elem.get("ParentId")

                # ANSWERS edge: Answer → Question (via ParentId)
                if post_type == "2" and parent_id:
                    batch.append(
                        (
                            "ANSWERS",
                            f"AnswerVertex:{post_id}",
                            f"QuestionVertex:{parent_id}",
                        )
                    )
                    answers_count += 1

                    if len(batch) >= batch_size:
                        count, query_t, db_t, total_t = self._execute_edge_batch(
                            db, batch
                        )
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        # ACCEPTED_ANSWER edge: Question → Answer (via AcceptedAnswerId)
        context = ET.iterparse(posts_path, events=("start", "end"))
        _, root = next(context)
        batch = []

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                post_id = elem.get("Id")
                post_type = elem.get("PostTypeId")
                accepted_id = elem.get("AcceptedAnswerId")

                if post_type == "1" and accepted_id:
                    batch.append(
                        (
                            "ACCEPTED_ANSWER",
                            f"QuestionVertex:{post_id}",
                            f"AnswerVertex:{accepted_id}",
                        )
                    )
                    accepted_count += 1

                    if len(batch) >= batch_size:
                        count, query_t, db_t, total_t = self._execute_edge_batch(
                            db, batch
                        )
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        total_edges = answers_count + accepted_count

        print(
            f"    ✓ {answers_count:,} ANSWERS + {accepted_count:,} ACCEPTED_ANSWER edges"
        )
        self._print_summary_stats(
            total_edges, elapsed, batch_times, item_name="edges", has_query=True
        )

    def _create_comment_edges(self, db):
        """Create COMMENTED/COMMENTED_ON edges for Comments."""
        edge_start = time.time()
        print("\n  Creating Comment edges (COMMENTED, COMMENTED_ON)...")

        commented_count = 0
        commented_on_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse Comments.xml
        comments_path = self.dataset_path / "Comments.xml"
        if not comments_path.exists():
            print("    ⚠ Comments.xml not found, skipping comment edges")
            return

        context = ET.iterparse(comments_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                comment_id = elem.get("Id")
                user_id = elem.get("UserId")
                post_id = elem.get("PostId")

                if not comment_id:
                    elem.clear()
                    continue

                # COMMENTED edge: User → Comment (skip if UserId is null)
                if user_id:
                    batch.append(
                        (
                            "COMMENTED",
                            f"UserVertex:{user_id}",
                            f"CommentVertex:{comment_id}",
                        )
                    )
                    commented_count += 1

                # COMMENTED_ON: Comment → Question|Answer (requires post_id_map lookup)
                if post_id and post_id in self.post_id_map:
                    post_type = self.post_id_map[post_id]
                    to_vertex = f"{post_type}Vertex:{post_id}"
                    batch.append(
                        ("COMMENTED_ON", f"CommentVertex:{comment_id}", to_vertex)
                    )
                    commented_on_count += 1

                if len(batch) >= batch_size:
                    count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
                    batch_times.append((count, query_t, db_t, total_t))
                    self._print_batch_stats(
                        count,
                        query_time=query_t,
                        db_time=db_t,
                        total_time=total_t,
                        item_name="edges",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        total_edges = commented_count + commented_on_count

        print(
            f"    ✓ {commented_count:,} COMMENTED + "
            f"{commented_on_count:,} COMMENTED_ON edges"
        )
        self._print_summary_stats(
            total_edges, elapsed, batch_times, item_name="edges", has_query=True
        )

    def _create_badge_edges(self, db):
        """Create EARNED edges from Users to Badges."""
        edge_start = time.time()
        print("\n  Creating Badge edges (EARNED)...")

        earned_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse Badges.xml
        badges_path = self.dataset_path / "Badges.xml"
        if not badges_path.exists():
            print("    ⚠ Badges.xml not found, skipping badge edges")
            return

        context = ET.iterparse(badges_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                badge_id = elem.get("Id")
                user_id = elem.get("UserId")

                if badge_id and user_id:
                    batch.append(
                        ("EARNED", f"UserVertex:{user_id}", f"BadgeVertex:{badge_id}")
                    )
                    earned_count += 1

                    if len(batch) >= batch_size:
                        count, query_t, db_t, total_t = self._execute_edge_batch(
                            db, batch
                        )
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        self._print_summary_stats(
            earned_count, elapsed, batch_times, item_name="EARNED edges", has_query=True
        )

    def _create_post_history_edges(self, db):
        """Create EDITED/EDIT_OF edges for PostHistory."""
        edge_start = time.time()
        print("\n  Creating PostHistory edges (EDITED, EDIT_OF)...")

        edited_count = 0
        edit_of_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse PostHistory.xml
        history_path = self.dataset_path / "PostHistory.xml"
        if not history_path.exists():
            print("    ⚠ PostHistory.xml not found, skipping post history edges")
            return

        context = ET.iterparse(history_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                history_id = elem.get("Id")
                user_id = elem.get("UserId")
                post_id = elem.get("PostId")

                if not history_id:
                    elem.clear()
                    continue

                # EDITED edge: User → PostHistory (skip if UserId is null)
                if user_id:
                    batch.append(
                        (
                            "EDITED",
                            f"UserVertex:{user_id}",
                            f"PostHistoryVertex:{history_id}",
                        )
                    )
                    edited_count += 1

                # EDIT_OF: PostHistory → Question|Answer (requires post_id_map)
                if post_id and post_id in self.post_id_map:
                    post_type = self.post_id_map[post_id]
                    to_vertex = f"{post_type}Vertex:{post_id}"
                    batch.append(
                        ("EDIT_OF", f"PostHistoryVertex:{history_id}", to_vertex)
                    )
                    edit_of_count += 1

                if len(batch) >= batch_size:
                    count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
                    batch_times.append((count, query_t, db_t, total_t))
                    self._print_batch_stats(
                        count,
                        query_time=query_t,
                        db_time=db_t,
                        total_time=total_t,
                        item_name="edges",
                    )
                    batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        total_edges = edited_count + edit_of_count

        print(f"    ✓ {edited_count:,} EDITED + {edit_of_count:,} EDIT_OF edges")
        self._print_summary_stats(
            total_edges, elapsed, batch_times, item_name="edges", has_query=True
        )

    def _create_tag_edges(self, db):
        """Create TAGGED_WITH edges from Questions to Tags."""
        edge_start = time.time()
        print("\n  Creating Tag edges (TAGGED_WITH)...")

        tagged_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse Posts.xml for Questions with Tags
        posts_path = self.dataset_path / "Posts.xml"
        context = ET.iterparse(posts_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                post_id = elem.get("Id")
                post_type = elem.get("PostTypeId")
                tags_str = elem.get("Tags")

                # Only Questions have tags
                if post_type == "1" and tags_str:
                    # Parse tags from "<python><django>" format
                    tag_names = tags_str.strip("<>").split("><") if tags_str else []

                    for tag_name in tag_names:
                        if tag_name:
                            batch.append(
                                (
                                    "TAGGED_WITH",
                                    f"QuestionVertex:{post_id}",
                                    f"TagVertex:{tag_name}",
                                )
                            )
                            tagged_count += 1

                    if len(batch) >= batch_size:
                        count, query_t, db_t, total_t = self._execute_edge_batch(
                            db, batch
                        )
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        self._print_summary_stats(
            tagged_count,
            elapsed,
            batch_times,
            item_name="TAGGED_WITH edges",
            has_query=True,
        )

    def _create_post_link_edges(self, db):
        """Create LINKED_TO edges from Questions to Questions."""
        edge_start = time.time()
        print("\n  Creating PostLink edges (LINKED_TO)...")

        linked_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse PostLinks.xml
        links_path = self.dataset_path / "PostLinks.xml"
        if not links_path.exists():
            print("    ⚠ PostLinks.xml not found, skipping post link edges")
            return

        context = ET.iterparse(links_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                post_id = elem.get("PostId")
                related_post_id = elem.get("RelatedPostId")
                link_type_id = elem.get("LinkTypeId")
                creation_date = elem.get("CreationDate")

                if post_id and related_post_id:
                    # Store properties on the edge
                    properties = {}
                    if link_type_id:
                        properties["LinkTypeId"] = int(link_type_id)
                    if creation_date:
                        properties["CreationDate"] = creation_date

                    batch.append(
                        (
                            "LINKED_TO",
                            f"QuestionVertex:{post_id}",
                            f"QuestionVertex:{related_post_id}",
                            properties,
                        )
                    )
                    linked_count += 1

                    if len(batch) >= batch_size:
                        count, query_t, db_t, total_t = self._execute_edge_batch(
                            db, batch
                        )
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        self._print_summary_stats(
            linked_count,
            elapsed,
            batch_times,
            item_name="LINKED_TO edges",
            has_query=True,
        )

    def _create_vote_edges(self, db):
        """Create VOTED_ON edges from Users to Questions/Answers."""
        edge_start = time.time()
        print("\n  Creating Vote edges (VOTED_ON)...")

        voted_count = 0
        batch = []
        batch_size = self.batch_size
        batch_times = []

        # Parse Votes.xml
        votes_path = self.dataset_path / "Votes.xml"
        if not votes_path.exists():
            print("    ⚠ Votes.xml not found, skipping vote edges")
            return

        context = ET.iterparse(votes_path, events=("start", "end"))
        _, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "row":
                user_id = elem.get("UserId")
                post_id = elem.get("PostId")
                vote_type_id = elem.get("VoteTypeId")
                creation_date = elem.get("CreationDate")
                bounty_amount = elem.get("BountyAmount")

                # Skip votes without UserId (community votes) or PostId
                if not user_id or not post_id:
                    elem.clear()
                    continue

                # Lookup post type (Question or Answer)
                if post_id in self.post_id_map:
                    post_type = self.post_id_map[post_id]
                    to_vertex = f"{post_type}Vertex:{post_id}"

                    # Store properties on the edge
                    properties = {}
                    if vote_type_id:
                        properties["VoteTypeId"] = int(vote_type_id)
                    if creation_date:
                        properties["CreationDate"] = creation_date
                    if bounty_amount:
                        properties["BountyAmount"] = int(bounty_amount)

                    batch.append(
                        ("VOTED_ON", f"UserVertex:{user_id}", to_vertex, properties)
                    )
                    voted_count += 1

                    if len(batch) >= batch_size:
                        count, query_t, db_t, total_t = self._execute_edge_batch(
                            db, batch
                        )
                        batch_times.append((count, query_t, db_t, total_t))
                        self._print_batch_stats(
                            count,
                            query_time=query_t,
                            db_time=db_t,
                            total_time=total_t,
                            item_name="edges",
                        )
                        batch = []

                elem.clear()
                root.clear()

        # Final batch
        if batch:
            count, query_t, db_t, total_t = self._execute_edge_batch(db, batch)
            batch_times.append((count, query_t, db_t, total_t))
            self._print_batch_stats(
                count,
                query_time=query_t,
                db_time=db_t,
                total_time=total_t,
                item_name="edges",
            )

        elapsed = time.time() - edge_start
        self._print_summary_stats(
            voted_count,
            elapsed,
            batch_times,
            item_name="VOTED_ON edges",
            has_query=True,
        )

    def _execute_edge_batch(self, db, batch):
        """Execute a batch of edge creations using Java API.

        Args:
            batch: List of tuples (edge_type, from_vertex_spec, to_vertex_spec[, properties])
                   where vertex_spec is "VertexType:Id"

        Returns:
            Tuple of (count, query_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Build vertex cache for this batch
        # Collect all unique vertex lookups needed
        from_lookups = {}  # (type, id) -> None (will be filled with vertex)
        to_lookups = {}  # (type, id) -> None

        for item in batch:
            edge_type = item[0]
            from_spec = item[1]  # e.g., "UserVertex:123"
            to_spec = item[2]  # e.g., "QuestionVertex:456"

            from_type, from_id = from_spec.split(":")
            to_type, to_id = to_spec.split(":")

            from_lookups[(from_type, from_id)] = None
            to_lookups[(to_type, to_id)] = None

        # Query vertices in batch
        query_start = time.time()

        # Group by type for efficient querying
        from_by_type = {}
        for vtype, vid in from_lookups.keys():
            if vtype not in from_by_type:
                from_by_type[vtype] = []
            from_by_type[vtype].append(vid)

        to_by_type = {}
        for vtype, vid in to_lookups.keys():
            if vtype not in to_by_type:
                to_by_type[vtype] = []
            to_by_type[vtype].append(vid)

        # Fetch from vertices
        for vtype, ids in from_by_type.items():
            if len(ids) == 1:
                query = f"SELECT FROM {vtype} WHERE Id = {ids[0]}"
            else:
                ids_str = ",".join(ids)
                query = f"SELECT FROM {vtype} WHERE Id IN [{ids_str}]"

            results = list(db.query("sql", query))
            for result in results:
                vid = str(result.get_property("Id"))
                vertex = result._java_result.getElement().get().asVertex()
                from_lookups[(vtype, vid)] = vertex

        # Fetch to vertices
        for vtype, ids in to_by_type.items():
            # Special case: TagVertex uses TagName instead of Id
            if vtype == "TagVertex":
                if len(ids) == 1:
                    # Escape single quotes in tag name
                    tag_name = ids[0].replace("'", "''")
                    query = f"SELECT FROM {vtype} WHERE TagName = '{tag_name}'"
                else:
                    # Escape and quote each tag name
                    quoted_tags = []
                    for t in ids:
                        escaped = t.replace("'", "''")
                        quoted_tags.append(f"'{escaped}'")
                    tags_str = ",".join(quoted_tags)
                    query = f"SELECT FROM {vtype} WHERE TagName IN [{tags_str}]"

                results = list(db.query("sql", query))
                for result in results:
                    tag_name = str(result.get_property("TagName"))
                    vertex = result._java_result.getElement().get().asVertex()
                    to_lookups[(vtype, tag_name)] = vertex
            else:
                if len(ids) == 1:
                    query = f"SELECT FROM {vtype} WHERE Id = {ids[0]}"
                else:
                    ids_str = ",".join(ids)
                    query = f"SELECT FROM {vtype} WHERE Id IN [{ids_str}]"

                results = list(db.query("sql", query))
                for result in results:
                    vid = str(result.get_property("Id"))
                    vertex = result._java_result.getElement().get().asVertex()
                    to_lookups[(vtype, vid)] = vertex

        query_time = time.time() - query_start

        # Create edges using Java API (within a transaction)
        db_start = time.time()
        edge_count = 0

        with db.transaction():
            for item in batch:
                if len(item) == 3:
                    edge_type, from_spec, to_spec = item
                    properties = {}
                else:
                    edge_type, from_spec, to_spec, properties = item

                from_type, from_id = from_spec.split(":")
                to_type, to_id = to_spec.split(":")

                from_vertex = from_lookups.get((from_type, from_id))
                to_vertex = to_lookups.get((to_type, to_id))

                if from_vertex and to_vertex:
                    # Use Java API to create edge with properties
                    if properties:
                        # Convert properties dict to alternating key-value pairs
                        prop_list = []
                        for key, value in properties.items():
                            prop_list.extend([key, value])
                        edge = from_vertex.newEdge(edge_type, to_vertex, *prop_list)
                    else:
                        edge = from_vertex.newEdge(edge_type, to_vertex)
                    edge.save()
                    edge_count += 1

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        return (edge_count, query_time, db_time, total_time)

    def _execute_edge_batch_with_rids(self, db, batch):
        """Execute edge creation batch using per-batch vertex caching.

        This follows the pattern from example 05: build a small cache for just
        the vertices needed in this batch, use it, then throw it away.
        No global RID caches = constant memory usage.

        Args:
            db: Database connection
            batch: List of (edge_type, from_spec, to_spec, [properties]) tuples
                   where spec is "VertexType:Id" (e.g., "UserVertex:123")

        Returns:
            Tuple of (edge_count, query_time, db_time, total_time)
        """
        if not batch:
            return (0, 0.0, 0.0, 0.0)

        batch_start = time.time()

        # Build vertex lookup for this batch
        # Collect all unique (type, id) pairs needed
        vertex_lookups = {}  # (type, id) -> None

        for item in batch:
            from_spec = item[1]  # e.g., "UserVertex:123"
            to_spec = item[2]  # e.g., "QuestionVertex:456"

            from_type, from_id = from_spec.split(":")
            to_type, to_id = to_spec.split(":")

            vertex_lookups[(from_type, from_id)] = None
            vertex_lookups[(to_type, to_id)] = None

        # Query vertices and get Java vertex objects
        query_start = time.time()
        vertex_cache = {}  # (type, id) -> Java vertex object

        # Group by type for efficient BULK querying
        by_type = {}
        for vtype, vid in vertex_lookups.keys():
            if vtype not in by_type:
                by_type[vtype] = []
            by_type[vtype].append(vid)

        # Fetch vertex objects using BULK queries
        # Pattern: SELECT FROM VertexType WHERE Id IN [id1, id2, ...]
        for vtype, ids in by_type.items():
            if len(ids) == 1:
                query = f"SELECT FROM {vtype} WHERE Id = {ids[0]}"
            else:
                ids_str = ",".join(ids)
                query = f"SELECT FROM {vtype} WHERE Id IN [{ids_str}]"

            results = list(db.query("sql", query))
            for result in results:
                vid = str(result.get_property("Id"))
                vertex = result._java_result.getElement().get().asVertex()
                vertex_cache[(vtype, vid)] = vertex

        query_time = time.time() - query_start

        # Create edges using Java API (FAST - direct vertex method calls)
        db_start = time.time()
        edge_count = 0
        missing_count = 0

        with db.transaction():
            for item in batch:
                if len(item) == 3:
                    edge_type, from_spec, to_spec = item
                    properties = {}
                else:
                    edge_type, from_spec, to_spec, properties = item

                from_type, from_id = from_spec.split(":")
                to_type, to_id = to_spec.split(":")

                # Get vertex objects from cache
                from_vertex = vertex_cache.get((from_type, from_id))
                to_vertex = vertex_cache.get((to_type, to_id))

                if from_vertex and to_vertex:
                    # Use Java API: vertex.newEdge(type, target, key, val, ...)
                    if properties:
                        # Build property list as alternating key-value pairs
                        prop_list = []
                        for key, value in properties.items():
                            prop_list.extend([key, value])
                        edge = from_vertex.newEdge(edge_type, to_vertex, *prop_list)
                    else:
                        edge = from_vertex.newEdge(edge_type, to_vertex)
                    edge.save()
                    edge_count += 1
                else:
                    missing_count += 1

        db_time = time.time() - db_start
        total_time = time.time() - batch_start

        # Cache is automatically garbage collected when method exits
        # No need for explicit clearing (Python handles this)

        if missing_count > 0:
            print(f"    ⚠️  Warning: {missing_count} edges skipped (missing vertices)")

        return (edge_count, query_time, db_time, total_time)

    def _create_index_with_retry(
        self, db, type_name, property_name, index_type="LSM_TREE", unique=False
    ):
        """Create an index with retry logic for compaction conflicts.

        Args:
            db: Database connection
            type_name: Type name to create index on
            property_name: Property name to index
            index_type: Index type (LSM_TREE, FULL_TEXT, etc.)
            unique: Whether the index should be unique

        Returns:
            Tuple of (success: bool, elapsed_time: float, error_msg: str)
        """
        # Generous retry limits for large datasets
        max_retries = 360  # 18 hours max per index (360 × 180s)
        retry_delay = 180  # Wait 180 seconds (3 mins) between retries

        index_start = time.time()
        retry_time = 0

        for attempt in range(1, max_retries + 1):
            try:
                with db.transaction():
                    if index_type == "FULL_TEXT":
                        db.schema.create_index(
                            type_name, [property_name], index_type=index_type
                        )
                    else:
                        db.schema.create_index(
                            type_name,
                            [property_name],
                            unique=unique,
                            index_type=index_type,
                        )
                total_time = time.time() - index_start
                return (True, total_time, None)

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
                            f"      ⏳ Waiting for {reason} "
                            f"(attempt {attempt}/{max_retries}, "
                            f"{elapsed}s elapsed)..."
                        )
                        time.sleep(retry_delay)
                        retry_time += retry_delay
                    else:
                        total_time = time.time() - index_start
                        return (False, total_time, error_msg)
                else:
                    # Non-retryable error
                    total_time = time.time() - index_start
                    return (False, total_time, error_msg)

        # Should never reach here
        total_time = time.time() - index_start
        return (False, total_time, "Max retries exceeded")

    def _create_so_vector_indexes(self, db):
        """Create HNSW vector indexes for Stack Overflow schema.

        Returns:
            Tuple of (elapsed_time, indexes_dict)
        """
        step_start = time.time()

        print("\n" + "=" * 80)
        print("STEP 4: Creating HNSW Vector Indexes")
        print("=" * 80)

        vertex_types = [
            "UserVertex",
            "QuestionVertex",
            "AnswerVertex",
            "CommentVertex",
            "PostHistoryVertex",
        ]
        indexes = {}

        for vertex_type in vertex_types:
            print(f"\n  Creating HNSW index for {vertex_type}.embedding")

            # Count total vertices (max_items = total, not just with embeddings)
            query = f"SELECT count(*) as count FROM {vertex_type}"
            result = list(db.query("sql", query))
            total_vertices = result[0].get_property("count") if result else 0

            if total_vertices == 0:
                print("    ⚠️  No vertices found")
                continue

            # Count vertices with embeddings
            query = f"SELECT FROM {vertex_type} WHERE embedding IS NOT NULL"
            result_list = list(db.query("sql", query))
            num_with_embeddings = len(result_list)

            if num_with_embeddings == 0:
                print("    ⚠️  No vertices with embeddings found")
                continue

            print(
                f"    max_items={total_vertices:,} (total vertices), "
                f"{num_with_embeddings:,} with embeddings"
            )
            print("    metric=cosine, m=16, ef=128")

            start_time = time.time()

            # Create index using db.create_vector_index()
            with db.transaction():
                index = db.create_vector_index(
                    vertex_type=vertex_type,
                    vector_property="embedding",
                    dimensions=384,
                    max_items=total_vertices,
                    id_property="vector_id",
                    edge_type=f"{vertex_type}_proximity",
                    distance_function="cosine",
                    m=16,
                    ef=128,
                    ef_construction=128,
                )

            # Populate index with vertices that have embeddings IN BATCHES
            # (adding all vertices in one transaction causes hangs for large datasets)
            total_indexed = 0
            batch_times = []  # (count, db_time, total_time)

            for i in range(0, len(result_list), self.batch_size):
                batch = result_list[i : i + self.batch_size]
                batch_start = time.time()

                with db.transaction():
                    for record in batch:
                        java_vertex = record._java_result.getElement().get().asVertex()
                        index.add_vertex(java_vertex)

                batch_time = time.time() - batch_start
                count = len(batch)
                total_indexed += count
                batch_times.append((count, batch_time, batch_time))

                # Print per-batch stats
                self._print_batch_stats(
                    count,
                    db_time=batch_time,
                    total_time=batch_time,
                    item_name="vectors",
                )

            # Explicitly save the index configuration (including entryPoint)
            try:
                index._java_index.save()
                print("    ✓ Index configuration saved")
            except Exception as save_err:
                print(f"    ⚠️  Error saving index: {save_err}")

            elapsed = time.time() - start_time

            # Print summary stats
            self._print_summary_stats(
                total_indexed,
                elapsed,
                batch_times,
                item_name="vectors",
                has_embed=False,
            )

            # Store index for demo queries
            indexes[vertex_type] = index

        elapsed = time.time() - step_start
        print(f"\n  ✓ Step 4 completed in {elapsed:.1f}s")
        return elapsed, indexes

    def _retrieve_vector_indexes(self, db):
        """Retrieve existing HNSW vector indexes from database.

        Vector indexes ARE persistent in ArcadeDB. This method retrieves
        them using db.schema.getIndexByName().

        Returns:
            Dictionary of {vertex_type: VectorIndex}
        """
        vertex_types = [
            "UserVertex",
            "QuestionVertex",
            "AnswerVertex",
            "CommentVertex",
            "PostHistoryVertex",
        ]
        indexes = {}

        print("\n  Retrieving persisted vector indexes...")

        for vertex_type in vertex_types:
            try:
                # Vector index name format: {vertexType}[{idProperty},{vectorProperty}]
                index_name = f"{vertex_type}[vector_id,embedding]"

                # Get the index from schema
                java_index = db._java_db.getSchema().getIndexByName(index_name)

                if java_index is not None:
                    # Wrap in Python VectorIndex object
                    from arcadedb_embedded.vector import VectorIndex

                    index = VectorIndex(java_index, db)
                    indexes[vertex_type] = index

                    # Get count of indexed items
                    query = (
                        f"SELECT count(*) as count FROM {vertex_type} "
                        f"WHERE embedding IS NOT NULL"
                    )
                    result = list(db.query("sql", query))
                    count = result[0].get_property("count") if result else 0

                    print(f"    ✓ {vertex_type}: {count:,} vectors indexed")

            except Exception:
                # Index doesn't exist for this vertex type
                pass

        return indexes

    def run_demo_queries(self, db, vector_indexes=None):
        """Run interesting demo queries showcasing SQL, Gremlin, and vector search.

        Args:
            db: Database instance
            vector_indexes: Dictionary of {vertex_type: VectorIndex} from Step 4
        """
        print("\n" + "=" * 80)
        print("DEMO QUERIES: Exploring the Stack Overflow Graph")
        print("=" * 80)

        # ===================================================================
        # SQL Queries
        # ===================================================================
        print("\n" + "─" * 80)
        print("📊 SQL QUERIES")
        print("─" * 80)

        # Query 1: Top users by reputation
        print("\n1️⃣  Top 10 Users by Reputation:")
        print("   SQL: SELECT DisplayName, Reputation, Location FROM UserVertex")
        print("        WHERE Reputation IS NOT NULL ORDER BY Reputation DESC LIMIT 10")
        try:
            start = time.time()
            results = list(
                db.query(
                    "sql",
                    "SELECT DisplayName, Reputation, Location FROM UserVertex "
                    "WHERE Reputation IS NOT NULL ORDER BY Reputation DESC LIMIT 10",
                )
            )
            elapsed = time.time() - start
            for i, user in enumerate(results, 1):
                name = user.get_property("DisplayName") or "Anonymous"
                rep = user.get_property("Reputation")
                loc = user.get_property("Location") or "Unknown"
                print(f"   {i:2d}. {name:30s} | Rep: {rep:>8,} | {loc}")
            print(f"   ⏱️  Query time: {elapsed:.3f}s")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Query 2: Most viewed questions
        print("\n2️⃣  Top 5 Most Viewed Questions:")
        print("   SQL: SELECT Title, ViewCount, Score FROM QuestionVertex")
        print("        ORDER BY ViewCount DESC LIMIT 5")
        try:
            start = time.time()
            results = list(
                db.query(
                    "sql",
                    "SELECT Title, ViewCount, Score FROM QuestionVertex "
                    "ORDER BY ViewCount DESC LIMIT 5",
                )
            )
            elapsed = time.time() - start
            for i, q in enumerate(results, 1):
                title = q.get_property("Title") or "No title"
                views = q.get_property("ViewCount") or 0
                score = q.get_property("Score") or 0
                # Truncate title
                if len(title) > 60:
                    title = title[:57] + "..."
                print(f"   {i}. {title}")
                print(f"      Views: {views:>6,} | Score: {score:>4}")
            print(f"   ⏱️  Query time: {elapsed:.3f}s")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Query 3: Database statistics
        print("\n3️⃣  Database Statistics:")
        print("   SQL: SELECT count(*) as count FROM <VertexType>")
        try:
            start = time.time()
            vertex_types = [
                "UserVertex",
                "QuestionVertex",
                "AnswerVertex",
                "CommentVertex",
                "BadgeVertex",
                "PostHistoryVertex",
                "TagVertex",
            ]
            for vtype in vertex_types:
                result = list(db.query("sql", f"SELECT count(*) as count FROM {vtype}"))
                count = result[0].get_property("count") if result else 0
                print(f"   {vtype:20s}: {count:>8,}")
            elapsed = time.time() - start
            print(f"   ⏱️  Query time: {elapsed:.3f}s")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Query 4: Questions with most answers
        print("\n4️⃣  Questions with Most Answers (via edge count):")
        print("   SQL: SELECT Title, AnswerCount FROM QuestionVertex")
        print("        ORDER BY AnswerCount DESC LIMIT 5")
        try:
            start = time.time()
            results = list(
                db.query(
                    "sql",
                    "SELECT Title, AnswerCount FROM QuestionVertex "
                    "WHERE AnswerCount IS NOT NULL "
                    "ORDER BY AnswerCount DESC LIMIT 5",
                )
            )
            elapsed = time.time() - start
            for i, q in enumerate(results, 1):
                title = q.get_property("Title") or "No title"
                ans_count = q.get_property("AnswerCount") or 0
                if len(title) > 70:
                    title = title[:67] + "..."
                print(f"   {i}. {title}")
                print(f"      Answers: {ans_count}")
            print(f"   ⏱️  Query time: {elapsed:.3f}s")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # ===================================================================
        # Gremlin Queries
        # ===================================================================
        print("\n" + "─" * 80)
        print("🔗 GREMLIN QUERIES (Graph Traversals)")
        print("─" * 80)

        # Query 5: User activity - questions + answers (using Gremlin)
        print("\n5️⃣  Most Active Users (by outgoing ASKED + ANSWERED edges):")
        print("   Gremlin: g.V().hasLabel('UserVertex').order()")
        print("            .by(outE('ASKED','ANSWERED').count(), desc).limit(10)")
        try:
            start = time.time()
            # Use Gremlin traversal to count outgoing edges
            result = db.query(
                "gremlin",
                """
                g.V().hasLabel('UserVertex')
                 .project('name', 'activity')
                   .by('DisplayName')
                   .by(outE('ASKED', 'ANSWERED').count())
                 .order().by(select('activity'), desc)
                 .limit(10)
                """,
            )
            results = list(result)
            elapsed = time.time() - start
            for i, user in enumerate(results, 1):
                name = user.get_property("name") or "Anonymous"
                activity = user.get_property("activity") or 0
                print(f"   {i:2d}. {name:30s} | Posts: {activity:>4}")
            print(f"   ⏱️  Query time: {elapsed:.3f}s")
        except Exception as e:
            print(f"   ⚠️  Graph traversal: {e}")
            print("      (Gremlin may not be fully supported)")

        # Query 6: Path traversal - user -> question -> answer
        print("\n6️⃣  Sample Path: User -> ASKED -> Question -> ANSWERS -> Answer:")
        print("   Traversal: Find a user who asked a question that has answers")
        try:
            start = time.time()
            # Find a question with answers
            results = list(
                db.query(
                    "sql",
                    "SELECT Id, Title FROM QuestionVertex "
                    "WHERE AnswerCount > 0 LIMIT 1",
                )
            )
            elapsed = time.time() - start
            if results:
                q_id = results[0].get_property("Id")
                q_title = results[0].get_property("Title") or "No title"
                if len(q_title) > 60:
                    q_title = q_title[:57] + "..."
                print(f"   Question (Id={q_id}): {q_title}")

                # Find the user who asked it
                user_results = list(
                    db.query(
                        "sql",
                        f"SELECT DisplayName FROM UserVertex "
                        f"WHERE Id IN (SELECT OwnerUserId FROM "
                        f"QuestionVertex WHERE Id = {q_id})",
                    )
                )
                if user_results:
                    user_name = (
                        user_results[0].get_property("DisplayName") or "Anonymous"
                    )
                    print(f"   Asked by: {user_name}")

                # Find answers to this question
                answer_results = list(
                    db.query(
                        "sql",
                        f"SELECT Id, Score FROM AnswerVertex "
                        f"WHERE ParentId = {q_id} LIMIT 3",
                    )
                )
                if answer_results:
                    print(f"   Answers ({len(answer_results)}):")
                    for ans in answer_results:
                        ans_id = ans.get_property("Id")
                        ans_score = ans.get_property("Score") or 0
                        print(f"      - Answer Id={ans_id}, Score={ans_score}")
            print(f"   ⏱️  Query time: {elapsed:.3f}s")
        except Exception as e:
            print(f"   ⚠️  Traversal error: {e}")

        # ===================================================================
        # Vector Search Queries
        # ===================================================================
        print("\n" + "─" * 80)
        print("🔍 VECTOR SEARCH QUERIES (Semantic Similarity)")
        print("─" * 80)

        # Query 7: Similar users by AboutMe text
        print("\n7️⃣  Finding Similar Users (by AboutMe embedding):")
        print("   Vector Search: Find users with similar 'About Me' descriptions")

        if not vector_indexes or "UserVertex" not in vector_indexes:
            print("   ⚠️  UserVertex index not available")
        else:
            try:
                user_index = vector_indexes["UserVertex"]

                start = time.time()
                # Get a user with an AboutMe and embedding
                sample_user = list(
                    db.query(
                        "sql",
                        "SELECT Id, DisplayName, AboutMe, embedding FROM UserVertex "
                        "WHERE AboutMe IS NOT NULL "
                        "AND embedding IS NOT NULL LIMIT 1",
                    )
                )

                if sample_user:
                    user = sample_user[0]
                    user_name = user.get_property("DisplayName") or "Anonymous"
                    user_id = user.get_property("Id")
                    about = user.get_property("AboutMe") or ""
                    embedding = user.get_property("embedding")

                    # Truncate AboutMe for display
                    if len(about) > 150:
                        about_display = about[:147] + "..."
                    else:
                        about_display = about

                    print(f"   Reference User: {user_name}")
                    print(f"   About: {about_display}")

                    # Convert Java array to numpy for search
                    import numpy as np

                    embedding_array = np.array(embedding, dtype=np.float32)

                    # Vector search using index.find_nearest()
                    try:
                        similar_results = user_index.find_nearest(embedding_array, k=6)

                        # Filter out the query user
                        similar = [
                            (vertex, distance)
                            for vertex, distance in similar_results
                            if vertex.get("Id") != user_id
                        ][:5]

                        elapsed = time.time() - start

                        if similar:
                            print("   Similar users:")
                            for i, (vertex, distance) in enumerate(similar, 1):
                                name_val = vertex.get("DisplayName") or "Anonymous"
                                similar_name = str(name_val)
                                loc_val = vertex.get("Location") or "Unknown"
                                similar_loc = str(loc_val)
                                print(
                                    f"      {i}. {similar_name:30s} | "
                                    f"{similar_loc} (dist: {distance:.4f})"
                                )
                            print(f"   ⏱️  Query time: {elapsed:.3f}s")
                        else:
                            print("   No similar users found")
                    except Exception as ve:
                        print(f"   ⚠️  Vector search error: {ve}")
                else:
                    print("   ⚠️  No users with AboutMe and embedding found")
            except Exception as e:
                print(f"   ❌ Error: {e}")

        # Query 8: Similar questions
        print("\n8️⃣  Finding Similar Questions (by Title+Body embedding):")
        print("   Vector Search: Find questions with similar content")

        if not vector_indexes or "QuestionVertex" not in vector_indexes:
            print("   ⚠️  QuestionVertex index not available")
        else:
            try:
                question_index = vector_indexes["QuestionVertex"]

                start = time.time()
                # Get a high-score question with embedding
                sample_q = list(
                    db.query(
                        "sql",
                        "SELECT Id, Title, Score, ViewCount, embedding FROM QuestionVertex "
                        "WHERE Score > 5 AND embedding IS NOT NULL "
                        "ORDER BY Score DESC LIMIT 1",
                    )
                )

                if sample_q:
                    q = sample_q[0]
                    q_id = q.get_property("Id")
                    q_title = q.get_property("Title") or "No title"
                    q_score = q.get_property("Score") or 0
                    q_views = q.get_property("ViewCount") or 0
                    embedding = q.get_property("embedding")

                    if len(q_title) > 80:
                        q_title_display = q_title[:77] + "..."
                    else:
                        q_title_display = q_title

                    print("   Reference Question:")
                    print(f"   Title: {q_title_display}")
                    print(f"   Score: {q_score} | Views: {q_views:,}")

                    # Convert Java array to numpy for search
                    import numpy as np

                    embedding_array = np.array(embedding, dtype=np.float32)

                    # Vector search using index.find_nearest()
                    try:
                        similar_results = question_index.find_nearest(
                            embedding_array, k=6
                        )

                        # Filter out the query question
                        similar = [
                            (vertex, distance)
                            for vertex, distance in similar_results
                            if vertex.get("Id") != q_id
                        ][:5]

                        elapsed = time.time() - start

                        if similar:
                            print("   Similar questions:")
                            for i, (vertex, distance) in enumerate(similar, 1):
                                title_val = vertex.get("Title") or "No title"
                                similar_title = str(title_val)
                                similar_score = vertex.get("Score") or 0

                                if len(similar_title) > 60:
                                    similar_title = similar_title[:57] + "..."

                                print(
                                    f"      {i}. Score: {similar_score:>3} | "
                                    f"{similar_title} (dist: {distance:.4f})"
                                )
                            print(f"   ⏱️  Query time: {elapsed:.3f}s")
                        else:
                            print("   No similar questions found")
                    except Exception as ve:
                        print(f"   ⚠️  Vector search error: {ve}")
                else:
                    print("   ⚠️  No questions with high score and embedding found")
            except Exception as e:
                print(f"   ❌ Error: {e}")

        print("\n" + "=" * 80)
        print("✓ Demo queries completed!")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Automated graph schema inference from data files"
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
        help="Dataset to use",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze files and show inferred schema (dry-run)",
    )
    parser.add_argument(
        "--import",
        action="store_true",
        dest="do_import",
        help="Execute import with inferred schema",
    )
    parser.add_argument(
        "--query",
        action="store_true",
        help="Run demo queries on existing database",
    )
    parser.add_argument(
        "--analysis-limit",
        type=int,
        default=1_000_000,
        help="Max rows to analyze per file (default: 1 million)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Database path (default: ./my_test_databases/{dataset}_db)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Batch size for vertex and edge creation (default: 5000)",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=512,
        help="Batch size for embedding generation (default: 512)",
    )

    args = parser.parse_args()

    db_path = args.db_path or f"./my_test_databases/{args.dataset}_db"
    builder = StackOverflowGraphBuilder(
        args.dataset,
        db_path,
        batch_size=args.batch_size,
        embedding_batch_size=args.embedding_batch_size,
    )

    if args.analyze:
        plan = builder.analyze(analysis_limit=args.analysis_limit)
    elif args.do_import:
        plan = builder.analyze(analysis_limit=args.analysis_limit)
        builder.execute_import(plan)
    elif args.query:
        # Run queries on existing database
        if not Path(db_path).exists():
            print(f"❌ Database not found: {db_path}")
            print("   Please run with --import first to create the database")
            return

        print(f"Opening existing database: {db_path}")
        with arcadedb.open_database(db_path) as db:
            # Retrieve existing vector indexes
            vector_indexes = builder._retrieve_vector_indexes(db)
            if vector_indexes:
                print(f"✓ Retrieved {len(vector_indexes)} vector indexes")
            builder.run_demo_queries(db, vector_indexes)
    else:
        print("Please specify --analyze, --import, or --query")
        parser.print_help()


if __name__ == "__main__":
    main()
