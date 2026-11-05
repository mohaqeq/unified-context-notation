"""UCN consistency validator: checks a model against its code. Deterministic: no LLM, no build, no network.

Usage:
  python tools/ucn_validate.py MODEL.ucn [--today YYYY-MM-DD] [--gate adopt] [--changed FILE ...]
                                         [--cache FILE] [--json]

Checks
  1. Architecture conformance (reflexion model). Imports between code files are lifted to model elements
     through `code:` globs and compared with declared relations. Deviations waive; authority decides
     whether a mismatch is a VIOLATION (model is authoritative) or a MODEL-UPDATE (code is authoritative).
  2. Parameter bindings. `param:` values on requirements vs the constants named by `bind:`.
  3. Convention checks. `check: only <glob> imports <module>`.
  4. Provenance. `src:` references to code files must exist and the line must be in range.
  5. Coverage. Code files that no element claims.
  6. Trace completeness (from the linter).
  7. --gate adopt: before switching a part to forward mode, no inferred facts or open conflicts may remain
     in model-authoritative intent and architecture.

Exit code 1 if there is any VIOLATION (or a blocked gate), otherwise 0.
--changed limits import scanning to the given files (pre-commit); everything else stays cheap.
--cache stores per-file imports keyed by mtime and size, so unchanged files are not re-read.
"""
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ucn_parse import RELS, UcnError, lint, parse, resolve  # noqa: E402

INTENT = {"goal", "req", "decision", "term", "convention", "rule"}
ARCH = {"system", "container", "component", "data", "api", "event", "config", "env", "actor"}
LOGIC = {"fn", "machine", "flow"}
PRESETS = {
    "reverse": {"intent": "source", "arch": "source", "logic": "source"},
    "forward": {"intent": "model", "arch": "model", "logic": "source"},
}
DEP_RELS = {"uses", "calls", "reads", "writes", "emits", "consumes", "implements", "exposes", "verifies"}
SYMMETRIC = {"implements"}  # an interface module may call its implementers
CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", "__pycache__", ".venv", "venv", "coverage"}
RESOLVE_EXT = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", "/index.ts", "/index.tsx", "/index.js"]

JS_IMPORT = re.compile(r"""(?:\bimport\s+(?:[\w*{}\s,]+\s+from\s+)?|\bexport\s+[\w*{}\s,]+\s+from\s+|\brequire\(\s*|\bimport\(\s*)["']([^"']+)["']""")
PY_IMPORT = re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import|import\s+([\w.]+))", re.M)
SRC_CODE = re.compile(r"^([\w./-]+(?:" + "|".join(re.escape(e) for e in CODE_EXT) + r"))(?::(\d+))?$")
CHECK_ONLY = re.compile(r"^only\s+(\S+)\s+imports\s+(\S+)$")

VIOLATION, WAIVED, KNOWN, UPDATE, INFO = "VIOLATION", "WAIVED", "KNOWN-CONFLICT", "MODEL-UPDATE", "INFO"


def slurp(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def glob_re(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out, i = out + ".*", i + 2
        elif pattern[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif pattern[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile("^" + out + "$")


def specificity(pattern):
    """Exact paths beat globs; otherwise the longer literal prefix wins."""
    wild = min([pattern.find(c) for c in "*?" if c in pattern] or [len(pattern) + 1000])
    return wild


class Model:
    def __init__(self, g):
        self.g = g
        self.nodes = {n["id"]: n for n in g["nodes"]}
        self.kind = {i: n["kind"] for i, n in self.nodes.items()}
        self.header = g["header"]
        self.mode = self.header.get("mode", "reverse")

    def attrs(self, nid, key):
        return self.nodes[nid].get("attrs", {}).get(key, [])

    def ancestors(self, nid):
        out, p = [], self.nodes[nid].get("parent")
        while p:
            out.append(p)
            p = self.nodes[p].get("parent")
        return out

    def is_under(self, a, b):  # a is b or a descendant of b
        return a == b or b in self.ancestors(a)

    def layer(self, nid):
        k = self.kind[nid]
        return "intent" if k in INTENT else "arch" if k in ARCH else "logic" if k in LOGIC else None

    def authority(self, nid):
        for x in [nid] + self.ancestors(nid):
            a = self.attrs(x, "authority")
            if a:
                return a[-1]
        k = self.kind[nid]
        if k == "test":
            return "source"
        if k in {"conflict", "side", "deviation"}:
            return "model"
        return PRESETS[self.mode][self.layer(nid)]

    def ref(self, r, kind=None):
        return resolve(r, set(self.kind), kind, self.kind)[0]


def list_code_files(root):
    files = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for n in names:
            if n.endswith(CODE_EXT):
                files.append(os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/"))
    return sorted(files)


def resolve_spec(src_file, spec, fileset):
    """Return ('file', path) for an internal import, or ('ext', module) for a package."""
    if spec.startswith("."):
        base = os.path.normpath(os.path.join(os.path.dirname(src_file), spec)).replace(os.sep, "/")
        for ext in RESOLVE_EXT:
            if base + ext in fileset:
                return "file", base + ext
        return "missing", base
    parts = spec.split("/")
    return "ext", "/".join(parts[:2]) if spec.startswith("@") else parts[0]


def py_resolve(src_file, mod, fileset):
    if mod.startswith("."):
        dots = len(mod) - len(mod.lstrip("."))
        base = os.path.dirname(src_file)
        for _ in range(dots - 1):
            base = os.path.dirname(base)
        rest = mod.lstrip(".").replace(".", "/")
        cand = f"{base}/{rest}" if rest else base
    else:
        cand = mod.replace(".", "/")
    cand = cand.lstrip("/")
    for c in (cand + ".py", cand + "/__init__.py"):
        if c in fileset:
            return "file", c
    return "ext", mod.lstrip(".").split(".")[0]


def scan_imports(root, files, fileset, cache):
    out = {}
    for f in files:
        p = os.path.join(root, f)
        st = os.stat(p)
        key = f"{st.st_mtime_ns}:{st.st_size}"
        hit = cache.get(f)
        if hit and hit["key"] == key:
            out[f] = [tuple(x) for x in hit["imports"]]
            continue
        text = slurp(p)
        if f.endswith(".py"):
            imps = [py_resolve(f, a or b, fileset) for a, b in PY_IMPORT.findall(text)]
        else:
            imps = [resolve_spec(f, s, fileset) for s in JS_IMPORT.findall(text)]
        out[f] = imps
        cache[f] = {"key": key, "imports": imps}
    return out


def validate(model_path, today=None, gate=None, changed=None, cache_path=None):
    t0 = time.perf_counter()
    g = parse(slurp(model_path))
    m = Model(g)
    root = os.path.join(os.path.dirname(os.path.abspath(model_path)), m.header.get("root", "."))
    today = today or datetime.date.today().isoformat()
    findings = []

    def add(cls, check, msg, at=None):
        findings.append({"class": cls, "check": check, "message": msg, **({"at": at} if at else {})})

    # ---- mapping: file -> most specific element (code: globs; tests by their src files)
    claims = []
    for nid, n in m.nodes.items():
        for pat in m.attrs(nid, "code"):
            claims.append((specificity(pat), len(m.ancestors(nid)), glob_re(pat), nid))
        if n["kind"] == "test":
            for s in m.attrs(nid, "src"):
                sm = SRC_CODE.match(s)
                if sm:
                    claims.append((10**9, 99, glob_re(sm.group(1)), nid))
    claims.sort(key=lambda c: (c[0], c[1]), reverse=True)
    buckets = {}  # index claims by the first path segment of their literal prefix ('' = matches anywhere)
    for rank, c in enumerate(claims):
        lit = c[2].pattern[1:].split(".*")[0].split("[^/]")[0].replace("\\", "")
        seg = lit.split("/")[0] if "/" in lit else ""
        buckets.setdefault(seg, []).append((rank, c))
    files = list_code_files(root)
    fileset = set(files)
    owner = {}
    for f in files:
        cands = sorted(buckets.get(f.split("/")[0], []) + buckets.get("", []))
        owner[f] = next((c[3] for _, c in cands if c[2].match(f)), None)
        if owner[f] is None:
            cls = VIOLATION if m.mode == "forward" else UPDATE
            add(cls, "coverage", f"{f} is not claimed by any element (add a code: glob)")

    # ---- imports
    cache = {}
    if cache_path and os.path.exists(cache_path):
        cache = json.loads(slurp(cache_path))
    scan = [f for f in files if not changed or f in set(changed)]
    imports = scan_imports(root, scan, fileset, cache)
    if cache_path:
        with open(cache_path, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)

    # ---- 1. architecture conformance
    edges = []
    for e in g["edges"]:
        a, b = e.get("from_id"), e.get("to_id")
        if a and b and e["rel"] in DEP_RELS:
            edges.append((a, b, None))
            if e["rel"] in SYMMETRIC:
                edges.append((b, a, None))
    waivers = []
    for nid, n in m.nodes.items():
        if n["kind"] != "deviation":
            continue
        exp = (m.attrs(nid, "expires") or [""])[-1]
        active = (m.attrs(nid, "lifecycle") or ["accepted"])[-1] == "accepted" and (not exp or exp >= today)
        for al in n.get("allows", []):
            a, b = m.ref(al["from"]), m.ref(al["to"])
            if not a or not b:
                add(VIOLATION, "deviation", f"deviation {nid}: cannot resolve '{al['from']} {al['rel']} {al['to']}'")
                continue
            waivers.append((a, b, nid, active, exp))

    def exposed(b, y):  # b may be reached inside container y only through what y exposes
        for (x, t, _) in edges:
            if x == y and m.is_under(b, t):
                return True  # y exposes / implements something b belongs to
        for (x, t, _) in edges:  # b implements an api that y exposes
            if m.is_under(x, b) and any(e2[0] == y and e2[1] == t for e2 in edges):
                return True
        return False

    def allowed(a, b):
        if m.is_under(a, b) or m.is_under(b, a):
            return True
        for (x, y, _) in edges:
            if not m.is_under(x, a):
                continue
            if m.is_under(y, b):
                return True
            if m.is_under(b, y) and (m.kind[y] != "container" or exposed(b, y)):
                return True
        return False

    observed = {}
    for f, imps in imports.items():
        a = owner.get(f)
        for kind, target in imps:
            if kind == "missing":
                add(INFO, "imports", f"{f}: unresolved relative import {target}")
            if kind != "file" or not a or not owner.get(target):
                continue
            b = owner[target]
            if a != b:
                observed.setdefault((a, b), []).append(f"{f} -> {target}")
    conform = 0
    for (a, b), where in sorted(observed.items()):
        if allowed(a, b):
            conform += 1
            continue
        hit = [w for w in waivers if m.is_under(a, w[0]) and m.is_under(b, w[1])]
        if any(w[3] for w in hit):
            w = next(w for w in hit if w[3])
            add(WAIVED, "architecture", f"{a} -> {b} waived by deviation {w[2]} (expires {w[4] or 'never'})", where[0])
            continue
        for w in hit:
            add(VIOLATION, "architecture", f"deviation {w[2]} for {a} -> {b} expired on {w[4]}", where[0])
        if m.authority(a) == "model":
            add(VIOLATION, "architecture", f"{a} depends on {b}, which the model does not allow", where[0])
        else:
            add(UPDATE, "architecture", f"{a} depends on {b} (authority: source): add a relation or a deviation to the model", where[0])

    # absences (declared, never observed) are informational
    if not changed:
        coded = {nid for nid in m.nodes if m.attrs(nid, "code") or m.kind[nid] == "test"}
        def code_owner(n):
            return next((x for x in [n] + m.ancestors(n) if x in coded), None)
        for e in g["edges"]:
            a, b = e.get("from_id"), e.get("to_id")
            if not (a and b) or e["rel"] not in DEP_RELS - {"exposes"}:
                continue
            ca, cb = code_owner(a), code_owner(b)
            if not ca or not cb or m.is_under(ca, cb) or m.is_under(cb, ca):
                continue
            if not any(m.is_under(x, ca) and m.is_under(y, cb) or (e["rel"] in SYMMETRIC and m.is_under(x, cb) and m.is_under(y, ca))
                       for (x, y) in observed):
                add(INFO, "architecture", f"declared {a} {e['rel']} {b}, but no code dependency realizes it")

    # ---- 2. parameter bindings
    file_text = {}
    def read(path):
        if path not in file_text:
            p = os.path.join(root, path)
            file_text[path] = slurp(p) if os.path.exists(p) else None
        return file_text[path]
    for nid in m.nodes:
        for b in m.attrs(nid, "bind"):
            bm = re.match(r"^([A-Za-z_][\w.]*)\.([A-Za-z_]\w*)\s*=\s*([^#\s]+)#([A-Za-z_]\w*)$", b)
            req_ref, pname, path, const = bm.groups()
            req = m.ref(req_ref, "req")
            params = {}
            for p in m.attrs(req, "param") if req else []:
                pm = re.match(r"^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*(.*)$", p)
                params[pm.group(1)] = (float(pm.group(2)), pm.group(2), pm.group(3))
            if not req or pname not in params:
                add(VIOLATION, "parameters", f"{nid}: bind names unknown parameter {req_ref}.{pname}")
                continue
            text = read(path)
            cm = text and re.search(r"\b" + re.escape(const) + r"\b\s*(?::\s*[\w<>\[\]]+\s*)?=\s*(-?\d[\d_]*(?:\.\d+)?)", text)
            if not cm:
                add(VIOLATION, "parameters", f"{nid}: constant {const} not found in {path}")
                continue
            code_val = float(cm.group(1).replace("_", ""))
            want, raw, unit = params[pname]
            label = f"{req}.{pname} = {raw}{(' ' + unit) if unit else ''} vs {path}#{const} = {cm.group(1)}"
            if code_val == want:
                conform += 1
                continue
            known = [c for c, n in m.nodes.items() if n["kind"] == "conflict"
                     and (m.attrs(c, "lifecycle") or ["open"])[-1] in ("open", "accepted")
                     and any(e["rel"] == "about" and e.get("from_id") == c and e.get("to_id") in (req, nid) for e in g["edges"])]
            if known:
                add(KNOWN, "parameters", f"{label} (conflict {known[0]})")
            elif m.authority(req) == "model":
                add(VIOLATION, "parameters", f"{label}: code does not meet the requirement")
            else:
                add(UPDATE, "parameters", f"{label}: update the requirement parameter")

    # ---- 3. convention checks
    for nid in m.nodes:
        for chk in m.attrs(nid, "check"):
            cm = CHECK_ONLY.match(chk)
            if not cm:
                add(VIOLATION, "conventions", f"{nid}: unknown check syntax '{chk}' (supported: only <glob> imports <module>)")
                continue
            allowed_glob, module = glob_re(cm.group(1)), cm.group(2)
            for f, imps in imports.items():
                if allowed_glob.match(f):
                    continue
                if any(t == module for _, t in imps):
                    cls = VIOLATION if m.authority(nid) == "model" else UPDATE
                    add(cls, "conventions", f"{f} imports {module}, but {nid} allows only {cm.group(1)}")

    # ---- 4. provenance of code references
    for nid in m.nodes:
        for s in m.attrs(nid, "src"):
            sm = SRC_CODE.match(s)
            if not sm:
                continue
            text = read(sm.group(1))
            if text is None:
                add(VIOLATION if m.authority(nid) == "model" else UPDATE, "provenance", f"{nid}: src {s} does not exist (stale)")
            elif sm.group(2) and int(sm.group(2)) > text.count("\n") + 1:
                add(UPDATE, "provenance", f"{nid}: src {s} points past the end of the file (stale)")

    # ---- 6. trace completeness
    for w in lint(g):
        add(INFO, "traces", w)

    # ---- 7. adopt gate
    blockers = []
    if gate == "adopt":
        for nid, n in m.nodes.items():
            if m.authority(nid) != "model" or m.layer(nid) not in ("intent", "arch"):
                continue
            if n.get("origin") == "inferred":
                blockers.append(f"{nid}: inferred {n['kind']} must be reviewed (stated) or removed")
            for c in n.get("contract", []):
                if c.get("origin") == "inferred":
                    blockers.append(f"{nid}: inferred clause '{c['clause']}: {c['expr']}' must be reviewed")
        for nid, n in m.nodes.items():
            if n["kind"] == "conflict" and (m.attrs(nid, "lifecycle") or ["open"])[-1] == "open":
                blockers.append(f"conflict {nid} is open: resolve it or mark it accepted")
        blockers += [f["message"] for f in findings if f["class"] == VIOLATION]

    ms = (time.perf_counter() - t0) * 1000
    return {"model": model_path, "mode": m.mode, "baseline": m.header.get("baseline"), "today": today,
            "files": len(files), "scanned": len(scan), "conforming": conform, "findings": findings,
            "gate": None if not gate else {"name": gate, "blockers": blockers, "pass": not blockers},
            "ms": round(ms, 1)}


def main(argv):
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None
    changed = None
    if "--changed" in argv:
        changed = [a for a in argv[argv.index("--changed") + 1:] if not a.startswith("--")]
    r = validate(argv[1], today=opt("--today"), gate=opt("--gate"), changed=changed, cache_path=opt("--cache"))
    if "--json" in argv:
        print(json.dumps(r, indent=2))
    else:
        print(f"{r['model']}: mode {r['mode']}, baseline {r['baseline']}, {r['files']} code files "
              f"({r['scanned']} scanned), {r['conforming']} conforming dependencies/bindings, {r['ms']} ms")
        order = [VIOLATION, KNOWN, WAIVED, UPDATE, INFO]
        for cls in order:
            for f in (x for x in r["findings"] if x["class"] == cls):
                at = f"  [{f['at']}]" if "at" in f else ""
                print(f"  {cls:<14} {f['check']:<12} {f['message']}{at}")
        counts = {c: sum(1 for f in r["findings"] if f["class"] == c) for c in order}
        print("  summary: " + ", ".join(f"{v} {k.lower()}" for k, v in counts.items()))
        if r["gate"]:
            print(f"  gate {r['gate']['name']}: {'PASS' if r['gate']['pass'] else 'BLOCKED'}")
            for b in r["gate"]["blockers"]:
                print(f"    blocker: {b}")
    bad = any(f["class"] == VIOLATION for f in r["findings"]) or (r["gate"] and not r["gate"]["pass"])
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except UcnError as e:
        print("error:", e)
        sys.exit(2)
