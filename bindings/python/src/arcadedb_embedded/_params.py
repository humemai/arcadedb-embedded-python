"""More positional values than a statement has placeholders is a wrong call, refused before it runs (P-07).

``query("sql", "... WHERE @rid IN ?", [rid_a, rid_b])`` reads the lone list as the positional-parameter list (the documented form,
one element per ``?``). The statement holds one ``?``, the engine binds the first element, ignores the second without a word, and
the query returns fewer rows than the caller meant. The engine does not count (it binds null for a missing value too), and the
bindings cannot ask it: the parsed statement's placeholder count is no public engine call, and the native library would need a new
entry point. So the check is the one that never refuses a call that binds: an UPPER BOUND on the placeholders, the characters
``?``, ``$`` and ``:`` anywhere in the SQL text (a ``?`` in a string literal counts, so such a statement is checked more loosely,
never refused wrongly). A call with more values than that bound has a value no placeholder can take.
"""

from functools import lru_cache

_COUNTED_LANGUAGES = frozenset(("sql", "sqlscript"))


@lru_cache(maxsize=1024)
def _placeholder_bound(command: str) -> int:
    """Upper bound on the positional placeholders of ``command``: ``?``, ``$1`` and ``:name`` characters, wherever they stand."""
    return command.count("?") + command.count("$") + command.count(":")


def refuse_surplus_positionals(
    name: str, language: str, command: str, args: tuple
) -> None:
    """Raise ``TypeError`` when ``args`` (the extra arguments of query()/command()) hold more positional values than ``command`` can bind.

    A lone list or tuple is the positional list itself, so its elements are the values; anything else counts one value per argument.
    Fewer than two values never mismatch an upper bound of one or more, and a mapping alone is the named form: both return at once.
    """
    if len(args) == 1:
        values = args[0]
        if not isinstance(values, (list, tuple)):
            return
        count = len(values)
    else:
        count = len(args)
    if count < 2 or language.lower() not in _COUNTED_LANGUAGES:
        return
    bound = _placeholder_bound(command)
    if count <= bound:
        return
    raise TypeError(
        f"{name}() got {count} positional values, but the statement has at most {bound} placeholder{'' if bound == 1 else 's'}. "
        "A list or tuple on its own is the positional-parameter list, one element per ?, so it does not bind one list to one ?. "
        "To bind a list as ONE parameter, wrap it in another list, [[a, b]], or pass it by name: "
        '"... WHERE x IN :ids" with {"ids": [a, b]}.'
    )
