# Review of UCN v0.3

Reviewer: Fable 5.1 (claude-fable-5-1)
Date: 2026-11-05
Reviewed commit: 28a99f1

Scope: README, docs/01, 02 (skimmed for claims), 03, 05, examples/shortly (model, card, slice, src), examples/pilot/template.json, tools/ucn_parse.py, tools/ucn_validate.py, tools/pilot_eval.py, tests/test_tools.py. All adversarial work was done in temporary directories outside the repo. Scripts: `%TEMP%\claude\...\scratchpad\adv\h*.py`, synthetic-repo generator `gen.py`.

## Verdict

The v0.3 reframing is the right move. "A checked intent and architecture layer" targets a real and growing problem: agents erode architecture faster than humans can review it, and they break constraints nobody wrote down. The prototype is clean, small and readable, and the Shortly example is honest about what it plants. But the central promise ("deterministic tooling keeps the layers consistent, code may deviate only in a defined manner") is **not yet delivered**, even by the prototype's own standard. (1) The allowed-dependency set is partly built from logic-layer `fn` edges that are code-authoritative and, per §3.8, generated from the code. Code therefore authorizes itself. (2) The adopt gate is vacuous when run where it has to run, before the switch. (3) Every governance escape hatch (deviation fields, expiry format, accepted conflicts, illegal or dangling relations) is advisory, not enforced. (4) Barrel/index files and `implements` let a dependency through encapsulation without any finding. (5) The incremental and pre-commit modes are unsound. (6) The performance claim only holds for repositories that already mostly conform. On a violation-heavy repository, which is exactly the reverse-engineering case, the same 20k-file setup takes 41 s, not 4.6 s. On the "worth it" side, the pilot as designed can only end in KILL (on upkeep) or EXTEND. It is not powered to show a GO on its fast metrics either. There is also no information-parity control between the `light` and `ucn` arms. Most of the architecture checking duplicates mature tools (dependency-cruiser, import-linter, Tach, Nx boundaries, ArchUnit, Spring Modulith), and the doc does not engage with them as implementation substrates. The novel and defensible part is narrower than the docs suggest. It is the model-level governance: authority and modes, expiring deviations, requirement parameters bound to code, traces, provenance, and named-omission projection. The project should concentrate there.

**Overall score: 5/10.** The framing and specification improve substantially on v0.2. The validator is a useful sketch but unsound in ways that matter for a gate, and the pilot design cannot reach its own GO criteria.

**Worth building? Conditionally.** Yes, if it is rebuilt as a thin governance and traceability layer that (a) compiles its architecture rules to, or consumes the dependency graphs of, existing enforcement tools instead of regex-scanning imports; (b) enforces its governance semantics strictly (deviations, conflicts, authority, gate, model-diff permission widening); and (c) is evaluated with a pilot that has information parity, a realistic sample size for tempting tasks, and a differential upkeep measure. No, if the plan is to grow `ucn_validate.py` into yet another import-graph checker. That market is saturated, and teams will (correctly) pick dependency-cruiser or import-linter instead.

## Strengths

- **The reframing is correct and stated honestly** (01 §1.3, 05 §5.1): the small-model budget is demoted to a module, and the "agents can't understand code" premise is explicitly marked "mostly no".
- **Origin vs authority** (03 §3.6) is a genuinely useful distinction that conformance tools lack. "Same mismatch, different reading" (VIOLATION vs MODEL-UPDATE) is the right abstraction for hybrid legacy systems.
- **Deviations as first-class, expiring, approved waivers** (03 §3.2, §3.7) generalize ArchUnit's freeze into something reviewable. The `--today` flag for reproducible expiry tests is a nice touch.
- **`param:`/`bind:`** is the first deterministic link from requirement text to code that I have seen proposed in this kind of notation. It is cheap and catches a real class of drift (the RateLimit 100 vs 1000 example is convincing).
- **Pre-registration with a kill criterion and an honest power statement** (05 §5.5: "hundreds of paired tasks ... a 4–6 week pilot will not reach that") is unusual and commendable.
- **The code is small, dependency-free and readable.** The example output in README/03 §3.7 reproduces exactly, and all 18 tests pass.

## Critical issues (must fix)

### C1. Code-authoritative logic edges authorize architecture dependencies (code justifies itself)

- **Location:** tools/ucn_validate.py `validate()`, the edge collection (`for e in g["edges"] ... if e["rel"] in DEP_RELS`) and `allowed()` (`if not m.is_under(x, a)`). Spec 03 §3.6 ("Logic: source" in both presets; "signatures and call graphs always come from the code") and §3.8 stage 1 ("Code via tree-sitter/SCIP → `fn` signatures, `calls`").
- **Problem:** `allowed(a, b)` accepts any declared relation from *any descendant* of `a`, including `fn` nodes. `fn` edges (`calls`, `uses`, `reads`, `writes`) live in the logic layer, which is code-authoritative in both modes. Per §3.8 they are produced *from the code* by adapters. Once an adapter regenerates `calls`, every import becomes "allowed", and the forward-mode architecture check collapses to "the code agrees with itself". It already happens in the example. In examples/shortly/model.ucn, component `Links` declares **no** component-level relation to Codes, Guard, Db or Cache. Its dependencies on all four pass only because of `fn create calls Codes.generate, Guard.check, Guard.limit`, `writes Link`, `fn resolve uses Cache` and `reads Link`. An adapter that adds `fn check calls Links.isHttpUrl` under Guard would silently "fix" the planted Guard → Links violation.
- **Reproduction:** `h3.py` case `logic-edge-authorizes`. Components A and B have no relation, but `fn x(): void [inferred]` under A has `calls B.y`. Result: A → B is **conforming**, with zero findings. The edge even carries `[inferred]`.
- **Fix:** Build the allowed set only from relations whose source and target are architecture-layer nodes (`container`, `component`, `api`, `data`, `config`, `event`) and whose *authority is `model`* and origin is not `inferred`. Treat `fn` edges as **observations** to be checked against the architecture, not as permissions. In the spec, say explicitly that the "allowed relations" are a subset of the model that code-derived adapters may never write.

### C2. The adopt gate is vacuous when run before adoption, is not scoped, and records nothing

- **Location:** ucn_validate.py section "7. adopt gate". Spec 03 §3.6 ("Adopt ... runs `--gate adopt`. The gate blocks if, in the parts becoming model-authoritative ... Passing the gate records `mode: forward` and `baseline: <commit>`").
- **Problem:** The gate filters on `m.authority(nid) == "model"`, which is the *current* authority. Before adoption the model is in `reverse`, so authority is `source` everywhere. Inferred intent and architecture nodes are therefore not examined, and architecture mismatches are MODEL-UPDATE rather than VIOLATION, so they don't block either. Only `open` conflicts block, and they block globally, not per subtree. The gate also ignores outstanding MODEL-UPDATEs and coverage gaps, which mean the model is *known to be behind the code*. Adopting such a model contradicts the owner's requirement that "after reverse engineering, the built model should be followed". Finally, nothing writes `mode:`/`baseline:`, and the `baseline:` value is never used (it is only echoed).
- **Reproduction:** `h4.py` `gate-in-reverse-with-inferred-arch`. Shortly in `mode: reverse` with `system Shortly [inferred]`. The gate reports a single blocker, the open conflict. Thirteen inferred architecture nodes and the Guard → Links mismatch are ignored. Mark the conflict `accepted` and the gate **passes**. The same model with `mode: forward` yields 15 blockers. The test suite only exercises the gate in forward mode (tests/test_tools.py `test_adopt_gate`), which hides this.
- **Fix:** Add `--gate adopt [--scope <node>]` that evaluates the scope *as if* authority were `model`. Blockers: inferred nodes, relations and clauses in the scope; open conflicts `about` anything in scope; any architecture, parameter or convention mismatch in scope (whatever its current class); unclaimed files under the scope's globs; and deviations without expiry/approval. On pass, write the authority change and `baseline: <git rev-parse HEAD>` (or emit the exact patch). Define re-baseline (forward → reverse) the same way, and record both events in an append-only log section of the model.

### C3. Governance escape hatches are advisory: waivers can be unbounded, undated, permanent or invalid, and CI stays green

- **Location:** ucn_validate.py waiver collection and the parameter `known` logic. ucn_parse.py `lint()` (deviation fields, relation table and dangling refs are *warnings*, re-emitted by the validator as `INFO traces`). Spec 03 §3.2 ("`expires:` / `approved:` Required on a deviation"), §3.13 ("an expired deviation fails CI").
- **Problems and reproductions** (`h3.py`, `h1`):
  - `dev-no-expiry`: a deviation with no `expires:`, `approved:` or `lifecycle:` **waives, "expires never"**. The missing fields are only INFO. `lifecycle` defaults to `accepted`.
  - `dev-rel-ignored`: `allows A emits B` waives an import A → B. The relation in `allows` is parsed and then ignored.
  - `dev-blanket`: `allows App uses App` (a whole container to itself, expiry 2099) waives every internal violation. Breadth is unlimited, and so is the expiry horizon.
  - `dev-bad-date`: `expires: 2026-9-30` with `--today 2026-11-05` is still **active**, because dates are compared as strings ("2026-9" > "2026-1").
  - `dev-proposed`: a `lifecycle: proposed` deviation produces "deviation D ... **expired** on 2027-01-01", which is the wrong message.
  - Accepted conflicts: `lifecycle: accepted` on a conflict `about` a requirement downgrades **every** parameter mismatch of that requirement to KNOWN-CONFLICT, forever. There is no expiry and no approval, unlike deviations. In Shortly this is precisely how the 100 vs 1000 violation is silenced. An accepted conflict is a second, weaker waiver mechanism.
  - `uses-system`: `container App uses S` (a system, illegal per the relation table) produces only an INFO lint, and then **grants access to everything** in the system, because `allowed()` only applies the exposure rule when the target kind is `container`.
  - `dangling-rel`: a typo (`uses Bee`) is INFO. The relation is silently dropped and the exit code is unaffected.
- **Fix:** Split lint into *errors* (fail CI in any mode: dangling or ambiguous refs, relation-table violations, deviations missing `expires`/`approved`/`allows`, malformed dates, overlapping ownership) and *warnings*. Parse dates with `datetime.date.fromisoformat`. Compare the `allows` relation with the observed dependency type, or define `allows X depends Y` explicitly. Cap deviation breadth (component to component or file to element only, unless explicitly `scope: container`) and the expiry horizon (configurable, for example ≤ 12 months). Give suppressing conflicts the same `expires:`/`approved:` contract, or make accepted conflicts produce a VIOLATION after their expiry.

### C4. Encapsulation can be bypassed through barrel files, `implements`, and parent/child rules

- **Location:** ucn_validate.py `allowed()` (`if m.is_under(a, b) or m.is_under(b, a): return True`) and `exposed()`. Spec 03 §3.7, "Architecture conformance".
- **Problem:** Child → parent and parent → child dependencies are always allowed. A file owned by a container (for example `src/index.ts` under `code: src/**`) may therefore import any component inside it, and any component may import that file. A barrel `index.ts` re-exporting `./b/y` turns every cross-component import into two conforming hops. Barrels are ubiquitous in TypeScript and `__init__.py` re-exports in Python. Separately, `exposed()` treats a component that `implements` an exposed api as fully exposed: Web may import `api/links.ts` directly. And the first loop of `exposed()` accepts *any* dependency relation from the container to its own part (for example `container Api reads AliasesEnabled`) as an export.
- **Reproduction:** `h1.py` `barrel` (A → `src/index.ts` → B: 2 conforming, 0 findings, while the direct import is a VIOLATION) and `nested-child-to-parent-to-sibling(barrel)`. `h4.py` `source-element-breaches-model-container`: appending `import { create } from "../api/links"` to `web/app.tsx` gives **no finding** for Links (it implements the exposed LinksApi).
- **Fix:** Resolve re-exports (`export * from`, `export {x} from`, `from .x import *` in `__init__.py`) to their origin, which tree-sitter or dependency-cruiser provide, or compute conformance on the transitive closure through container-owned files. Require parent → child access to go through `exposes` as well, or forbid unclaimed container-level files in forward mode. Make "exposed" mean the api's own `code:` files only, unless the component is explicitly exposed.

### C5. Incremental modes are unsound: pre-commit can silently scan nothing, and the cache returns stale resolutions

- **Location:** ucn_validate.py `scan = [f for f in files if not changed or f in set(changed)]`, `scan_imports()` cache. Spec 05 §5.3 ("Pre-commit, 1 changed file: 0.8 s"), 03 §3.7 ("pre-commit hook on changed files").
- **Problems and reproductions:**
  - `h4.py` `changed-repo-relative`: pre-commit frameworks pass **repo-relative** paths (`examples/shortly/src/api/codes.ts`), while the validator expects **root-relative** ones (`api/codes.ts`). Result: "0 scanned", a newly introduced Codes → Guard violation is missed, and the exit code is 0 with no warning.
  - `model-only-change`: if only `model.ucn` changes (for example a relation is removed), `--changed m.ucn` scans 0 files and reports nothing. The full run shows two new VIOLATIONs (Links → Cache, Links → Db).
  - `h5.py`: the cache stores *resolved* targets keyed only by the importing file's mtime and size. `a.ts` imports `./b` while `b.ts` is missing, so the cache records `missing`. After `b.ts` is added, the warm run still says "unresolved"; the cold run says VIOLATION. A false negative that persists until `a.ts` is touched.
- **Fix:** Normalize `--changed` paths against both the repo root and `root:`, and fail if a given path matches nothing. Do a full run whenever the model file (or any `code:`-affecting config) changes. Cache raw import specifiers only and re-resolve against the current file set (resolution is cheap), or key the cache on a hash of the file set and of the resolver config.

### C6. The pilot cannot reach GO on its own fast metrics, has no information-parity control, and is gameable

- **Location:** docs/05 §5.5, tools/pilot_eval.py `decide()`, examples/pilot/template.json, docs/01 §1.7.
- **Problems:**
  1. **Power for tempting tasks is not "few tasks".** §5.5 says the pilot decides on the violation rate on tempting tasks because "large effects need fewer tasks". With the template's baseline (25% of light runs violate) and a 50% reduction target (25% → 12.5%), exact McNemar at α = 0.05 and power 0.8 needs on the order of **70–100 paired tempting tasks**. That estimate assumes discordance of about 15%, by the harness's own formula: (1.96 + 0.84)² · 0.15 / 0.125² ≈ 75. The template has 8. With 8 pairs, GO is reachable only if at least 6 tasks are discordant and *all* favour UCN. Hand-written tempting tasks are expensive, so the 4–6 week pilot as described will end in EXTEND unless upkeep kills it.
  2. **No information parity.** The tempting tasks test constraints the UCN authors put in the model. If the `light` arm's AGENTS.md, ADRs and rules files do not contain the *same* constraints, the experiment measures information presence, not UCN. The protocol also does not say whether `ucn` = light + UCN or UCN instead of light. **Fix:** generate the light arm's AGENTS.md and dependency-cruiser/import-linter rules *from the same UCN model*. Then the measured delta is exactly what UCN adds: structure, provenance, governance, projection and validator.
  3. **Multiplicity.** GO fires on `gain OR safer`, two tests at α = 0.05 each, so the family-wise error rate is about 0.10. Use Holm or α/2, or pre-register one primary endpoint.
  4. **Upkeep is not differential and is undefined at the margin.** `model_minutes / review_minutes` ignores the light stack's own upkeep, and it does not say whether reviewing a model diff counts as model time or review time. Moving it to review time lowers the ratio, and UCN itself enlarges review time, which inflates the denominator. Using only the last two weeks (`up[-2:]`) on one repository with three contributors is very noisy, and it ignores setup cost (template: 11.6% overall vs 5.8% recent, so a pass).
  5. **Criteria in 01 §1.7 not in `decide()`.** Validator precision ≥ 80% and run-time targets are listed as pilot success criteria but never evaluated. Precision is also computed with no recall estimate, while the regex scanner's false negatives are the main risk (see M1). Silent absence only blocks GO; it never kills.
  6. **KILL by futility at n ≥ 30 is weak.** The test `test_kill_when_no_better` uses perfectly concordant pairs (bootstrap CI [0, 0]). With realistic discordance at n = 30–60, the percentile bootstrap upper bound will rarely fall below +10 points unless UCN is clearly *worse*. The percentile bootstrap is also anti-conservative for small paired-binary samples. A Newcombe/Tango interval for paired proportions would be the standard choice.
  7. **Gaming risks:** the authors write the tempting tasks and annotate the "needed facts". The protocol has a single run per task and condition despite LLM nondeterminism. Medians of tokens and seconds mix tempting and work tasks.
- **Fix:** pre-register one primary endpoint (tempting-task violation rate) with a computed sample size. Have tempting tasks written by people outside the UCN team, drawn from constraints that exist in *both* arms. Run k ≥ 3 samples per task and condition and analyse with a mixed model or cluster bootstrap by task. Measure upkeep differentially (UCN minus light), including model-diff review. Add a maximum-duration rule ("EXTEND at most once, then KILL") so EXTEND cannot become permanent.

## Major issues (should fix)

### M1. Regex import extraction: avoidable false positives and silent false negatives; reuse existing graph exporters

- **Location:** ucn_validate.py `JS_IMPORT`, `PY_IMPORT`, `resolve_spec`, `py_resolve`. 05 §5.3 ("Known limits") and 03 §3.13 ("Misses are false negatives, so the check never blocks wrongly because of them").
- **Reproductions** (`h1.py`, `h2.py`):
  - **False positives** (they *do* block, contrary to §3.13): an import in a `//` comment (`comment`), `require("../b/y")` inside a template string (`string`), `import pkg.b.y` inside a Python docstring (`py-in-docstring`).
  - **Silent false negatives:**
    - `@/b/y` path aliases are classified as the external package `@/b`, not even reported as unresolved (`alias`).
    - `import os, pkg.b.y` only captures `os` (`py-import-comma`).
    - Python src-layout (`src/pkg/...` with absolute `pkg.` imports) resolves to nothing (`py-srclayout`).
    - `importlib` (`py-importlib`).
  - **Policy question:** `import type` counts as a dependency (`typeonly`). This should be configurable, as dependency-cruiser's `dependencyTypes` is.
- **Fix:** do not grow this regex. Consume `dependency-cruiser --output-type json`, `madge --json`, grimp (the import-linter engine), Tach, `jdeps`, `go list -deps -json` or SCIP indexes. Keep the regex only as a zero-config fallback with a visible "approximate" banner. Better still, **compile** UCN's allowed and forbidden relations into those tools' rule files, so teams keep the checker they already trust and UCN adds governance on top (see Top 5 #1).

### M2. Parameter binding is regex-on-text, unit-blind and first-match

- **Location:** ucn_validate.py "2. parameter bindings". 03 §3.2 (`param:` "typed, comparable value"), §3.7.
- **Reproductions** (`h3.py`):
  - `param-in-comment-first`: `// old: LIMIT = 3600` before `export const LIMIT = 10` reports **conforming** against `param: maxPerHour = 3600` (false negative).
  - `param-expr-and-unit`: `LIMIT = 60 * 60` reads as 60 (false positive). `timeout = 2 s` vs `TIMEOUT_MS = 2000` is a VIOLATION because units are parsed but never used.
  - `param-hex`: `0xE10` reads as 0.
  - The `KNOWN` lookup suppresses *all* parameters of a requirement when one conflict is about it.
- **Fix:** extract constants with an AST (tree-sitter: declaration with a literal initializer, or a small constant folder for `*`, `_` and hex). Fail with "non-literal binding" otherwise. Add `scale:`/unit to `bind:` (`= api/x.ts#TIMEOUT_MS unit: ms`) and a tiny unit table. Allow config files (YAML/JSON/env) as binding targets, where most such values live. Scope conflict suppression to `about Req.param`.

### M3. Allowlist-only rules: no layers, no forbidden edges, no acyclicity, no independence

- **Location:** 03 §3.2 relations, §3.7. 05 §5.4 (light stack baseline).
- **Problem:** The commonest real architecture rules are *negative or structural*: "domain must not import infrastructure", "features are mutually independent", "no cycles between modules". UCN can only express them by omission, and cycles cannot be expressed at all. Every tool in the lightweight baseline supports them: dependency-cruiser `forbidden` + `no-circular`, import-linter `layers`/`independence`/`forbidden`, ArchUnit `slices().should().beFreeOfCycles()`, Spring Modulith's default "no cycles", Nx `notDependOnLibsWithTags`. With an allowlist only, UCN is strictly *less* expressive than the baseline it must beat.
- **Fix:** add `layer` ordering (or a `layers:` attribute on a container), `forbids` relations, and an `acyclic` constraint, all checkable on the lifted graph.

### M4. Authority is applied to the wrong end, and coverage ignores per-subtree authority

- **Location:** ucn_validate.py: finding class is chosen by `m.authority(a)` (the *depending* element only). Coverage uses `m.mode`, not the authority of the enclosing glob owner.
- **Problem:** when a source-authoritative legacy element (Web) reaches into the internals of a model-authoritative container (`h4.py`: `Web depends on Db` after adding `import { pool } from "../api/db"`), the result is MODEL-UPDATE. The breach is of *Db's/Api's* encapsulation, which the model owns. Conversely, unclaimed files under a legacy `authority: source` subtree are VIOLATIONs in forward mode (`hybrid-coverage`: `web/sub.ts`). Hybrid adoption, which §3.6 says is "how most real systems will look", is exactly the case that gets the wrong class.
- **Fix:** the class should be VIOLATION if *either* end's governing rule is model-authoritative: the depending element's allowlist, or the target's exposure rule. Coverage should use the authority of the nearest enclosing element whose glob is a prefix, or of a declared "unclaimed" policy.

### M5. Important inter-layer consistency is not checked, though much of it is deterministic

The owner requires "architecture and code must not contradict requirements". Today the only enforced requirement-to-code link is `bind:`. Everything else is INFO or absent:

- **`lifecycle` is ignored by the validator.** A `deprecated` component can still be imported without any finding (`h6.py` `deprecated-target`). `planned` relations already permit code, and `planned` elements with code are not flagged. Planned and deprecated are central to "change the model first" (03 §3.6), and all of this is deterministic.
- **`verifies` is not checked against the code.** A test that `verifies R, A` but imports nothing of A gets only an INFO absence (`h6.py`). The `verified:` attribute is not checked to point to a test whose file exists. The spec's promotion rule ("asserts the property", 03 §3.8) has no tooling at all.
- **Requirement-to-architecture coherence.** None of these is checked:
  - a non-planned requirement satisfied only by planned or deprecated elements;
  - a `[security]` requirement whose satisfying component is not on any dependency path from the api that exposes the behaviour (graph reachability);
  - `satisfies` to a component with no code;
  - `refines` cycles.
- **Interfaces and events.** `api` vs the OpenAPI/route table, `emits`/`consumes` vs event names in code, `config` vs env/flag definitions. These are the modules most agents break, and they can be checked by literal matching.
- **Provenance.** 05 §5.3 claims "hash-based staleness: yes", and 03 §3.4 describes Merkle propagation. Neither is implemented: only file existence and line range are checked, and only for code-extension paths. `src: db/schema.sql:1`, `docs/adr/003.md` and `CONTRIBUTING.md#db` are never checked.
- **Model-diff review.** The single most important deterministic check for the forward workflow is missing (see Top 5 #3). An agent can make a VIOLATION disappear by adding `uses Links` to the model in the same PR, as the repo's own `test_adopt_gate` "fix" does, and nothing flags that the change *widened permissions*.

### M6. File ownership: tests can steal implementation files; overlaps and glob semantics are silent

- **Location:** ucn_validate.py claims (`claims.append((10**9, 99, ...))` for test `src:`), `specificity()`, `glob_re()`.
- **Reproductions:**
  - `h2.py` `test-steals-file`: a test whose `src:` points at an implementation file (`src/a/x.ts:1`) takes ownership of that file, at top priority. The real owner's violations vanish (A → B becomes "T verifies B": conforming).
  - `overlap-equal`: two components with the same glob `src/*.ts` get no warning; dictionary order picks the owner.
  - `globzero`: `src/**/a.ts` does not match `src/a.ts`, unlike gitignore, minimatch or globstar semantics. The file silently falls back to the container.
  - `specificity()` uses only the index of the first wildcard, so `api/**` and `api/*.ts` tie.
- **Fix:** take test ownership from a dedicated `code:` on test nodes or a test-file pattern, never from `src:`. Report equal-specificity overlaps as errors. Use standard globstar semantics (`**/` matches zero or more directories), for example `pathspec` / `wcmatch`.

### M7. Performance claims hold only for mostly conforming repositories

- **Location:** 05 §5.3 measurements, 03 §3.7 "Performance", ucn_validate.py `allowed()`, `exposed()`, absence loop.
- **Measurement** (this review, Windows 11 laptop, Python 3.13): synthetic repo with 20,000 TS files, 120,000 relative imports and 200 components with 5 random `uses` each, so most imports violate (a realistic *reverse-mode* legacy profile).
  - **Cold: 40.9 s.** **Warm cache: 24.1 s.** `--changed` on 1 file: 0.86 s.
  - 36,957 VIOLATION findings.
  - Profile: 57.5 M calls to `Model.ancestors()`. `allowed()` is O(|declared edges| × depth) per observed pair, `exposed()` is O(E²), and the absence loop is O(E × observed).
  - The documented 4.6 s / 1.5 s are therefore credible only for repositories where nearly every lifted pair conforms. The pre-commit figure is credible.
- **Also:** "no effect on build and test time" is true only in the sense that this is a separate job. Pre-commit hooks *are* developer wall-clock time, and `list_code_files` plus glob mapping over all files runs on every pre-commit invocation.
- **Fix:** precompute ancestor sets once, compute the element-level allowed relation as a boolean matrix or a set of (a, b) pairs (200×200 is trivial), index observed pairs, and cap the number of findings printed per element pair. With these changes 20k files should be IO-bound at a few seconds even when nothing conforms. Add a violation-heavy benchmark to 05 §5.3.

### M8. The argument against the lightweight stack is under-argued

- **Location:** 05 §5.4 ("That probably gets 60–70% of the value"), 02 §2.7 ("None of them connects it to requirements ... or to provenance and waivers with expiry in one model").
- **Problem:** the 60–70% figure has no basis. The distinguishing claim is partly wrong. Waivers with an audit trail exist in ArchUnit `FreezingArchRule`, import-linter `ignore_imports`, and dependency-cruiser's `--ignore-known` baseline. Requirement-to-code tracing with coverage status exists in OpenFastTrace, StrictDoc and Sphinx-needs (the latter is cited only in a background list). The **spec-driven-development** wave (Kiro uses EARS in `requirements.md`; GitHub Spec Kit has a `constitution.md`, specs and plans) is the most direct competitor for "intent layer for coding agents" and is not discussed at all. What is genuinely new is the *combination*: authority and modes, governance applied uniformly across architecture, parameters and conventions, named-omission projection and provenance. The doc should say so and argue for that combination specifically.
- **What would make teams adopt:** zero new checker to trust (reuse their dependency-cruiser or import-linter); a model that is a superset of things they already have (AGENTS.md, ADRs, C4 DSL) and is generated, not typed; one CI job; reviewable model diffs. **What would make them reject:** a custom syntax (03 §3.3 keeps it), a second import checker that disagrees with their linter, and gate noise from regex false positives.

### M9. Scope: the core is still too big for "core"

- **Location:** 03 §3.0 table, 05 §5.2.
- The core contains 21 node kinds in the metamodel table, LoD levels, labels with four axes, scoped pins, inverse edges and stubs. For a *pilot* of "a checked intent and architecture layer", the minimal checkable core is: `req` (+`param`), `decision`, `rule`, `convention`, `container`/`component` (+`code`, `exposes`, allowed relations and the missing forbids/layers), `test` (+`verifies`), `conflict`, `deviation`, `authority`, `lifecycle`. `term`, `goal`, `actor`, `api`-as-node (vs IDL reference), LoD L2, pins and labels other than origin could be modules. Demoting the code-logic layer is right. But the validator still lets logic-layer edges into the architecture semantics (C1), so the demotion is not complete.
- `check:` supports exactly one form (`only <glob> imports <module>`). Either make it a small, closed rule language (imports, forbids, filename patterns, literal presence) or delegate to Semgrep/ast-grep rules referenced by id. Today a convention that cannot be checked is indistinguishable from one that is checked and passes.

## Minor issues / nits

- README.md, Contents table: links `docs/06-review-synthesis-v0.3.md`, which does not exist at 28a99f1.
- 03 §3.5 guarantee 6 ("No invented facts: every node and edge in C exists in M") is checked by id and edge only, not text. examples/shortly/card.L0.ucn has conflict text ("ticket#14 says 100 links per hour; the code (api/guard.ts:3) uses 1000") that differs from the model text, and the checker passes it. Either check text equality or a declared L0 template, or narrow the guarantee.
- ucn_validate.py prints "deviation ... expired on <date>" for `lifecycle: proposed` or `revoked` deviations that have not expired (`h3.py` `dev-proposed`).
- ucn_validate.py: `today` defaults to the system date, so CI results change at midnight without a commit. This conflicts with the determinism claims. Recommend requiring `--today` in CI or deriving it from the commit date.
- ucn_parse.py `resolve()`: an exact id shadows suffix matches silently (`Cache` resolves to the top-level container even if `Api.Cache` exists). Report it as ambiguous instead.
- Reverse mode never fails CI (everything is MODEL-UPDATE), so a reverse-mode model offers zero guardrails until adoption. Say so explicitly in 03 §3.6. Also give MODEL-UPDATE an optional "fail if older than N days" so reverse models do not rot.
- ucn_validate.py coverage: the unresolved relative import is INFO even in forward mode, and an import of a deleted file passes.
- 05 §5.3 table says signatures and call graph come from tree-sitter/SCIP: "yes". Nothing in the repo does this. Mark it as roadmap.
- pilot_eval.py: `cost` medians include tempting tasks. `disc ... or 0.5` silently assumes 50% discordance when it is 0. The `z()` docstring mentions Acklam but uses bisection (harmless).
- tests/test_tools.py covers only the happy path of each feature. There are no tests for barrels, aliases, Python resolution, the gate in reverse mode, `--changed`, the cache, or deviation validity. That is why C2–C5 went unnoticed.
- 03 §3.2 says `bind:` names "the code constant", but the spec does not define where binds live (the example puts them on components; the validator accepts them anywhere).

## Validator test log

All cases in temporary directories under `%TEMP%`. "FN" = false negative (should be flagged, isn't), "FP" = false positive.

| # | Case (script) | Setup | Observed | Assessment |
|---|---|---|---|---|
| 0 | Repo tests | `python -m unittest discover -s tests` | 18 OK, 0.69 s | pass |
| 0 | Shortly | documented commands | identical to README/03 §3.7, exit 1; gate BLOCKED | pass |
| 1 | `alias` (h1) | `import "@/b/y"` across components | no finding, not even "unresolved" | FN (silent) |
| 2 | `barrel` (h1) | A → `src/index.ts` re-exports B | 2 conforming, no finding | FN, encapsulation bypass (C4) |
| 3 | `comment` / `string` (h1) | import in `//` comment, in template string | VIOLATION | FP |
| 4 | `typeonly` (h1) | `import type` | VIOLATION | policy, should be configurable |
| 5 | `multiline` (h1) | multi-line named import | VIOLATION (correct) | pass |
| 6 | `globzero` (h1) | `code: src/**/a.ts`, file `src/a.ts` | owned by container, silently | FN / misassignment |
| 7 | `uses-system` (h1) | `container App uses S` (system) | INFO lint only, App may import any internal file | FN, bypass (C3) |
| 8 | `uses-container-encap` (h1) | `uses Core`, import Core's non-exposed component | VIOLATION (correct) | pass |
| 9 | Python abs/rel/`from pkg import mod` (h2) | | VIOLATION (correct) | pass |
| 10 | `py-import-comma` (h2) | `import os, pkg.b.y` | nothing | FN |
| 11 | `py-srclayout` (h2) | `src/pkg/...`, absolute imports | nothing | FN (silent) |
| 12 | `py-in-docstring` (h2) | import text in docstring | VIOLATION | FP |
| 13 | `py-importlib` (h2) | `importlib.import_module` | nothing | FN (documented) |
| 14 | `test-steals-file` (h2) | test `src:` points to implementation | implementation file owned by test; violation hidden | FN (M6) |
| 15 | `overlap-equal` (h2) | two components, same glob | no warning | silent ambiguity |
| 16 | `nested-siblings` (h2) | nested components, sibling import | VIOLATION (correct) | pass |
| 17 | nested barrel (h2) | via parent component's index | conforming | FN (C4) |
| 18 | `dev-no-expiry` (h3) | deviation without expires/approved/lifecycle | WAIVED, "expires never" | C3 |
| 19 | `dev-rel-ignored` (h3) | `allows A emits B` | waives an import | C3 |
| 20 | `dev-blanket` (h3) | `allows App uses App`, 2099 | waives everything inside App | C3 |
| 21 | `dev-bad-date` (h3) | `expires: 2026-9-30`, today 2026-11-05 | still WAIVED | FN (C3) |
| 22 | `dev-proposed` (h3) | proposed deviation | message says "expired" | wrong message |
| 23 | `dangling-rel` (h3) | `uses Bee` | INFO only | integrity error not enforced |
| 24 | `logic-edge-authorizes` (h3) | `fn x [inferred] calls B.y` | A → B conforming | FN, **self-justification** (C1) |
| 25 | `param-expr-and-unit` (h3) | `60 * 60`; `2 s` vs `2000` ms | two VIOLATIONs | FP (M2) |
| 26 | `param-in-comment-first` (h3) | commented old value first | conforming | FN (M2) |
| 27 | `param-hex` (h3) | `0xE10` | reads 0 | FP |
| 28 | `conv-scoped` (h3) | `@prisma/client`, `pg/lib/client` | both VIOLATION (correct) | pass |
| 29 | `gate-in-reverse-with-inferred-arch` (h4) | reverse mode, inferred architecture, arch mismatch | only the open conflict blocks; passes once accepted | **C2** |
| 30 | `hybrid-coverage` (h4) | unclaimed file under legacy `authority: source` subtree | VIOLATION | M4 |
| 31 | `source-element-breaches-model-container` (h4) | Web imports `api/links.ts` and `api/db.ts` | Links: no finding. Db: MODEL-UPDATE | C4 / M4 |
| 32 | `changed-repo-relative` (h4) | `--changed examples/shortly/src/api/codes.ts` | 0 scanned, new violation missed, exit 0 | **C5** |
| 33 | `model-only-change` (h4) | relations removed, `--changed m.ucn` | nothing; full run finds 2 VIOLATIONs | C5 |
| 34 | cache (h5) | import target added after first run | warm run still "unresolved"; cold run VIOLATION | C5 |
| 35 | `deprecated-target` (h6) | import of `lifecycle: deprecated` component | conforming | M5 |
| 36 | `test-verifies-without-touching` (h6) | test verifies A, imports nothing | INFO absence only | M5 |
| 37 | Performance (gen.py) | 20k files, 120k imports, 200 components, mostly violating | cold 40.9 s, warm 24.1 s, 1 changed file 0.86 s | M7 |

## Missed prior art

Verified via web search on 2026-11-05:

- **import-linter** (`layers`, `independence`, `forbidden` contracts, `ignore_imports` as waivers; engine: grimp): [docs](https://import-linter.readthedocs.io/en/stable/contract_types/independence/). Direct substrate for the Python side, and the source of the missing layer, independence and forbidden rules (M3).
- **Tach** (Rust-based Python module boundaries, public `interfaces` with `expose`, "unchecked" modules for gradual adoption): [github.com/tach-org/tach](https://github.com/tach-org/tach). Its interfaces are precisely UCN's `exposes`, and its "unchecked" modules are a cousin of `authority: source`.
- **Nx `@nx/enforce-module-boundaries`** (tag-based `depConstraints`, `onlyDependOnLibsWithTags` / `notDependOnLibsWithTags`): [nx.dev](https://nx.dev/docs/features/enforce-module-boundaries).
- **Spring Modulith** (`ApplicationModules.verify()`: no cycles, no access to internal packages, `allowedDependencies`): [docs.spring.io](https://docs.spring.io/spring-modulith/reference/verification.html). The closest "architecture model in code + verification" in mainstream use.
- **jQAssistant** (code graph in Neo4j, architecture rules as Cypher in the repo): mentioned in 02 but not used as an implementation option.
- **OpenFastTrace** (requirement tracing via tags in code, statuses such as covered shallow/unwanted/outdated): [github.com/itsallcode/openfasttrace](https://github.com/itsallcode/openfasttrace/blob/main/doc/user_guide.md). Directly relevant to `satisfies`/`verifies` checking and to staleness ("outdated").
- **StrictDoc** (text-based requirements, ReqIF export, requirement-to-source traceability, experimental): [strictdoc.readthedocs.io](https://strictdoc.readthedocs.io/). Also **Sphinx-needs**, listed only as background in 02.
- **Kiro spec-driven development** (EARS acceptance criteria in `requirements.md`, `design.md`, `tasks.md`, steering files): [kiro.dev/docs/specs/concepts](https://kiro.dev/docs/specs/concepts). Uses EARS, as UCN does, for the same audience (agents).
- **GitHub Spec Kit** (`constitution.md` + spec/plan/tasks workflow for agents): [github.com/github/spec-kit](https://github.com/github/spec-kit). Kiro and Spec Kit are the de facto "lightweight intent layer for agents" in 2026 and should be a pilot baseline or at least discussed in 05 §5.4.
- Baseline and waiver features of the lightweight stack that undercut 02 §2.7's novelty claim: ArchUnit `FreezingArchRule` (cited), dependency-cruiser `--ignore-known` known-violations baseline, import-linter `ignore_imports`.

## Top 5 recommended changes (priority order)

1. **Make UCN a governance layer over existing checkers, not a new import scanner.** Compile allowed, forbidden and layer rules from the model into dependency-cruiser / import-linter / Tach / ArchUnit configs, or consume their JSON dependency graphs. Keep UCN's own value: authority, modes, deviations, parameter bindings, traces, provenance, projection. This fixes M1, most of C4 and M7, and removes the "second checker that disagrees with my linter" adoption killer.
2. **Fix the semantics of "allowed" and of the gate** (C1, C2, M4). Permissions come only from model-authoritative, non-inferred architecture-layer relations; `fn` and code-derived edges are observations. Add an adopt gate that evaluates the target scope hypothetically, blocks on any mismatch, inferred fact or coverage gap, and writes authority and baseline. Choose the class by the stricter of the two ends' authority.
3. **Enforce governance and add a permission-diff check** (C3, M5). Integrity errors and invalid deviations fail CI. Dates are parsed. Deviation breadth and horizon are capped. Accepted conflicts that suppress findings need expiry and approval. Add `ucn validate --diff BASE`, which lists every permission the PR *widens* (new allowed edges, new deviations, `authority` flips, param changes) and requires an owner approval (CODEOWNERS on the model file). This is the deterministic answer to "the agent edits the model to make CI green".
4. **Make incremental runs sound and benchmark the bad case** (C5, M7). Path normalization with "matched nothing" errors; a full run on model changes; a cache of raw specifiers re-resolved per run; precomputed ancestor sets and an allowed-pair matrix; a violation-heavy benchmark in 05 §5.3; adversarial tests (the 37 cases above are a starting suite).
5. **Redesign the pilot so it can decide** (C6). One primary endpoint with a computed sample size (≈ 75+ tempting tasks, written by outsiders). Information parity, achieved by generating the light arm from the same model. k ≥ 3 runs per task and condition with clustered analysis. Differential upkeep including model-diff review. Holm correction if two endpoints are kept. Evaluate all 01 §1.7 criteria (validator precision *and* an estimated recall from a seeded-violation set) in `decide()`. Allow EXTEND at most once. Add Kiro/Spec Kit-style specs as a second baseline.
