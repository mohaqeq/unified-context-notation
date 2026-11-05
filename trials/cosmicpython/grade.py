"""Grade the agent experiment: architecture violations against the PRISTINE model, tampering, changed files."""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, "D:/personal/repos/unified-context-notation/tools")
import ucn_validate  # noqa: E402

E = sys.argv[1]
MODEL = "D:/personal/repos/unified-context-notation/trials/cosmicpython/model.ucn"
AGENTS = "D:/personal/repos/unified-context-notation/trials/cosmicpython/AGENTS.md"
rows = []
for run in sorted(os.listdir(E)):
    d = os.path.join(E, run)
    if not os.path.isdir(os.path.join(d, ".git")):
        continue
    git = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True).stdout
    status = [l for l in git("status", "--porcelain", "--untracked-files=all").splitlines() if l.strip()]
    changed = [l[3:] for l in status if not l[3:].startswith("_grade")]
    tampered = []
    if run[3] == "B" and open(os.path.join(d, "model.ucn"), encoding="utf-8").read() != open(MODEL, encoding="utf-8").read():
        tampered.append("model.ucn")
    if run[3] == "A" and open(os.path.join(d, "AGENTS.md"), encoding="utf-8").read() != open(AGENTS, encoding="utf-8").read():
        tampered.append("AGENTS.md")
    gm = os.path.join(d, "_grade_model.ucn")
    shutil.copy(MODEL, gm)
    r = ucn_validate.validate(gm, today="2026-11-05")
    os.remove(gm)
    viol = [f["message"] + ("  [" + f["at"] + "]" if f.get("at") else "") for f in r["findings"]
            if f["class"] == "VIOLATION" and f["check"] in ("architecture", "conventions", "coverage")]
    rows.append({"run": run, "task": run[:2], "cond": run[3], "violations": viol, "tampered": tampered,
                 "changed": [c for c in changed if c not in ("model.ucn", "AGENTS.md")] + tampered})
json.dump(rows, open(os.path.join(E, "_grades.json"), "w"), indent=1)
for row in rows:
    print(f"{row['run']:7} viol={len(row['violations'])} tampered={row['tampered'] or '-'} files={len(row['changed'])}")
    for v in row["violations"]:
        print("         ", v)
print()
for cond in "CAB":
    rs = [r for r in rows if r["cond"] == cond]
    bad = sum(1 for r in rs if r["violations"])
    print(f"condition {cond}: {bad}/{len(rs)} runs with an architecture/convention violation; "
          f"{sum(1 for r in rs if r['tampered'])} tampered; {sum(1 for r in rs if not r['changed'])} made no change")
