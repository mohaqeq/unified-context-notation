"""Tests for the UCN prototype tools. Run: python -m unittest discover -s tests"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import pilot_eval  # noqa: E402
import ucn_export  # noqa: E402
import ucn_project  # noqa: E402
import ucn_parse  # noqa: E402
import ucn_validate  # noqa: E402

EX = os.path.join(ROOT, "examples", "shortly")
MODEL = os.path.join(EX, "model.ucn")
TODAY = "2026-11-05"


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(textwrap.dedent(text).lstrip("\n"))


def run(path, **kw):
    kw.setdefault("today", TODAY)
    r = ucn_validate.validate(path, **kw)
    r.pop("_model")
    return r


def classes(r, check=None):
    return sorted((f["class"], f["message"].split(" ")[0]) for f in r["findings"]
                  if f["class"] != "INFO" and (check is None or f["check"] == check))


def has(r, cls, text):
    return any(f["class"] == cls and text in f["message"] for f in r["findings"])


GENERIC = """
ucn 0.4 system: S origin: stated mode: forward root: src
system S [derived]: s
  container App: app
    code: app/**
    component A: a
      code: app/a/**
    component B: b
      code: app/b/**
    component C: c
      code: app/c/**
      uses B
"""


def rmtree(d):
    def onexc(func, path, exc):  # git marks object files read-only on Windows
        os.chmod(path, 0o700)
        func(path)
    shutil.rmtree(d, onexc=onexc)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(rmtree, self.d)

    def project(self, model=GENERIC, files=None, extra=""):
        write(os.path.join(self.d, "model.ucn"), model + textwrap.dedent(extra))
        for rel, text in (files or {}).items():
            write(os.path.join(self.d, "src", rel), text)
        return os.path.join(self.d, "model.ucn")


# ------------------------------------------------------------------------------------------- parser / projections
class ParseAndProject(unittest.TestCase):
    def test_model_parses_and_resolves(self):
        g = ucn_parse.parse(read(MODEL))
        self.assertEqual(g["header"]["mode"], "forward")
        self.assertFalse([e for e in g["edges"] if e.get("problems")])
        self.assertFalse([w for sev, w in ucn_parse.lint(g) if sev == "error"])

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
        for bad in ["ucn 0.4 system: S mode: sideways",
                    "ucn 0.4 system: S\nreq R: x\n  param: limit is high",
                    "ucn 0.4 system: S\ngoal G: x\n  allows A uses B"]:
            with self.assertRaises(ucn_parse.UcnError):
                ucn_parse.parse(bad)

    def test_edge_origin_inherited_and_labelled(self):
        g = ucn_parse.parse("ucn 0.4 system: S origin: stated\nsystem S: s\n  container A: a\n    uses B [inferred]\n  container B: b\n    uses A\n")
        origins = {(e["from"], e["to"]): e["origin"] for e in g["edges"]}
        self.assertEqual(origins[("A", "B")], "inferred")
        self.assertEqual(origins[("B", "A")], "stated")


# ------------------------------------------------------------------------------------------- the example
class ExampleBase(unittest.TestCase):
    def copy(self, model_text=None, edit=None):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        shutil.copytree(os.path.join(EX, "src"), os.path.join(d, "src"))
        shutil.copytree(os.path.join(EX, "docs"), os.path.join(d, "docs"))
        write(os.path.join(d, "model.ucn"), model_text or read(MODEL))
        if edit:
            edit(d)
        return os.path.join(d, "model.ucn")


class Example(ExampleBase):
    def test_example_findings(self):
        self.assertEqual(classes(run(MODEL)), [("KNOWN-CONFLICT", "RateLimit.maxLinksPerHour"),
                                                ("MODEL-UPDATE", "Web.Form"),
                                                ("VIOLATION", "Api.Guard"),
                                                ("WAIVED", "Api.Stats"),
                                                ("WAIVED", "Web.Form")])

    def test_expired_waiver_is_a_violation(self):
        r = run(MODEL, today="2027-04-01")
        self.assertTrue(has(r, "VIOLATION", "expired on 2027-03-31"))

    def test_reverse_mode_turns_violations_into_model_updates(self):
        r = run(self.copy(read(MODEL).replace("mode: forward baseline: v1.4.0", "mode: reverse")))
        self.assertNotIn("VIOLATION", [c for c, _ in classes(r)])
        self.assertIn(("MODEL-UPDATE", "Api.Guard"), classes(r))

    def test_parameter_mismatch_without_conflict_is_a_violation(self):
        r = run(self.copy(read(MODEL).replace("about RateLimit, Guard.limit", "about Guard.limit")))
        self.assertIn(("VIOLATION", "RateLimit.maxLinksPerHour"), classes(r, "parameters"))

    def test_accepted_conflict_stops_suppressing_when_code_moves(self):
        def drift(d):
            p = os.path.join(d, "src", "api", "guard.ts")
            write(p, read(p).replace("LIMIT_PER_HOUR = 1000", "LIMIT_PER_HOUR = 999999"))
        r = run(self.copy(edit=drift))
        self.assertTrue(has(r, "VIOLATION", "the code has moved"))

    def test_accepted_conflict_needs_expiry_and_approval(self):
        r = run(self.copy(read(MODEL).replace("  expires: 2027-01-31\n  approved: person:maintainer\n  note: accepted", "  note: accepted")))
        self.assertTrue(has(r, "VIOLATION", "accepted conflict needs"))

    def test_convention_check(self):
        def leak(d):
            with open(os.path.join(d, "src", "api", "links.ts"), "a", encoding="utf-8") as f:
                f.write('\nimport { Pool } from "pg";\n')
        self.assertIn(("VIOLATION", "api/links.ts"), classes(run(self.copy(edit=leak)), "conventions"))

    def test_unmapped_file_and_stale_src(self):
        def add(d):
            write(os.path.join(d, "src", "orphan.ts"), "export const x = 1;\n")
            os.remove(os.path.join(d, "src", "api", "guard.test.ts"))
        r = run(self.copy(edit=add))
        self.assertIn(("VIOLATION", "orphan.ts"), classes(r, "coverage"))
        self.assertTrue(any(f["check"] == "provenance" for f in r["findings"]))

    def test_logic_edges_do_not_grant_permissions(self):
        # Fable C1: an fn-level 'calls' must not make the Guard -> Links import conforming
        text = read(MODEL).replace("        uses SafeBrowsing\n        src: api/guard.ts:6",
                                   "        uses SafeBrowsing\n        calls Links.create\n        src: api/guard.ts:6")
        r = run(self.copy(text))
        self.assertTrue(has(r, "VIOLATION", "Api.Guard depends on Api.Links"))
        self.assertTrue(has(r, "INFO", "logic edge Api.Guard.check calls Api.Links.create"))

    def test_implementation_files_are_not_exposed(self):
        def bypass(d):
            p = os.path.join(d, "src", "web", "client.ts")
            write(p, 'import { create } from "../api/links";\n' + read(p))
        self.assertTrue(has(run(self.copy(edit=bypass)), "VIOLATION", "Web.Client depends on Api.Links"))


# ------------------------------------------------------------------------------------------- adopt gate
class Gate(ExampleBase):
    def fixed(self):
        return read(MODEL).replace("    component Guard: abuse protection\n", "    component Guard: abuse protection\n      uses Links\n") \
                          .replace("      code: web/app.tsx\n", "      code: web/app.tsx\n      uses Client\n")

    def test_forward_gate(self):
        self.assertFalse(run(MODEL, gate_kind="adopt")["gate"]["pass"])
        self.assertTrue(run(self.copy(self.fixed()), gate_kind="adopt")["gate"]["pass"])

    def test_gate_in_reverse_mode_simulates_model_authority(self):
        # both reviews, C1/C2: the gate used to pass in reverse mode
        rev = read(MODEL).replace("mode: forward baseline: v1.4.0", "mode: reverse").replace("system Shortly [derived]", "system Shortly [inferred]")
        g = run(self.copy(rev), gate_kind="adopt")["gate"]
        self.assertFalse(g["pass"])
        self.assertTrue(any("Api.Guard depends on Api.Links" in b for b in g["blockers"]))
        self.assertTrue(any("inferred system" in b for b in g["blockers"]))

    def test_scoped_gate_and_apply(self):
        path = self.copy(self.fixed().replace("mode: forward baseline: v1.4.0", "mode: reverse"))
        g = run(path, gate_kind="adopt", scope="Api", apply=True, baseline="abc123")["gate"]
        self.assertTrue(g["pass"], g["blockers"])
        text = read(path)
        self.assertIn("    authority: model\n", text)
        self.assertIn("adopt scope: Api baseline: abc123", text)
        self.assertEqual(ucn_parse.parse(text)["header"]["mode"], "reverse")

    def test_inferred_clause_blocks(self):
        t = self.fixed().replace("guarantee: entries expire within an hour [stated]", "guarantee: entries expire within an hour [inferred]")
        self.assertTrue(any("inferred clause" in b for b in run(self.copy(t), gate_kind="adopt")["gate"]["blockers"]))

    def test_rebaseline_needs_reason_and_reports(self):
        g = run(MODEL, gate_kind="rebaseline", scope="Api")["gate"]
        self.assertFalse(g["pass"])
        self.assertTrue(any("StatsDirectDb" in x for x in g["report"]))


# ------------------------------------------------------------------------------------------- fail-closed governance
class Governance(Tmp):
    FILES = {"app/a/x.ts": 'import { y } from "../b/y";\nexport const x = 1;\n', "app/b/y.ts": "export const y = 1;\n",
             "app/c/z.ts": "export const z = 1;\n"}

    def deviation(self, body):
        return self.project(files=self.FILES, extra="deviation D: waiver\n" + textwrap.indent(textwrap.dedent(body), "  "))

    def test_valid_deviation_waives(self):
        r = run(self.deviation("allows A uses B\nwhy: w\nexpires: 2027-01-01\napproved: person:x\nlifecycle: accepted\n"))
        self.assertEqual(classes(r), [("WAIVED", "App.A")])

    def test_deviation_without_expiry_or_approval_does_not_waive(self):
        r = run(self.deviation("allows A uses B\nwhy: w\nlifecycle: accepted\n"))
        self.assertTrue(has(r, "VIOLATION", "needs 'expires:'"))
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.B"))

    def test_non_iso_and_far_dates_fail(self):
        r = run(self.deviation("allows A uses B\nwhy: w\nexpires: 2027-3-1\napproved: p\nlifecycle: accepted\n"))
        self.assertTrue(has(r, "VIOLATION", "not an ISO date"))
        r = run(self.deviation("allows A uses B\nwhy: w\nexpires: 2099-01-01\napproved: p\nlifecycle: accepted\n"))
        self.assertTrue(has(r, "VIOLATION", "more than 365 days"))

    def test_blanket_and_wide_waivers_fail(self):
        r = run(self.deviation("allows App uses App\nwhy: w\nexpires: 2027-01-01\napproved: p\nlifecycle: accepted\n"))
        self.assertTrue(has(r, "VIOLATION", "blanket waiver"))

    def test_non_dependency_relation_fails(self):
        r = run(self.deviation("allows A affects B\nwhy: w\nexpires: 2027-01-01\napproved: p\nlifecycle: accepted\n"))
        self.assertTrue(has(r, "VIOLATION", "not a dependency relation"))

    def test_proposed_deviation_message(self):
        r = run(self.deviation("allows A uses B\nwhy: w\nexpires: 2027-01-01\napproved: p\nlifecycle: proposed\n"))
        self.assertTrue(has(r, "VIOLATION", "is 'proposed', not accepted"))

    def test_dangling_reference_fails(self):
        r = run(self.project(GENERIC.replace("      uses B", "      uses Bee"), self.FILES))
        self.assertTrue(has(r, "VIOLATION", "dangling"))

    def test_missing_mode_with_governance_fails(self):
        r = run(self.project(GENERIC.replace(" mode: forward", "") + "    bind: R.p = app/a/x.ts#x\nreq R: r\n  param: p = 1\n", self.FILES))
        self.assertTrue(has(r, "VIOLATION", "no 'mode:'"))

    def test_lifecycle_enum(self):
        r = run(self.deviation("allows A uses B\nwhy: w\nexpires: 2027-01-01\napproved: p\nlifecycle: acepted\n"))
        self.assertTrue(has(r, "VIOLATION", "lifecycle 'acepted'"))

    def test_diff_reports_widening(self):
        path = self.project(files=self.FILES)
        git = lambda *a: subprocess.run(["git", "-C", self.d, *a], capture_output=True, check=True)
        git("init", "-q"); git("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
        write(path, read(path).replace("      code: app/a/**\n", "      code: app/a/**\n      uses B\n"))
        r = run(path, diff_rev="HEAD")
        self.assertTrue(has(r, "WIDENED", "new permission: App.A uses App.B"))
        self.assertFalse(any(f["class"] == "WIDENED" for f in run(path, diff_rev="HEAD", allow_widening=True)["findings"]))


# ------------------------------------------------------------------------------------------- scanning and resolution
class Scanning(Tmp):
    def test_comments_strings_and_docstrings_are_not_imports(self):
        r = run(self.project(files={
            "app/a/x.ts": '// import { y } from "../b/y";\n/* import "../b/y" */\nconst s = "import { y } from \'../b/y\'";\nexport const x = 1;\n',
            "app/b/y.ts": "export const y = 1;\n",
            "app/a/p.py": '"""\nfrom ..b import y\n"""\n# import app.b.y\nX = 1\n', "app/b/__init__.py": "", "app/a/__init__.py": "",
            "app/__init__.py": ""}))
        self.assertEqual(classes(r, "architecture"), [])

    def test_esm_js_specifier_and_tsconfig_alias(self):
        files = {"app/a/x.ts": 'import { y } from "../b/y.js";\nimport { z } from "@c/z";\n',
                 "app/b/y.ts": "export const y = 1;\n", "app/c/z.ts": "export const z = 1;\n"}
        path = self.project(files=files)
        write(os.path.join(self.d, "src", "tsconfig.json"),
              '{ // comment\n "compilerOptions": { "baseUrl": ".", "paths": { "@c/*": ["app/c/*"], }, },\n}\n')
        r = run(path)
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.B"))
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.C"))

    def test_python_from_package_import_submodule_and_src_layout(self):
        model = GENERIC.replace("app/a/**", "pkg/src/app/a/**").replace("app/b/**", "pkg/src/app/b/**") \
                       .replace("app/c/**", "pkg/src/app/c/**").replace("code: app/**", "code: pkg/**")
        r = run(self.project(model, {"pkg/src/app/__init__.py": "", "pkg/src/app/a/__init__.py": "",
                                     "pkg/src/app/a/x.py": "from app.b import y\n", "pkg/src/app/b/__init__.py": "",
                                     "pkg/src/app/b/y.py": "Y = 1\n"}))
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.B"))

    def test_barrel_does_not_launder(self):
        r = run(self.project(files={"app/index.ts": 'export * from "./b/y";\n', "app/b/y.ts": "export const y = 1;\n",
                                    "app/a/x.ts": 'import { y } from "../index";\n'}))
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.B"))

    def test_glob_semantics_and_overlap(self):
        model = GENERIC.replace("code: app/a/**", "code: app/a/**/*.ts").replace("code: app/b/**", "code: app/b/")
        r = run(self.project(model, {"app/a/x.ts": 'import { y } from "../b/y";\n', "app/b/y.ts": "export const y = 1;\n"}))
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.B"))
        model = GENERIC.replace("      code: app/c/**\n", "      code: app/b/**\n")
        self.assertTrue(has(run(self.project(model, {"app/b/y.ts": "export const y = 1;\n"})), "VIOLATION", "claimed by both"))

    def test_changed_paths_are_normalized_and_model_change_runs_fully(self):
        files = {"app/a/x.ts": 'import { y } from "../b/y";\n', "app/b/y.ts": "export const y = 1;\n"}
        path = self.project(files=files)
        r = run(path, changed=[os.path.join(self.d, "src", "app", "a", "x.ts")])
        self.assertEqual(r["scanned"], 1)
        self.assertTrue(has(r, "VIOLATION", "App.A depends on App.B"))
        self.assertEqual(run(path, changed=[path])["scanned"], 2)

    def test_cache_re_resolves(self):
        path = self.project(files={"app/a/x.ts": 'import { y } from "../b/y";\n', "app/c/z.ts": "export const z = 1;\n"})
        cache = os.path.join(self.d, "cache.json")
        self.assertFalse(has(run(path, cache_path=cache), "VIOLATION", "App.A depends on App.B"))
        write(os.path.join(self.d, "src", "app", "b", "y.ts"), "export const y = 1;\n")
        self.assertTrue(has(run(path, cache_path=cache), "VIOLATION", "App.A depends on App.B"))

    def test_deps_file_input(self):
        path = self.project(files={"app/a/x.ts": "export const x = 1;\n", "app/b/y.ts": "export const y = 1;\n"})
        dc = os.path.join(self.d, "dc.json")
        write(dc, json.dumps({"modules": [{"source": "src/app/a/x.ts", "dependencies": [
            {"resolved": "src/app/b/y.ts", "module": "../b/y", "dependencyTypes": ["local"], "coreModule": False, "couldNotResolve": False},
            {"resolved": "node_modules/pg/index.js", "module": "pg", "dependencyTypes": ["npm"], "coreModule": False, "couldNotResolve": False}]}]}))
        self.assertTrue(has(run(path, deps_path=dc), "VIOLATION", "App.A depends on App.B"))


# ------------------------------------------------------------------------------------------- parameter binding
class Binding(Tmp):
    def bind(self, code, path="app/a/g.ts", want="100"):
        model = GENERIC + f"    bind: R.lim = {path}#LIMIT\nreq R: r\n  param: lim = {want}\n"
        return run(self.project(model, {path: code}))

    def test_literals(self):
        for code in ["export const LIMIT = 0x64;\n", "export const LIMIT = 1e2;\n", "export const LIMIT = 10 * 10;\n",
                     "// export const LIMIT = 5;\nexport const LIMIT = 100;\n", "export const LIMIT = 1_00 as const;\n"]:
            self.assertEqual(classes(self.bind(code), "parameters"), [], code)

    def test_not_evaluable_is_info_not_violation(self):
        r = self.bind("export const LIMIT = Number(process.env.LIMIT ?? 100);\n")
        self.assertEqual(classes(r, "parameters"), [])
        self.assertTrue(has(r, "INFO", "not statically evaluable"))
        self.assertTrue(has(self.bind("let LIMIT = 100;\nLIMIT = 200;\n"), "INFO", "assigned more than once"))

    def test_python_and_scaling(self):
        self.assertEqual(classes(self.bind("LIMIT = 60 * 60\n", path="app/a/g.py", want="3600"), "parameters"), [])
        model = GENERIC + "    bind: R.lim = app/a/g.ts#LIMIT / 1000\nreq R: r\n  param: lim = 2 seconds\n"
        self.assertEqual(classes(run(self.project(model, {"app/a/g.ts": "export const LIMIT = 2000;\n"})), "parameters"), [])

    def test_mismatch(self):
        self.assertIn(("VIOLATION", "R.lim"), classes(self.bind("export const LIMIT = 500;\n"), "parameters"))


# ------------------------------------------------------------------------------------------- executable evidence (v0.6)
EVIDENCE_MODEL = GENERIC + """
req Fast: THE system SHALL be fast
  src: doc
req Safe: THE system SHALL be safe
  src: doc
req Later: THE system SHALL do later things
  lifecycle: planned
  src: doc
test FastTests [derived]: speed
  verifies Fast
  case: test_speed_*
  src: ../tests/test_perf.py
test SafeTests [derived]: safety
  verifies Safe
  src: ../tests/unit/test_safe.py
test LaterTests [derived]: later
  verifies Later
  src: ../tests/test_later.ts
"""


def junit(cases):
    rows = []
    for cls, name, status, f in cases:
        attrs = f'classname="{cls}" name="{name}"' + (f' file="{f}"' if f else "")
        body = {"failed": "<failure message='x'/>", "skipped": "<skipped/>"}.get(status, "")
        rows.append(f"<testcase {attrs}>{body}</testcase>")
    return '<testsuites><testsuite name="s">' + "".join(rows) + "</testsuite></testsuites>"


class Evidence(Tmp):
    def evidence(self, cases, **kw):
        path = self.project(EVIDENCE_MODEL, {"app/a/x.ts": "export const x = 1;\n"})
        for f in ("tests/test_perf.py", "tests/unit/test_safe.py", "tests/test_later.ts"):
            write(os.path.join(self.d, f), "x = 1\n")
        res = os.path.join(self.d, "junit.xml")
        write(res, junit(cases))
        return run(path, results=[res], **kw)

    def test_pass_fail_and_case_glob(self):
        r = self.evidence([("test_perf", "test_speed_fast", "passed", ""), ("test_perf", "test_other", "failed", ""),
                           ("unit.test_safe.TestX", "test_ok", "failed", "")])
        self.assertTrue(has(r, "VIOLATION", "req Safe is not met: test SafeTests failed"))
        self.assertFalse(has(r, "VIOLATION", "Fast"))   # the failing case does not match case: test_speed_*
        self.assertEqual(r["evidence"]["passed"], 1)

    def test_missing_and_require_evidence(self):
        r = self.evidence([("test_perf", "test_speed_fast", "passed", "")])
        self.assertTrue(has(r, "INFO", "req Safe has no passing evidence (SafeTests: missing)"))
        r = self.evidence([("test_perf", "test_speed_fast", "passed", "")], require_evidence=True)
        self.assertTrue(has(r, "VIOLATION", "req Safe has no passing evidence"))
        self.assertFalse(has(r, "VIOLATION", "Later"))   # planned requirements are not required to have evidence

    def test_planned_failure_is_info_and_file_attribute_matching(self):
        r = self.evidence([("Later suite", "does later things", "failed", "tests/test_later.ts")])
        self.assertTrue(has(r, "INFO", "req Later is not met"))
        self.assertFalse(has(r, "VIOLATION", "Later"))

    def test_skipped_is_not_evidence(self):
        r = self.evidence([("test_perf", "test_speed_fast", "skipped", "")])
        self.assertTrue(has(r, "INFO", "req Fast has no passing evidence (FastTests: skipped)"))

    def test_classname_suffix_must_match_the_path(self):
        # 'other.test_safe' is a different module than tests/unit/test_safe.py
        r = self.evidence([("other.test_safe", "test_ok", "passed", "")])
        self.assertTrue(has(r, "INFO", "req Safe has no passing evidence"))

    def test_file_attribute_matches_on_a_path_boundary(self):
        # 'tests/old_test_later.ts' ends with 'test_later.ts' but is a different file (review v0.6)
        r = self.evidence([("Later suite", "does later things", "failed", "tests/old_test_later.ts")])
        self.assertFalse(has(r, "INFO", "req Later is not met"))
        r = self.evidence([("Later suite", "does later things", "failed", "repo/tests/test_later.ts")])
        self.assertTrue(has(r, "INFO", "req Later is not met"))


# ------------------------------------------------------------------------------------------- stale sources (v0.6)
class Stale(Tmp):
    MODEL = GENERIC + "    fn run(x: int): int\n      src: app/a/x.ts:2\n"

    def setUp(self):
        super().setUp()
        self.path = self.project(self.MODEL, {"app/a/x.ts": "// a\nexport function run(x: number) { return x; }\n"})
        ucn_validate.stamp(self.path)
        self.code = os.path.join(self.d, "src", "app", "a", "x.ts")

    def test_stamp_adds_hash_and_clean_run(self):
        self.assertRegex(read(self.path), r"src: app/a/x.ts:2@[0-9a-f]{8}")
        self.assertFalse(any(f["check"] == "provenance" for f in run(self.path)["findings"]))

    def test_moved_line_is_followed(self):
        write(self.code, "// new header\n" + read(self.code))
        self.assertTrue(has(run(self.path), "MODEL-UPDATE", "moved to line 3"))
        ucn_validate.stamp(self.path)
        self.assertIn("app/a/x.ts:3@", read(self.path))
        self.assertFalse(any(f["check"] == "provenance" for f in run(self.path)["findings"]))

    def test_changed_content_needs_review(self):
        write(self.code, read(self.code).replace("run(x: number)", "run(x: number, y: number)"))
        r = run(self.path)
        self.assertTrue(has(r, "MODEL-UPDATE", "the referenced code changed"))
        self.assertEqual(r["stale"], 1)
        before = read(self.path)
        changes = ucn_validate.stamp(self.path)
        self.assertTrue(any("needs review" in c for c in changes))
        self.assertEqual(read(self.path), before)                 # not accepted silently
        ucn_validate.stamp(self.path, accept_changed=True)
        self.assertFalse(any(f["check"] == "provenance" for f in run(self.path)["findings"]))

    def test_indentation_does_not_matter(self):
        write(self.code, read(self.code).replace("export function", "    export   function"))
        self.assertFalse(any(f["check"] == "provenance" for f in run(self.path)["findings"]))

    def test_ambiguous_move_is_never_guessed(self):
        fn = read(self.code).split("\n")[1]
        write(self.code, f"// h\n// h2\n{fn}\n// gap\n{fn}\n")
        self.assertTrue(has(run(self.path), "MODEL-UPDATE", "now appears 2 times"))
        before = read(self.path)
        self.assertTrue(any("appears 2 times" in c for c in ucn_validate.stamp(self.path)))
        self.assertEqual(read(self.path), before)

    def test_trivial_lines_are_not_followed(self):
        # a reference to '}' must not "move" to another function's '}' (review v0.6)
        write(self.code, "function f() {\n}\nfunction g() {\n}\n")
        write(self.path, re.sub(r"x\.ts:2@\w+", "x.ts:2", read(self.path)))
        ucn_validate.stamp(self.path)
        write(self.code, "function f() {\n  return 1;\n}\n")
        self.assertTrue(has(run(self.path), "MODEL-UPDATE", "the referenced code changed"))

    def test_line_zero_is_invalid(self):
        write(self.path, read(self.path).replace(re.search(r"x\.ts:2@\w+", read(self.path)).group(0), "x.ts:0@deadbeef"))
        self.assertTrue(has(run(self.path), "MODEL-UPDATE", "points outside the file"))
        self.assertTrue(any("invalid line number" in c for c in ucn_validate.stamp(self.path)))


# ------------------------------------------------------------------------------------------- rationale links (v0.6)
class Rationale(ExampleBase):
    def test_links_resolve_and_breakage_is_reported(self):
        r = run(MODEL)
        self.assertEqual(r.get("rationale"), 4)
        self.assertFalse(any(f["check"] == "rationale" for f in r["findings"]))

        def break_docs(d):
            p = os.path.join(d, "docs", "adr", "003-immutable-codes.md")
            write(p, read(p).replace("## Why immutable", "## Rationale"))
            os.remove(os.path.join(d, "docs", "adr", "002-cache-aside.md"))
        r = run(self.copy(edit=break_docs))
        self.assertTrue(has(r, "MODEL-UPDATE", "no heading with anchor #why-immutable"))
        self.assertTrue(has(r, "MODEL-UPDATE", "002-cache-aside.md#why-cache-aside: file not found"))

    def test_slugs(self):
        self.assertEqual(ucn_validate.heading_slugs("# A b\n## Why: (now)?\n## A b\n"), {"a-b", "why-now", "a-b-1"})


# ------------------------------------------------------------------------------------------- default projector (v0.6)
class Projector(unittest.TestCase):
    TASK = "implement custom aliases: premium users can choose the code of a link"

    def test_projections_pass_the_checker_at_every_budget(self):
        for budget in (400, 800, 1500, 3000):
            text, errs = ucn_project.project(MODEL, self.TASK, budget)
            self.assertEqual(errs, [], budget)
            self.assertIn("goal Abuse [pin]", text)             # global pins always present
            self.assertIn("Blocklist", text)                    # scoped pins at least named

    def test_seeds_and_detail(self):
        text, _ = ucn_project.project(MODEL, self.TASK, 3000)
        self.assertIn("req Alias", text)
        self.assertIn("config AliasesEnabled", text)
        self.assertIn("term PremiumUser", text)
        self.assertIn("pre: isHttpUrl(url) [inferred]", text)   # create() upgraded to L2 when the budget allows

    def test_stated_rules_follow_the_seeds(self):
        d = tempfile.mkdtemp()
        self.addCleanup(rmtree, d)
        write(os.path.join(d, "model.ucn"), RULES)
        text, errs = ucn_project.project(os.path.join(d, "model.ucn"), "change Q so it can show Side output", 1500)
        self.assertEqual(errs, [])
        self.assertIn("forbids Side", text)

    def test_deterministic(self):
        self.assertEqual(ucn_project.project(MODEL, self.TASK, 1500)[0], ucn_project.project(MODEL, self.TASK, 1500)[0])

    def test_budget_too_small_is_reported(self):
        _, errs = ucn_project.project(MODEL, self.TASK, 100)
        self.assertTrue(any("exceed budget" in e for e in errs))


# ------------------------------------------------------------------------------------------- export
class Export(Tmp):
    def test_dependency_cruiser_and_import_linter(self):
        path = self.project(GENERIC + "convention Db: db only in b\n  check: only app/b/** imports pg\n")
        dc = ucn_export.export(path, "dependency-cruiser")
        self.assertIn("allowedSeverity", dc)
        self.assertIn('"path": "^src/app/c', dc)
        il = ucn_export.export(path, "import-linter", package="app")
        self.assertIn("[importlinter:contract:", il)
        self.assertIn("app.a", il)


# ------------------------------------------------------------------------------------------- rule vocabulary (v0.5)
RULES = """
ucn 0.5 system: S origin: stated mode: forward policy: deny root: src
container App [derived]: app
  code: app/**
  acyclic: yes
  layers: Top > Mid > Low
  independent: P, Q
  component Top: top layer
    code: app/top/**
  component Mid: middle layer
    code: app/mid/**
  component Low: bottom layer
    code: app/low/**
  component Side: outside the layers
    code: app/side/**
  component P: independent part
    code: app/p/**
  component Q: independent part
    code: app/q/**
    forbids Side
"""
DEV = "deviation D: w\n  allows {}\n  why: w\n  expires: 2027-01-01\n  approved: p\n  lifecycle: accepted\n"


class Rules(Tmp):
    def rules(self, files, extra="", model=RULES):
        return run(self.project(model + extra, files))

    def test_deny_policy_allows_undeclared(self):
        r = self.rules({"app/top/a.ts": 'import "../low/b";\n', "app/low/b.ts": "export {};\n"})
        self.assertEqual(classes(r, "architecture"), [])

    def test_layers_direct_and_transitive(self):
        r = self.rules({"app/low/a.ts": 'import "../top/b";\n', "app/top/b.ts": "export {};\n"})
        self.assertTrue(has(r, "VIOLATION", "App.Low is below App.Top"))
        r = self.rules({"app/low/a.ts": 'import "../side/s";\n', "app/side/s.ts": 'import "../top/b";\n',
                        "app/top/b.ts": "export {};\n"})
        self.assertTrue(has(r, "VIOLATION", "App.Low reaches App.Top indirectly"))

    def test_waiver_breaks_the_chain_and_counts_as_used(self):
        files = {"app/low/a.ts": 'import "../side/s";\n', "app/side/s.ts": 'import "../top/b";\n', "app/top/b.ts": "export {};\n"}
        r = self.rules(files, DEV.format("Side uses Top"))
        self.assertFalse(has(r, "VIOLATION", "indirectly"))
        self.assertFalse(has(r, "INFO", "matches no dependency"))

    def test_unused_deviation_is_reported(self):
        r = self.rules({"app/top/b.ts": "export {};\n"}, DEV.format("Low uses Top"))
        self.assertTrue(has(r, "INFO", "deviation D matches no dependency"))

    def test_independent_forbids_and_cycles(self):
        r = self.rules({"app/p/a.ts": 'import "../q/b";\n', "app/q/b.ts": 'import "../side/s";\n',
                        "app/side/s.ts": 'import "../q/b";\n'})
        self.assertTrue(has(r, "VIOLATION", "must stay independent"))
        self.assertTrue(has(r, "VIOLATION", "App.Q forbids App.Side"))
        self.assertTrue(has(r, "VIOLATION", "cycle inside App"))

    def test_reverse_mode_contradiction_is_a_conflict_and_not_proposed(self):
        path = self.project(RULES.replace("mode: forward", "mode: reverse"),
                            {"app/q/b.ts": 'import "../side/s";\n', "app/side/s.ts": "export {};\n"})
        r = ucn_validate.validate(path, today=TODAY)
        m = r.pop("_model")
        self.assertTrue(has(r, "CONFLICT", "contradicts a stated rule"))
        proposal = "\n".join(ucn_validate.propose(m, r["findings"]))
        self.assertIn("not proposed", proposal)
        self.assertNotIn("uses Side", proposal)
        self.assertFalse(run(path, gate_kind="adopt")["gate"]["pass"])

    def test_known_conflict_downgrades(self):
        extra = "conflict QS: stated rule vs code\n  about Q, Side\n  lifecycle: open\n  side Rule: never\n  side Code: does\n"
        r = self.rules({"app/q/b.ts": 'import "../side/s";\n', "app/side/s.ts": "export {};\n"}, extra)
        self.assertTrue(has(r, "KNOWN-CONFLICT", "App.Q forbids App.Side"))

    def test_inherit(self):
        model = GENERIC.replace("      uses B\n", "      uses B\n      component C1: part of c\n        code: app/c/c1/**\n")
        files = {"app/c/c1/x.ts": 'import "../../b/y";\n', "app/b/y.ts": "export {};\n"}
        self.assertTrue(has(run(self.project(model, files)), "VIOLATION", "App.C.C1 depends on App.B"))
        model = model.replace("        code: app/c/c1/**\n", "        code: app/c/c1/**\n        inherit: yes\n")
        self.assertFalse(has(run(self.project(model, files)), "VIOLATION", "App.C.C1 depends on App.B"))

    def test_diff_reports_removed_rule(self):
        path = self.project(RULES, {"app/top/b.ts": "export {};\n"})
        git = lambda *a: subprocess.run(["git", "-C", self.d, "-c", "user.email=t@t", "-c", "user.name=t", *a],
                                        capture_output=True, check=True)
        git("init", "-q")
        git("add", "-A")
        git("commit", "-qm", "base")
        write(path, read(path).replace("    forbids Side\n", ""))
        self.assertTrue(has(run(path, diff_rev="HEAD"), "WIDENED", "removed rule"))

    def test_export_bugs_found_by_running_the_real_tools(self):
        # dependency-cruiser rejects nested quantifiers; 'type-only' is not external; bare dirs inside braces
        model = GENERIC.replace("code: app/**", "code: {app,lib}/**")
        dc = ucn_export.export(self.project(model), "dependency-cruiser")
        self.assertNotIn("(?:/.*)?", dc)
        self.assertNotIn('"type-only"', dc)
        self.assertIn("(?:app|lib)/", dc)
        self.assertNotIn("app//", dc)
        # import-linter: exact module pairs for ignores, and direct-only conventions
        files = {"app/__init__.py": "", "app/a/__init__.py": "", "app/a/x.py": "from app.b import y\n",
                 "app/b/__init__.py": "", "app/b/y.py": "import pg\n"}
        model = GENERIC.replace("    component C: c", "    layers: B > A\n    component C: c") + \
            "convention Db: db only in b\n  check: only app/b/** imports pg\n" + \
            "deviation D: w\n  allows A uses B\n  why: w\n  expires: 2027-01-01\n  approved: p\n  lifecycle: accepted\n"
        il = ucn_export.export(self.project(model, files), "import-linter", package="app", today=TODAY)
        self.assertIn("    app.a.x -> app.b.y", il)
        self.assertIn("allow_indirect_imports = True", il.split("[importlinter:contract:ucn-Db]")[1])

    def test_export_rules(self):
        path = self.project(RULES)
        il = ucn_export.export(path, "import-linter", package="app")
        self.assertIn("type = layers", il)
        self.assertIn("type = independence", il)
        self.assertIn("name = App.Q forbids App.Side", il)
        dc = ucn_export.export(path, "dependency-cruiser")
        self.assertIn('"circular": true', dc)
        self.assertNotIn("allowedSeverity", dc)   # deny policy: no allow-list


# ------------------------------------------------------------------------------------------- pilot harness
class PythonSubmoduleConvention(Tmp):
    """'only X imports django.db.models.signals' must see submodule imports (found on saleor, v0.6 follow-up)."""

    def test_submodule_convention(self):
        extra = ("convention NoSignals: logic is called explicitly, not through signals\n"
                 "  check: only app/a/{migrations/**,apps.py} imports django.db.models.signals\n")
        path = self.project(files={"app/a/x.ts": "export const x = 1;\n",
                                   "app/a/apps.py": "from django.db.models.signals import post_migrate\n",
                                   "app/c/y.py": "from django.db.models.signals import post_save\nimport django.db.models\n"},
                            extra=extra)
        bad = [f["message"] for f in run(path)["findings"] if f["check"] == "conventions"]
        self.assertEqual(len(bad), 1)
        self.assertIn("app/c/y.py imports django.db.models.signals", bad[0])

    def test_uses_pattern_convention(self):
        extra = ("rule NoSiteId: never read settings.SITE_ID outside the site picker\n"
                 "  check: only app/a/** uses settings\\.SITE_ID\\b\n")
        path = self.project(files={"app/a/x.ts": "export const x = 1;\n",
                                   "app/a/pick.py": "site_id = settings.SITE_ID\n",
                                   "app/c/y.py": "# settings.SITE_ID in a comment is fine\nx = settings.SITE_ID\n"},
                            extra=extra)
        bad = [f["message"] for f in run(path)["findings"] if f["check"] == "conventions"]
        self.assertEqual(bad, ["app/c/y.py:2 uses /settings\\.SITE_ID\\b/, but NoSiteId allows it only in app/a/**"])


class ReconGrading(Tmp):
    """recon.grade_one with the containers faked: it must fail closed and catch tampering (review v0.6)."""

    def setUp(self):
        super().setUp()
        import recon
        self.recon = recon
        self.model = self.project(files={"app/a/x.ts": "export const x = 1;\n"})
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
            subprocess.run(["git", "-C", self.d, *cmd], capture_output=True, check=True)
        self.pristine = os.path.join(self.d, "..", os.path.basename(self.d) + "-pristine.ucn")
        shutil.copy(self.model, self.pristine)
        self.addCleanup(os.remove, self.pristine)
        os.makedirs(os.path.join(self.d, "_task", "grader"))
        self.spec = {"model": self.pristine, "validator": os.path.join(ROOT, "tools", "ucn_validate.py"),
                     "grader_image": "G", "lint_image": "L"}

    def grade(self, lint_stdout, cond="L", guarded=None):
        real = self.recon.run

        def fake(cmd, **kw):
            if cmd[0] != "docker":
                return real(cmd, **kw)
            if "G" in cmd:  # the hidden grader: one passing case
                out = [a for a in cmd if a.endswith(":/out")][0].rsplit(":", 1)[0]
                write(os.path.join(out, "r1.xml"), junit([("test_t", "test_ok", "passed", "")]))
            return subprocess.CompletedProcess(cmd, 0, lint_stdout if "L" in cmd else "", "")
        self.recon.run = fake
        self.addCleanup(setattr, self.recon, "run", real)
        entry = {"run": "r1", "task": "t", "cond": cond, "workspace": self.d, "guarded": guarded or {},
                 "validator_sha": self.recon.sha(self.spec["validator"])}
        return self.recon.grade_one(self.spec, entry, {"dir": os.path.join(self.d, "_task")}, set())

    def test_clean_run(self):
        r = self.grade("Contracts: 4 kept, 0 broken.")
        self.assertEqual((r["success"], r["violations"], r["tampered"]), (1, 0, []))

    def test_missing_import_linter_result_fails_closed(self):
        r = self.grade("Traceback: something broke")
        self.assertEqual(r["violations"], 1)
        self.assertIn("grading_error", r)

    def test_missing_contract_fails_closed_and_old_results_are_not_reused(self):
        self.spec["contracts"] = 4
        self.assertEqual(self.grade("Contracts: 3 kept, 0 broken.")["violations"], 1)
        real = self.recon.run  # second grading: the grader container "fails" and writes nothing
        self.recon.run = lambda cmd, **kw: (subprocess.CompletedProcess(cmd, 125, "", "") if cmd[0] == "docker" else real(cmd, **kw))
        try:
            entry = {"run": "r1", "task": "t", "cond": "L", "workspace": self.d}
            r = self.recon.grade_one(self.spec, entry, {"dir": os.path.join(self.d, "_task")}, set())
        finally:
            self.recon.run = real
        self.assertEqual(r["success"], 0)

    def test_tampering_with_model_context_or_contracts(self):
        ctx = os.path.join(self.d, "context.ucn")
        write(ctx, "ucn 0.4 system: S\n")
        guarded = {"context.ucn": self.recon.sha(ctx)}
        shutil.copy(self.pristine, os.path.join(self.d, "model.ucn"))
        self.assertEqual(self.grade("Contracts: 4 kept, 0 broken.", "B", guarded)["tampered"], [])
        write(ctx, "ucn 0.4 system: S\n# edited\n")
        write(os.path.join(self.d, "model.ucn"), read(self.pristine) + "\n# loosened\n")
        write(os.path.join(self.d, "pyproject.toml"), "[tool.importlinter]\n")
        r = self.grade("Contracts: 4 kept, 0 broken.", "B", guarded)
        self.assertEqual(r["tampered"], ["context.ucn", "model.ucn", "pyproject.toml"])
        self.assertEqual(r["violations"], 1)


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

    def test_template_runs(self):
        with open(os.path.join(ROOT, "examples", "pilot", "template.json")) as f:
            self.assertIn(pilot_eval.evaluate(json.load(f))["decision"], ("GO", "KILL", "EXTEND"))


if __name__ == "__main__":
    unittest.main()
