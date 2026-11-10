import sqlfluff.api as api
from sqlfluff.api.info import list_dialect_names


def test_names():
    names = list_dialect_names()
    assert isinstance(names, list)
    assert all(isinstance(n, str) for n in names)
    assert names == sorted(names)
    assert {"ansi", "postgres", "bigquery", "tsql"} <= set(names)


def test_matches_list_dialects():
    assert set(list_dialect_names()) == {d.label for d in api.list_dialects()}
    assert len(list_dialect_names()) == len(api.list_dialects())


def test_exported():
    assert api.list_dialect_names is list_dialect_names
