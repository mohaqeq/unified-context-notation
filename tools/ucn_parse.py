"""Minimal UCN 0.1 parser: UCN text -> canonical JSON graph. Prototype for the v0.2 roadmap item.

Usage: python tools/ucn_parse.py FILE.ucn [--json] [--tokens] [--lint]
  (with no flags it only validates and prints a summary)
"""
import json
import re
import sys

KINDS = {"goal", "req", "decision", "actor", "system", "container", "component",
         "data", "api", "fn", "rule", "machine", "flow", "test"}
RELS = {"refines", "satisfies", "verifies", "uses", "calls", "reads", "writes",
        "exposes", "affects", "supersedes"}
CLAUSES = {"pre", "post", "err", "inv", "assume", "guarantee", "effect"}
ATTRS = {"src", "tech", "owner", "status", "why"}
META = {"more", "conflict"}

NODE_RE = re.compile(r"^(\w+)\s+([\w.]+)(?:\s*\[([^\]]*)\])?(?:\s*:\s*(.*))?$")
TRANS_RE = re.compile(r"^(\w+)\s*->\s*(\w+)\s*:\s*on\s+(.*)$")


class UcnError(Exception):
    pass


def parse(text):
    lines = text.splitlines()
    if not lines or not lines[0].startswith("ucn "):
        raise UcnError("line 1: missing 'ucn <version> system: <Id>' header")
    header = lines[0]
    nodes, edges, metas = {}, [], []
    stack = []  # (indent, node_id)

    def parent_at(indent):
        while stack and stack[-1][0] >= indent:
            stack.pop()
        return stack[-1][1] if stack else None

    for no, raw in enumerate(lines[1:], start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise UcnError(f"line {no}: indentation must be a multiple of 2")
        if indent // 2 > 4:
            raise UcnError(f"line {no}: nesting deeper than 4")
        line = raw.strip()
        word = line.split()[0].rstrip(":")
        owner = parent_at(indent)

        if word in KINDS:
            if word == "fn":  # fn <signature in host-language notation>
                kind, sig, tags, summary = "fn", line[3:].strip(), None, None
                nid = sig.split("(")[0]
            else:
                m = NODE_RE.match(line)
                if not m:
                    raise UcnError(f"line {no}: malformed node: {line}")
                kind, nid, tags, summary = m.groups()
            # logic nodes are qualified by their owner: Links.create, Links.CodeImmutable
            fid = f"{owner}.{nid}" if owner and kind in {"fn", "rule", "machine", "flow"} and "." not in nid else nid
            node = nodes.setdefault(fid, {"id": fid, "kind": kind})
            if summary:
                node["text"] = summary
            if kind == "fn":
                node["signature"] = sig
            if tags:
                node["tags"] = [t.strip() for t in tags.split(",")]
            if owner:
                node["parent"] = owner
            stack.append((indent, fid))
        elif word in RELS:
            targets = [t.strip() for t in line[len(word):].split(",") if t.strip()]
            if owner is None:
                raise UcnError(f"line {no}: relation outside a node")
            edges += [{"from": owner, "rel": word, "to": t} for t in targets]
        elif word in CLAUSES or word in ATTRS:
            if owner is None:
                raise UcnError(f"line {no}: '{word}' outside a node")
            val = line.split(":", 1)[1].strip()
            key = "contract" if word in CLAUSES else "attrs"
            if key == "contract":
                nodes[owner].setdefault(key, []).append({word: val})
            else:
                nodes[owner].setdefault(key, {})[word] = val
        elif word in META:
            metas.append({"type": word, "at": owner, "text": line.split(":", 1)[1].strip()})
        elif TRANS_RE.match(line):
            if owner is None or nodes[owner]["kind"] != "machine":
                raise UcnError(f"line {no}: transition outside a machine")
            a, b, ev = TRANS_RE.match(line).groups()
            nodes[owner].setdefault("transitions", []).append({"from": a, "to": b, "on": ev})
        else:
            raise UcnError(f"line {no}: unknown line role '{word}'")

    return {"header": header, "nodes": list(nodes.values()), "edges": edges, "meta": metas}


def lint(g):
    """Warnings only: dangling relation targets, requirements without satisfies/verifies."""
    ids = {n["id"] for n in g["nodes"]}
    short = {i.split(".")[-1] for i in ids} | ids
    warns = [f"dangling target: {e['from']} {e['rel']} {e['to']}"
             for e in g["edges"] if e["to"] not in short and e["to"].split(".")[-1] not in short]
    for n in g["nodes"]:
        if n["kind"] == "req":
            if not any(e["rel"] == "satisfies" and e["to"] == n["id"] for e in g["edges"]):
                warns.append(f"req {n['id']}: nothing satisfies it")
            if not any(e["rel"] == "verifies" and e["to"] == n["id"] for e in g["edges"]):
                warns.append(f"req {n['id']}: nothing verifies it")
    return warns


def count_tokens(s):
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(s))
    except ImportError:
        return round(len(s) / 4)  # rough fallback


if __name__ == "__main__":
    path = sys.argv[1]
    text = open(path, encoding="utf-8").read()
    g = parse(text)
    if "--json" in sys.argv:
        print(json.dumps(g, indent=2))
    else:
        kinds = {}
        for n in g["nodes"]:
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
        print(f"OK {path}: {len(g['nodes'])} nodes {kinds}, {len(g['edges'])} edges, {len(g['meta'])} meta")
        if "--lint" in sys.argv:  # only meaningful on a full model, not on projections
            for w in lint(g):
                print("  warn:", w)
    if "--tokens" in sys.argv:
        print(f"  tokens (o200k): ucn={count_tokens(text)}"
              f"  json-pretty={count_tokens(json.dumps(g, indent=2))}"
              f"  json-compact={count_tokens(json.dumps(g, separators=(',', ':')))}")
