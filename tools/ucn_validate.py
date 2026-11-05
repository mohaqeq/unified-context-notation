"""UCN consistency validator: checks a model against its code. Deterministic: no LLM, no build, no network.

Usage:
  python tools/ucn_validate.py MODEL.ucn [options]

Options:
  --today YYYY-MM-DD        date used for expiry checks (default: today)
  --deps FILE               read dependency edges from FILE instead of scanning imports. Formats:
                            dependency-cruiser JSON, madge JSON, {"edges": [{"from", "to"}]} or [[from, to]]
  --changed FILE...         pre-commit: scan only these files (repo- or root-relative). A changed model or
                            tsconfig triggers a full run. A path that matches no code file is an error.
  --cache FILE              cache raw import specifiers (resolution is redone on every run)
  --diff REV                report permissions this model widens compared with the model at git REV
  --allow-widening          do not fail on widened permissions (use after code-owner approval)
  --gate adopt|rebaseline   adopt: simulate model authority for --scope and block on anything not ready.
                            rebaseline: report what loses enforcement when --scope goes back to source.
  --scope ID                subtree for the gate (default: the whole model)
  --apply                   write the authority change and an adoption-log line (gate must pass)
  --baseline REV            baseline to record on --apply (default: git HEAD of the model's directory)
  --reason TEXT             required for rebaseline
  --authority-map           print the effective authority of every node and where it comes from
  --propose                 print the relation lines that would make MODEL-UPDATE dependencies conforming
                            (--include-violations: also for violations; that is a decision, not a fix)
  --max N                   print at most N findings per class (default 40)
  --json                    machine-readable output

Finding classes: VIOLATION (fails CI), WIDENED (fails CI unless --allow-widening), KNOWN-CONFLICT, WAIVED,
MODEL-UPDATE (the code is authoritative and the model is behind), INFO.
Exit code: 1 on VIOLATION, unapproved WIDENED, or a blocked gate; 2 on a model syntax error; otherwise 0.
"""
import ast
import datetime
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ucn_parse import BIND_RE, PARAM_RE, RELS, UcnError, lint, parse, resolve  # noqa: E402

TOOL_VERSION = "0.4"
INTENT = {"goal", "req", "decision", "term", "convention", "rule"}
ARCH = {"system", "container", "component", "data", "api", "event", "config", "env", "actor"}
LOGIC = {"fn", "machine", "flow"}
PERMIT_KINDS = ARCH - {"system"}          # only architecture relations can grant permissions
PRESETS = {
    "reverse": {"intent": "source", "arch": "source", "logic": "source"},
    "forward": {"intent": "model", "arch": "model", "logic": "source"},
}
DEP_RELS = {"uses", "calls", "reads", "writes", "emits", "consumes", "implements", "exposes", "verifies"}
LIFECYCLES = {"deviation": {"proposed", "accepted", "revoked"}, "conflict": {"open", "accepted", "resolved"},
              "decision": {"proposed", "accepted", "superseded"}}
ELEMENT_LIFECYCLE = {"planned", "active", "deprecated"}
HORIZON_DAYS = 365
CODE_EXT = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".py")
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", "__pycache__", ".venv", "venv", "coverage", ".tox",
             ".mypy_cache", ".pytest_cache", ".next", ".turbo"}
TS_TRY = ["", ".ts", ".tsx", ".mts", ".cts", ".d.ts", ".js", ".jsx", ".mjs", ".cjs",
          "/index.ts", "/index.tsx", "/index.js", "/index.jsx"]
ASSET_EXT = {".css", ".scss", ".sass", ".less", ".json", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
             ".woff", ".woff2", ".ttf", ".otf", ".eot", ".wasm", ".md", ".txt", ".html", ".mp3", ".mp4", ".yaml", ".yml"}
JS_TO_TS = {".js": [".ts", ".tsx"], ".jsx": [".tsx"], ".mjs": [".mts"], ".cjs": [".cts"]}

SRC_CODE = re.compile(r"^([\w./@-]+(?:" + "|".join(re.escape(e) for e in CODE_EXT) + r"))(?::(\d+))?$")
CHECK_ONLY = re.compile(r"^only\s+(\S+)\s+imports\s+(\S+)$")
JS_STATIC = re.compile(r"(?m)^[ \t]*(?:import|export)\b[^;'\"`]*?\bfrom\s*['\"]([^'\"\n]+)['\"]")
JS_SIDE = re.compile(r"(?m)^[ \t]*import\s*['\"]([^'\"\n]+)['\"]")
JS_CALL = re.compile(r"\b(?:require|import|jest\.mock|vi\.mock|require\.resolve)\s*\(\s*['\"]([^'\"\n]+)['\"]\s*[,)]")
JS_DYNAMIC = re.compile(r"\b(?:import|require)\s*\(\s*(?!['\"])[^)\s]")

VIOLATION, WIDENED, KNOWN, WAIVED, UPDATE, INFO = "VIOLATION", "WIDENED", "KNOWN-CONFLICT", "WAIVED", "MODEL-UPDATE", "INFO"
ORDER = [VIOLATION, WIDENED, KNOWN, WAIVED, UPDATE, INFO]


# ----------------------------------------------------------------------------------------------- helpers
def slurp(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_date(s):
    try:
        return datetime.date.fromisoformat(s.strip())
    except ValueError:
        return None


def norm_glob(p):
    p = p.strip()
    if p.startswith("./"):
        p = p[2:]
    if p.endswith("/"):
        p += "**"
    elif not any(c in p for c in "*?{") and "." not in p.rsplit("/", 1)[-1]:
        p += "/**"  # a bare directory name means everything under it
    return p


def glob_re(pattern):
    return re.compile("^" + _glob_body(norm_glob(pattern)) + "$")


def _glob_body(p):
    out, i = "", 0
    while i < len(p):
        if p.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif p.startswith("/**", i) and i + 3 == len(p):
            out, i = out + "(?:/.*)?", i + 3
        elif p.startswith("**", i):
            out, i = out + ".*", i + 2
        elif p[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif p[i] == "?":
            out, i = out + "[^/]", i + 1
        elif p[i] == "{" and "}" in p[i:]:
            j = p.index("}", i)
            alts = [_glob_body(a) for a in p[i + 1:j].split(",")]
            out, i = out + "(?:" + "|".join(alts) + ")", j + 1
        else:
            out, i = out + re.escape(p[i]), i + 1
    return out


def literal_prefix(pattern):
    p = norm_glob(pattern)
    cut = min([p.find(c) for c in "*?{" if c in p] or [len(p)])
    return p[:cut]


def specificity(pattern):
    p = norm_glob(pattern)
    return 10**9 if not any(c in p for c in "*?") else len(literal_prefix(p))


_JS_TOKENS = re.compile(r"""("(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`)|//[^\n]*|/\*.*?\*/""", re.S)


def strip_js(text):
    """Remove // and /* */ comments while keeping strings (import specifiers live in strings). One regex pass."""
    return _JS_TOKENS.sub(lambda mt: mt.group(1) if mt.group(1) is not None else "\n" * mt.group(0).count("\n"), text)


_BINOPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
           ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
           ast.Pow: lambda a, b: a ** b}


def eval_number(node):
    """Evaluate a numeric literal expression (numbers and + - * / // % **). Raises ValueError otherwise."""
    if isinstance(node, ast.Expression):
        return eval_number(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = eval_number(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](eval_number(node.left), eval_number(node.right))
    raise ValueError("not a numeric literal expression")


def js_number(expr):
    e = re.sub(r"\s+as\s+const\s*$", "", expr.strip().rstrip(";").strip())
    e = re.sub(r"(?<=\d)_(?=\d)", "", e)
    return eval_number(ast.parse(e, mode="eval"))


# ----------------------------------------------------------------------------------------------- model view
class Model:
    def __init__(self, g):
        self.g = g
        self.nodes = {n["id"]: n for n in g["nodes"]}
        self.kind = {i: n["kind"] for i, n in self.nodes.items()}
        self.header = g["header"]
        self.mode = self.header.get("mode", "reverse")
        self.anc = {}
        for nid in self.nodes:
            chain, p = [nid], self.nodes[nid].get("parent")
            while p:
                chain.append(p)
                p = self.nodes[p].get("parent")
            self.anc[nid] = chain            # self first, then ancestors
        self.anc_set = {k: set(v) for k, v in self.anc.items()}
        self.override = None                 # (scope_id or None, authority) used by the gates

    def attrs(self, nid, key):
        return self.nodes[nid].get("attrs", {}).get(key, [])

    def attr(self, nid, key, default=None):
        v = self.attrs(nid, key)
        return v[-1] if v else default

    def under(self, a, b):                   # a is b or inside b
        return b in self.anc_set[a]

    def layer(self, nid):
        k = self.kind[nid]
        return "intent" if k in INTENT else "arch" if k in ARCH else "logic" if k in LOGIC else None

    def authority_info(self, nid):
        if self.override:
            scope, value = self.override
            if (scope is None or self.under(nid, scope)) and self.layer(nid) in ("intent", "arch"):
                return value, "gate simulation"
        for x in self.anc[nid]:
            a = self.attrs(x, "authority")
            if a:
                return a[-1], ("explicit" if x == nid else f"inherited from {x}")
        k = self.kind[nid]
        if k == "test":
            return "source", "tests follow the code"
        if k in {"conflict", "side", "deviation"}:
            return "model", "governance records"
        return PRESETS[self.mode][self.layer(nid)], f"mode {self.mode} preset for {self.layer(nid)}"

    def authority(self, nid):
        return self.authority_info(nid)[0]

    def ref(self, r, kind=None):
        return resolve(r, set(self.kind), kind, self.kind)[0]


# ----------------------------------------------------------------------------------------------- code scanning
def list_code_files(root):
    files = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for n in names:
            if n.endswith(CODE_EXT):
                files.append(os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/"))
    return sorted(files)


def scan_specs(path, rel):
    """Raw import specifiers of one file, plus blind-spot counts. Deterministic, no resolution."""
    text = slurp(path)
    if rel.endswith(".py"):
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return {"specs": [], "blind": {"python syntax error": 1}}
        specs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                specs += [["py", a.name, 0, []] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                specs.append(["py", node.module or "", node.level, [a.name for a in node.names]])
            elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in ("import_module", "__import__"):
                specs.append(["blind", "dynamic python import"])
        return {"specs": specs, "blind": {}}
    code = strip_js(text)
    found = JS_STATIC.findall(code) + JS_SIDE.findall(code) + JS_CALL.findall(code)
    seen, specs = set(), []
    for s in found:
        if s not in seen:
            seen.add(s)
            specs.append(["js", s])
    dyn = len(JS_DYNAMIC.findall(code))
    return {"specs": specs, "blind": {"computed dynamic import": dyn} if dyn else {}}


def load_tsconfig_aliases(root, repo_root, explicit=None):
    """[(prefix, has_wildcard, [root-relative targets])] from tsconfig 'paths' (follows 'extends')."""
    cands = [explicit] if explicit else [os.path.join(root, "tsconfig.json"), os.path.join(repo_root, "tsconfig.json"),
                                         os.path.join(root, "tsconfig.base.json"), os.path.join(repo_root, "tsconfig.base.json")]
    for path in cands:
        if path and os.path.exists(path):
            break
    else:
        return []
    aliases, seen = [], set()
    while path and os.path.exists(path) and path not in seen:
        seen.add(path)
        try:
            cfg = json.loads(re.sub(r",(\s*[}\]])", r"\1", strip_js(slurp(path))))
        except ValueError:
            break
        opts = cfg.get("compilerOptions", {})
        base = os.path.join(os.path.dirname(path), opts.get("baseUrl", "."))
        for key, targets in (opts.get("paths") or {}).items():
            if any(a[0] == key.rstrip("*") for a in aliases):
                continue  # a nearer config already defined it
            rel_targets = [os.path.relpath(os.path.normpath(os.path.join(base, t)), root).replace(os.sep, "/") for t in targets]
            aliases.append((key.rstrip("*"), key.endswith("*"), rel_targets))
        ext = cfg.get("extends")
        path = os.path.normpath(os.path.join(os.path.dirname(path), ext)) if isinstance(ext, str) and ext.startswith(".") else None
        if path and not path.endswith(".json"):
            path += ".json"
    aliases.sort(key=lambda a: -len(a[0]))
    return aliases


class Resolver:
    def __init__(self, files, aliases):
        self.files = set(files)
        self.aliases = aliases
        tops = set()
        for f in files:  # python roots: parents of top-level packages, plus the code root
            if f.endswith("/__init__.py"):
                d = f.rsplit("/", 1)[0]
                parent = d.rsplit("/", 1)[0] if "/" in d else ""
                if (parent + "/__init__.py" if parent else "__init__.py") not in self.files:
                    tops.add(parent)
        self.py_roots = sorted(tops | {""})

    def try_file(self, base):
        base = base.lstrip("/")
        for ext, alts in JS_TO_TS.items():
            if base.endswith(ext):
                for a in alts:
                    if base[: -len(ext)] + a in self.files:
                        return base[: -len(ext)] + a
        for t in TS_TRY:
            if base + t in self.files:
                return base + t
        return None

    def resolve(self, rel, spec):
        """-> list of ('file', path) | ('ext', module) | ('missing', spec)"""
        if spec[0] == "blind":
            return []
        if spec[0] == "js":
            s = spec[1]
            if os.path.splitext(s.split("?")[0])[1].lower() in ASSET_EXT:
                return [("asset", s)]
            if s.startswith("."):
                hit = self.try_file(os.path.normpath(os.path.join(os.path.dirname(rel), s)).replace(os.sep, "/"))
                return [("file", hit)] if hit else [("missing", s)]
            for prefix, wild, targets in self.aliases:
                if (wild and s.startswith(prefix)) or (not wild and s == prefix):
                    rest = s[len(prefix):] if wild else ""
                    for t in targets:
                        hit = self.try_file(t.replace("*", rest) if wild else t)
                        if hit:
                            return [("file", hit)]
                    return [("missing", s)]
            if s.startswith(("@/", "~/", "#")):
                return [("missing", s)]
            parts = s.split("/")
            return [("ext", "/".join(parts[:2]) if s.startswith("@") else parts[0])]
        _, mod, level, names = spec
        if level:
            base = os.path.dirname(rel)
            for _ in range(level - 1):
                base = os.path.dirname(base)
            bases = [(base + "/" if base else "") + mod.replace(".", "/") if mod else base]
        else:
            bases = [(r + "/" if r else "") + mod.replace(".", "/") for r in self.py_roots]
        out = []
        for b in bases:
            b = b.strip("/")
            for name in names:
                for c in (f"{b}/{name}.py", f"{b}/{name}/__init__.py"):
                    if name != "*" and c.lstrip("/") in self.files:
                        out.append(("file", c.lstrip("/")))
            if not out:
                for c in (b + ".py", b + "/__init__.py"):
                    if c in self.files:
                        out.append(("file", c))
                        break
            if out:
                return out
        if level:
            return [("missing", "." * level + mod)]
        return [("ext", mod.split(".")[0])]


def load_deps_file(path, root, files):
    """Normalize dependency-cruiser / madge / plain edge lists to {file: [('file', f) | ('ext', m)]}."""
    data = json.loads(slurp(path))
    fileset = set(files)

    def norm(p):
        p = p.replace("\\", "/")
        if os.path.isabs(p):
            p = os.path.relpath(p, root).replace(os.sep, "/")
        p = p[2:] if p.startswith("./") else p
        parts = p.split("/")
        for k in range(len(parts)):
            cand = "/".join(parts[k:])
            if cand in fileset:
                return cand
        return None

    out = {}
    def add(a, b, ext=None):
        fa = norm(a)
        if not fa:
            return
        fb = norm(b) if b else None
        out.setdefault(fa, []).append(("file", fb) if fb else ("ext", ext or b))
    if isinstance(data, dict) and "modules" in data:            # dependency-cruiser
        for m in data["modules"]:
            out.setdefault(norm(m.get("source", "")) or "", [])
            for d in m.get("dependencies", []):
                internal = not d.get("coreModule") and not d.get("couldNotResolve") and \
                    not any(t.startswith(("npm", "core")) for t in d.get("dependencyTypes", []))
                add(m["source"], d.get("resolved") if internal else None, d.get("module"))
        out.pop("", None)
    elif isinstance(data, dict) and "edges" in data:
        for e in data["edges"]:
            add(e["from"], e["to"])
    elif isinstance(data, dict):                                  # madge
        for a, bs in data.items():
            for b in bs:
                add(a, b)
    else:
        for a, b in data:
            add(a, b)
    return out


# ----------------------------------------------------------------------------------------------- checks
class Ctx:
    def __init__(self, model_path, today, changed, cache_path, deps_path):
        self.model_path = model_path
        self.model_dir = os.path.dirname(os.path.abspath(model_path))
        self.today = today
        self.changed = changed
        self.cache_path = cache_path
        self.deps_path = deps_path


def build_allowed(m):
    """The single definition of 'allowed', shared by the validator and the config exporters."""
    g = m.g
    perms = []
    for e in g["edges"]:
        a, b = e.get("from_id"), e.get("to_id")
        if not (a and b) or e["rel"] not in DEP_RELS or e.get("origin") == "inferred":
            continue
        if m.kind[a] in PERMIT_KINDS and m.kind[b] in PERMIT_KINDS:
            perms.append((a, b))
            if e["rel"] == "implements":
                perms.append((b, a))   # an interface module may call its implementers
        elif m.kind[a] == "test" and e["rel"] == "verifies":
            perms.append((a, b))
    exposes = {}
    for e in g["edges"]:
        if e["rel"] == "exposes" and e.get("from_id") and e.get("to_id") and e.get("origin") != "inferred":
            exposes.setdefault(e["from_id"], set()).add(e["to_id"])
    perms_from = {}
    for x, y in perms:
        for a in m.anc[x]:
            perms_from.setdefault(a, []).append((x, y))
    memo = {}

    def allowed(a, b):
        if (a, b) in memo:
            return memo[(a, b)]
        ok = m.under(a, b) or m.under(b, a)  # inside one element (the pass-through closure handles barrels)
        if not ok:
            for x, y in perms_from.get(a, []):
                if m.under(b, y):
                    if b == y or any(m.under(b, e) for e in exposes.get(y, ())):
                        ok = True
                        break
                elif m.under(y, b):
                    ok = True
                    break
        memo[(a, b)] = ok
        return ok
    allowed.exposes = exposes
    return allowed, perms


def check(m, ctx):
    """Run every check under the model's current authority function. Returns (findings, stats)."""
    findings = []
    stats = {"conforming": 0, "blind": {}}

    def add(cls, chk, msg, at=None, el=None, target=None):
        f = {"class": cls, "check": chk, "message": msg}
        if at:
            f["at"] = at
        if el:
            f["element"] = el
        if target:
            f["target"] = target
        findings.append(f)

    g = m.g
    root = os.path.normpath(os.path.join(ctx.model_dir, m.header.get("root", ".")))
    today = parse_date(ctx.today)

    # ---- 0. model integrity (fails CI in every mode)
    for sev, msg in lint(g):
        add(VIOLATION if sev == "error" else INFO, "integrity" if sev == "error" else "traces", msg)
    governance = any(m.attrs(n, "bind") or m.attrs(n, "check") or m.kind[n] == "deviation" for n in m.nodes)
    if governance and "mode" not in m.header:
        add(VIOLATION, "integrity", "the model has bindings, checks or deviations but no 'mode:' in the header")
    for nid, n in m.nodes.items():
        lc = m.attr(nid, "lifecycle")
        allowed_lc = LIFECYCLES.get(n["kind"], ELEMENT_LIFECYCLE if m.layer(nid) in ("arch", "logic") or n["kind"] == "req" else None)
        if lc and allowed_lc and lc not in allowed_lc:
            add(VIOLATION, "integrity", f"{nid}: lifecycle '{lc}' is not one of {sorted(allowed_lc)}")

    # ---- 1. ownership
    claims = []
    for nid, n in m.nodes.items():
        for pat in m.attrs(nid, "code"):
            claims.append((specificity(pat), len(m.anc[nid]), glob_re(pat), nid, False, literal_prefix(pat)))
        if n["kind"] == "test":
            for s in m.attrs(nid, "src"):
                sm = SRC_CODE.match(s)
                if sm:
                    claims.append((10**9 - 1, 0, glob_re(sm.group(1)), nid, True, sm.group(1)))
    claims.sort(key=lambda c: (c[0], c[1]), reverse=True)
    buckets = {}
    for rank, c in enumerate(claims):
        seg = c[5].split("/")[0] if "/" in c[5] else ""
        buckets.setdefault(seg, []).append((rank, c))
    files = list_code_files(root)
    owner, overlaps = {}, set()
    for f in files:
        cands = [c for _, c in sorted(buckets.get(f.split("/")[0], []) + buckets.get("", [])) if c[2].match(f)]
        if not cands:
            owner[f] = None
            continue
        owner[f] = cands[0][3]
        for c in cands[1:]:
            same_rank = c[0] == cands[0][0] and c[1] == cands[0][1] and c[3] != cands[0][3]
            test_steals = cands[0][4] is False and c[4] is True and cands[0][0] == 10**9
            if (same_rank or test_steals) and (cands[0][3], c[3]) not in overlaps:
                overlaps.add((cands[0][3], c[3]))
                why = "test src points at an implementation file" if test_steals else "equally specific code: globs"
                add(VIOLATION, "integrity", f"{f} is claimed by both {cands[0][3]} and {c[3]} ({why})")
    has_code_desc = {a for f, o in owner.items() if o for a in m.anc[o][1:]}  # elements whose parts own files

    # ---- 2. dependency edges (exported graph, or scan)
    changed_set = None
    if ctx.changed is not None:
        model_rel = os.path.basename(ctx.model_path)
        full = any(c.replace("\\", "/").endswith((model_rel, "tsconfig.json", "tsconfig.base.json")) for c in ctx.changed)
        if not full:
            changed_set = set()
            fileset = set(files)
            try:
                root_rel = os.path.relpath(root, os.getcwd()).replace(os.sep, "/")
            except ValueError:   # different drive (Windows)
                root_rel = root.replace(os.sep, "/")
            for c in ctx.changed:
                c = c.replace("\\", "/")
                c = c[2:] if c.startswith("./") else c
                try:
                    from_root = os.path.relpath(os.path.abspath(c), root).replace(os.sep, "/")
                except ValueError:
                    from_root = None
                cand = [c, c[len(root_rel) + 1:] if c.startswith(root_rel + "/") else None, from_root]
                hit = next((x for x in cand if x and x in fileset), None)
                if hit:
                    changed_set.add(hit)
                elif c.endswith(CODE_EXT) and os.path.exists(c):
                    add(VIOLATION, "coverage", f"changed file {c} is outside the code root {root_rel}")
                elif c.endswith(CODE_EXT):
                    pass  # deleted file: nothing to scan
    aliases = load_tsconfig_aliases(root, ctx.model_dir, os.path.join(ctx.model_dir, m.header["tsconfig"]) if "tsconfig" in m.header else None)
    resolver = Resolver(files, aliases)
    scan = [f for f in files if changed_set is None or f in changed_set]
    deps = {}
    if ctx.deps_path:
        deps = load_deps_file(ctx.deps_path, root, files)
        stats["source"] = f"dependency graph {os.path.basename(ctx.deps_path)}"
    else:
        cache = {}
        if ctx.cache_path and os.path.exists(ctx.cache_path):
            try:
                c = json.loads(slurp(ctx.cache_path))
                cache = c["files"] if c.get("v") == TOOL_VERSION else {}
            except (ValueError, KeyError):
                cache = {}
        for f in scan:
            st = os.stat(os.path.join(root, f))
            key = f"{st.st_mtime_ns}:{st.st_size}"
            if f not in cache or cache[f]["key"] != key:
                cache[f] = {"key": key, **scan_specs(os.path.join(root, f), f)}
            for k, v in cache[f]["blind"].items():
                stats["blind"][k] = stats["blind"].get(k, 0) + v
            deps[f] = [r for s in cache[f]["specs"] for r in resolver.resolve(f, s)]
        if ctx.cache_path:
            live = set(files)
            with open(ctx.cache_path, "w", encoding="utf-8") as fh:
                json.dump({"v": TOOL_VERSION, "files": {k: v for k, v in cache.items() if k in live}}, fh)
        stats["source"] = "regex/ast scan (fallback: prefer --deps from a dependency-graph tool)"
    for f, items in deps.items():
        for kind, t in items:
            if kind == "missing":
                stats["blind"]["unresolved import"] = stats["blind"].get("unresolved import", 0) + 1
    stats["files"], stats["scanned"] = len(files), len(scan) if not ctx.deps_path else len(deps)

    # ---- 3. permissions (architecture relations only; logic edges are observations)
    allowed, perms = build_allowed(m)

    # observed element-level dependencies, including through container-level (barrel) files
    observed, extra_deps = {}, {}
    def file_deps(f):
        if f in deps:
            return deps[f]
        if f not in extra_deps:  # pre-commit mode: a pass-through file that was not scanned
            extra_deps[f] = resolver_specs(f, root, resolver) if not ctx.deps_path else []
        return extra_deps[f]

    def note(a, b, ev):
        if a and b and a != b:
            observed.setdefault((a, b), []).append(ev)
    for f, items in deps.items():
        a = owner.get(f)
        for kind, t in items:
            if kind != "file" or not owner.get(t):
                continue
            note(a, owner[t], f"{f} -> {t}")
            tb = owner[t]
            if a and tb != a and m.under(a, tb) and tb in has_code_desc:   # upward hop into a pass-through file
                stack, seen = [t], {t}
                while stack:
                    cur = stack.pop()
                    for k2, t2 in file_deps(cur):
                        if k2 != "file" or t2 in seen or not owner.get(t2):
                            continue
                        seen.add(t2)
                        note(a, owner[t2], f"{f} -> {t} -> {t2}")
                        if owner[t2] == tb or (m.under(a, owner[t2]) and owner[t2] in has_code_desc):
                            stack.append(t2)

    waivers = []
    for nid, n in m.nodes.items():
        if n["kind"] != "deviation":
            continue
        exp_s, appr, lc = m.attr(nid, "expires"), m.attr(nid, "approved"), m.attr(nid, "lifecycle", "proposed")
        exp = parse_date(exp_s) if exp_s else None
        valid = True
        if exp_s and not exp:
            add(VIOLATION, "integrity", f"deviation {nid}: expires '{exp_s}' is not an ISO date (YYYY-MM-DD)")
            valid = False
        if not exp_s or not appr:
            valid = False  # missing fields are already integrity errors from lint
        if exp and today and (exp - today).days > HORIZON_DAYS:
            add(VIOLATION, "integrity", f"deviation {nid}: expires {exp_s} is more than {HORIZON_DAYS} days ahead")
            valid = False
        for al in n.get("allows", []):
            x, y = m.ref(al["from"]), m.ref(al["to"])
            if not x or not y:
                add(VIOLATION, "integrity", f"deviation {nid}: cannot resolve '{al['from']} {al['rel']} {al['to']}'")
                continue
            if al["rel"] not in DEP_RELS - {"verifies"}:
                add(VIOLATION, "integrity", f"deviation {nid}: '{al['rel']}' is not a dependency relation")
                continue
            if m.under(x, y) or m.under(y, x) or "system" in (m.kind[x], m.kind[y]):
                add(VIOLATION, "integrity", f"deviation {nid}: allows {x} {al['rel']} {y} is a blanket waiver")
                continue
            if "container" in (m.kind[x], m.kind[y]) and m.attr(nid, "breadth") != "wide":
                add(VIOLATION, "integrity", f"deviation {nid}: container-wide waiver needs 'breadth: wide'")
                continue
            active = valid and lc == "accepted" and exp and today and exp >= today
            waivers.append((x, y, nid, active, exp_s, lc))

    for (a, b), where in sorted(observed.items()):
        if allowed(a, b):
            stats["conforming"] += 1
            continue
        hit = [w for w in waivers if m.under(a, w[0]) and (m.under(b, w[1]) or m.under(w[1], b))]
        live = [w for w in hit if w[3]]
        if live:
            add(WAIVED, "architecture", f"{a} -> {b} waived by deviation {live[0][2]} (expires {live[0][4]})", where[0], a)
            continue
        for w in hit:
            why = f"expired on {w[4]}" if w[5] == "accepted" else f"is '{w[5]}', not accepted"
            add(VIOLATION, "architecture", f"deviation {w[2]} for {a} -> {b} {why}", where[0], a)
        strict = "model" in (m.authority(a), m.authority(b))
        tag = " (through " + where[0].split(" -> ")[1] + ")" if where[0].count("->") > 1 and len(where) == 1 else ""
        if strict:
            add(VIOLATION, "architecture", f"{a} depends on {b}, which the model does not allow{tag}", where[0], a, b)
        else:
            add(UPDATE, "architecture", f"{a} depends on {b} (both ends authority: source): add a relation or a deviation{tag}", where[0], a, b)

    if changed_set is None:
        coded = {o for o in owner.values() if o} | {a for o in owner.values() if o for a in m.anc[o]}
        def code_owner(n):
            return next((x for x in m.anc[n] if x in coded), None)
        realized = {(ax, ay) for (x, y) in observed for ax in m.anc[x] for ay in m.anc[y]}  # lifted to every level
        for e in g["edges"]:
            a, b = e.get("from_id"), e.get("to_id")
            if not (a and b) or e["rel"] not in DEP_RELS - {"exposes"}:
                continue
            ca, cb = code_owner(a), code_owner(b)
            if not ca or not cb or m.under(ca, cb) or m.under(cb, ca):
                continue
            if m.kind[a] in LOGIC and not allowed(ca, cb):
                add(INFO, "architecture", f"logic edge {a} {e['rel']} {b} implies {ca} -> {cb}, which the architecture does not allow")
            if m.kind[a] in PERMIT_KINDS and (ca, cb) not in realized and not (e["rel"] == "implements" and (cb, ca) in realized):
                add(INFO, "architecture", f"declared {a} {e['rel']} {b}, but no code dependency realizes it")

    # ---- 4. parameter bindings
    def const_value(path, name):
        p = os.path.join(root, path)
        if not os.path.exists(p):
            return None, "file not found"
        text = slurp(p)
        if path.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                return None, "python syntax error"
            vals = [n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
            vals += [n.value for n in tree.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == name and n.value]
            if not vals:
                return None, "not a top-level constant"
            if len(vals) > 1:
                return None, "assigned more than once at top level"
            try:
                return eval_number(vals[0]), None
            except ValueError:
                return None, "not statically evaluable"
        code = strip_js(text)
        decl = re.findall(r"(?m)^(?:export\s+)?(?:const|let|var)\s+" + re.escape(name) + r"\b\s*(?::[^=\n]+)?=\s*([^;\n]+)", code)
        reassigned = re.findall(r"(?m)^\s*" + re.escape(name) + r"\s*(?:[-+*/]?=)(?!=)", code)
        if not decl:
            return None, "not a top-level constant"
        if len(decl) > 1 or reassigned:
            return None, "assigned more than once"
        try:
            return js_number(decl[0]), None
        except (ValueError, SyntaxError):
            return None, "not statically evaluable"

    for nid in m.nodes:
        for b in m.attrs(nid, "bind"):
            req_ref, pname, path, const, op, k = BIND_RE.match(b).groups()
            req = m.ref(req_ref, "req")
            params = {}
            for p in (m.attrs(req, "param") if req else []):
                pm = PARAM_RE.match(p)
                params[pm.group(1)] = (float(pm.group(2)), pm.group(2), pm.group(3))
            if not req or pname not in params:
                add(VIOLATION, "integrity", f"{nid}: bind names unknown parameter {req_ref}.{pname}")
                continue
            val, why = const_value(path, const)
            if val is None:
                cls = VIOLATION if why == "file not found" else INFO
                add(cls, "parameters", f"{nid}: {path}#{const}: {why}")
                continue
            if op:
                val = val * float(k) if op == "*" else val / float(k)
            want, raw, unit = params[pname]
            label = f"{req}.{pname} = {raw}{(' ' + unit) if unit else ''} vs {path}#{const}{(' ' + op + ' ' + k) if op else ''} = {val:g}"
            if abs(val - want) <= 1e-9 * max(1.0, abs(want)):
                stats["conforming"] += 1
                continue
            suppress, note_ = None, ""
            for c, n in m.nodes.items():
                if n["kind"] != "conflict" or not any(e["rel"] == "about" and e.get("from_id") == c and e.get("to_id") in (req, nid) for e in g["edges"]):
                    continue
                lc = m.attr(c, "lifecycle", "open")
                exp = parse_date(m.attr(c, "expires", "") or "")
                asserted = [m.attr(s, "asserts") for s in m.nodes if m.nodes[s].get("parent") == c and m.attr(s, "asserts")]
                if lc != "accepted":
                    note_ = f" (conflict {c} is {lc}; only an accepted conflict suppresses)"
                elif not exp or not m.attr(c, "approved"):
                    add(VIOLATION, "integrity", f"conflict {c}: an accepted conflict needs 'expires:' (ISO date) and 'approved:'")
                elif today and exp < today:
                    note_ = f" (conflict {c} expired on {exp})"
                elif not any(abs(float(v) - val) <= 1e-9 * max(1.0, abs(val)) for v in asserted if re.match(r"^-?\d+(\.\d+)?$", v)):
                    note_ = f" (conflict {c} asserts {', '.join(asserted) or 'nothing'}; the code has moved)"
                else:
                    suppress = c
            if suppress:
                add(KNOWN, "parameters", f"{label} (conflict {suppress})", el=req)
            elif m.authority(req) == "model":
                add(VIOLATION, "parameters", f"{label}: code does not meet the requirement{note_}", el=req)
            else:
                add(UPDATE, "parameters", f"{label}: update the requirement parameter{note_}", el=req)

    # ---- 5. convention checks
    for nid in m.nodes:
        for chk in m.attrs(nid, "check"):
            cm = CHECK_ONLY.match(chk)
            if not cm:
                add(VIOLATION, "integrity", f"{nid}: unknown check syntax '{chk}' (supported: only <glob> imports <module>)")
                continue
            ok_glob, module = glob_re(cm.group(1)), cm.group(2)
            for f, items in deps.items():
                if ok_glob.match(f):
                    continue
                if any(k == "ext" and (t == module or t.startswith(module + "/") or t.startswith(module + ".")) for k, t in items):
                    add(VIOLATION if m.authority(nid) == "model" else UPDATE, "conventions",
                        f"{f} imports {module}, but {nid} allows only {cm.group(1)}", el=nid)

    # ---- 6. provenance of code references
    for nid in m.nodes:
        for s in m.attrs(nid, "src"):
            sm = SRC_CODE.match(s)
            if not sm:
                continue
            p = os.path.join(root, sm.group(1))
            if not os.path.exists(p):
                add(VIOLATION if m.authority(nid) == "model" else UPDATE, "provenance", f"{nid}: src {s} does not exist (stale)", el=nid)
            elif sm.group(2) and int(sm.group(2)) > slurp(p).count("\n") + 1:
                add(UPDATE, "provenance", f"{nid}: src {s} points past the end of the file (stale)", el=nid)

    # ---- 7. coverage (class from the nearest element's authority)
    if changed_set is None:
        for f in files:
            if owner[f]:
                continue
            near = max(((len(c[5]), c[3]) for c in claims if not c[4] and f.startswith(c[5].rsplit("/", 1)[0] + "/" if "/" in c[5] else "")),
                       default=(0, None))[1]
            auth = m.authority(near) if near else PRESETS[m.mode]["arch"]
            add(VIOLATION if auth == "model" else UPDATE, "coverage", f"{f} is not claimed by any element (add a code: glob)", el=near)

    return findings, stats


def resolver_specs(f, root, resolver):
    return [r for s in scan_specs(os.path.join(root, f), f)["specs"] for r in resolver.resolve(f, s) if r[0] == "file"]


# ----------------------------------------------------------------------------------------------- diff, gates
def permissions(m):
    p = set()
    for e in m.g["edges"]:
        a, b = e.get("from_id"), e.get("to_id")
        if a and b and e["rel"] in DEP_RELS and e.get("origin") != "inferred" and \
                (m.kind[a] in PERMIT_KINDS and m.kind[b] in PERMIT_KINDS or (m.kind[a] == "test" and e["rel"] == "verifies")):
            p.add((a, e["rel"], b))
    return p


def diff_widening(m_old, m_new):
    out = []
    for a, rel, b in sorted(permissions(m_new) - permissions(m_old)):
        out.append(f"new permission: {a} {rel} {b}")
    def devs(m):
        return {nid: (m.attr(nid, "expires"), m.attr(nid, "lifecycle"), tuple((x["from"], x["rel"], x["to"]) for x in m.nodes[nid].get("allows", [])))
                for nid in m.nodes if m.kind[nid] == "deviation"}
    od, nd = devs(m_old), devs(m_new)
    for nid, (exp, lc, al) in sorted(nd.items()):
        if nid not in od:
            out.append(f"new deviation {nid} (expires {exp})")
        else:
            oexp, olc, oal = od[nid]
            if (exp or "") > (oexp or ""):
                out.append(f"deviation {nid} extended from {oexp} to {exp}")
            if set(al) - set(oal):
                out.append(f"deviation {nid} allows more: {sorted(set(al) - set(oal))}")
            if lc == "accepted" and olc != "accepted":
                out.append(f"deviation {nid} became accepted")
    for nid in sorted(m_new.nodes):
        if nid in m_old.nodes and m_old.authority(nid) == "model" and m_new.authority(nid) == "source":
            out.append(f"authority of {nid} lowered from model to source")
        if m_new.kind[nid] == "conflict" and m_new.attr(nid, "lifecycle") == "accepted" and \
                (nid not in m_old.nodes or m_old.attr(nid, "lifecycle") != "accepted" or (m_new.attr(nid, "expires") or "") > (m_old.attr(nid, "expires") or "")):
            out.append(f"conflict {nid} newly accepted or extended")
    for key in ("check", "bind", "param"):
        for nid in m_old.nodes:
            lost = set(m_old.attrs(nid, key)) - set(m_new.attrs(nid, key) if nid in m_new.nodes else [])
            for v in sorted(lost):
                out.append(f"removed {key} on {nid}: {v}")
    return out


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, encoding="utf-8")


def gate(m, ctx, kind, scope, findings_now):
    """Return (blockers, report). adopt: simulate model authority; rebaseline: list what loses enforcement."""
    in_scope = (lambda n: True) if scope is None else (lambda n: m.under(n, scope))
    if kind == "rebaseline":
        report = []
        for nid, n in m.nodes.items():
            if n["kind"] == "deviation" and any(in_scope(m.ref(a["from"]) or "") for a in n.get("allows", []) if m.ref(a["from"])):
                report.append(f"deviation {nid} would no longer be enforced")
            if n["kind"] == "conflict" and any(e["rel"] == "about" and e.get("from_id") == nid and e.get("to_id") and in_scope(e["to_id"]) for e in m.g["edges"]):
                report.append(f"conflict {nid} would no longer be enforced")
            if in_scope(nid) and (m.attrs(nid, "bind") or m.attrs(nid, "check")):
                report.append(f"{nid}: bindings/checks become informational")
        return ([] if ctx.reason else ["rebaseline needs --reason"]), report
    m.override = (scope, "model")
    sim, _ = check(m, ctx)
    m.override = None
    blockers = [f"{f['check']}: {f['message']}" for f in sim if f["class"] == VIOLATION]
    blockers += [f"{f['check']}: {f['message']} (the model is behind the code)" for f in sim
                 if f["class"] == UPDATE and (f.get("element") is None or in_scope(f["element"]))]
    for nid, n in m.nodes.items():
        if not in_scope(nid) or m.layer(nid) not in ("intent", "arch"):
            continue
        if n.get("origin") == "inferred":
            blockers.append(f"{nid}: inferred {n['kind']} must be reviewed (stated) or removed")
        for c in n.get("contract", []):
            if c.get("origin") == "inferred":
                blockers.append(f"{nid}: inferred clause '{c['clause']}: {c['expr']}' must be reviewed")
    for e in m.g["edges"]:
        if e.get("origin") == "inferred" and e.get("from_id") and in_scope(e["from_id"]) and m.layer(e["from_id"]) in ("intent", "arch"):
            blockers.append(f"inferred relation {e['from_id']} {e['rel']} {e['to']} must be reviewed")
    for nid, n in m.nodes.items():
        if n["kind"] == "conflict" and m.attr(nid, "lifecycle", "open") == "open" and \
                any(e["rel"] == "about" and e.get("from_id") == nid and e.get("to_id") and in_scope(e["to_id"]) for e in m.g["edges"]):
            blockers.append(f"conflict {nid} is open: resolve it, or accept it with expires/approved")
    return sorted(set(blockers)), []


def apply_gate(ctx, m, kind, scope, baseline):
    text = slurp(ctx.model_path)
    lines = text.split("\n")
    value = "model" if kind == "adopt" else "source"
    if scope is None:
        h = lines[0]
        h = re.sub(r"\s+mode:\s*\S+", "", h)
        h = re.sub(r"\s+baseline:\s*\S+", "", h)
        lines[0] = h + f" mode: {'forward' if kind == 'adopt' else 'reverse'}" + (f" baseline: {baseline}" if baseline else "")
    else:
        ln = m.nodes[scope]["line"] - 1
        indent = len(lines[ln]) - len(lines[ln].lstrip(" ")) + 2
        j, replaced = ln + 1, False
        while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip(" ")) >= indent):
            if lines[j].strip().startswith("authority:") and len(lines[j]) - len(lines[j].lstrip(" ")) == indent:
                lines[j] = " " * indent + f"authority: {value}"
                replaced = True
                break
            j += 1
        if not replaced:
            lines.insert(ln + 1, " " * indent + f"authority: {value}")
    while lines and not lines[-1].strip():
        lines.pop()
    if not any(l.startswith("# ---------- adoption log") for l in lines):
        lines += ["", "# ---------- adoption log (append-only; written by ucn_validate.py --apply) ----------"]
    extra = f" reason: {ctx.reason}" if ctx.reason else ""
    lines.append(f"# {ctx.today} {kind} scope: {scope or '(whole model)'} baseline: {baseline or '-'}{extra}")
    with open(ctx.model_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------------------------- entry points
def validate(model_path, today=None, gate_kind=None, scope=None, changed=None, cache_path=None, deps_path=None,
             diff_rev=None, allow_widening=False, apply=False, baseline=None, reason=None):
    t0 = time.perf_counter()
    m = Model(parse(slurp(model_path)))
    ctx = Ctx(model_path, today or datetime.date.today().isoformat(), changed, cache_path, deps_path)
    ctx.reason = reason
    findings, stats = check(m, ctx)
    widened = []
    if diff_rev:
        rel = os.path.relpath(os.path.abspath(model_path), git(ctx.model_dir, "rev-parse", "--show-toplevel").stdout.strip() or ctx.model_dir)
        old = git(ctx.model_dir, "show", f"{diff_rev}:{rel.replace(os.sep, '/')}")
        if old.returncode != 0:
            findings.append({"class": INFO, "check": "diff", "message": f"no model at {diff_rev}; nothing to compare"})
        else:
            widened = diff_widening(Model(parse(old.stdout)), m)
            for w in widened:
                findings.append({"class": INFO if allow_widening else WIDENED, "check": "diff",
                                 "message": w + (" (approved via --allow-widening)" if allow_widening else "")})
    scope_id = m.ref(scope) if scope else None
    if scope and not scope_id:
        raise UcnError(f"--scope {scope}: no such node")
    gate_res = None
    if gate_kind:
        blockers, report = gate(m, ctx, gate_kind, scope_id, findings)
        gate_res = {"name": gate_kind, "scope": scope_id, "blockers": blockers, "report": report, "pass": not blockers}
        if apply and not blockers:
            base = baseline or git(ctx.model_dir, "rev-parse", "--short", "HEAD").stdout.strip() or None
            if gate_kind == "adopt" and not base:
                gate_res["blockers"].append("--apply needs --baseline (not a git repository)")
                gate_res["pass"] = False
            else:
                apply_gate(ctx, m, gate_kind, scope_id, base)
                gate_res["applied"] = {"baseline": base}
    return {"model": model_path, "mode": m.mode, "baseline": m.header.get("baseline"), "today": ctx.today,
            **stats, "findings": findings, "gate": gate_res, "ms": round((time.perf_counter() - t0) * 1000, 1),
            "_model": m}


def propose(m, findings, include_violations=False):
    """Deterministic model update: the 'uses' lines that would make observed dependencies conforming.
    Only MODEL-UPDATE findings by default (code is authoritative); violations need a human decision."""
    wanted = {}
    for f in findings:
        if f["check"] == "architecture" and f.get("target") and (f["class"] == UPDATE or (include_violations and f["class"] == VIOLATION)):
            wanted.setdefault(f["element"], set()).add(f["target"])
    out = []
    for a in sorted(wanted, key=lambda n: m.nodes[n]["line"]):
        names = sorted(t.rsplit(".", 1)[-1] if m.ref(t.rsplit(".", 1)[-1]) == t else t for t in wanted[a])
        out.append(f"# under {m.kind[a]} {a} (line {m.nodes[a]['line']}):")
        out.append(f"uses {', '.join(names)}")
    return out or ["# nothing to propose"]


def authority_map(m):
    rows = []
    for nid in sorted(m.nodes, key=lambda n: m.nodes[n]["line"]):
        if m.kind[nid] == "side":
            continue
        a, why = m.authority_info(nid)
        rows.append(f"{'  ' * (len(m.anc[nid]) - 1)}{m.kind[nid]} {nid}: {a}  ({why})")
    return rows


def main(argv):
    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None
    changed = None
    if "--changed" in argv:
        changed = []
        for a in argv[argv.index("--changed") + 1:]:
            if a.startswith("--"):
                break
            changed.append(a)
    r = validate(argv[1], today=opt("--today"), gate_kind=opt("--gate"), scope=opt("--scope"), changed=changed,
                 cache_path=opt("--cache"), deps_path=opt("--deps"), diff_rev=opt("--diff"),
                 allow_widening="--allow-widening" in argv, apply="--apply" in argv, baseline=opt("--baseline"),
                 reason=opt("--reason"))
    m = r.pop("_model")
    if "--authority-map" in argv:
        print("\n".join(authority_map(m)))
        return 0
    if "--propose" in argv:
        print("\n".join(propose(m, r["findings"], "--include-violations" in argv)))
        return 0
    if "--json" in argv:
        print(json.dumps(r, indent=2))
    else:
        limit = int(opt("--max") or 40)
        print(f"{r['model']}: mode {r['mode']}, baseline {r['baseline']}, {r['files']} code files "
              f"({r['scanned']} scanned via {r['source']}), {r['conforming']} conforming dependencies/bindings, {r['ms']} ms")
        for cls in ORDER:
            items = [x for x in r["findings"] if x["class"] == cls]
            for f in items[:limit]:
                at = f"  [{f['at']}]" if "at" in f else ""
                print(f"  {cls:<14} {f['check']:<12} {f['message']}{at}")
            if len(items) > limit:
                print(f"  {cls:<14} ... and {len(items) - limit} more")
        counts = {c: sum(1 for f in r["findings"] if f["class"] == c) for c in ORDER}
        print("  summary: " + ", ".join(f"{v} {k.lower()}" for k, v in counts.items()))
        if r["blind"]:
            print("  blind spots: " + ", ".join(f"{v} {k}" for k, v in sorted(r["blind"].items())))
        if r["gate"]:
            gr = r["gate"]
            print(f"  gate {gr['name']} (scope: {gr['scope'] or 'whole model'}): {'PASS' if gr['pass'] else 'BLOCKED'}")
            for b in gr["blockers"][:limit]:
                print(f"    blocker: {b}")
            if len(gr["blockers"]) > limit:
                print(f"    ... and {len(gr['blockers']) - limit} more blockers")
            for x in gr["report"]:
                print(f"    loses enforcement: {x}")
            if gr.get("applied"):
                print(f"    applied: model updated, baseline {gr['applied']['baseline']}")
    bad = any(f["class"] in (VIOLATION, WIDENED) for f in r["findings"]) or (r["gate"] and not r["gate"]["pass"])
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except UcnError as e:
        print("error:", e)
        sys.exit(2)
