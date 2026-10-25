"""More positional values than the statement has placeholders is refused, not bound silently (P-07).

``query("sql", "... WHERE @rid IN ?", [rid_a, rid_b])`` reads the lone list as the positional-parameter list (the documented
form: one element per ``?``). The statement has one ``?``, so the engine bound the first element, dropped the second without a
word, and returned fewer rows than the caller meant. The engine does not check the count (it also lets a call with fewer values
than placeholders bind null), so the bindings refuse the form that cannot be right: more values than the statement can hold.

The check is an upper bound (placeholder characters counted anywhere in the text), so it never refuses a call that binds.
"""

import pytest


@pytest.fixture
def db(temp_db):
    temp_db.command("sql", "CREATE DOCUMENT TYPE T")
    with temp_db.transaction():
        for k in range(4):
            temp_db.command("sql", "INSERT INTO T SET k = ?, v = 0", k)
    return temp_db


def _rids(db, *keys):
    by_key = {row.get("k"): row.get_rid() for row in db.query("sql", "SELECT FROM T")}
    return [by_key[k] for k in keys]


def _keys(rows):
    return sorted(row["k"] for row in rows)


LIST_FORMS = [
    pytest.param(lambda a, b: ([a, b],), id="list"),
    pytest.param(lambda a, b: ((a, b),), id="tuple"),
    pytest.param(lambda a, b: (a, b), id="two-arguments"),
]


@pytest.mark.parametrize("form", LIST_FORMS)
def test_query_refuses_two_values_for_one_placeholder(db, form):
    with pytest.raises(TypeError, match=r"2 positional values.*1 placeholder"):
        db.query("sql", "SELECT FROM T WHERE k IN ?", *form(0, 1))


@pytest.mark.parametrize("form", LIST_FORMS)
def test_rid_list_by_position_is_refused_not_cut_to_the_first(db, form):
    rid_a, rid_b = _rids(db, 0, 1)
    with pytest.raises(TypeError, match="IN :ids"):
        db.query("sql", "SELECT FROM T WHERE @rid IN ?", *form(rid_a, rid_b))


def test_command_refuses_and_changes_nothing(db):
    with pytest.raises(TypeError, match="positional values"):
        with db.transaction():
            db.command("sql", "UPDATE T SET v = 1 WHERE k = ?", [0, 1])
    assert {row["v"] for row in db.query("sql", "SELECT FROM T").to_list()} == {0}


def test_the_refusal_is_raised_before_the_statement_runs(db):
    # not wrapped as "Query failed": it is a wrong call, not a failed statement
    with pytest.raises(TypeError) as caught:
        db.query("sql", "SELECT FROM T WHERE k = ?", 1, 2, 3)
    assert not str(caught.value).startswith("Query failed")


def test_the_message_names_the_two_ways_out(db):
    with pytest.raises(TypeError) as caught:
        db.query("sql", "SELECT FROM T WHERE k IN ?", [0, 1])
    message = str(caught.value)
    assert "[[0, 1]]" not in message  # the message does not echo the data
    assert "wrap" in message and "IN :ids" in message


# -- the documented forms keep binding


def test_a_list_wrapped_in_a_list_binds_as_one_parameter(db):
    rows = db.query("sql", "SELECT FROM T WHERE k IN ?", [[0, 1]]).to_list()
    assert _keys(rows) == [0, 1]


def test_a_rid_list_wrapped_in_a_list_binds_as_one_parameter(db):
    rid_a, rid_b = _rids(db, 0, 1)
    rows = db.query("sql", "SELECT FROM T WHERE @rid IN ?", [[rid_a, rid_b]]).to_list()
    assert _keys(rows) == [0, 1]


def test_the_named_form_binds_the_whole_list(db):
    rows = db.query(
        "sql", "SELECT FROM T WHERE k IN :ids", {"ids": [0, 1, 2]}
    ).to_list()
    assert _keys(rows) == [0, 1, 2]


@pytest.mark.parametrize("form", LIST_FORMS)
def test_one_value_per_placeholder_still_binds(db, form):
    rows = db.query("sql", "SELECT FROM T WHERE k = ? OR k = ?", *form(0, 3)).to_list()
    assert _keys(rows) == [0, 3]


def test_one_value_one_placeholder_in_every_spelling(db):
    for args in ((2,), ([2],), ((2,),)):
        assert _keys(db.query("sql", "SELECT FROM T WHERE k = ?", *args).to_list()) == [
            2
        ]


def test_a_placeholder_character_in_a_literal_does_not_refuse_a_binding_call(db):
    # the bound is an upper bound: a "?" in a string counts as a placeholder, so this call (2 values, 2 counted) is not refused
    rows = db.query("sql", "SELECT FROM T WHERE k = ? AND '?' = '?'", [1]).to_list()
    assert _keys(rows) == [1]


def test_positional_dollar_placeholders_count(db):
    db.query(
        "sql", "SELECT FROM T WHERE k = $1 OR k = $2", [0, 1]
    ).to_list()  # two `$n`, two values: not a TypeError


def test_a_script_with_two_placeholders_binds_two_values(db):
    rows = db.command(
        "sqlscript", "SELECT FROM T WHERE k = ? OR k = ?;", [0, 1]
    ).to_list()
    assert _keys(rows) == [0, 1]


def test_other_languages_are_not_counted(db):
    # openCypher has no "?" placeholders; the check is for SQL, whose list form is the documented one
    rows = db.query("opencypher", "RETURN $a AS a", {"a": 1}).to_list()
    assert [row["a"] for row in rows] == [1]
