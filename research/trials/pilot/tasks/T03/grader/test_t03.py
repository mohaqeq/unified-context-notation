import pytest

from sqlfluff.core.parser.helpers import references_overlap


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (("tbl",), ("tbl",), True),
        (("schema", "tbl"), ("schema", "tbl"), True),
        (("tbl",), ("schema", "tbl"), True),
        (("schema", "tbl"), ("tbl",), True),
        (("b", "c"), ("a", "b", "c"), True),
        (("a", "b", "c"), ("b", "c"), True),
        (("schema",), ("schema", "tbl"), False),
        (("a", "c"), ("a", "b", "c"), False),
        (("TBL",), ("tbl",), False),
        (("x",), ("y",), False),
        ((), ("tbl",), False),
        (("tbl",), (), False),
        ((), (), False),
    ],
)
def test_references_overlap(a, b, expected):
    assert references_overlap(a, b) is expected


def test_symmetric():
    pairs = [(("a",), ("z", "a")), (("a", "b"), ("b",)), (("q",), ("r",))]
    for a, b in pairs:
        assert references_overlap(a, b) == references_overlap(b, a)
