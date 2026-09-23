#!/usr/bin/env python3
"""A Python list must never be what crosses into the JVM.

THE DEFECT THIS EXISTS FOR (BUGS F116, F117, 2026-09-23). Three call sites
handed a Python list where a NumPy array or a Java array was wanted, and every
one of them was correct code that ran, returned right answers, and passed every
gate:

  e2_hybrid.ArcadeE2.build     vecs[i].tolist() -> create_vertices      4.29x
  docs .../test-numpy-support  embedding.tolist() -> vertex.set()      18.40x
  examples/03_vector_search    .tolist() then to_java_float_array()     2.20x

JPype copies a NumPy array across the boundary in one crossing through the
buffer protocol, and marshals a list element by element. The cost is invisible
at review time, scales with the length of the vector, and the fast path
declines it SILENTLY -- `graph_batch._create_vertices_json_bulk` returns None
for any non-scalar value and the caller falls back without a word (F118).

WHY A CHECK AND NOT A SWEEP. The three above were found by grepping for
`.tolist()` on one afternoon. A grep holds until the next call site is written;
this runs every time. It is deliberately narrow: it flags `.tolist()` only
where the result flows into a SINK that crosses into the JVM, so a comparator
adapter calling `.tolist()` on its way to Qdrant, Milvus, Chroma or MongoDB --
which genuinely want Python lists, since they serialise to JSON or protobuf --
is not a finding and is not reported.

Usage:  python jvm_payload_check.py [paths...]     # exit 1 on any finding
"""
import ast
import os
import sys

# Calls whose argument crosses into the JVM. A `.tolist()` reaching one of
# these is always waste: every one of them takes a NumPy array directly.
# Unambiguous: nothing but the bindings defines these names.
SINKS = {
    "to_java_float_array", "to_java_int_array", "to_java_byte_array",
    "create_vertices", "new_edges", "JArray",
}

# AMBIGUOUS BY NAME, so they are matched on their RECEIVER as well. The first
# version of this file flagged six sites and every one was a false positive:
# four were Python's builtin `set(...)`, and two were pymongo's
# `collection.insert_many(...)`, which genuinely wants Python lists because it
# serialises to BSON. `Database.insert_many` and `Collection.insert_many` are
# spelled identically, so the name alone cannot separate them -- the receiver
# can, because the bindings' method hangs off a database handle.
RECEIVER_SINKS = {"insert_many"}
DB_RECEIVERS = {"db", "database", "_db", "jdb"}

# `vertex.set("embedding", value)` -- an ATTRIBUTE call with a string literal
# property name. Requiring both is what keeps `set(x.tolist())`, the builtin,
# out of the results.
SETTERS = {"set"}

DEFAULT_PATHS = (
    "benchmarks/experiments",
    "bindings/python/src",
    "bindings/python/examples",
    "bindings/python/tests",
)


def _call_name(node):
    """The bare name of what is being called, through one layer of attribute
    access and through `JArray(JFloat)(x)`, which is a call on a call."""
    f = node.func
    while isinstance(f, ast.Call):        # JArray(JInt)(payload)
        f = f.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return None


def _tolist_calls(node):
    """Every `<expr>.tolist()` anywhere inside this subtree."""
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "tolist"):
            yield sub


def _receiver_base(node):
    """The last name in the receiver chain: `self.db.insert_many` -> 'db',
    `prod.insert_many` -> 'prod'."""
    f = node.func
    if not isinstance(f, ast.Attribute):
        return None
    recv = f.value
    if isinstance(recv, ast.Attribute):
        return recv.attr
    if isinstance(recv, ast.Name):
        return recv.id
    if isinstance(recv, ast.Call):
        return _call_name(recv)
    return None


def _receiver_is_a_database(node):
    base = _receiver_base(node)
    return base is not None and base.lower() in DB_RECEIVERS


def _is_property_setter(node):
    """`obj.set("name", value)` -- an attribute call whose first argument is a
    string literal. Python's builtin `set(x)` is a Name call with no such
    argument, which is exactly what this excludes."""
    if not isinstance(node.func, ast.Attribute):
        return False
    return (len(node.args) >= 2
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str))


def _scopes(tree):
    """Each function body as its OWN unit, not descending into nested ones.

    Two wrong versions preceded this, and both produced the same false
    positive, so it is worth stating what the trap is: `ast.walk` does not stop
    at a scope boundary. Skipping the nested `FunctionDef` NODE does nothing,
    because walk has already queued its children. Walking from `Module`
    therefore collected every method in the file into one namespace, and `rows`
    -- assigned from a .tolist() in `SurrealE2.build` -- made `ArcadeE2`'s
    unrelated `create_vertices(..., rows)` a hit. Two classes, one obvious
    local name, one bogus finding.

    So the traversal is explicit: descend from a scope's own statements and
    STOP at anything that introduces a new scope, handing that back as a scope
    of its own.
    """
    scopes = [tree]
    while scopes:
        scope = scopes.pop()
        own = []
        # A Lambda's `body` is a single expression, not a list of statements
        # (`lambda x: [i for i in x]` put a ListComp there and this raised).
        body = getattr(scope, "body", [])
        stack = list(body) if isinstance(body, list) else [body]
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Lambda)):
                scopes.append(node)          # its own namespace, seen separately
                continue
            own.append(node)
            for child in ast.iter_child_nodes(node):
                stack.append(child)
        yield scope, own


def _tainted_in(stmts):
    """{name: lineno of the .tolist()} for locals assigned from an expression
    containing one, within a single scope."""
    out = {}
    for stmt in stmts:
        if not isinstance(stmt, ast.Assign) or stmt.value is None:
            continue
        hits = list(_tolist_calls(stmt.value))
        if not hits:
            continue
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                out.setdefault(target.id, hits[0].lineno)
    return out


def _hit_lines(node, tainted):
    """Line numbers to report for this call: every .tolist() inside it, plus
    any argument that merely NAMES a local built from one."""
    lines = {t.lineno for t in _tolist_calls(node)}
    for arg in list(node.args) + [kw.value for kw in node.keywords]:
        for sub in ast.walk(arg):
            if isinstance(sub, ast.Name) and sub.id in tainted:
                lines.add(tainted[sub.id])
    return sorted(lines)


def check_file(path):
    # THE CONVERSION HELPERS THEMSELVES ARE NOT A CALL SITE. `vector.py` is
    # where a list legitimately becomes a Java array -- flagging it is circular,
    # and its one internal `vector.tolist()` feeds a normalisation loop rather
    # than the JVM directly.
    if os.path.basename(path) == "vector.py" and "arcadedb_embedded" in path:
        return []
    try:
        src = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return []
    if ".tolist()" not in src:
        return []
    try:
        tree = ast.parse(src, path)
    except SyntaxError as exc:
        return [(path, exc.lineno or 0, f"does not parse: {exc.msg}")]

    found = set()
    for _scope, stmts in _scopes(tree):
        tainted = _tainted_in(stmts)
        for node in stmts:
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in SINKS:
                why = (f"a .tolist() result reaches {name}(), which takes the "
                       f"NumPy array directly and crosses it in one copy")
            elif name in RECEIVER_SINKS and _receiver_is_a_database(node):
                why = (f"a .tolist() result reaches {name}() on a database handle; "
                       f"pass the NumPy array and it crosses in one copy")
            elif name in SETTERS and _is_property_setter(node):
                for arg in node.args[1:]:
                    if (isinstance(arg, ast.Call)
                            and isinstance(arg.func, ast.Attribute)
                            and arg.func.attr == "tolist"):
                        found.add((path, arg.lineno,
                                   "a .tolist() result is passed to .set(); a Vertex "
                                   "or Document property wants to_java_float_array/"
                                   "to_java_int_array, which take NumPy directly"))
                continue
            else:
                continue
            for ln in _hit_lines(node, tainted):
                found.add((path, ln, why))
    return sorted(found)


def _iter_py(paths):
    for p in paths:
        if os.path.isfile(p) and p.endswith(".py"):
            yield p
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs
                       if d not in {"__pycache__", ".venv", "node_modules", ".git"}]
            for f in files:
                if f.endswith(".py"):
                    yield os.path.join(root, f)


# The check must be able to prove it still SEES the defects it exists for. A
# checker that silently stops matching looks exactly like a clean tree, and
# this one has already been wrong twice -- it missed F116 itself (the .tolist()
# was bound to a local one statement before the sink), then flagged an
# unrelated SurrealDB arm (module-wide name scoping). Both are in here.
_MUST_FLAG = '''
def f116(b, vecs):                                   # e2_hybrid, pre-fix
    rows = [{"pid": i, "embedding": vecs[i].tolist()} for i in range(len(vecs))]
    return b.create_vertices("Product", rows)

def f117(db, embedding):                             # the NumPy doc page
    vertex = db.new_vertex("Document")
    vertex.set("embedding", embedding.tolist())

def ex03(arcadedb, doc):                             # examples/03, pre-fix
    return arcadedb.to_java_float_array(doc["e"].tolist())

def sparse(jpype, idxs):                             # l3_sparse shape
    return jpype.JArray(jpype.JInt)(idxs.tolist())

def bulk(db, vecs):                                  # Database.insert_many
    db.insert_many("Article", [{"e": vecs[i].tolist()} for i in range(3)])
'''

_MUST_NOT_FLAG = '''
def mongo(coll, vecs):                               # pymongo wants lists
    coll.insert_many([{"e": vecs[i].tolist()} for i in range(3)], ordered=False)

def mongo_attr(self, vecs):
    self.coll.insert_many([{"e": vecs[i].tolist()} for i in range(3)])

def qdrant(client, vecs):
    client.upsert("a", vectors=[vecs[i].tolist() for i in range(3)])

def chroma(col, vecs):
    col.add(embeddings=vecs.tolist(), ids=["a"])

def builtin_set(gt, qi, ids, K):                     # set(), not vertex.set()
    return len(set(ids[:K]) & set(gt[qi].tolist())) / K

def neo4j(s, vecs):
    s.run("UNWIND $rows AS r CREATE (:A {e: r.e})",
          rows=[{"e": vecs[i].tolist()} for i in range(3)]).consume()

def surreal_then_arcade(self, vecs, b):              # the scoping false positive
    rows = [{"id": i, "e": vecs[i].tolist()} for i in range(3)]
    self.db.insert("product", rows)
'''


def selftest():
    import tempfile
    ok = True
    for label, src, expect in (("must flag", _MUST_FLAG, 5),
                               ("must not flag", _MUST_NOT_FLAG, 0)):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
            fh.write(src)
            tmp = fh.name
        try:
            n = len(check_file(tmp))
        finally:
            os.unlink(tmp)
        good = (n == expect)
        ok &= good
        print(f"  {label:<16} {n} finding(s), expected {expect}   {'ok' if good else 'BROKEN'}")
    print("\nselftest " + ("passed" if ok else "FAILED -- the check has gone blind"))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()

    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    paths = argv[1:] or [os.path.join(repo, p) for p in DEFAULT_PATHS]
    paths = [p for p in paths if os.path.exists(p)]

    found, n = [], 0
    for f in _iter_py(paths):
        n += 1
        found.extend(check_file(f))

    for path, line, why in sorted(found):
        rel = os.path.relpath(path, repo)
        print(f"  PAYLOAD  {rel}:{line}  {why}")
    print(f"\n{len(found)} list-into-the-JVM site(s) across {n} file(s)")
    if not found:
        print("  (a .tolist() on its way to Qdrant, Milvus, Chroma or MongoDB is not "
              "a finding: those clients want Python lists)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
