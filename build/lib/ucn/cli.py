"""`ucn`: one command for the UCN toolchain (standard library only).

  ucn check   MODEL.ucn [--results junit.xml ...] [--require-evidence] [--diff REV] [--json] ...
  ucn stamp   MODEL.ucn [--accept-changed]          add/refresh content hashes on `src:` references
  ucn export  MODEL.ucn --to import-linter --package PKG | --to dependency-cruiser
  ucn project MODEL.ucn --task "TEXT" [--budget 2500]  task-specific context for a coding agent
  ucn lint    MODEL.ucn                             syntax and reference check only

`ucn check --help` lists every validator option.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # the modules import each other by their file names

COMMANDS = {"check": "ucn_validate.py", "stamp": "ucn_validate.py", "export": "ucn_export.py",
            "project": "ucn_project.py", "lint": "ucn_parse.py"}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help") or argv[0] not in COMMANDS:
        print(__doc__.strip())
        return 0 if argv and argv[0] in ("-h", "--help", "help") else 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "stamp" and "--stamp" not in rest:
        rest = rest + ["--stamp"]
    sys.argv = [f"ucn {cmd}"] + rest
    try:
        runpy.run_path(os.path.join(HERE, COMMANDS[cmd]), run_name="__main__")
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
