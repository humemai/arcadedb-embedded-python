"""What the JPype ``Schema`` returns as Java objects, rebuilt from ``schema:types`` and ``schema:indexes`` rows for the native
backend: types and indexes with the engine's camelCase accessors (``getName``, ``existsProperty``, ``getTypeName``, ...) and the
vector index wrapper over ``vectorNeighbors``. Read-only views: DDL stays SQL statements.
"""

import json
import re

from ..exceptions import ArcadeDBError
from ..vector import VectorIndex as _BaseVectorIndex
from . import not_yet
from .codec import _np

_PROPERTY = re.compile(r"name: (.+?), type: ([A-Z_]+)")


class NativeType:
    """A type as a ``schema:types`` row."""

    def __init__(self, row: dict):
        self._row = row

    def getName(self) -> str:
        return self._row["name"]

    def getType(self) -> str:
        return self._row.get("type")

    def getPropertyNames(self):
        return [
            m.group(1)
            for m in map(_PROPERTY.search, self._row.get("properties") or [])
            if m
        ]

    def existsProperty(self, name: str) -> bool:
        return name in self.getPropertyNames()

    def getParentTypes(self):
        return list(self._row.get("parentTypes") or [])

    getSuperTypes = getParentTypes

    def getBuckets(self):
        return list(self._row.get("buckets") or [])

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        not_yet(f"the Java object a Schema method returns ({name})")

    def __repr__(self):
        return f"<Type {self.getName()}>"


class NativeIndex:
    """An index as a ``schema:indexes`` row."""

    def __init__(self, row: dict):
        self._row = row

    def getName(self) -> str:
        return self._row["name"]

    def getTypeName(self) -> str:
        return self._row.get("typeName")

    def getPropertyNames(self):
        props = self._row.get("properties") or []
        return list(props[0]) if props and isinstance(props[0], list) else list(props)

    def isUnique(self) -> bool:
        return bool(self._row.get("unique"))

    def getType(self) -> str:
        return self._row.get("indexType")

    def isAutomatic(self) -> bool:
        return bool(self._row.get("automatic"))

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        not_yet(f"the Java object a Schema method returns ({name})")

    def __repr__(self):
        return f"<Index {self.getName()}>"


class _IndexShim:
    """The few LSMVectorIndex methods the shared ``VectorIndex`` code calls, over statements."""

    def __init__(self, database, type_name, prop, name):
        self._db, self._type, self._prop, self._name = database, type_name, prop, name

    def getName(self):
        return self._name

    def getTypeName(self):
        return self._type

    def getPropertyNames(self):
        return [self._prop]

    def getMetadata(self):
        """Just what the PRODUCT-readiness check reads: the session's quantization and pq_clusters (engine default 256)."""
        from types import SimpleNamespace

        meta = self._db._vector_meta.get((self._type, self._prop), {})
        return SimpleNamespace(
            quantizationType=str(meta.get("quantization") or "NONE"),
            pqClusters=int(meta.get("pqClusters", 256)),
        )

    def getIdPropertyName(self):
        return self._db._vector_id_properties.get((self._type, self._prop), "id")

    def countEntries(self):
        count_sql = f"SELECT count(*) AS c FROM `{self._type}` WHERE `{self._prop}` IS NOT NULL"  # nosec B608 - backtick-quoted schema identifiers, no values
        row = self._db.query("sql", count_sql).first()
        return int(row.get("c"))

    def warmUp(self):
        return None

    def buildVectorGraphNow(self):
        # the engine builds the graph on the first search: one search now, on a vector of the index's dimension
        dims = self._db._vector_dimensions.get((self._type, self._prop))
        if dims:
            self._db.query(
                "sql", "SELECT vectorNeighbors(?, ?, 1)", self._name, [0.0] * dims
            ).close()


def _rid_text(value) -> str:
    get_rid = getattr(value, "get_rid", None)
    return get_rid() if get_rid is not None else str(value)


def _query_vector_param(query_vector):
    """The query vector as the one parameter the library takes it in.

    A numeric 1-d vector (an ndarray, or a list/tuple of numbers: numpy walks a list in C) becomes a float32 array, which
    ``encode_params`` sends through the binary float32 side buffer: no ``_prep`` call and no float repr per element. The engine reads
    the vector as float32 whatever it is given, so the rounding is the same. Anything else (text or None entries, a generator,
    numpy missing) stays a list and reaches the engine as it was given; numpy would turn a None into nan.
    """
    if _np is not None:
        try:
            arr = _np.asarray(query_vector)
        except (
            Exception
        ):  # nosec B110 - ragged or unconvertible input: the list path below reports it
            arr = None
        if arr is not None and arr.ndim == 1 and arr.dtype.kind in "fiu":
            return arr.astype(_np.float32, copy=False)
    return (
        query_vector.tolist() if hasattr(query_vector, "tolist") else list(query_vector)
    )


class NativeVectorIndex(_BaseVectorIndex):
    """``VectorIndex`` over ``vectorNeighbors``: ``find_nearest`` returns ``[(record, distance)]`` like the JPype wrapper."""

    def __init__(self, database, type_name, prop, name=None):
        shim = _IndexShim(database, type_name, prop, name or f"{type_name}[{prop}]")
        super().__init__(shim, database)
        self._shim = shim

    def _resolve_lsm_indexes(self):
        return [self._shim]

    def _run_search(
        self, *, query_vector, k, allowed_rids, approximate, ef_search=None
    ):
        if approximate:
            not_yet("VectorIndex.find_nearest_approximate over PRODUCT quantization")
        from .records import _wrap_dict

        vector = _query_vector_param(query_vector)
        # the statement's own options: efSearch, and filter (the RIDs the search may return), as the JPype path passes them
        options = {}
        if ef_search is not None:
            options["efSearch"] = int(ef_search)
        if allowed_rids:
            options["filter"] = [_rid_text(r) for r in allowed_rids]
        if options:
            rows = self._database.query(
                "sql",
                "SELECT expand(vectorNeighbors(?, ?, ?, ?))",
                self._shim._name,
                vector,
                int(k),
                options,
            )
        else:
            rows = self._database.query(
                "sql",
                "SELECT expand(vectorNeighbors(?, ?, ?))",
                self._shim._name,
                vector,
                int(k),
            )
        out = []
        for row in rows:
            nested = row.get("record")
            record = (
                None
                if nested is None
                else _wrap_dict(
                    self._database, nested, self._database._kind_of(nested.get("@type"))
                )
            )
            out.append((record, float(row.get("distance"))))
        return self._sort_results(out)[:k]

    def find_nearest_approximate(self, query_vector, k=10, allowed_rids=None):
        """PQ approximate search needs PRODUCT quantization; the search itself has no statement form (not on native yet)."""
        if self.get_quantization() != "PRODUCT":
            raise ArcadeDBError("Approximate search requires quantization=PRODUCT (PQ)")
        not_yet("VectorIndex.find_nearest_approximate over PRODUCT quantization")

    def _lookup_query_vector_by_key(self, key):
        type_name, prop = self._shim._type, self._shim._prop
        id_prop = self._shim.getIdPropertyName()
        lookup_sql = f"SELECT `{prop}` AS `query_vector` FROM `{type_name}` WHERE `{id_prop}` = ? LIMIT 1"  # nosec B608 - backtick-quoted schema identifiers; the key goes through the ? parameter
        row = self._database.query("sql", lookup_sql, key).first()
        if row is None:
            raise ArcadeDBError(
                f"No record found in type '{type_name}' where {id_prop} = {key!r}"
            )
        if row.get("query_vector") is None:
            raise ArcadeDBError(
                f"Record found for {id_prop} = {key!r} but property '{prop}' is null"
            )
        return row.get("query_vector")

    def get_stats(self):
        not_yet("VectorIndex.get_stats")

    def get_metadata(self):
        """The configuration this session created the index with (no engine-chosen values: the image has no accessor for them)."""
        meta = self._database._vector_meta.get((self._shim._type, self._shim._prop))
        if meta is None:
            not_yet("VectorIndex.get_metadata of an index this session did not create")
        names = {
            "dimensions": "dimensions",
            "similarity": "similarity_function",
            "idPropertyName": "id_property",
            "quantization": "quantization",
            "maxConnections": "max_connections",
            "beamWidth": "beam_width",
            "graphBuildCacheSize": "graph_build_cache_size",
            "mutationsBeforeRebuild": "mutations_before_rebuild",
            "storeVectorsInGraph": "store_vectors_in_graph",
            "addHierarchy": "add_hierarchy",
            "pqSubspaces": "pq_subspaces",
            "pqClusters": "pq_clusters",
            "pqCenterGlobally": "pq_center_globally",
            "pqTrainingLimit": "pq_training_limit",
        }
        buckets = [
            r["name"]
            for r in self._database.query(
                "sql", "SELECT FROM schema:indexes WHERE indexType = 'LSM_VECTOR'"
            ).to_list()
            if r["typeName"] == self._shim._type
            and r["properties"] == [[self._shim._prop]]
            and "fileId" in r
        ]
        out = {
            "index_name": self._shim._name,
            "bucket_index_name": buckets[0] if buckets else None,
            "type_name": self._shim._type,
            "vector_property": self._shim._prop,
        }
        out.update({names[k]: v for k, v in meta.items() if k in names})
        if "similarity_function" in out:
            out["similarity_function"] = str(out["similarity_function"]).upper()
        if "quantization" in out:
            out["quantization"] = str(out["quantization"]).upper()
        return out

    def get_quantization(self):
        meta = self._database._vector_meta.get((self._shim._type, self._shim._prop))
        if meta is None:
            not_yet(
                "VectorIndex.get_quantization of an index this session did not create"
            )
        return str(meta.get("quantization") or "NONE")


def _check_vector_arguments(
    quantization,
    encoding,
    pq_subspaces,
    pq_clusters,
    pq_center_globally,
    pq_training_limit,
):
    if any(
        v is not None
        for v in (pq_subspaces, pq_clusters, pq_center_globally, pq_training_limit)
    ):
        if not quantization or quantization.upper() != "PRODUCT":
            raise ValueError("PQ parameters require quantization='PRODUCT'")
    if (
        encoding
        and encoding.upper() == "INT8"
        and quantization
        and quantization.upper() == "INT8"
    ):
        raise ValueError(
            "encoding='INT8' cannot be combined with quantization='INT8'; use quantization='NONE' for native INT8 storage"
        )


def create_vector_index(
    db,
    vertex_type,
    vector_property,
    dimensions,
    id_property,
    distance_function,
    max_connections,
    beam_width,
    quantization,
    encoding,
    graph_build_cache_size,
    mutations_before_rebuild,
    store_vectors_in_graph,
    add_hierarchy,
    pq_subspaces,
    pq_clusters,
    pq_center_globally,
    pq_training_limit,
    build_graph_now,
):
    """``CREATE INDEX .. LSM_VECTOR METADATA {..}`` with the JPype builder's defaults and checks; returns the wrapper."""
    try:
        _check_vector_arguments(
            quantization,
            encoding,
            pq_subspaces,
            pq_clusters,
            pq_center_globally,
            pq_training_limit,
        )
    except ValueError as e:
        raise ArcadeDBError(f"Failed to create vector index: {e}") from e
    meta = {
        "dimensions": int(dimensions),
        "similarity": distance_function,
        "maxConnections": int(max_connections),
        "beamWidth": int(beam_width),
    }
    if id_property:
        meta["idPropertyName"] = id_property
    if quantization:
        meta["quantization"] = quantization
    if encoding:
        meta["encoding"] = encoding
    for key, value in (
        ("pqSubspaces", pq_subspaces),
        ("pqClusters", pq_clusters),
        ("pqCenterGlobally", pq_center_globally),
        ("pqTrainingLimit", pq_training_limit),
    ):
        if value is not None:
            meta[key] = bool(value) if key == "pqCenterGlobally" else int(value)
    if store_vectors_in_graph:
        meta["storeVectorsInGraph"] = True
    if add_hierarchy is not None:
        meta["addHierarchy"] = bool(add_hierarchy)
    if graph_build_cache_size is not None:
        meta["graphBuildCacheSize"] = int(graph_build_cache_size)
    if mutations_before_rebuild is not None:
        meta["mutationsBeforeRebuild"] = int(mutations_before_rebuild)
    try:
        db.command(
            "sql",
            f"CREATE INDEX ON `{vertex_type}` (`{vector_property}`) LSM_VECTOR METADATA {json.dumps(meta)}",
        ).close()
        key = (vertex_type, vector_property)
        db._vector_meta[key] = meta
        db._vector_dimensions[key] = int(dimensions)
        db._vector_id_properties[key] = id_property or "id"
        index = NativeVectorIndex(db, vertex_type, vector_property)
        if build_graph_now:
            index.build_graph_now()
        return index
    except Exception as e:
        raise ArcadeDBError(f"Failed to create vector index: {e}") from e
