import sqlfluff
from sqlfluff.core import SQLBaseError, SQLParseError

LONG = (
    "Keywords must be consistently upper case because the configured "
    "capitalisation policy says so and this is a rather long explanation"
)


def test_wraps_to_width():
    err = SQLBaseError(LONG)
    lines = err.desc_lines(30)
    assert isinstance(lines, list)
    assert len(lines) > 1
    assert all(len(line) <= 30 for line in lines)
    assert " ".join(lines) == LONG


def test_short_is_single_line():
    assert SQLBaseError("short one").desc_lines(80) == ["short one"]


def test_subclasses_have_it():
    err = SQLParseError("Found unparsable section: 'foo bar baz qux'")
    lines = err.desc_lines(12)
    assert all(len(line) <= 12 for line in lines)
    assert " ".join(lines) == err.desc()


def test_real_lint_violation():
    result = sqlfluff.lint("select a FROM b\n", dialect="ansi", rules=["CP01"])
    assert result
    vio = SQLBaseError(result[0]["description"])
    lines = vio.desc_lines(15)
    assert len(lines) >= 2
    assert all(len(line) <= 15 for line in lines)
    assert " ".join(lines) == result[0]["description"]
