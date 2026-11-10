"""Compile a UCN model's architecture rules into configs for existing checkers, so the model is the single
source of truth instead of a second rules file.

Usage:
  python tools/ucn_export.py MODEL.ucn --to dependency-cruiser [--today YYYY-MM-DD] > .dependency-cruiser.js
  python tools/ucn_export.py MODEL.ucn --to import-linter --package PKG [--today YYYY-MM-DD] > .importlinter

Semantics are the validator's (tools/ucn_validate.py build_allowed): permissions come only from non-inferred
architecture relations, `implements` works both ways, entering another element requires `exposes`, and active
deviations become allowed exceptions (re-generate before they expire: neither tool knows about expiry).
Conventions with `check: only <glob> imports <module>` become forbidden rules.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ucn_parse import parse  # noqa: E402
from ucn_validate import (CHECK_ONLY, SRC_CODE, Ctx, Model, build_allowed, check, glob_re, list_code_files,  # noqa: E402
                          waiver_covers,
                          literal_prefix, norm_glob, parse_date, slurp)

EXTERNAL_TYPES = ["npm", "npm-dev", "npm-optional", "npm-peer", "npm-bundled", "npm-no-pkg", "core", "unknown",
                  "undetermined"]   # not "type-only": that type also marks internal type imports


def _elements(m):
    """Coded elements -> list of globs (code: and, for tests, src: files)."""
    out = {}
    for nid, n in m.nodes.items():
        globs = list(m.attrs(nid, "code"))
        if n["kind"] == "test":
            globs += [SRC_CODE.match(s).group(1) for s in m.attrs(nid, "src") if SRC_CODE.match(s)]
        if globs:
            out[nid] = globs
    return out


def _active_deviations(m, today):
    out = []
    for nid, n in m.nodes.items():
        if n["kind"] != "deviation" or m.attr(nid, "lifecycle") != "accepted" or not m.attr(nid, "approved"):
            continue
        exp = parse_date(m.attr(nid, "expires", "") or "")
        if not exp or exp < today:
            continue
        for al in n.get("allows", []):
            x, y = m.ref(al["from"]), m.ref(al["to"])
            if x and y:
                out.append((x, y, nid, exp.isoformat()))
    return out


def element_pairs(m, today):
    """All (a, b) coded-element pairs the model allows, plus waived pairs with their deviation."""
    els = _elements(m)
    allowed, _ = build_allowed(m)
    devs = _active_deviations(m, today)
    allow, waived = [], []
    for a in els:
        for b in els:
            if a == b:
                continue
            if allowed(a, b) and not allowed.forbidden(a, b):
                allow.append((a, b))
            else:
                w = next((d for d in devs if m.under(a, d[0]) and waiver_covers(m, b, d[1])), None)
                if w:
                    waived.append((a, b, w[2], w[3]))
    return els, allow, waived


_META = set(".^$*+?()[]{}|\\")


def _esc(s):
    return "".join("\\" + c if c in _META else c for c in s)


def _dc_glob(p):
    """Glob -> regex body without nested quantifiers (dependency-cruiser rejects 'unsafe' regexes).
    'dir/**' becomes a plain prefix; '**/' becomes '.*' (slightly broader than zero-or-more directories)."""
    p = norm_glob(p)
    if p.endswith("/**") and not any(c in p[:-3] for c in "*?{"):
        return _esc(p[:-3]) + "/"
    return _dc_body(p) + "$"


def _dc_body(p):
    out, i = "", 0
    while i < len(p):
        if p.startswith("**", i):
            out, i = out + ".*", i + (3 if p.startswith("**/", i) else 2)
        elif p[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif p[i] == "?":
            out, i = out + "[^/]", i + 1
        elif p[i] == "{" and "}" in p[i:]:
            j = p.index("}", i)
            out, i = out + "(?:" + "|".join(_dc_body(a) for a in p[i + 1:j].split(",")) + ")", j + 1
        else:
            out, i = out + _esc(p[i]), i + 1
    return out


def _rx(globs, prefix):
    parts = [_dc_glob(g) for g in globs]
    return "^" + _esc(prefix) + ("(?:" + "|".join(parts) + ")" if len(parts) > 1 else parts[0])


def to_dependency_cruiser(m, model_path, today):
    root = m.header.get("root", ".")
    prefix = "" if root in (".", "") else norm_glob(root).rstrip("*").rstrip("/") + "/"
    els, allow, waived = element_pairs(m, today)

    def own(e):
        """Files owned by e: its globs minus the globs of coded descendants."""
        desc = [g for d, gs in els.items() if d != e and m.under(d, e) for g in gs]
        r = {"path": _rx(els[e], prefix)}
        if desc:
            r["pathNot"] = _rx(desc, prefix)
        return r

    def full(e):
        return _rx([g for d, gs in els.items() if m.under(d, e) for g in gs], prefix)

    allowed, _ = build_allowed(m)
    deny = m.header.get("policy", "allow") == "deny"
    rules = [{"comment": "external packages and node core modules (conventions below restrict some)",
              "from": {}, "to": {"dependencyTypes": EXTERNAL_TYPES}}]
    for e in sorted(els):
        rules.append({"comment": f"{e}: within itself", "from": own(e), "to": own(e)})
    for a, b in sorted(allow):
        rules.append({"comment": f"{a} -> {b}", "from": own(a), "to": own(b)})
    for a, b, dev, exp in sorted(waived):
        rules.append({"comment": f"{a} -> {b}: deviation {dev}, expires {exp} (re-generate before then)",
                      "from": own(a), "to": own(b)})
    forbidden = []
    for x, y, reason in allowed.forb:
        if not any(m.under(d, x) for d in els) or not any(m.under(d, y) for d in els):
            continue
        exempt = sorted({w[0] for w in waived if m.under(w[0], x) and m.under(w[1], y)})
        frm = {"path": full(x)}
        if exempt:
            frm["pathNot"] = _rx([g for e in exempt for g in els[e]], prefix)
        forbidden.append({"name": f"ucn-forbid-{x}-{y}".replace(".", "-"), "severity": "error",
                          "comment": reason + (f" (waived sources exempt: {', '.join(exempt)}; coarser than the deviation)" if exempt else ""),
                          "from": frm, "to": {"path": full(y)}})
    for nid in m.nodes:
        if (m.attr(nid, "acyclic") or "").lower() in ("yes", "true") and any(m.under(d, nid) for d in els):
            forbidden.append({"name": f"ucn-acyclic-{nid}".replace(".", "-"), "severity": "error",
                              "comment": f"{nid} must be acyclic", "from": {"path": full(nid)},
                              "to": {"path": full(nid), "circular": True}})
    for nid in m.nodes:
        for chk in m.attrs(nid, "check"):
            cm = CHECK_ONLY.match(chk)
            if cm:
                forbidden.append({"name": f"ucn-{nid}".replace(".", "-"), "comment": f"{nid}: {chk}", "severity": "error",
                                  "from": {"pathNot": _rx([cm.group(1)], prefix)},
                                  "to": {"path": "(^|/)node_modules/" + re.escape(cm.group(2)) + "(/|$)"}})
    cfg = {"forbidden": forbidden, "options": {"doNotFollow": {"path": "node_modules"}, "tsPreCompilationDeps": True}}
    if not deny:  # allow-list policy: everything not listed is an error
        cfg = {"allowedSeverity": "error", "allowed": rules, **cfg}
    return (f"/** Generated by tools/ucn_export.py from {os.path.basename(model_path)} on {today}. Do not edit:\n"
            f" *  change the model and re-generate. Deviations expire; re-generate before the earliest expiry. */\n"
            f"module.exports = {json.dumps(cfg, indent=2)};\n")


def _module(glob, package):
    """'pkg/src/app/a/**' -> 'app.a'; 'app/a/x.py' -> 'app.a.x' (the module path from the root package on)."""
    lit = literal_prefix(glob).rstrip("/")
    lit = re.sub(r"(/__init__)?\.py$", "", lit)
    parts = lit.split("/")
    if package not in parts:
        return None
    return ".".join(parts[parts.index(package):])


def _module_cover(files, keep, package):
    """Smallest set of dotted modules covering exactly the files where keep(f) is true."""
    def mod(f):
        parts = f[:-3].split("/")
        parts = parts[parts.index(package):]
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    tree = {}
    for f in files:
        tree.setdefault(mod(f), []).append(keep(f))
    pkgs = {mm for mm in tree}

    def all_kept(prefix):
        return all(all(v) for mm, v in tree.items() if mm == prefix or mm.startswith(prefix + "."))
    out = []
    for mm in sorted(pkgs, key=lambda x: (x.count("."), x)):
        if not all_kept(mm) or any(mm == o or mm.startswith(o + ".") for o in out):
            continue  # (a package whose descendants are not all kept is covered by its kept children only)
        if False:
            continue
        parent = mm
        while "." in parent and all_kept(parent.rsplit(".", 1)[0]) and parent.rsplit(".", 1)[0] in pkgs:
            parent = parent.rsplit(".", 1)[0]
        if not any(parent == o or parent.startswith(o + ".") for o in out):
            out.append(parent)
    return sorted(out)


def to_import_linter(m, model_path, today, package):
    els, allow, waived = element_pairs(m, today)
    mods = {e: sorted({x for x in (_module(g, package) for g in gs) if x}) for e, gs in els.items()}
    mods = {e: v for e, v in mods.items() if v}
    allowed_set = set(allow)
    out = [f"# Generated by tools/ucn_export.py from {os.path.basename(model_path)} on {today}. Do not edit:",
           "# change the model and re-generate. Deviations become ignore_imports; re-generate before they expire.",
           "[importlinter]", f"root_package = {package}", "include_external_packages = True", ""]
    allowed, _ = build_allowed(m)

    def mods_of(e):
        if mods.get(e):
            return mods[e]
        return sorted({x for d in mods if m.under(d, e) for x in mods[d]})

    # import-linter matches ignore_imports against exact module pairs and rejects entries that match nothing,
    # so derive them from the observed file-level imports that each deviation covers
    _, stats = check(m, Ctx(model_path, today.isoformat(), None, None, None))
    deps, owner = stats["_deps"], stats["_owner"]

    def dotted(f):
        parts = f[:-3].split("/")
        parts = parts[parts.index(package):] if package in parts else parts
        return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)

    def waiver_pairs(a, b):
        return sorted({f"    {dotted(f)} -> {dotted(t)}" for f, items in deps.items() if f.endswith(".py")
                       and owner.get(f) and m.under(owner[f], a) for k, t in items
                       if k == "file" and t.endswith(".py") and owner.get(t) and waiver_covers(m, owner[t], b)})

    def ignores(x, y):
        return sorted({i for a, b, dev, exp in waived if m.under(a, x) and m.under(b, y) for i in waiver_pairs(a, b)})
    layered = set()
    for nid in m.nodes:
        def local(name):
            return f"{nid}.{name}" if f"{nid}.{name}" in m.nodes else m.ref(name)
        layers = [local(x) for x in m.attrs(nid, "layers")]
        if layers and all(layers) and all(mods_of(l) for l in layers):
            layered |= {(lo, hi) for i, hi in enumerate(layers) for lo in layers[i + 1:]}
            ign = sorted({i for a, b, dev, exp in waived if m.under(a, nid) and m.under(b, nid) for i in waiver_pairs(a, b)})
            out += [f"[importlinter:contract:ucn-layers-{nid}]", f"name = layers of {nid}", "type = layers",
                    "layers =", *[f"    {mods_of(l)[0]}" for l in layers]]
            out += (["ignore_imports =", *ign] if ign else []) + [""]
        indep = [local(x) for x in m.attrs(nid, "independent")]
        if indep and all(indep) and all(mods_of(i) for i in indep):
            layered |= {(x, y) for x in indep for y in indep if x != y}
            out += [f"[importlinter:contract:ucn-independent-{nid}]", f"name = independent parts of {nid}",
                    "type = independence", "modules =", *[f"    {mods_of(i)[0]}" for i in indep], ""]
    for x, y, reason in allowed.forb:
        if (x, y) in layered or not mods_of(x) or not mods_of(y):
            continue
        ign = ignores(x, y)
        out += [f"[importlinter:contract:ucn-forbid-{x}-{y}]", f"name = {reason}", "type = forbidden",
                "source_modules =", *[f"    {v}" for v in mods_of(x)], "forbidden_modules =", *[f"    {v}" for v in mods_of(y)],
                "allow_indirect_imports = True"] + (["ignore_imports =", *ign] if ign else []) + [""]
    for a in (sorted(mods) if m.header.get("policy", "allow") == "allow" else []):
        forb = sorted({x for b in mods if b != a and not m.under(a, b) and not m.under(b, a)
                       and (a, b) not in allowed_set and not any(w[0] == a and w[1] == b for w in waived) for x in mods[b]})
        if not forb:
            continue
        out += [f"[importlinter:contract:ucn-{a}]", f"name = {a} imports only what the UCN model allows", "type = forbidden",
                "source_modules =", *[f"    {x}" for x in mods[a]], "forbidden_modules =", *[f"    {x}" for x in forb],
                "allow_indirect_imports = True", ""]
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(model_path)), m.header.get("root", ".")))
    pyfiles = [f for f in list_code_files(root) if f.endswith(".py") and package in f.split("/")]
    for nid in m.nodes:
        for chk in m.attrs(nid, "check"):
            cm = CHECK_ONLY.match(chk)
            if not cm:
                continue
            ok = glob_re(cm.group(1))
            srcs = _module_cover(pyfiles, lambda f: not ok.match(f), package)
            if srcs:
                out += [f"[importlinter:contract:ucn-{nid}]", f"name = {nid}: {chk}", "type = forbidden",
                        "source_modules =", *[f"    {x}" for x in srcs], "forbidden_modules =", f"    {cm.group(2)}",
                        "allow_indirect_imports = True", ""]
    return "\n".join(out) + "\n"


def export(model_path, target, package=None, today=None):
    m = Model(parse(slurp(model_path)))
    today = parse_date(today) if today else datetime.date.today()
    if target == "dependency-cruiser":
        return to_dependency_cruiser(m, model_path, today)
    if target == "import-linter":
        if not package:
            raise SystemExit("--package is required for import-linter")
        return to_import_linter(m, model_path, today, package)
    raise SystemExit(f"unknown target {target}")


if __name__ == "__main__":
    argv = sys.argv
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    sys.stdout.write(export(argv[1], opt("--to"), opt("--package"), opt("--today")))
