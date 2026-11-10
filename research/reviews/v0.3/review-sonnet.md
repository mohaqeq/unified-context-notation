Reviewer: Sonnet 5.5 (claude-sonnet-5-5)
Date: 2026-11-05
Reviewed commit: 28a99f1

# Review of UCN v0.3

## Verdict

The v0.3 reframing is the right move. A checked intent-and-architecture layer is a more defensible product than "compact context for small LLMs", and the self-assessment in docs/05 (lightweight-stack baseline, MDE history, "the pilot will not reach statistical power") is more honest than most research proposals. But the artifacts do not yet back the claims. The validator is a ~400-line regex reflexion checker. In its present form it is a weaker ArchUnit/dependency-cruiser/import-linter with a nicer model file, and it has several correctness holes that make it fail open in exactly the places the spec says it fails closed:

- the adopt gate is vacuous when run before switching to forward mode;
- deviation expiry is optional and string-compared;
- parameter binding reads the first textual match of a name;
- the cache goes stale;
- `--changed` silently scans nothing with the paths git produces.

The differentiators (authority/origin, expiring deviations, accepted conflicts, `param`/`bind`) are good ideas implemented at demo depth, and nothing yet shows they beat "structured AGENTS.md + ADRs + a dependency rules file + requirement IDs" on a real repository. The pilot as designed can practically only kill the project through the upkeep criterion. It cannot confirm a benefit, and a cheap path to GO exists through author-written "tempting tasks". The performance claims hold only for a favourable synthetic case.

**Overall score: 6/10** (idea and honesty 8, spec 7, tooling 4, pilot design 5).

**Worth building? Conditionally.** Build the narrow thing: a model-driven conformance and traceability checker on top of existing graph exporters, with a layering/forbid/cycle vocabulary, requirement-to-test evidence checks, an exact deviation lifecycle, and a precise authority/gate. Run the pilot only after the Critical issues are fixed. Do not invest in the custom syntax, the knapsack projection or the logic module before the pilot says GO. The real differentiator against the baseline is governance (waivers with expiry, authority per subtree, reviewed adoption). That is the one place where the baseline is genuinely weak, and also where the implementation is currently weakest.

## Strengths

- The goal change is coherent. Core vs modules is mostly right, and demoting the code-logic layer is correct (docs/05 §5.2): code is its own best representation, so index and check it rather than restate it.
- Origin vs authority (docs/03 §3.6) is a real insight. The four result classes (VIOLATION / MODEL-UPDATE / WAIVED / KNOWN-CONFLICT) are what a team in transition needs. No mainstream arch linter distinguishes "code wrong" from "model stale".
- Expiring, approved, in-model deviations beat ArchUnit freeze stores. `conflict` + `about` for known doc-vs-code disagreement is novel and practical.
- Pre-registered pilot with kill criteria and a harness. The statistics family (exact McNemar, paired bootstrap) is right, and the self-critique on power is accurate (I reproduced about 368 pairs).
- Zero dependencies, milliseconds on small repos, 18/18 tests pass. The example plants one finding per class, which teaches well.
- The lightweight stack is treated as the real baseline (docs/03 §3.12 f2).

## Critical issues (must fix)

### C1. The adopt gate is vacuous when used as specified
**Location:** tools/ucn_validate.py gate block (`if m.authority(nid) != "model" or m.layer(nid) not in ("intent","arch"): continue`), docs/03 §3.6, tests/test_tools.py `test_adopt_gate`.

**Problem:**
- The gate evaluates current authority. Run on a reverse-mode model (the only time you would run an adopt gate), `authority()` is `source` for every node, so the inferred-node check is skipped. Architecture violations are classed MODEL-UPDATE rather than VIOLATION, so the `blockers += VIOLATION findings` list is empty too.
- There is no target argument (`--subtree`, `--to forward`) and no simulation of the switch.
- §3.6 says "Passing the gate records `mode: forward` and `baseline: <commit>`". Nothing is written.
- The test only runs the gate on a model already in forward mode.
- Open conflicts block regardless of authority. `accepted` conflicts are never checked for the "tracking note" the spec requires.

**Reproduction:**
```
reverse model, A.A1 imports B.B1 with no relation  -> MODEL-UPDATE, gate pass: True, blockers []
same model, header origin: inferred, mode reverse   -> no findings, gate pass: True
same violation with mode: forward                   -> VIOLATION, gate BLOCKED
```
**Fix:**
1. Add a target: `--gate adopt [--subtree X]`.
2. Compute authority as if the target subtree were `model` (override the map in memory), run the full pipeline, and block on every finding that would be a VIOLATION under that map.
3. Write `mode`/`baseline` (or `authority:` on the subtree) only on pass, via an explicit `--apply`.
4. Add reverse-mode gate tests.

### C2. Deviation lifecycle fails open
**Location:** tools/ucn_validate.py waivers (`active = ... and (not exp or exp >= today)`), tools/ucn_parse.py lint, docs/03 §3.13 ("Every deviation needs `expires:` and `approved:`; an expired deviation fails CI").

**Reproductions (all produce WAIVED and exit 0):**
- A deviation with no `expires:` and no `approved:` waives forever ("expires never"). The lint warning is demoted to INFO.
- `expires: never` waives forever (string 'n' > '2').
- `expires: 2027-3-1` evaluated on 2027-12-01 is still active (lexical comparison).
- `lifecycle: acepted` (typo) or `proposed` produce the message "deviation expired on 2030-01-01", which is wrong. The enum is not validated for deviations.
- The waiver scope is the element pair, not the instance. `allows Stats uses Db` also waives any future file in Stats that imports Db.
- The `allows <ref> <relation> <ref>` relation keyword is ignored (`allows A1 emits B1` waives an import).

**Fix:**
1. Parse `expires` as an ISO date (hard error otherwise), and require `expires` and `approved`.
2. Validate the lifecycle enums per kind.
3. Cap the maximum lifetime.
4. Optionally add `scope: <file glob>`.
5. Warn on deviations that expire within N days.

### C3. Parameter binding is regex-on-text, with false negatives and false positives
**Location:** tools/ucn_validate.py parameter block, docs/03 §3.7.

**Problem:** the first textual occurrence of `NAME ... = number` anywhere in the file is used. Requirement `lim = 100`, binding `R.lim = a/g.ts#LIMIT`:

| Code | Result |
|---|---|
| `// const LIMIT = 100;` then `export const LIMIT = 500;` | pass (false negative) |
| local `const LIMIT = 100` in a function, then exported `LIMIT = 999` | pass (false negative) |
| `let LIMIT = 100; LIMIT = 200;` | pass (false negative) |
| `LIMIT = 0x64` | VIOLATION, reads 0 (false positive) |
| `LIMIT = 1e2` | VIOLATION, reads 1 (false positive) |
| `LIMIT = Number(process.env.LIMIT ?? 100)` | VIOLATION "constant not found" (hard fail on the most common production pattern) |
| `{ LIMIT: 100 }` object property | VIOLATION "not found" |
| `60 * 60` | reads 60 |

Units are ignored: "100 per hour" can never be compared with `3600_000`.

An `accepted` conflict masks every future value. With the code drifting from 1000 to 999999 the result is still KNOWN-CONFLICT. Conflicts have no expiry either, which makes them a permanent waiver and contradicts the "waivers become permanent" mitigation.

**Fix:**
1. Resolve the exported symbol with tree-sitter, the TS compiler API or Python `ast`, and evaluate only literal expressions. Anything else is INFO "not statically evaluable", never VIOLATION.
2. Restrict bindings to same-unit values, or add `unit:` normalisation.
3. Let a `side` assert its code value, and downgrade only while the code still equals it.
4. Give `conflict` an optional `expires:`.

### C4. Incremental mode and cache have silent-pass bugs
**Location:** tools/ucn_validate.py `scan_imports`, `--changed`, `--cache`, docs/05 §5.3 (the pre-commit < 1 s claim).

1. **Stale cache.** The key is the importing file's mtime and size. Resolution ("missing"/"file"/"ext") depends on the whole file set. Reproduction: `a/one.ts` imports `../b/new`, which does not exist, so the result is cached. Create `b/new.ts`. With the cache: no finding. Without it: `A.A1 depends on B, which the model does not allow`.
2. **`--changed` path base.** Paths are compared with paths relative to the model's `root:`. Git hooks pass repo-root-relative paths. With `root: src`, `--changed src/a/one.ts` scans 0 files and exits 0; `a\one.ts` and nonexistent paths do the same. The headline pre-commit feature therefore passes everything unless users normalise paths by hand.
3. Smaller problems: `set(changed)` is rebuilt for every file (O(n·m)), the cache never prunes deleted files, and the cache is not versioned against the tool or the model.

**Fix:** normalise `--changed` against the repo root and `root:` and error on non-matches. Cache raw specifiers and resolve on every run (cheap). Version the cache header.

### C5. Import extraction misses mainstream cases and invents others
**Location:** `JS_IMPORT`, `PY_IMPORT`, `RESOLVE_EXT` in tools/ucn_validate.py. docs/03 §3.13 claims "Misses are false negatives, so the check never blocks wrongly". Invented dependencies do block.

| Case | Result |
|---|---|
| `import x from '../b/one.js'` where the file is `one.ts` (NodeNext/ESM) | INFO "unresolved". The dependency is invisible. This is a false negative on a large share of modern TS repos. |
| `@/b/one`, `~/b/one` tsconfig `paths` aliases | silently treated as external packages |
| `import './s.css'`, images, JSON | INFO noise |
| import text inside `//`, `/* */`, a string, or a Python docstring | VIOLATION (false positive that fails CI in forward mode) |
| `jest.mock('../b/one')`, computed `import(p)`, `importlib.import_module` | missed |
| Python `from pkg import b` (b is a subpackage) | missed |
| Python src-layout (`src/pkg/...`, `from pkg.b.mod import f`) | missed; no source-root config |

**Fix:** do not make the regex the enforcement path. Make the input contract a normalised edge list: `dependency-cruiser --output-type json`, `madge --json`, grimp, `go list`/`jdeps`, SCIP, or tree-sitter plus a tsconfig-aware resolver. Keep the regex as a labelled fallback that reports its blind spots with counts.

## Major issues (should fix)

### M1. The dependency model is allow-list only
**Location:** docs/03 §3.7, §3.2.

- There is no `forbid`, layering, cycle or transitive rule.
- Reproduction: containers `A uses B` / `B uses A` with mutual imports produce no findings, and the same holds for component cycles P<->Q. The shipped example's single violation (Guard<->Links) is a cycle that is caught only because the reverse edge happens to be undeclared.
- Barrel `A -> Barrel -> B` is accepted. This is correct reflexion semantics, but there is no way to say "A must never reach B transitively".
- Parent/child imports are always allowed (`is_under` either way), so a child importing its container's own file (an upward dependency) passes silently.

**Fix:** add `forbids`, `layer` ordering, `acyclic`, and reachability rules. ArchUnit, import-linter (`forbidden`, `layers`, `independence`) and Deptrac already have them.

### M2. Lifting and `exposes` are too permissive and inconsistent
**Location:** `allowed()` and `exposed()` in tools/ucn_validate.py.

- An edge declared by any descendant of the importer is credited to the importer, so a relation declared on a `fn` licenses every file of the owning container.
- `Web uses Api`, `Api exposes Pub` and `Links implements Pub` make `api/links.ts` importable from `web/x.ts`. A static import of an implementation file from another container is treated as using the exposed interface. In Shortly the interface is HTTP, so a static import is exactly the bypass the rule should catch.
- Two implementers of one `api` are importable from outside.
- Encapsulation exists only for containers. `Q uses P` may import `P.Inner` directly.
- `SYMMETRIC` implements is inconsistent. Links->Secret (sibling implementers) is flagged, but Pub->Secret and Web->Secret are allowed.
- `test` authority is fixed at `source`, so a test importing an unrelated container is MODEL-UPDATE, never VIOLATION, even in forward mode. Production code importing a test file is a VIOLATION. This asymmetry is undocumented.
- A test node without `src:` leaves its file owned by the container, so the container's rules apply. Behaviour flips on an unrelated attribute.

**Fix:** define encapsulation as "reachable from outside only through files owned by an `api` node the element exposes, or listed in `entry:`". Do not use `implements` to extend reachability.

### M3. Glob semantics diverge from every tool people know, and overlap is silent
**Location:** `glob_re`, `specificity`, claim ordering.

- `a/**/*.ts` does not match `a/z.ts`, contrary to gitignore/minimatch/CODEOWNERS.
- `a/`, `a` and `./a/**` match nothing, so a flood of "not claimed" coverage violations follows in forward mode.
- Overlapping globs resolve by literal prefix, then depth, then declaration order. `a/*.ts` (X) and `a/**/gen.ts` (Y) both claim `a/gen.ts`; X wins silently. There is no overlap report.
- Matching is case-sensitive on case-insensitive filesystems.
- Coverage uses the header `mode`, not per-subtree authority, so in a hybrid model an unclaimed legacy file is a VIOLATION although §3.6 says hybrid is the normal adoption state.

**Fix:** use a gitignore/pathspec-compatible matcher, treat `dir/` as `dir/**`, warn on equal-specificity overlaps, and derive the coverage class from the nearest subtree's authority.

### M4. Spec/code disagreement on `rule`, and `mode` defaults to the weakest setting
**Location:** docs/03 §3.2 table (rule under Logic) vs §3.0 (rule under Intent in Core); tools/ucn_validate.py `INTENT` includes `rule` while tools/ucn_parse.py `LOGIC` includes `rule`.

The preset gives `rule` model authority in the validator but source authority by the spec's own layer table. Separately, `self.mode = header.get("mode", "reverse")` means a model with a forgotten `mode:` blocks nothing.

**Fix:** put `rule` in Intent everywhere, and require `mode` once any `bind`, `check` or `deviation` is present.

### M5. Provenance and "staleness" are weaker than claimed
**Location:** docs/05 §5.3 table ("hash-based staleness | yes"), docs/03 §3.4, tools/ucn_validate.py provenance.

- Hash propagation and Merkle staleness exist only in the spec. The validator checks that the file exists and the line is in range. A function that moved 200 lines is "fresh".
- `docs/...#section` and `ticket#` sources are never verified, so the trust tiers in §3.13 have no mechanism.
- `test` nodes: nothing checks that the named test exists or passes. `verifies`/`verified:` are only links.

**Fix:** store a content hash of the cited range or symbol (`src: api/links.ts#create@a1b2c3`). For tests, ingest JUnit/jest JSON from CI and check requirement -> test -> last result. That is the highest-value deterministic requirements<->code check available, and it is absent.

### M6. Inter-layer consistency that is deterministic but uncovered
- Requirement -> architecture: a `satisfies` target with no `code:` match or no test.
- `api` vs OpenAPI/Protobuf: diff operations between the spec file and the model.
- `emits`/`consumes` vs publisher/subscriber call sites, `config` vs env/flag reads, `data` vs migrations/schema, and `deploysTo` vs IaC.
- A superseded `decision` whose `affects` target still has live links; `refines` cycles; goals with no requirement.
- The thesis "architecture and code must not contradict requirements" reduces to numeric `param` equality plus one `check:` grammar (`only <glob> imports <module>`). Most requirements are not numeric constants. A small catalogue of check templates, plus an escape hatch that runs an external rule file (ArchUnit, Semgrep, dependency-cruiser) and ingests its exit status or SARIF, would extend this cheaply and stay deterministic.
- Dangling and ambiguous references in `uses`/`implements` are INFO ("traces") in the validator. They silently remove edges from conformance checking and should be errors.

### M7. Performance claims are credible only for a favourable case
**Location:** docs/05 §5.3, docs/03 §3.7.

I measured on Windows 11, Python 3.13, 20,000 TS files, 120,000 imports and 200 containers with 6 declared `uses` each (random import graph, so dense):

| Run | Time |
|---|---|
| first read of freshly generated files | 232 s |
| second cold run (no cache) | 31 s |
| warm cache | 23-33 s (no speed-up) |
| `--changed` 1 file, with cache | 0.78 s |
| `--changed` 1 file, no cache | 0.4 s |

- The authors' 4.6 s and 1.5 s are not reproduced on a dense graph. The warm run is dominated not by file reading but by `allowed()`, which is O(distinct owner/target pairs x declared edges x ancestor chains) and is recomputed on every run without memoisation (about 37k distinct pairs here). Precomputing ancestor-expanded edge sets would make it linear. My graph is denser than most real ones, but the algorithm is quadratic where it need not be.
- The "176 s was an antivirus artifact" statement is not an artifact for users. Fresh clones, branch switches and CI cache restores all hit first-read scanning (232 s for me). Say that the cold cost is dominated by the OS.
- 36,619 findings are printed one per line. Group by (owner, target) with counts and add `--max`.
- "No effect on build/test time" is true only in the sense that the validator is not a build dependency. It still competes for the same cores on a shared CI runner.
- 0.8 s for a pre-commit hook includes interpreter startup, and the pre-commit run still walks all 20k files for coverage. Also see C4: the incremental path is broken for git-style paths.

### M8. Authority/mode model needs sharper definitions
**Location:** docs/03 §3.6.

- Authority is taken from the depending element only. "Nothing new may depend on legacy X" (a target-side rule) cannot be expressed.
- Re-baselining (forward->reverse) is a free-form event. It does not say what happens to deviations, accepted conflicts or `planned` requirements, or who may do it. It is the main laundering path: flip to reverse, edit the model to match the code, flip back with a new baseline.
- Preset x per-node override x three layers is a large state space. There is no command that prints the effective authority map.
- Real-team failure modes: agents add deviations to turn CI green (expiry is the only brake, see C2); hybrid never converges because nothing measures it (share of files under model authority, age of the oldest MODEL-UPDATE); `approved:` is free text and not bound to CODEOWNERS or review identity, so authors can approve their own waiver.
- The example is internally inconsistent: the model records `mode: forward baseline: 6794ead` and "accepted at adoption", yet the adopt gate BLOCKS on the shipped model. `6794ead` is a commit of the research repo, not of Shortly.

### M9. Pilot statistics and decision rules
**Location:** docs/05 §5.5, tools/pilot_eval.py.

I simulated the actual `evaluate()` (300 replications per cell, my own generator, base success 50-60%, 40 work items):

| Scenario | GO | KILL | EXTEND |
|---|---|---|---|
| No effect, 30 change + 12 tempting | 2% | 12% | 86% |
| True +10pp success, 40 tasks | 12% | 3% | 85% |
| True halving of violations (40%->20%), 12 tempting | 7% | 12% | 81% |
| Same, 30 tempting | 35% | 10% | 55% |
| True harm -10pp success | 1% | 44% | 55% |
| True harm -20pp success | 1% | 76% | 23% |

- The pilot is powered mainly to detect large harm. A true +10pp gain is confirmed 12% of the time, and a true halving of violations with 12 tempting tasks 7% of the time. docs/05 nonetheless says the pilot "decides mainly" on violations on tempting tasks, which is where its power is lowest.
- GO has two routes (success gain OR violation reduction) with no multiplicity control, and the violation route has no minimum n. Six tempting tasks with all discordant pairs in one direction give exact p = 0.031, so a six-task pilot can say GO. The tempting tasks are written by the people who built the constraints, which is the strongest gaming vector.
- "Gain >= +10 points" tests the point estimate, while the CI only has to exclude 0. GO is possible with a lower bound of +1pp.
- A percentile bootstrap at n about 30 on paired binary data is anti-conservative. Use an exact or Newcombe interval. The power formula `(z_a+z_b)^2 * disc / min_gain^2` omits the `- delta^2` term and uses the noisy observed discordance.
- `ci` data (violations caught, false positives) and cost (tokens, seconds) are collected but do not enter `decide()`, although docs/05 lists "violations caught in CI" as a deciding metric. Validator precision is the real adoption killer and is not a kill criterion. There is also no comparison with what the light stack's own CI rules caught.
- Upkeep (the one decisive criterion): self-reported by participants who are advocates; the denominator is review minutes, not total engineering or agent time; the last-two-weeks window lets setup effort be moved earlier and is noisy; LLM token cost for agent-proposed model diffs and the reverse-engineering/setup cost are excluded. A flat 10% has no value-based justification.
- Comparator parity: nothing requires that `light` gets the same setup effort. There is a single run per condition on a stochastic agent, and tasks from one repo are clustered. How a "violation" is counted (before or after CI feedback to the agent) is unspecified. If the validator runs in the agent loop only for `ucn`, feedback is confounded with context.
- `silent_absence` counts only the UCN side. `named` counts as fine even if the agent never expanded it. Annotators who see the model when marking "needed" facts bias towards what UCN contains. A task without a `kind` key crashes the harness.

**Fix:**
1. Fix the detectable-effect table before starting.
2. Require both upkeep within budget and one pre-registered primary endpoint, with a Holm correction if there are two.
3. Have a third party write at least half the tempting tasks, with a minimum n.
4. Replace the upkeep ratio with a net-benefit formula.
5. Feed validator precision into `decide()`.
6. Give the baseline equal setup effort and use exact intervals.

### M10. The argument against the lightweight stack is asserted
**Location:** docs/05 §5.4 ("probably gets 60-70% of the value"), docs/03 §3.12 (f2).

The 60-70% figure is a guess. UCN's real additions, in order of strength: governance with expiry and per-subtree authority; known-conflict handling; requirement parameters bound to constants; one place for traceability. What it duplicates: allowed-dependency rules (dependency-cruiser, ArchUnit, import-linter, Deptrac, Nx boundaries do this with exact resolvers), and provenance (mostly unchecked in v0.3). Teams will adopt it if the model replaces the rule files (one source of truth, lower upkeep). They will reject it if it is a second file to keep next to `.dependency-cruiser.js`. The design question is whether UCN can emit or call the existing tools' configs.

## Minor issues / nits

1. README links `docs/06-review-synthesis-v0.3.md`, which does not exist at this commit.
2. `--today` defaults to the real date, so a runner clock skew can bypass expiry. Record the date and reject dates earlier than the commit date.
3. Duplicate `param:` lines silently take the last value.
4. "unresolved relative import" prints the resolved base path, not the specifier written.
5. Top-level name shadowing: a top-level `req Create` and `Api.Create` resolve `Create` to the top-level node first with no ambiguity warning.
6. The tests (18) re-run the planted example and mostly confirm the demo. None cover the reverse-mode gate, the cache, `--changed`, Python imports, glob edge cases, malformed dates, conflict masking or numeric literals. A differential test against a trusted resolver on random import graphs is cheap and missing.
7. The benchmark statement gives no CPU, Python version or run count. Publish the generator and use medians.
8. The default projector, which is the original "compact context" feature, does not exist. docs/03 §3.5 guarantees are checked only on two hand-written projections.
9. The sizing table in docs/05 §5.1 (500k-line system: ~50k intent, ~20k architecture tokens) is an assumption and should be labelled as one. It underpins the "frontier models need no compression" argument.
10. The error message for `lifecycle: proposed` deviations says "expired on <date>" (see C2).

## Validator test log

Models and code were written in a scratch directory outside the repo and run through `ucn_validate.validate()`. Baseline: 18 unit tests pass; Shortly output matches README (1 violation, 1 known-conflict, 1 waived, 1 model-update, 5 info); `--gate adopt` on Shortly is BLOCKED (Guard->Links); the pilot template gives EXTEND (368 pairs needed); the slice projection check passes.

| Probe | Result |
|---|---|
| Gate on reverse model with a forbidden import | pass, blockers [] (C1) |
| Gate on reverse model with `origin: inferred` everywhere | pass (C1) |
| Same violation with `mode: forward` | blocked |
| tsconfig alias `@/`, `~/` | no finding (C5) |
| `'../b/one.js'` -> `one.ts` | INFO only (C5) |
| import inside `//`, `/* */`, string, Python docstring | VIOLATION, false positive (C5) |
| multi-line import, `import type`, `export * from`, `require`, `import x = require`, dynamic literal | detected |
| computed dynamic import, `jest.mock` | missed |
| cache: target file added after caching | stale, violation missed (C4) |
| `--changed src/a/one.ts` with `root: src` | 0 scanned, exit 0 (C4) |
| `--changed a\one.ts` | 0 scanned |
| `a/*.ts` vs `a/**/gen.ts` | silent order-dependent resolution (M3) |
| `a/`, `a`, `./a/**`, `a/**/*.ts` vs `a/z.ts` | unclaimed (M3) |
| `A/Z.ts` vs `a/**` | unclaimed (M3) |
| deviation without `expires`/`approved` | WAIVED forever (C2) |
| `expires: never`; `expires: 2027-3-1` on 2027-12-01 | still active (C2) |
| deviation expired yesterday | VIOLATION x2 (correct) |
| `lifecycle: acepted` / `proposed` | not waived, wrong message |
| waiver covers a new file in the same pair | yes, too broad |
| `allows A1 emits B1` waives an import | yes |
| expired + active deviations on one edge | waived (correct) |
| `authority: modle` | parser error (good) |
| A1 `authority: source` in forward | MODEL-UPDATE (correct) |
| cycles A<->B and P<->Q declared both ways | no finding (M1) |
| child imports its container's own file | allowed (M1) |
| Web -> `api/pub`, `api/links` (implements Pub), `api/index` | allowed; `api/secret` flagged (M2) |
| two implementers of one api | importable from outside (M2) |
| Q uses P imports P.Inner | allowed (M2) |
| barrel A->Barrel->B | allowed (M1) |
| test imports unrelated container | MODEL-UPDATE (test authority is source) |
| production code imports a test file | VIOLATION (correct) |
| Python `import pkg.b.mod`, `from pkg.b.mod import f`, relative `..b`, try/nested | detected |
| Python `from pkg import b`, importlib, src-layout | missed |
| bind: comments, shadowing, reassignment, hex, 1e2, env, object property | see C3 table |
| accepted conflict, code drifts to 999999 | KNOWN-CONFLICT (C3) |
| bind to missing file / unknown param | VIOLATION (correct) |
| `src:` missing file; `../outside.ts` | VIOLATION provenance (correct); docs/tickets never checked |
| `src:` line in range but content moved | pass (M5) |
| `check: only a/db.ts imports pg` with `pg`, `pg/lib/client`, `require('pg')`, Python `psycopg2.extras` | VIOLATION (correct); `pg-promise` and alias `@db/pg` not flagged |
| perf, 20k files | see M7 |
| pilot simulations, 6 scenarios x 300 runs | see M9 |

## Missed prior art

- **Reflexion models** (Murphy, Notkin, Sullivan). The follow-on commercial tools (Sonargraph, Structure101, Lattix, Axivion) are the evidence base for whether teams keep a code-to-model mapping current. That is the central adoption question and it is not cited. Not verified by search in this review.
- **import-linter** (`forbidden`, `layers`, `independence` contracts): <https://github.com/seddonym/import-linter>, docs <https://import-linter.readthedocs.io/en/stable/readme.html> (verified).
- **Deptrac** (PHP layers and rules in YAML, fails CI): <https://github.com/sensiolabs-de/deptrac> (verified).
- **OpenFastTrace** (requirement-ID tracing from Markdown to code and tests, with coverage; CLI, Maven, Gradle): <https://github.com/itsallcode/openfasttrace>, <https://github.com/itsallcode/openfasttrace/blob/main/doc/user_guide.md> (verified). This is direct prior art for `satisfies`/`verifies` completeness. Also Doorstop, StrictDoc and sphinx-needs (requirements-as-code), not verified here.
- **GitHub Spec Kit** (spec-driven development for coding agents): <https://github.github.com/spec-kit/> (verified). Similar spec-first agent workflows (Kiro, OpenSpec, Tessl) target the same "agents drifting from intent" problem with prose specs and no deterministic gates. They are the competition for agent-facing adoption, and UCN's differentiation should be stated against them.
- **dependency-cruiser, madge, Nx `enforce-module-boundaries`, ArchUnit, jQAssistant, Packwerk, SonarQube architecture** are the baseline tools. The docs name some, but v0.3 does not map UCN's vocabulary onto their rule languages. Not verified by search here.
- **Edge extraction:** SCIP, tree-sitter, `jdeps`, `go list -deps`, `cargo metadata`, CodeQL. A production implementation should consume these edge lists rather than parse imports.
- **Model-to-rules:** Structurizr/LikeC4, Archi/jArchi scripting, ArchCNL (ontology to ArchUnit rules). Not verified by search here.

## Top 5 recommended changes (priority order)

1. **Fix the fail-open governance paths (C1, C2, C3 conflict masking, C4).** The gate should simulate the target authority and write the header only on `--apply`. Enforce ISO `expires`, `approved` and lifecycle enums. Give conflicts an expiry and an asserted value. Normalise `--changed` paths and make the cache independent of file-set changes. Add a regression test for each reproduction above. Until then the "deterministic guardrail" claim is not true.
2. **Replace the regex import scan with a normalised edge-list input** (dependency-cruiser, madge, grimp, SCIP, or tree-sitter with tsconfig resolution). Keep the regex as a flagged fallback that reports its blind spots. This fixes C5 and half of M7.
3. **Add the missing rule vocabulary and the top deterministic cross-layer checks:** `forbids`, `layer`, `acyclic`, component entry-point encapsulation, requirement -> test result evidence (JUnit/jest JSON), `satisfies` -> element has code, and OpenAPI/event/config adapters (M1, M2, M5, M6). Without these UCN does not beat the lightweight stack on conformance. With them plus the governance model it can.
4. **Redesign the pilot for decidability and anti-gaming (M9):** one pre-registered primary endpoint with multiplicity control, independently authored tempting tasks and a minimum n, validator precision and a net-benefit upkeep formula in `decide()`, equal setup effort for the baseline, exact intervals, repeated runs. State plainly that the pilot can only confirm a large effect.
5. **Cut and sequence scope:** freeze the custom syntax, knapsack projection, logic and runtime modules until the pilot returns GO. Make UCN able to emit config for existing linters (dependency-cruiser, import-linter, ArchUnit) so that it is the single source of truth rather than a second rules file. Define target-side authority and re-baseline rules (M8) and ship a command that prints the effective authority map.
