"""Record wrappers for the native backend: ``Document``, ``Vertex`` and ``Edge`` as Python objects over SQL statements.

The JPype wrappers hold a Java record; here a record is its type, its RID (``None`` until saved) and its properties as a
dict, and every write is one DSL statement (``CREATE VERTEX .. CONTENT``, ``INSERT .. CONTENT``, ``UPDATE .. MERGE``,
``DELETE``, ``CREATE EDGE``). They subclass the JPype wrapper classes so ``isinstance`` checks keep their meaning.
"""

from typing import Any, Dict, List, Optional

from ..exceptions import ArcadeDBError
from ..graph import Document as _BaseDocument
from ..graph import Edge as _BaseEdge
from ..graph import Vertex as _BaseVertex
from . import not_yet
from .codec import RID


def _java_object():
    from .database import _JavaObject

    return _JavaObject()


_UNSAVED = "#-1:-1"


def _q(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


class _Mixin:
    """What the three native wrappers share (state in ``_db``, ``_type``, ``_rid``, ``_props``, ``_mutable``)."""

    _CREATE = "INSERT INTO {t} CONTENT :row"
    # the record id goes over as a parameter (a RID, passed back it is a link), never in the text: the engine caches a parsed statement by its
    # text and keeps a record id in a FROM target as part of it, so a pasted id would make one cache entry per record
    _UPDATE = "UPDATE :rid MERGE :row"
    _DELETE = "DELETE FROM :rid"

    def __init__(self, database, type_name, rid=None, props=None, mutable=False):
        self._java_document = _java_object()
        self._database = database
        self._db = database
        self._type = type_name
        self._rid = rid or None
        self._props: Dict[str, Any] = dict(props or {})
        self._mutable = mutable or not rid
        self._property_names_cache = None

    # -- reading

    def _check_open(self) -> None:
        database = self._database
        if database is not None and database._closed and self._rid:
            raise ArcadeDBError(
                "Database is closed: a record cannot be read after its database was closed. "
                "Read what you need before closing it."
            )

    def get(self, name: str, convert_types: bool = True) -> Any:
        self._check_open()
        return self._props.get(name)

    def get_raw(self, name: str) -> Any:
        return self.get(name)

    def has_property(self, name: str) -> bool:
        self._check_open()
        return name in self._props

    def get_property_names(self) -> List[str]:
        self._check_open()
        return list(self._props)

    def to_dict(self, convert_types: bool = True) -> Dict[str, Any]:
        self._check_open()
        return dict(self._props)

    def get_rid(self) -> str:
        return self._rid or _UNSAVED

    def get_identity(self):
        return RID(self.get_rid())

    def get_type_name(self) -> str:
        self._check_open()
        return self._type

    def get_java_document(self):
        not_yet("get_java_document")

    # -- writing

    def set(self, name: str, value: Any):
        if not self._mutable:
            raise AttributeError(
                f"{type(self).__name__} is immutable. Call .modify() first to get a mutable version."
            )
        self._props[name] = value
        return self

    def save(self):
        db = self._db
        if self._rid is None:
            row = db.command(
                "sql", self._CREATE.format(t=_q(self._type)), {"row": self._props}
            ).first()
            self._adopt(row)
        else:
            db.command(
                "sql", self._UPDATE, {"rid": RID(self._rid), "row": self._props}
            ).close()
        return self

    def _adopt(self, row) -> None:
        if row is None or not row.get_rid():
            raise ArcadeDBError(
                f"Failed to save a {self._type} record: the statement returned no record"
            )
        self._rid = row.get_rid()
        self._props = row.to_dict()

    def delete(self):
        if self._rid is None:
            raise ArcadeDBError("Cannot delete a record that was never saved")
        self._db.command("sql", self._DELETE, {"rid": RID(self._rid)}).close()

    def modify(self):
        self._check_open()
        return type(self)(self._db, self._type, self._rid, self._props, mutable=True)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} rid={self.get_rid()} type={self._type}>"


class Document(_Mixin, _BaseDocument):
    pass


class Vertex(_Mixin, _BaseVertex):
    _CREATE = "CREATE VERTEX {t} CONTENT :row"

    def new_edge(self, label: str, target: "Vertex", **kwargs) -> "Edge":
        self._check_open()
        if self._rid is None or getattr(target, "_rid", None) is None:
            raise ArcadeDBError(
                "Both vertices of an edge must be saved before new_edge()"
            )
        sql = f"CREATE EDGE {_q(label)} FROM :src TO :dst"
        params = {"src": RID(self._rid), "dst": RID(target._rid)}
        if kwargs:
            sql += " CONTENT :row"
            params["row"] = kwargs
        row = self._db.command("sql", sql, params).first()
        edge = Edge(self._db, label, mutable=False)
        edge._adopt(row)
        return edge

    def _edges(self, fn: str, labels) -> List["Edge"]:
        self._check_open()
        args = ", ".join("'" + label.replace("'", "\\'") + "'" for label in labels)
        edges_sql = f"SELECT expand({fn}({args})) FROM :rid"  # nosec B608 - fn is a fixed function name, labels are escaped literals, the record id is a parameter
        rows = self._db.query("sql", edges_sql, {"rid": RID(self._rid)})
        return [_wrap(self._db, row) for row in rows]

    def get_out_edges(self, *labels: str) -> List["Edge"]:
        return self._edges("outE", labels)

    def get_in_edges(self, *labels: str) -> List["Edge"]:
        return self._edges("inE", labels)

    def get_both_edges(self, *labels: str) -> List["Edge"]:
        return self._edges("bothE", labels)


class Edge(_Mixin, _BaseEdge):

    def _end(self, fn: str) -> "Vertex":
        self._check_open()
        end_sql = f"SELECT expand({fn}()) FROM :rid"  # nosec B608 - fn is a fixed function name, the record id is a parameter
        row = self._db.query("sql", end_sql, {"rid": RID(self._rid)}).first()
        return _wrap(self._db, row)

    def get_in(self) -> Vertex:
        return self._end("inV")

    def get_out(self) -> Vertex:
        return self._end("outV")


def _wrap(database, row):
    """The wrapper for a result row that is a record (vertex, edge or document); None for a projection."""
    meta = row._meta
    if not meta:
        return None
    rid, type_name, kind = meta
    cls = {"v": Vertex, "e": Edge}.get(kind, Document)
    return cls(database, type_name, rid, row._props)


def _wrap_dict(database, record: dict, kind: str = "d"):
    """The wrapper for a nested record the engine sent as a dict with ``@rid``, ``@type`` and ``@cat`` members."""
    props = dict(record)
    rid = props.pop("@rid", None)
    type_name = props.pop("@type", None)
    kind = props.pop("@cat", kind)
    cls = {"v": Vertex, "e": Edge}.get(kind, Document)
    return cls(database, type_name, rid, props)
