from sqlfluff.core.helpers.string import split_comma_separated_string as split


def test_string_unchanged():
    assert split("a, b ,,c ") == ["a", "b", "c"]
    assert split("") == []


def test_list_cleaned():
    assert split(["a ", "", " b", "   "]) == ["a", "b"]


def test_tuple_accepted():
    out = split((" x", "y "))
    assert out == ["x", "y"]
    assert isinstance(out, list)


def test_returns_new_list():
    src = ["a", "b"]
    out = split(src)
    assert out == ["a", "b"]
    assert out is not src
