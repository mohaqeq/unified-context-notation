import types

from sqlfluff.core.helpers.string import findall_slices


def test_basic():
    assert list(findall_slices("ab", "abcab")) == [slice(0, 2), slice(3, 5)]


def test_overlapping():
    assert list(findall_slices("aa", "aaaa")) == [slice(0, 2), slice(1, 3), slice(2, 4)]


def test_slices_extract_match():
    s = "select a, b from t, u"
    got = list(findall_slices(", ", s))
    assert got == [slice(8, 10), slice(18, 20)]
    assert all(s[x] == ", " for x in got)


def test_empty_inputs_and_no_match():
    assert list(findall_slices("", "abc")) == []
    assert list(findall_slices("a", "")) == []
    assert list(findall_slices("z", "abc")) == []


def test_is_lazy():
    assert isinstance(findall_slices("a", "aaa"), types.GeneratorType)
