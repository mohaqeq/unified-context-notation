import pytest

from sqlfluff.core.helpers.string import parse_dotted_assignments


def test_basic():
    assert parse_dotted_assignments("rules.LT01.foo=1, core.dialect=ansi") == {
        "rules": {"LT01": {"foo": "1"}},
        "core": {"dialect": "ansi"},
    }


def test_merge_prefix_and_whitespace():
    assert parse_dotted_assignments(" a.b = 1 ,a.c=2,  d=x y ") == {
        "a": {"b": "1", "c": "2"},
        "d": "x y",
    }


def test_empty():
    assert parse_dotted_assignments("") == {}
    assert parse_dotted_assignments("  ") == {}


def test_value_may_contain_equals():
    assert parse_dotted_assignments("a.b=x=y") == {"a": {"b": "x=y"}}


def test_later_duplicate_wins():
    assert parse_dotted_assignments("a.b=1,a.b=2") == {"a": {"b": "2"}}


@pytest.mark.parametrize("bad", ["novalue", "a..b=1", ".a=1", "a.=1", "=1"])
def test_invalid(bad):
    with pytest.raises(ValueError):
        parse_dotted_assignments(bad)
