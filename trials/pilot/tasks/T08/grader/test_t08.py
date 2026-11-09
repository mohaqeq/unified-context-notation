from sqlfluff.core import FluffConfig, Linter


def _tree(sql):
    cfg = FluffConfig(overrides={"dialect": "ansi"})
    return Linter(config=cfg).parse_string(sql).tree


def _raws(sql):
    return [c.raw for c in _tree(sql).get_noqa_comments()]


def test_inline_noqa():
    sql = "SELECT a  -- noqa: LT01\nFROM t -- just a note\n"
    assert _raws(sql) == ["-- noqa: LT01"]


def test_bare_noqa_and_block_comment_in_order():
    sql = "SELECT /* noqa: disable=all */ a, b -- noqa\nFROM t\n"
    assert _raws(sql) == ["/* noqa: disable=all */", "-- noqa"]


def test_chained_comment_last_section_counts():
    sql = "SELECT a -- note -- noqa: LT05\nFROM t\n"
    assert _raws(sql) == ["-- note -- noqa: LT05"]


def test_mentions_do_not_count():
    sql = "SELECT a -- see the noqa docs\nFROM t /* not noqa here */\n"
    assert _raws(sql) == []


def test_non_comment_text_and_no_comments():
    assert _raws("SELECT 'noqa' AS noqa FROM t\n") == []


def test_called_on_subtree():
    tree = _tree("SELECT a -- noqa\nFROM t\nWHERE b = 1 -- noqa: LT01\n  AND c = 2\n")
    where = next(tree.recursive_crawl("where_clause"))
    assert [c.raw for c in where.get_noqa_comments()] == ["-- noqa: LT01"]
    assert len(tree.get_noqa_comments()) == 2
