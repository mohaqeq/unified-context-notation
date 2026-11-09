"""Hidden grader for T2: behavior of describe_segment, independent of the agent's own tests."""
from sqlfluff.core.helpers.string import describe_segment


class FakeSegment:
    def __init__(self, raw, type_="keyword"):
        self.raw = raw
        self.type = type_

    def get_type(self):
        return self.type


def test_short_text_is_kept():
    assert describe_segment(FakeSegment("SELECT")) == "keyword: SELECT"


def test_long_text_is_truncated():
    out = describe_segment(FakeSegment("x" * 100))
    assert out.startswith("keyword: " + "x" * 37)
    assert len(out) <= len("keyword: ") + 43


def test_used_in_unparsable_message():
    import sqlfluff
    v = [x["description"] for x in sqlfluff.lint("SELECT +++ FROM t\n", dialect="ansi") if x["code"] == "PRS"]
    assert v and "unparsable: +++" in v[0]
