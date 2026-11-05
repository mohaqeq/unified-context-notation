"""Tests for the UCN prototype tools. Run: python -m unittest discover -s tests"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pilot_eval  # noqa: E402
import ucn_parse  # noqa: E402
import ucn_validate  # noqa: E402

EX = os.path.join(ROOT, "examples", "shortly")
MODEL = os.path.join(EX, "model.ucn")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class ParseAndProject(unittest.TestCase):
    def test_model_parses_and_resolves(self):
        g = ucn_parse.parse(read(MODEL))
        self.assertEqual(g["header"]["mode"], "forward")
        self.assertFalse([e for e in g["edges"] if e.get("problems")])
        dev = next(n for n in g["nodes"] if n["kind"] == "deviation")
        self.assertEqual(dev["allows"][0]["rel"], "uses")

    def test_projections_pass(self):
        m = ucn_parse.parse(read(MODEL))
        for f in ("card.L0.ucn", "slice.alias.ucn"):
            text = read(os.path.join(EX, f))
            self.assertEqual(ucn_parse.check_projection(ucn_parse.parse(text), m, text), [], f)

    def test_projection_catches_dropped_node_and_bad_count(self):
        m = ucn_parse.parse(read(MODEL))
        text = "\n".join(l for l in read(os.path.join(EX, "slice.alias.ucn")).splitlines()
                         if "component Guard" not in l and "fn check" not in l and "fn limit" not in l)
        text = text.replace("more: 3 req", "more: 6 req")
        errs = ucn_parse.check_projection(ucn_parse.parse(text), m, text)
        self.assertTrue(any("Api.Guard is referenced" in e for e in errs))
        self.assertTrue(any(e.startswith("accounting for req") for e in errs))

    def test_bad_syntax_rejected(self):
        for bad in ["ucn 0.3 system: S mode: sideways",
                    "ucn 0.3 system: S\nreq R: x\n  param: limit is high",
                    "ucn 0.3 system: S\ngoal G: x\n  allows A uses B"]:
            with self.assertRaises(ucn_parse.UcnError):
                ucn_parse.parse(bad)


class Validate(unittest.TestCase):
    def run_on(self, model_text=None, today="2026-11-05", gate=None, edit=None):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copytree(os.path.join(EX, "src"), os.path.join(d, "src"))
        with open(os.path.join(d, "model.ucn"), "w", encoding="utf-8") as f:
            f.write(model_text or read(MODEL))
        if edit:
            edit(d)
        return ucn_validate.validate(os.path.join(d, "model.ucn"), today=today, gate=gate)

    def classes(self, r, check=None):
        return sorted((f["class"], f["message"].split(" ")[0]) for f in r["findings"]
                      if f["class"] != "INFO" and (check is None or f["check"] == check))

    def test_example_findings(self):
        r = self.run_on()
        self.assertEqual(self.classes(r), [("KNOWN-CONFLICT", "RateLimit.maxLinksPerHour"),
                                           ("MODEL-UPDATE", "Web"),
                                           ("VIOLATION", "Api.Guard"),
                                           ("WAIVED", "Api.Stats")])

    def test_expired_waiver_is_a_violation(self):
        r = self.run_on(today="2027-04-01")
        msgs = [f["message"] for f in r["findings"] if f["class"] == "VIOLATION"]
        self.assertTrue(any("expired" in m for m in msgs))

    def test_reverse_mode_turns_violations_into_model_updates(self):
        r = self.run_on(read(MODEL).replace("mode: forward baseline: 6794ead", "mode: reverse"))
        self.assertNotIn("VIOLATION", [c for c, _ in self.classes(r)])
        self.assertIn(("MODEL-UPDATE", "Api.Guard"), self.classes(r))

    def test_parameter_mismatch_without_conflict_is_a_violation(self):
        text = read(MODEL).replace("about RateLimit, Guard.limit", "about Guard.limit")
        r = self.run_on(text)
        self.assertIn(("VIOLATION", "RateLimit.maxLinksPerHour"), self.classes(r, "parameters"))

    def test_convention_check(self):
        def leak(d):
            with open(os.path.join(d, "src", "api", "links.ts"), "a", encoding="utf-8") as f:
                f.write('\nimport { Pool } from "pg";\n')
        r = self.run_on(edit=leak)
        self.assertIn(("VIOLATION", "api/links.ts"), self.classes(r, "conventions"))

    def test_unmapped_file_and_stale_src(self):
        def add(d):
            with open(os.path.join(d, "src", "orphan.ts"), "w") as fh:
                fh.write("export const x = 1;\n")
            os.remove(os.path.join(d, "src", "api", "guard.test.ts"))
        r = self.run_on(edit=add)
        self.assertIn(("VIOLATION", "orphan.ts"), self.classes(r, "coverage"))
        self.assertTrue(any(f["check"] == "provenance" for f in r["findings"]))

    def test_adopt_gate(self):
        self.assertFalse(self.run_on(gate="adopt")["gate"]["pass"])  # the Guard -> Links violation blocks
        fixed = read(MODEL).replace("    component Guard: abuse protection\n",
                                    "    component Guard: abuse protection\n      uses Links\n")
        self.assertTrue(self.run_on(fixed, gate="adopt")["gate"]["pass"])
        inferred = fixed.replace("guarantee: entries expire within an hour [stated]",
                                 "guarantee: entries expire within an hour [inferred]")
        blockers = self.run_on(inferred, gate="adopt")["gate"]["blockers"]
        self.assertTrue(any("inferred clause" in b for b in blockers))


class Pilot(unittest.TestCase):
    def data(self, light, ucn, n=40, tempting=None, upkeep=(30, 1000), absent=0):
        tasks = [{"id": f"T{i}", "kind": "change",
                  "results": {"light": {"success": int(i < light * n)}, "ucn": {"success": int(i < ucn * n)}}}
                 for i in range(n)]
        for i, (vl, vu) in enumerate(tempting or []):
            tasks.append({"id": f"X{i}", "kind": "tempting",
                          "results": {"light": {"success": 1, "violations": vl}, "ucn": {"success": 1, "violations": vu}}})
        facts = [{"task": "T0", "fact": f"F{i}", "ucn": "absent" if i < absent else "present"} for i in range(100)]
        up = [{"week": w, "model_minutes": upkeep[0], "review_minutes": upkeep[1]} for w in range(1, 5)]
        return {"tasks": tasks, "facts": facts, "upkeep": up}

    def test_go_on_clear_gain(self):
        self.assertEqual(pilot_eval.evaluate(self.data(0.4, 0.8))["decision"], "GO")

    def test_go_on_fewer_violations(self):
        r = pilot_eval.evaluate(self.data(0.5, 0.5, tempting=[(1, 0)] * 12 + [(0, 0)] * 4))
        self.assertEqual(r["decision"], "GO")

    def test_kill_on_upkeep(self):
        self.assertEqual(pilot_eval.evaluate(self.data(0.4, 0.8, upkeep=(200, 1000)))["decision"], "KILL")

    def test_kill_when_no_better(self):
        self.assertEqual(pilot_eval.evaluate(self.data(0.6, 0.6, n=60))["decision"], "KILL")

    def test_extend_when_inconclusive(self):
        self.assertEqual(pilot_eval.evaluate(self.data(0.5, 0.6, n=20))["decision"], "EXTEND")

    def test_silent_absence_blocks_go(self):
        r = pilot_eval.evaluate(self.data(0.4, 0.8, absent=10))
        self.assertEqual(r["decision"], "EXTEND")
        self.assertTrue(any("silent absence" in x for x in r["reasons"]))

    def test_template_runs(self):
        with open(os.path.join(ROOT, "examples", "pilot", "template.json")) as f:
            r = pilot_eval.evaluate(json.load(f))
        self.assertIn(r["decision"], ("GO", "KILL", "EXTEND"))


if __name__ == "__main__":
    unittest.main()
