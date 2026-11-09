import pytest

from sqlfluff.core.helpers.slice import slice_contains


@pytest.mark.parametrize(
    "s,i,expected",
    [
        (slice(2, 5), 1, False),
        (slice(2, 5), 2, True),
        (slice(2, 5), 4, True),
        (slice(2, 5), 5, False),
        (slice(3, 3), 3, False),
        (slice(0, 1), 0, True),
    ],
)
def test_slice_contains(s, i, expected):
    assert slice_contains(s, i) is expected


@pytest.mark.parametrize("s", [slice(None, 3), slice(1, None), slice(None, None)])
def test_open_slice_asserts(s):
    with pytest.raises(AssertionError):
        slice_contains(s, 1)
