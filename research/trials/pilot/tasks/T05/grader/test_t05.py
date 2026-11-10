import pytest

from sqlfluff.core import FluffConfig, Linter
from sqlfluff.core.rules.context import RuleContext
from sqlfluff.utils.identifers import identifiers_policy_applicable

SQL = "SELECT a, b AS col_alias FROM tbl AS tbl_alias, (SELECT 1 AS inner_alias) sub\n"
POLICIES = ["all", "none", "aliases", "column_aliases", "table_aliases"]


def _contexts():
    cfg = FluffConfig(overrides={"dialect": "ansi"})
    parsed = Linter(config=cfg).parse_string(SQL)
    assert parsed.tree is not None

    def walk(seg, stack):
        yield seg, stack
        for child in seg.segments:
            yield from walk(child, stack + (seg,))

    for seg, stack in walk(parsed.tree, ()):
        if seg.is_type("naked_identifier", "identifier"):
            yield RuleContext(
                dialect=None,
                fix=False,
                templated_file=None,
                path=None,
                config=cfg,
                segment=seg,
                parent_stack=stack,
            )


def test_method_matches_utility_everywhere():
    ctxs = list(_contexts())
    assert len(ctxs) >= 6
    for ctx in ctxs:
        for policy in POLICIES:
            assert ctx.identifier_policy_applies(policy) is (
                identifiers_policy_applicable(policy, ctx.parent_stack)
            )


def _by_raw(raw):
    return [c for c in _contexts() if c.segment.raw == raw][0]


@pytest.mark.parametrize(
    "raw,policy,expected",
    [
        ("a", "all", True),
        ("a", "none", False),
        ("a", "aliases", False),
        ("col_alias", "aliases", True),
        ("col_alias", "column_aliases", True),
        ("col_alias", "table_aliases", False),
        ("tbl_alias", "aliases", True),
        ("tbl_alias", "table_aliases", True),
        ("tbl_alias", "column_aliases", False),
        # Column alias inside a derived table is still a column alias.
        ("inner_alias", "column_aliases", True),
        ("inner_alias", "table_aliases", False),
    ],
)
def test_specific_values(raw, policy, expected):
    assert _by_raw(raw).identifier_policy_applies(policy) is expected
