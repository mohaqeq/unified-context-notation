"""Independent grader review by a non-Claude model (OpenRouter): does a hidden test assert anything the ticket does not
state (or the named rule does not require)? One request per task.

  python tools/review_graders.py TASKS_DIR OUT.json [--model MODEL]

The API key is read from ~/.openrouter_key (never printed or stored).
"""
import json
import os
import sys
import time
import urllib.request

MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
PROMPT = """You review hidden acceptance tests for a coding task. The developer only sees the TICKET. A test is
OVER-SPECIFIED if it fails a reasonable implementation that satisfies the ticket, by asserting something the ticket
does not state. Tests named test_rule_* may also assert the documented RULE given below (the developer is expected to
follow the project's documented rules), but nothing beyond it.

TICKET:
{ticket}

RULE (from the project's docs; may be "none"): {rule}

TESTS:
{tests}

Answer with JSON only: {{"over_specified": [{{"test": "<name>", "why": "<one sentence>"}}], "ok": ["<names>"]}}"""


def ask(key, model, text):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": text}], "temperature": 0}).encode()
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=300))["choices"][0]["message"]["content"]
        except Exception as e:  # rate limits on the free tier: back off
            if attempt == 3:
                return f"ERROR: {e}"
            time.sleep(30 * (attempt + 1))


def main():
    tasks, out = sys.argv[1], sys.argv[2]
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else MODEL
    key = open(os.path.expanduser("~/.openrouter_key"), encoding="ascii").read().strip()
    results = json.load(open(out)) if os.path.exists(out) else {}
    for t in sorted(os.listdir(tasks)):
        d = os.path.join(tasks, t)
        if t in results or not os.path.isfile(os.path.join(d, "task.md")):
            continue
        meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
        tests = "\n\n".join(open(os.path.join(d, "grader", f), encoding="utf-8").read()
                            for f in sorted(os.listdir(os.path.join(d, "grader"))) if f.endswith(".py"))
        raw = ask(key, model, PROMPT.format(ticket=open(os.path.join(d, "task.md"), encoding="utf-8").read(),
                                            rule=meta.get("rule", "none"), tests=tests))
        try:
            parsed = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        except ValueError:
            parsed = {"unparsed": raw[:2000]}
        results[t] = {"model": model, **parsed}
        json.dump(results, open(out, "w"), indent=1)
        print(t, "over-specified:", [x.get("test") for x in parsed.get("over_specified", [])] if "over_specified" in parsed else parsed)


if __name__ == "__main__":
    main()
