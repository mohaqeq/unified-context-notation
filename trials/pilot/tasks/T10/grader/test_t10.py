import sqlfluff
from sqlfluff.api import format_violations as exported
from sqlfluff.api.simple import format_violations


def test_exported():
    assert exported is format_violations


def test_empty():
    assert format_violations([]) == ""


def test_layout_exact():
    vs = [
        {
            "start_line_no": 1,
            "start_line_pos": 9,
            "code": "LT01",
            "description": "Too many spaces.",
            "name": "layout.spacing",
            "warning": False,
        },
        {
            "start_line_no": 123,
            "start_line_pos": 10,
            "code": "PRS",
            "description": "Boom.",
            "name": "",
            "warning": False,
        },
    ]
    assert format_violations(vs) == (
        "L:   1 | P:   9 | LT01 | Too many spaces. [layout.spacing]\n"
        "L: 123 | P:  10 |  PRS | Boom."
    )


def test_real_lint_round_trip():
    vs = sqlfluff.lint("SELECT  1\n", rules=["LT01"])
    assert vs
    out = format_violations(vs)
    assert "\x1b" not in out
    assert not out.endswith("\n")
    lines = out.split("\n")
    assert len(lines) == len(vs)
    for line, v in zip(lines, vs):
        prefix = f"L:{v['start_line_no']:4d} | P:{v['start_line_pos']:4d} | LT01 | "
        assert line.startswith(prefix)
        assert v["description"] in line
        assert line.endswith(f"[{v['name']}]")
