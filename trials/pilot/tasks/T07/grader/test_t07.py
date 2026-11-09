from sqlfluff.core import FluffConfig, Linter
from sqlfluff.core.rules.context import RuleContext


def _contexts(sql):
    cfg = FluffConfig(overrides={"dialect": "ansi"})
    tree = Linter(config=cfg).parse_string(sql).tree
    clause = next(tree.recursive_crawl("select_clause"))
    for i, seg in enumerate(clause.segments):
        yield seg, RuleContext(
            dialect=cfg.get("dialect_obj"),
            fix=False,
            templated_file=None,
            path=None,
            config=cfg,
            segment=seg,
            parent_stack=(clause,),
            segment_idx=i,
        )


def _raw(seg):
    return None if seg is None else seg.raw


def test_neighbours_skip_non_code():
    found = {}
    for seg, ctx in _contexts("SELECT a, /* hi */ b -- x\nFROM t"):
        if seg.is_code:
            found[seg.raw] = (
                _raw(ctx.previous_code_sibling),
                _raw(ctx.next_code_sibling),
            )
    assert found["SELECT"] == (None, "a")
    assert found["a"] == ("SELECT", ",")
    assert found[","] == ("a", "b")
    assert found["b"] == (",", None)


def test_non_code_segment_has_neighbours_too():
    for seg, ctx in _contexts("SELECT a, b FROM t"):
        if seg.is_type("whitespace"):
            assert ctx.previous_code_sibling.raw == "SELECT"
            assert ctx.next_code_sibling.raw == "a"
            return
    raise AssertionError("no whitespace found")


def test_no_parent():
    cfg = FluffConfig(overrides={"dialect": "ansi"})
    tree = Linter(config=cfg).parse_string("SELECT 1").tree
    ctx = RuleContext(
        dialect=cfg.get("dialect_obj"),
        fix=False,
        templated_file=None,
        path=None,
        config=cfg,
        segment=tree,
    )
    assert ctx.previous_code_sibling is None
    assert ctx.next_code_sibling is None
