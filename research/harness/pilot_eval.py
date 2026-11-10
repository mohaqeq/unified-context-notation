"""Pilot evaluation: is UCN worth it compared with the lightweight stack? Applies pre-registered criteria.

Usage: python tools/pilot_eval.py PILOT.json [--json]

Input (see research/harness/pilot_template.json):
  criteria  pre-registered thresholds, fixed before the pilot starts
  tasks     each task run under both conditions ("light" = structured AGENTS.md + ADRs + architecture rules
            in CI + requirement IDs; "ucn" = UCN core). kind: question | change | tempting.
            results.<condition> = {success: 0|1, violations: n, tokens: n, seconds: n}
  facts     facts annotators marked as needed for each task, and whether the UCN context had them:
            present | named | absent
  upkeep    per week: minutes spent maintaining the model, and total review minutes
  ci        per week: architecture violations the validator caught, and how many were false positives

Decision
  KILL    upkeep too expensive, or UCN cannot reach the minimum gain and does not reduce violations
  GO      upkeep within budget, silent absence within budget, and a significant gain in task success
          or a significant reduction in constraint violations
  EXTEND  otherwise (inconclusive); reports roughly how many paired tasks would be needed
Everything is deterministic (fixed bootstrap seed), pure Python, no dependencies.
"""
import json
import math
import random
import statistics
import sys

DEFAULTS = {"min_gain": 0.10, "violation_reduction": 0.5, "max_upkeep_ratio": 0.10,
            "max_silent_absence": 0.05, "alpha": 0.05, "power": 0.8, "bootstrap": 4000, "seed": 7}


def mcnemar_p(b, c):
    """Exact two-sided McNemar test on discordant pairs b (ucn better) and c (light better)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def paired_bootstrap_ci(pairs, alpha, reps, seed):
    """CI for mean(ucn - light) over paired binary outcomes."""
    rng = random.Random(seed)
    diffs = [u - l for l, u in pairs]
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(reps))
    return means[int(reps * alpha / 2)], means[int(reps * (1 - alpha / 2)) - 1]


def z(p):
    """Inverse standard normal CDF (Acklam's approximation is overkill; bisection is enough here)."""
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 0.5 * (1 + math.erf(mid / math.sqrt(2))) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def evaluate(data):
    cr = {**DEFAULTS, **data.get("criteria", {})}
    tasks = data.get("tasks", [])
    paired = [t for t in tasks if "light" in t["results"] and "ucn" in t["results"]]
    out = {"criteria": cr, "tasks": len(tasks), "paired": len(paired)}

    # success on questions and changes
    work = [t for t in paired if t["kind"] in ("question", "change")]
    pairs = [(t["results"]["light"]["success"], t["results"]["ucn"]["success"]) for t in work]
    if pairs:
        b = sum(1 for l, u in pairs if u > l)
        c = sum(1 for l, u in pairs if l > u)
        lo, hi = paired_bootstrap_ci(pairs, cr["alpha"], cr["bootstrap"], cr["seed"])
        diff = sum(u - l for l, u in pairs) / len(pairs)
        out["success"] = {"n": len(pairs), "light": sum(l for l, _ in pairs) / len(pairs),
                          "ucn": sum(u for _, u in pairs) / len(pairs), "diff": diff,
                          "ci": [lo, hi], "p": mcnemar_p(b, c), "ucn_better": b, "light_better": c}
    # violations on tempting tasks
    tempt = [t for t in paired if t["kind"] == "tempting"]
    if tempt:
        vl = [1 if t["results"]["light"].get("violations", 0) > 0 else 0 for t in tempt]
        vu = [1 if t["results"]["ucn"].get("violations", 0) > 0 else 0 for t in tempt]
        b = sum(1 for l, u in zip(vl, vu) if l and not u)
        c = sum(1 for l, u in zip(vl, vu) if u and not l)
        rl, ru = sum(vl) / len(vl), sum(vu) / len(vu)
        out["violations"] = {"n": len(tempt), "light_rate": rl, "ucn_rate": ru,
                             "reduction": (1 - ru / rl) if rl else 0.0, "p": mcnemar_p(b, c)}
    # silent absence
    facts = data.get("facts", [])
    if facts:
        absent = sum(1 for f in facts if f["ucn"] == "absent")
        named = sum(1 for f in facts if f["ucn"] == "named")
        out["facts"] = {"needed": len(facts), "absent": absent, "named": named,
                        "silent_absence": absent / len(facts)}
    # upkeep: overall and the last two weeks (habits settle; the early weeks include setup)
    up = sorted(data.get("upkeep", []), key=lambda w: w["week"])
    if up:
        def ratio(ws):
            r = sum(w["review_minutes"] for w in ws)
            return sum(w["model_minutes"] for w in ws) / r if r else float("inf")
        out["upkeep"] = {"weeks": len(up), "ratio_all": ratio(up), "ratio_recent": ratio(up[-2:])}
    ci = data.get("ci", [])
    if ci:
        caught = sum(w["arch_violations_caught"] for w in ci)
        fp = sum(w.get("false_positives", 0) for w in ci)
        out["ci"] = {"caught": caught, "false_positives": fp,
                     "precision": (caught - fp) / caught if caught else None}
    for cond in ("light", "ucn"):
        tok = [t["results"][cond]["tokens"] for t in paired if "tokens" in t["results"][cond]]
        sec = [t["results"][cond]["seconds"] for t in paired if "seconds" in t["results"][cond]]
        out.setdefault("cost", {})[cond] = {"median_tokens": statistics.median(tok) if tok else None,
                                            "median_seconds": statistics.median(sec) if sec else None}

    out["decision"], out["reasons"] = decide(out, cr)
    return out


def decide(r, cr):
    reasons = []
    up = r.get("upkeep")
    if up and up["ratio_recent"] > cr["max_upkeep_ratio"]:
        return "KILL", [f"upkeep {up['ratio_recent']:.0%} of review time in the last weeks exceeds {cr['max_upkeep_ratio']:.0%}"]
    s, v, f = r.get("success"), r.get("violations"), r.get("facts")
    gain = bool(s and s["ci"][0] > 0 and s["diff"] >= cr["min_gain"] and s["p"] < cr["alpha"])
    safer = bool(v and v["reduction"] >= cr["violation_reduction"] and v["p"] < cr["alpha"])
    cannot_gain = bool(s and s["ci"][1] < cr["min_gain"])
    no_safety = not v or v["p"] >= cr["alpha"] or v["reduction"] < cr["violation_reduction"]
    if cannot_gain and no_safety and s["n"] >= 30:
        return "KILL", [f"success gain CI upper bound {s['ci'][1]:+.0%} is below the minimum {cr['min_gain']:+.0%}, "
                        "and constraint violations are not significantly reduced"]
    if not up:
        reasons.append("no upkeep data")
    if f and f["silent_absence"] > cr["max_silent_absence"]:
        reasons.append(f"silent absence {f['silent_absence']:.1%} exceeds {cr['max_silent_absence']:.0%}: fix projection first")
    if (gain or safer) and up and not reasons:
        why = []
        if gain:
            why.append(f"success {s['diff']:+.0%} (CI {s['ci'][0]:+.0%}..{s['ci'][1]:+.0%}, p={s['p']:.3f})")
        if safer:
            why.append(f"violations reduced by {v['reduction']:.0%} (p={v['p']:.3f})")
        return "GO", why + [f"upkeep {up['ratio_recent']:.0%} of review time"]
    if s:
        disc = (s["ucn_better"] + s["light_better"]) / s["n"] or 0.5
        need = math.ceil((z(1 - cr["alpha"] / 2) + z(cr["power"])) ** 2 * disc / cr["min_gain"] ** 2)
        reasons.append(f"inconclusive at n={s['n']}; roughly {need} paired tasks needed to detect {cr['min_gain']:+.0%}")
    return "EXTEND", reasons or ["not enough data"]


def main(argv):
    with open(argv[1], encoding="utf-8") as f:
        r = evaluate(json.load(f))
    if "--json" in argv:
        print(json.dumps(r, indent=2))
        return 0
    print(f"pilot: {r['tasks']} tasks, {r['paired']} paired")
    if "success" in r:
        s = r["success"]
        print(f"  success     light {s['light']:.0%}  ucn {s['ucn']:.0%}  diff {s['diff']:+.0%}  "
              f"CI [{s['ci'][0]:+.0%}, {s['ci'][1]:+.0%}]  McNemar p={s['p']:.3f}  (n={s['n']})")
    if "violations" in r:
        v = r["violations"]
        print(f"  violations  light {v['light_rate']:.0%}  ucn {v['ucn_rate']:.0%}  reduction {v['reduction']:.0%}  p={v['p']:.3f}  (n={v['n']})")
    if "facts" in r:
        f = r["facts"]
        print(f"  facts       needed {f['needed']}  named {f['named']}  absent {f['absent']}  silent absence {f['silent_absence']:.1%}")
    if "upkeep" in r:
        u = r["upkeep"]
        print(f"  upkeep      {u['ratio_all']:.1%} of review time overall, {u['ratio_recent']:.1%} in the last two weeks")
    if "ci" in r:
        c = r["ci"]
        prec = f"{c['precision']:.0%}" if c["precision"] is not None else "n/a"
        print(f"  ci          {c['caught']} architecture violations caught, precision {prec}")
    for cond, c in r.get("cost", {}).items():
        print(f"  cost {cond:<6} median tokens {c['median_tokens']}, median seconds {c['median_seconds']}")
    print(f"  DECISION: {r['decision']}")
    for why in r["reasons"]:
        print(f"    - {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
