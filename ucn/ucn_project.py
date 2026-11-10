"""Default projector: a task-specific UCN context that fits a token budget and passes the projection checker.

Usage:
  ucn project MODEL.ucn --task "TEXT" [--budget 2500] [--seed ID,ID] [--depth 1] > context.ucn

Deterministic, no ranking model (docs/03 §3.5, default projection):
  1. core: goals, the system and its containers, global pins, open or accepted conflicts, active deviations (L0);
  2. seeds: ids and code paths named in the task, plus the best keyword matches over names and text;
  3. stated rules: every forbids / layers / independent / acyclic that involves a seed or its ancestors;
  4. the seeds at L2 (clauses, attributes, relations), their typed-graph neighbours at L1;
  5. named stubs for every node a rendered line references but the budget left out, and per-kind counts for the
     rest, so `ucn_parse.py PROJECTION --against MODEL` passes (closure, pins, exact accounting).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ucn_parse import check_projection, parse  # noqa: E402
from ucn_validate import Model, glob_re, slurp  # noqa: E402

STOP = set("a an and are as at be by for from has have in into is it its of on or that the this to was were will with "
           "should must when then add make use new implement support".split())
STRUCT = {"system", "container", "component", "data", "api", "event", "config", "env"}


def tokens(text):
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except ImportError:
        return round(len(text) / 4)


def words(text):
    return {w for w in re.findall(r"[a-z][a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text).lower()) if w not in STOP and len(w) > 2}


def seeds_for(m, task, explicit):
    out = [m.ref(x) for x in explicit if m.ref(x)]
    low = task.lower()
    for nid in m.nodes:
        name = nid.rsplit(".", 1)[-1]
        if m.kind[nid] != "side" and len(name) > 2 and re.search(r"\b" + re.escape(name.lower()) + r"\b", low):
            out.append(nid)
    for path in re.findall(r"[\w./-]+\.\w+|[\w-]+(?:/[\w.-]+)+", task):
        for nid in m.nodes:
            if any(glob_re(g).match(path.strip("./")) for g in m.attrs(nid, "code")):
                out.append(nid)
    tw = words(task)
    scored = []
    for nid, n in m.nodes.items():
        if n["kind"] in ("side",):
            continue
        nw = words(nid.rsplit(".", 1)[-1] + " " + n.get("text", "") + " " + n.get("signature", ""))
        hit = len(tw & nw)
        if hit:
            scored.append((-hit, len(m.anc[nid]), nid))
    out += [nid for _, _, nid in sorted(scored)[:5]]
    seen, res = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


def neighbours(m, ids):
    out = set()
    for e in m.g["edges"]:
        a, b = e.get("from_id"), e.get("to_id")
        if not (a and b):
            continue
        if a in ids:
            out.add(b)
        if b in ids:
            out.add(a)
    return out


def rule_nodes(m, focus):
    """Nodes carrying stated rules that involve the focus set (or its ancestors)."""
    anc = {a for f in focus for a in m.anc[f]}
    out = set()
    for e in m.g["edges"]:
        if e["rel"] == "forbids" and (e.get("from_id") in anc or e.get("to_id") in anc):
            out |= {e["from_id"], e["to_id"]}
    for nid in m.nodes:
        if any(m.attrs(nid, k) for k in ("layers", "independent", "acyclic")) and (nid in anc or any(m.under(f, nid) for f in focus)):
            out.add(nid)
    for nid, n in m.nodes.items():
        if n["kind"] == "rule" and any(w in words(n.get("text", "")) for f in focus for w in words(f.rsplit(".", 1)[-1])):
            out.add(nid)
    return out


def labels(n):
    ls = list(n.get("category", [])) + list(n.get("pattern", []))
    if n.get("pin"):
        ls.append("pin")
    if n.get("origin") == "inferred":
        ls.append("inferred")
    if n.get("stale"):
        ls.append("stale")
    return f" [{', '.join(ls)}]" if ls else ""


def node_line(m, nid, with_text=True):
    n = m.nodes[nid]
    name = nid.rsplit(".", 1)[-1] if n.get("parent") else nid
    if n["kind"] == "fn":
        sig = n.get("signature", name)
        return f"fn {sig}" if sig.startswith(name) else f"fn {name}: {sig}"
    text = f": {n['text']}" if with_text and n.get("text") else ""
    return f"{n['kind']} {name}{labels(n)}{text}"


def body_lines(m, nid, level):
    """Lines under a node: L1 = relations; L2 = relations, clauses, attributes, transitions, allows."""
    n = m.nodes[nid]
    out = []
    if level >= 2:
        for k, vs in n.get("attrs", {}).items():
            if k in ("states", "aka", "independent"):
                out.append(f"{k}: {', '.join(vs)}")
            elif k == "layers":
                out.append(f"layers: {' > '.join(vs)}")
            else:
                out += [f"{k}: {v}" for v in vs]
        for c in n.get("contract", []):
            out.append(f"{c['clause']}: {c['expr']}" + (f" [{c['origin']}]" if c.get("origin") == "inferred" else ""))
        for t in n.get("transitions", []):
            out.append(f"on {t['on']}: {t['from']} -> {t['to']}")
        for a in n.get("allows", []):
            out.append(f"allows {a['from']} {a['rel']} {a['to']}")
    else:
        for k in ("layers", "independent", "acyclic", "lifecycle"):
            vs = n.get("attrs", {}).get(k, [])
            if vs:
                out.append(f"{k}: {' > '.join(vs) if k == 'layers' else ', '.join(vs)}")
    rels = {}
    for e in m.g["edges"]:
        if e.get("owner") == nid and not e.get("inverse"):
            rels.setdefault(e["rel"], []).append(e["to"])
    out += [f"{rel} {', '.join(ts)}" for rel, ts in rels.items()]
    return out


def project(model_path, task, budget=2500, explicit=(), depth=1):
    m = Model(parse(slurp(model_path)))
    level = {}

    def want(nid, lv):
        if m.kind[nid] == "side":
            return
        level[nid] = max(level.get(nid, -1), lv)

    # 1. core
    for nid, n in m.nodes.items():
        k = n["kind"]
        if k == "goal" or n.get("pin") or k == "system" or (k == "container" and (not n.get("parent") or m.kind[n["parent"]] == "system")):
            want(nid, 0)
        if k == "conflict" and m.attr(nid, "lifecycle", "open") in ("open", "accepted"):
            want(nid, 0)
        if k == "deviation" and m.attr(nid, "lifecycle") == "accepted":
            want(nid, 0)
    core = set(level)
    # 2-4. task slice
    seeds = seeds_for(m, task, explicit)
    focus = set(seeds)
    for _ in range(depth):
        focus |= neighbours(m, focus)
    plan = [(s, 2) for s in seeds] + [(r, 1) for r in sorted(rule_nodes(m, set(seeds)) - set(seeds))] + \
           [(x, 1) for x in sorted(focus - set(seeds))]
    plan = [(n, lv) for n, lv in plan if m.kind[n] != "side"]
    rendered = None
    named = []
    for nid, lv in [(None, None)] + plan:
        if nid is not None:
            trial = dict(level)
            trial[nid] = max(trial.get(nid, -1), lv)
            text = render(m, model_path, task, budget, trial, core)
            if tokens(text) > budget * 0.9:      # keep a reserve for stubs
                named.append(nid)
                continue
            level = trial
        rendered = render(m, model_path, task, budget, level, core)
    # second pass: upgrade the neighbourhood to L2 while the budget allows (seeds first, then plan order)
    for nid, lv in plan:
        if nid in level and level[nid] < 2:
            trial = dict(level)
            trial[nid] = 2
            if tokens(render(m, model_path, task, budget, trial, core)) <= budget * 0.9:
                level = trial
    named = [x for x in named if x not in level]
    text = render(m, model_path, task, budget, level, core, extra_named=named)
    errs = check_projection(parse(text), m.g, text)
    return text, errs


def render(m, model_path, task, budget, level, core, extra_named=()):
    h = m.header
    head = f"ucn {h.get('version', '0.6')} system: {h['system']} level: mixed origin: {h.get('origin', 'stated')}"
    for k in ("mode", "policy"):
        if k in h:
            head += f" {k}: {h[k]}"
    short = " ".join(task.split())
    short = short if len(short) <= 100 else short[:97].rstrip() + "..."
    head += f' task: "{short.replace(chr(34), chr(39))}" budget: {budget}'
    out = [head, "# Generated by ucn project (default projection). Core first; task slice last; omissions named or counted."]
    present = set(level)
    show = set(present)
    for nid in present:
        show |= set(m.anc[nid])
    order = sorted(show, key=lambda n: m.nodes[n]["line"])
    in_core = [n for n in order if n in core or (n not in present and any(c in core for c in present if m.under(c, n)) and n not in level)]
    slice_ = [n for n in order if n not in core]
    for title, group in (("core", order), ):
        pass
    out.append("")
    out.append("# ---------- core ----------")
    out += render_tree(m, [n for n in order if n in core or any(m.under(c, n) for c in core)], level, core_only=True, core=core)
    out.append("")
    out.append("# ---------- task slice ----------")
    slice_set = {a for c in present if c not in core for a in m.anc[c]}
    out += render_tree(m, [n for n in order if n in slice_set], level, core_only=False, core=core)
    # stubs: everything referenced but absent is named; the rest is counted per kind
    referenced = set()
    tmp = parse("\n".join(out))
    from ucn_parse import resolve
    for e in tmp["edges"]:
        for end in ("from", "to"):
            rid = resolve(e[end], set(m.kind))[0]
            if rid and rid not in present:
                referenced.add(rid)
    shown = {resolve(n["id"], set(m.kind), n["kind"], m.kind)[0] for n in tmp["nodes"]} - {None}
    scoped = {nid for nid, n in m.nodes.items() if set(n.get("category", [])) & {"security", "safety", "legal", "privacy"}}
    named = sorted((set(referenced) | set(extra_named) | scoped) - shown, key=lambda n: m.nodes[n]["line"])
    named = [n for n in named if m.kind[n] != "side"]
    present = shown
    if named:
        out.append("more: " + ", ".join(f"{m.kind[n]} {n}" for n in named))
    counts = {}
    for nid, n in m.nodes.items():
        if n["kind"] == "side" or nid in present or nid in named:
            continue
        counts[n["kind"]] = counts.get(n["kind"], 0) + 1
    if counts:
        root = next((n for n in m.nodes if m.kind[n] == "system"), h["system"])
        out.append("more: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + f" -> expand {root}@L1")
    return "\n".join(out) + "\n"


def render_tree(m, nodes, level, core_only, core):
    out = []
    nodes_set = set(nodes)
    for nid in nodes:
        n = m.nodes[nid]
        depth = len([a for a in m.anc[nid][1:] if a in nodes_set])
        ind = "  " * depth
        if nid in level and (core_only == (nid in core)):
            lv = level[nid]
            out.append(ind + node_line(m, nid))
            if not (core_only and lv == 0):
                out += [ind + "  " + b for b in body_lines(m, nid, lv)]
        else:
            out.append(ind + node_line(m, nid, with_text=False).split(" [")[0].split(":")[0] if n["kind"] != "fn" else ind + node_line(m, nid))
    return out


if __name__ == "__main__":
    argv = sys.argv
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    text, errs = project(argv[1], opt("--task", ""), int(opt("--budget", 2500)),
                         [x for x in (opt("--seed") or "").split(",") if x], int(opt("--depth", 1)))
    sys.stdout.write(text)
    if errs:
        sys.stderr.write("projection check FAILED:\n" + "\n".join("  " + e for e in errs) + "\n")
        sys.exit(1)
