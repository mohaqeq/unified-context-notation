"""Replay a repo's history: element-level dependency pairs per commit, using the UCN validator (static reading only).

Usage: python replay.py REPO MODEL_ELEMENTS_ONLY OUT.json [pathspec ...]
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, "D:/personal/repos/unified-context-notation/tools")
import ucn_validate  # noqa: E402

repo, model, out = sys.argv[1], sys.argv[2], sys.argv[3]
specs = sys.argv[4:] or ["src"]
git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, check=True).stdout
commits = git("log", "--reverse", "--format=%h %cs", "-G", r"^\s*(from|import) ", "--", *[s + "/*.py" for s in specs] + [s + "/**/*.py" for s in specs]).decode().split("\n")
commits = [c.split() for c in commits if c.strip()]
oldest = git("log", "--reverse", "--format=%h %cs").decode().split("\n")[0].split()
commits = [oldest] + [c for c in commits if c[0] != oldest[0]]
results = []
for h, date in commits:
    d = tempfile.mkdtemp()
    try:
        data = git("archive", "--format=tar", h, *specs)
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extractall(d, filter="data")
        shutil.copy(model, os.path.join(d, "model.ucn"))
        r = ucn_validate.validate(os.path.join(d, "model.ucn"), today="2026-11-05")
        pairs = sorted({(f["element"], f["target"]) for f in r["findings"] if f.get("target")})
        results.append({"commit": h, "date": date, "files": r["files"], "pairs": pairs, "ms": r["ms"]})
        print(h, date, r["files"], len(pairs), r["ms"], flush=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)
json.dump(results, open(out, "w"), indent=1)
