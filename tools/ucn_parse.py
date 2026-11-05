"""UCN 0.5 parser, linter and projection checker. The consistency validator is tools/ucn_validate.py.

Usage:
  python tools/ucn_parse.py MODEL.ucn [--json] [--lint] [--tokens]
  python tools/ucn_parse.py PROJECTION.ucn --against MODEL.ucn [--tokens]

--lint     checks a full model: references, relation domain/range, trace gaps, pins, machines.
--against  checks a projection against its model: every node exists in the model, every
           edge exists in the model, closure under references, pins present, stub accounting
           (each model node is present, named in a stub, or counted), and the token budget.
--tokens   counts tokens with tiktoken o200k_base if installed, otherwise prints an estimate.
"""
import json
import re
import sys

KINDS = {"goal", "req", "decision", "term", "actor", "system", "container", "component",
         "data", "api", "event", "config", "env", "fn", "rule", "machine", "flow", "test",
         "convention", "conflict", "side", "deviation"}
NOT_COUNTED = {"side"}  # parts of a conflict, not facts of their own

STRUCT = {"system", "container", "component", "data", "api", "event", "config", "env"}
LOGIC = {"fn", "rule", "machine", "flow"}
ANY = KINDS - {"side"}
# relation: (allowed source kinds, allowed target kinds)
RELS = {
    "refines": ({"req"}, {"goal", "req"}),
    "satisfies": (STRUCT | LOGIC, {"req", "goal"}),
    "verifies": ({"test"}, {"req", "fn", "rule", "machine", "component", "api", "flow"}),
    "uses": ({"actor", "container", "component", "fn"}, {"actor", "container", "component", "api", "config", "env"}),
    "calls": ({"fn"}, {"fn", "api"}),
    "reads": ({"container", "component", "fn"}, {"data", "config"}),
    "writes": ({"container", "component", "fn"}, {"data", "config"}),
    "exposes": ({"container", "component"}, {"api"}),
    "implements": ({"component", "fn"}, {"api"}),
    "emits": ({"container", "component", "fn"}, {"event"}),
    "consumes": ({"container", "component", "fn"}, {"event"}),
    "affects": ({"decision"}, ANY - {"decision"}),
    "supersedes": ({"decision"}, {"decision"}),
    "about": ({"conflict"}, ANY),
    "deploysTo": ({"container"}, {"env"}),
    "forbids": (STRUCT | {"actor"}, STRUCT | {"actor"}),   # a stated "never": overrides permissions
}
# inverse names a projector may render at the target, for small models (denormalized view)
INVERSE = {"satisfiedBy": "satisfies", "verifiedBy": "verifies", "refinedBy": "refines",
           "calledBy": "calls", "affectedBy": "affects", "implementedBy": "implements"}
CLAUSES = {"pre", "post", "err", "inv", "assume", "guarantee", "effect"}
ATTRS = {"src", "tech", "owner", "why", "lifecycle", "verified", "code", "aka", "note",
         "states", "initial", "authority", "param", "bind", "expires", "approved", "check", "asserts",
         "breadth", "layers", "independent", "acyclic", "inherit"}
MAX_DEPTH = 6
POLICIES = {"allow", "deny"}
MODES = {"reverse", "forward"}
AUTHORITIES = {"model", "source"}
PARAM_RE = re.compile(r"^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*(.*)$")          # name = 100 per hour
BIND_RE = re.compile(r"^([A-Za-z_][\w.]*)\.([A-Za-z_]\w*)\s*=\s*([^#\s]+)#([A-Za-z_]\w*)(?:\s*([*/])\s*(\d+(?:\.\d+)?))?$")
# Req.param = file#CONST [* k | / k]   (optional unit scaling of the code value)
ALLOWS_RE = re.compile(r"^allows\s+([A-Za-z_][\w.]*)\s+(\w+)\s+([A-Za-z_][\w.]*)$")
LABELS = {
    "category": {"nfr", "security", "safety", "legal", "privacy"},
    "pattern": {"event", "state", "unwanted", "option", "complex"},
    "pin": {"pin"},
    "origin": {"stated", "derived", "inferred"},
    "fresh": {"stale"},
}
LABEL_WORDS = set().union(*LABELS.values())
SCOPED_PIN = {"security", "safety", "legal", "privacy"}  # inlined when the slice touches them, else named
GLOBAL_PIN_CAP = 15

NODE_RE = re.compile(r"^(\w+)\s+([A-Za-z_][\w.]*)(?:\s*\[([^\]]*)\])?(?:\s*:\s*(.*))?$")
FN_EXPLICIT_RE = re.compile(r"^fn\s+([A-Za-z_][\w.]*)\s*:\s*(.+)$")   # fn Id: <signature>
FN_ID_RE = re.compile(r"^[A-Za-z_][\w.]*")
TRAIL_RE = re.compile(r"\s+\[([^\]]+)\]$")
TRANS_RE = re.compile(r"^on\s+(.+?):\s*(\w+)\s*->\s*(\w+)$")
HEADER_RE = re.compile(r'(\w+):\s*("[^"]*"|\S+)')
COUNT_RE = re.compile(r"^(\d+)\s+(\w+)$")
NAMED_RE = re.compile(r"^(\w+)\s+([A-Za-z_][\w.]*)(?:\s*\[([^\]]*)\])?$")


class UcnError(Exception):
    pass


def split_labels(raw, no):
    out = {}
    for w in (t.strip() for t in raw.split(",") if t.strip()):
        axis = next((a for a, ws in LABELS.items() if w in ws), None)
        if axis is None:
            raise UcnError(f"line {no}: unknown label '{w}'")
        out.setdefault(axis, []).append(w)
    return out


def trailing_labels(text):
    """Split 'expr [inferred]' into ('expr', 'inferred') if every bracket word is a label word."""
    m = TRAIL_RE.search(text)
    if m and all(w.strip() in LABEL_WORDS for w in m.group(1).split(",")):
        return text[:m.start()], m.group(1)
    return text, None


def split_items(text):
    items, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "["
        depth -= ch == "]"
        if ch == "," and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def parse_header(line):
    parts = line.split()
    if len(parts) < 2 or parts[0] != "ucn":
        raise UcnError("line 1: missing 'ucn <version> system: <Id>' header")
    h = {"version": parts[1]}
    for k, v in HEADER_RE.findall(line):
        h[k] = v.strip('"')
    if "system" not in h:
        raise UcnError("line 1: header needs 'system: <Id>'")
    if "budget" in h:
        h["budget"] = int(h["budget"])
    if "origin" in h and h["origin"] not in LABELS["origin"]:
        raise UcnError(f"line 1: unknown origin '{h['origin']}'")
    if "policy" in h and h["policy"] not in POLICIES:
        raise UcnError(f"line 1: policy must be one of {sorted(POLICIES)}")
    if "mode" in h and h["mode"] not in MODES:
        raise UcnError(f"line 1: mode must be one of {sorted(MODES)}")
    return h


def parse(text):
    lines = text.splitlines()
    if not lines:
        raise UcnError("empty file")
    header = parse_header(lines[0])
    nodes, edges, stubs = {}, [], []
    stack = []  # (indent, node_id)

    def parent_at(indent):
        while stack and stack[-1][0] >= indent:
            stack.pop()
        return stack[-1][1] if stack else None

    def origin_of(nid):
        while nid:
            n = nodes[nid]
            if "origin" in n:
                return n["origin"]
            nid = n.get("parent")
        return header.get("origin")

    for no, raw in enumerate(lines[1:], start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise UcnError(f"line {no}: indentation must be a multiple of 2")
        if indent // 2 > MAX_DEPTH:
            raise UcnError(f"line {no}: nesting deeper than {MAX_DEPTH}")
        line = raw.strip()
        word = line.split()[0].rstrip(":")
        owner = parent_at(indent)
        if stack and indent > stack[-1][0] + 2:
            raise UcnError(f"line {no}: indentation jumps more than one level")

        if word in KINDS:
            if word == "fn":
                m = FN_EXPLICIT_RE.match(line)
                body, labels = trailing_labels(line[3:].strip())
                if m:
                    nid, sig = m.group(1), trailing_labels(m.group(2))[0]
                else:
                    idm = FN_ID_RE.match(body)
                    if not idm:
                        raise UcnError(f"line {no}: cannot find fn id; write 'fn Id: <signature>'")
                    nid, sig = idm.group(0), body
                kind, summary = "fn", None
            else:
                m = NODE_RE.match(line)
                if not m:
                    raise UcnError(f"line {no}: malformed node: {line}")
                kind, nid, labels, summary = m.groups()
                sig = None
            if kind == "side" and (owner is None or nodes[owner]["kind"] != "conflict"):
                raise UcnError(f"line {no}: 'side' only inside a conflict")
            okind = nodes[owner]["kind"] if owner else None
            qualify = owner and okind != "system" and "." not in nid
            fid = f"{owner}.{nid}" if qualify else nid
            node = nodes.get(fid)
            if node is None:
                node = nodes[fid] = {"id": fid, "kind": kind, "line": no}
            elif node["kind"] != kind:
                raise UcnError(f"line {no}: id {fid} is a {node['kind']} at line {node['line']}, not a {kind}")
            if summary:
                if node.get("text") not in (None, summary):
                    raise UcnError(f"line {no}: {fid} re-declared with different text")
                node["text"] = summary
            if sig:
                node["signature"] = sig
            if labels:
                for axis, ws in split_labels(labels, no).items():
                    if axis == "origin":
                        node["origin"] = ws[-1]
                    elif axis == "pin":
                        node["pin"] = True
                    elif axis == "fresh":
                        node["stale"] = True
                    else:
                        node[axis] = ws
            if owner:
                node["parent"] = owner
            stack.append((indent, fid))
        elif word in RELS or word in INVERSE:
            if owner is None:
                raise UcnError(f"line {no}: relation outside a node")
            body, tag = trailing_labels(line[len(word):].strip())
            origin = next((w.strip() for w in (tag or "").split(",") if w.strip() in LABELS["origin"]), None)
            for t in split_items(body):
                if word in INVERSE:
                    e = {"from": t, "rel": INVERSE[word], "to": owner, "line": no, "inverse": True, "owner": owner}
                else:
                    e = {"from": owner, "rel": word, "to": t, "line": no, "owner": owner}
                if origin:
                    e["origin"] = origin
                edges.append(e)
        elif word in CLAUSES or word in ATTRS:
            if owner is None:
                raise UcnError(f"line {no}: '{word}' outside a node")
            if ":" not in line:
                raise UcnError(f"line {no}: '{word}' needs ':'")
            val = line.split(":", 1)[1].strip()
            if word in CLAUSES:
                expr, tag = trailing_labels(val)
                c = {"clause": word, "expr": expr}
                if tag:
                    c["origin"] = tag.strip()
                nodes[owner].setdefault("contract", []).append(c)
                continue
            if word == "authority" and val not in AUTHORITIES:
                raise UcnError(f"line {no}: authority must be 'model' or 'source'")
            if word == "param" and not PARAM_RE.match(val):
                raise UcnError(f"line {no}: param is 'name = number [unit]'")
            if word == "bind" and not BIND_RE.match(val):
                raise UcnError(f"line {no}: bind is 'Req.param = path#CONSTANT'")
            if word == "layers":
                nodes[owner].setdefault("attrs", {})["layers"] = [x.strip() for x in re.split(r"[>,]", val) if x.strip()]
            elif word in ("states", "aka", "independent"):
                nodes[owner].setdefault("attrs", {}).setdefault(word, []).extend(split_items(val))
            else:
                nodes[owner].setdefault("attrs", {}).setdefault(word, []).append(val)
        elif word == "more":
            body = line.split(":", 1)[1].strip()
            expand = None
            if " -> expand " in body:
                body, expand = body.rsplit(" -> expand ", 1)
            stub = {"at": owner, "named": [], "counts": [], "line": no}
            if expand:
                stub["expand"] = expand.strip()
            for item in split_items(body):
                if m := COUNT_RE.match(item):
                    stub["counts"].append({"n": int(m.group(1)), "kind": m.group(2)})
                elif m := NAMED_RE.match(item):
                    if m.group(1) not in KINDS:
                        raise UcnError(f"line {no}: unknown kind '{m.group(1)}' in stub")
                    stub["named"].append({"kind": m.group(1), "id": m.group(2)})
                else:
                    raise UcnError(f"line {no}: stub items are '<kind> <Id>' or '<n> <kind>': {item}")
            for c in stub["counts"]:
                if c["kind"] not in KINDS:
                    raise UcnError(f"line {no}: unknown kind '{c['kind']}' in stub")
            stubs.append(stub)
        elif word == "allows":
            m = ALLOWS_RE.match(line)
            if not m or owner is None or nodes[owner]["kind"] != "deviation" or m.group(2) not in RELS:
                raise UcnError(f"line {no}: 'allows <ref> <relation> <ref>' only inside a deviation")
            nodes[owner].setdefault("allows", []).append(
                {"from": m.group(1), "rel": m.group(2), "to": m.group(3), "line": no})
        elif word == "on":
            m = TRANS_RE.match(line)
            if not m or owner is None or nodes[owner]["kind"] != "machine":
                raise UcnError(f"line {no}: transitions are 'on <event>: A -> B' inside a machine")
            ev, a, b = m.groups()
            nodes[owner].setdefault("transitions", []).append({"on": ev, "from": a, "to": b})
        else:
            raise UcnError(f"line {no}: unknown line role '{word}'")

    for nid, n in nodes.items():  # resolve inherited origin
        o = origin_of(nid)
        if o:
            n["origin"] = o
    for e in edges:  # an edge without its own label has the origin of the node it is written under
        if "origin" not in e and nodes[e["owner"]].get("origin"):
            e["origin"] = nodes[e["owner"]]["origin"]
    g = {"header": header, "nodes": list(nodes.values()), "edges": edges, "stubs": stubs}
    resolve_edges(g, g)
    return g


def resolve(ref, ids, kind=None, kinds_of=None):
    """Resolve a reference by exact id or unique dotted suffix. Returns (id|None, problem|None)."""
    if ref in ids and (kind is None or kinds_of[ref] == kind):
        return ref, None
    cands = [i for i in ids if i.endswith("." + ref) and (kind is None or kinds_of[i] == kind)]
    if len(cands) == 1:
        return cands[0], None
    return None, ("ambiguous: " + ", ".join(sorted(cands))) if cands else "dangling"


def resolve_edges(g, model):
    ids = {n["id"] for n in model["nodes"]}
    for e in g["edges"]:
        for end in ("from", "to"):
            rid, prob = resolve(e[end], ids)
            e[end + "_id"] = rid
            if prob:
                e.setdefault("problems", []).append(f"{end} {e[end]}: {prob}")


def lint(g):
    """Returns (severity, message) pairs. 'error' = model integrity (fails CI in every mode); 'warn' = gaps."""
    out = []
    err = lambda m: out.append(("error", m))
    warn = lambda m: out.append(("warn", m))
    kind = {n["id"]: n["kind"] for n in g["nodes"]}
    for e in g["edges"]:
        for p in e.get("problems", []):
            err(f"line {e['line']}: {e['rel']} {p}")
        a, b = e.get("from_id"), e.get("to_id")
        if a and b:
            dom, rng = RELS[e["rel"]]
            if kind[a] not in dom or kind[b] not in rng:
                err(f"line {e['line']}: {kind[a]} {a} {e['rel']} {kind[b]} {b}: not allowed by the relation table")
    rel_to = lambda rel, nid: any(e["rel"] == rel and e.get("to_id") == nid for e in g["edges"])
    for n in g["nodes"]:
        attrs = n.get("attrs", {})
        if "origin" not in n:
            warn(f"{n['kind']} {n['id']}: origin unknown (set it on the node, a parent, or the header)")
        if n["kind"] == "req":
            planned = attrs.get("lifecycle") == ["planned"]
            if not rel_to("satisfies", n["id"]) and not planned:
                warn(f"req {n['id']}: nothing satisfies it")
            if not rel_to("verifies", n["id"]):
                warn(f"req {n['id']}: nothing verifies it" + (" (planned)" if planned else ""))
        if n["kind"] == "conflict":
            sides = [m for m in g["nodes"] if m.get("parent") == n["id"] and m["kind"] == "side"]
            if len(sides) < 2:
                err(f"conflict {n['id']}: needs two or more sides")
            if not any(e["rel"] == "about" and e.get("from_id") == n["id"] for e in g["edges"]):
                err(f"conflict {n['id']}: 'about' does not name the facts it concerns")
        if n["kind"] == "deviation":
            for a in ("why", "expires", "approved"):
                if a not in attrs:
                    err(f"deviation {n['id']}: needs '{a}:'")
            if not n.get("allows"):
                err(f"deviation {n['id']}: needs at least one 'allows <ref> <relation> <ref>'")
        if n["kind"] == "machine":
            states = set(attrs.get("states", []))
            for t in n.get("transitions", []):
                for s_ in (t["from"], t["to"]):
                    if s_ not in states:
                        err(f"machine {n['id']}: state '{s_}' not listed in states:")
            for s_ in attrs.get("initial", []):
                if s_ not in states:
                    err(f"machine {n['id']}: initial state '{s_}' not listed in states:")
        for t in attrs.get("verified", []):
            rid, prob = resolve(t, set(kind), "test", kind)
            if prob:
                err(f"{n['id']}: verified: {t} is not a test ({prob})")
        for a in ("param", "lifecycle", "authority", "expires", "approved"):
            if len(attrs.get(a, [])) > 1:
                err(f"{n['id']}: '{a}:' given more than once")
    pins = [n["id"] for n in g["nodes"] if n.get("pin")]
    if len(pins) > GLOBAL_PIN_CAP:
        warn(f"{len(pins)} global pins exceed the cap of {GLOBAL_PIN_CAP}; scope them instead")
    return out


def check_projection(p, m, text):
    """Check a projection p (parsed) against its full model m. Returns a list of errors."""
    errs = []
    mkind = {n["id"]: n["kind"] for n in m["nodes"]}
    mids = set(mkind)
    present = set()
    for n in p["nodes"]:
        rid, prob = resolve(n["id"], mids, n["kind"], mkind)
        if prob:
            errs.append(f"line {n['line']}: {n['kind']} {n['id']} is not in the model ({prob})")
        else:
            present.add(rid)
    named = set()
    for s in p["stubs"]:
        for it in s["named"]:
            rid, prob = resolve(it["id"], mids, it["kind"], mkind)
            if prob:
                errs.append(f"line {s['line']}: stub names {it['kind']} {it['id']}, not in the model ({prob})")
            elif rid in present:
                errs.append(f"line {s['line']}: stub names {rid}, which is already present")
            else:
                named.add(rid)
    # edges: must exist in the model; both ends present or named (closure)
    medges = {(e.get("from_id"), e["rel"], e.get("to_id")) for e in m["edges"]}
    resolve_edges(p, m)
    for e in p["edges"]:
        a, b = e.get("from_id"), e.get("to_id")
        if not a or not b:
            errs.append(f"line {e['line']}: {e['rel']} cannot be resolved against the model: {e.get('problems')}")
            continue
        if (a, e["rel"], b) not in medges:
            errs.append(f"line {e['line']}: edge {a} {e['rel']} {b} is not in the model")
        for end in (a, b):
            if end not in present | named:
                errs.append(f"line {e['line']}: {end} is referenced but neither present nor named in a stub")
    # pins
    for n in m["nodes"]:
        if n.get("pin") and n["id"] not in present:
            errs.append(f"global pin {n['id']} is missing")
        if set(n.get("category", [])) & SCOPED_PIN and n["id"] not in present | named:
            errs.append(f"scoped pin {n['id']} is neither present nor named")
    # accounting: every model node is present, named, or counted, exactly once
    counted = {}
    for s in p["stubs"]:
        for c in s["counts"]:
            counted[c["kind"]] = counted.get(c["kind"], 0) + c["n"]
    for k in sorted(KINDS - NOT_COUNTED):
        total = sum(1 for i in mids if mkind[i] == k)
        seen = sum(1 for i in present | named if mkind[i] == k)
        if total != seen + counted.get(k, 0):
            errs.append(f"accounting for {k}: model has {total}, projection shows/names {seen}, "
                        f"stubs count {counted.get(k, 0)} (should be {total - seen})")
    budget = p["header"].get("budget")
    if budget:
        n, exact = count_tokens(text)
        if n > budget:
            errs.append(f"{n} tokens{'' if exact else ' (estimate)'} exceed budget {budget}")
    return errs


def canonical(g):
    """The canonical JSON form: references resolved to ids, parser bookkeeping removed."""
    drop = {"line", "problems", "inverse", "from_id", "to_id"}
    clean = lambda d: {k: v for k, v in d.items() if k not in drop}
    edges = [dict(clean(e), **{"from": e.get("from_id") or e["from"], "to": e.get("to_id") or e["to"]})
             for e in g["edges"]]
    return {"header": g["header"], "nodes": [clean(n) for n in g["nodes"]], "edges": edges,
            "stubs": [clean(s) for s in g["stubs"]]}


def count_tokens(s):
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(s)), True
    except ImportError:
        return round(len(s) / 4), False


def main(argv):
    path = argv[1]
    text = open(path, encoding="utf-8").read()
    g = parse(text)
    status = 0
    if "--json" in argv:
        print(json.dumps(canonical(g), indent=2))
    else:
        kinds = {}
        for n in g["nodes"]:
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
        print(f"OK {path}: {len(g['nodes'])} nodes {kinds}, {len(g['edges'])} edges, {len(g['stubs'])} stubs")
    if "--lint" in argv:
        for sev, w in lint(g):
            print(f"  {sev}:", w)
    if "--against" in argv:
        mpath = argv[argv.index("--against") + 1]
        errs = check_projection(g, parse(open(mpath, encoding="utf-8").read()), text)
        for e in errs:
            print("  error:", e)
        print(f"  projection check against {mpath}: {'PASS' if not errs else f'{len(errs)} error(s)'}")
        status = 1 if errs else 0
    if "--tokens" in argv:
        def t(s):
            n, exact = count_tokens(s)
            return f"{n}" if exact else f"~{n}"
        exact = count_tokens("")[1]
        c = canonical(g)
        print(f"  tokens ({'o200k' if exact else 'estimate: chars/4, install tiktoken for o200k'}): ucn={t(text)}"
              f"  json-pretty={t(json.dumps(c, indent=2))}"
              f"  json-compact={t(json.dumps(c, separators=(',', ':')))}")
    return status


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except UcnError as e:
        print("error:", e)
        sys.exit(2)
