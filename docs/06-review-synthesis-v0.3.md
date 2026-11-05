# 6. Review Synthesis (v0.3)

UCN v0.3 (commit `28a99f1`) was reviewed independently by the same two models as v0.1, **against the new goal**: a checked, traceable intent and architecture layer that keeps coding agents consistent with requirements and architecture. The owner's requirements were:
- the framework must solve a real problem and be worth introducing into a real system;
- forward and reverse engineering are both supported, and the choice can change;
- the layers must be consistent, and code may deviate only in a defined manner;
- deterministic, fast tooling must do as much as possible.

Both reviewers read everything, ran the tests, and **attacked the validator** with adversarial models and code (37 cases from Fable, about 40 probes from Sonnet). Both re-ran the performance benchmark on a denser synthetic repo and **simulated the pilot harness**. Neither saw the other's review.

| Reviewer | Score | Worth building? | Raw review |
|---|---|---|---|
| **Fable 5.1** | **5 / 10** | Conditionally | [reviews/v0.3/review-fable.md](../reviews/v0.3/review-fable.md) |
| **Sonnet 5.5** | **6 / 10** (idea 8, spec 7, tooling 4, pilot 5) | Conditionally | [reviews/v0.3/review-sonnet.md](../reviews/v0.3/review-sonnet.md) |

## 6.1 The verdict both reached

**The reframing is right, and the problem is real.** Both called the goal change coherent. Both agreed with demoting the code-logic layer ("index and check code, don't restate it"). Both singled out the same differentiators as genuinely new:
- *origin vs authority* (no mainstream architecture linter distinguishes "code is wrong" from "model is stale");
- expiring, approved deviations kept in the model;
- known-conflict handling;
- requirement parameters bound to code constants.

**But the tooling does not yet back the claims.** In both reviewers' words, the validator "fails open in exactly the places the spec says it fails closed". As a regex import checker it is weaker than tools teams already use: dependency-cruiser, import-linter, Tach, Nx module boundaries, ArchUnit, Deptrac. And the pilot as designed "can practically only kill the project through the upkeep criterion".

**Worth building: conditionally.** Both said the same thing in nearly the same words:

> Yes, as a **thin governance and traceability layer over existing checkers**: authority and modes, expiring deviations, bound requirement parameters, traces, provenance, and context with named omissions. No, as yet another regex import checker.

## 6.2 Findings both reviewers reproduced

| # | Finding | Fable | Sonnet |
|---|---|---|---|
| 1 | **Adopt gate is vacuous** when run before adoption, in reverse mode, which is the only time it matters. It evaluates the *current* authority, so inferred nodes and architecture mismatches don't block. Accept the conflict and it passes. It never writes `mode`/`baseline`. The test only covers forward mode. | C2 | C1 |
| 2 | **Deviations fail open.** <ul><li>No `expires`/`approved` means the waiver is active forever.</li><li>Dates are compared as strings, so `2026-9-30` and `never` never expire.</li><li>The relation in `allows` is ignored.</li><li>`allows App uses App` waives a whole container.</li><li>A wrong "expired" message appears for `proposed`.</li></ul> | C3 | C2 |
| 3 | **Accepted conflicts are a permanent second waiver.** They silence any later drift of a bound value (1000 → 999999 stays KNOWN-CONFLICT), with no expiry and no approval. | C3 | C3 |
| 4 | **Integrity problems are only INFO.** A dangling or ambiguous reference silently removes an edge from conformance checking. | C3 | M6 |
| 5 | **`--changed` silently scans nothing** with the repo-relative paths pre-commit tools pass, and exits 0. | C5 | C4 |
| 6 | **The cache returns stale resolutions.** An import that was unresolved stays unresolved after its target file is added. | C5 | C4 |
| 7 | **Regex import extraction:** <ul><li>False positives (imports inside comments, strings or docstrings fail CI).</li><li>Silent false negatives (`@/` tsconfig aliases, `.js` ESM specifiers for `.ts` files, `jest.mock`, Python src-layout, `from pkg import sub`).</li><li>The spec's claim "misses are false negatives, so it never blocks wrongly" is false.</li></ul> | M1 | C5 |
| 8 | **Parameter binding is regex-on-text.** It takes the first match (including a commented-out old value), misreads `0x64`, `1e2` and `60*60`, ignores units, and hard-fails on `Number(process.env.X ?? 100)`. | M2 | C3 |
| 9 | **Allow-list only.** No layers, forbidden edges, acyclicity or independence rules; mutual imports between components pass. | M3 | M1 |
| 10 | **Encapsulation is bypassable.** <ul><li>Parent ↔ child imports are always allowed, so a barrel `index.ts` launders any cross-component dependency.</li><li>Implementing an exposed `api` makes the whole component importable from other containers.</li><li>Encapsulation exists only for containers.</li></ul> | C4 | M2 |
| 11 | **Authority is taken from the depending end only.** "Nothing new may depend on legacy X" cannot be expressed. Coverage uses the header mode instead of per-subtree authority, so hybrid models get false violations. | M4 | M3, M8 |
| 12 | **Glob semantics diverge from gitignore/minimatch.** `a/**/*.ts` doesn't match `a/z.ts`, and `a/` matches nothing. Overlapping claims resolve silently by declaration order. Test `src:` can take ownership of an implementation file. | M6 | M3 |
| 13 | **Performance holds only for mostly conforming repos.** On a violation-heavy 20k-file repo: 31–41 s cold and 23–33 s warm, versus the documented 4.6 s / 1.5 s. The cost is `allowed()` (pairs × edges × ancestor walks, 57.5M `ancestors()` calls), not file reading. The one-file pre-commit time (≈ 0.8 s) does reproduce. | M7 | M7 |
| 14 | **Hash-based staleness is spec-only**, although docs/05 lists it as implemented. `src:` checks only that the file exists and the line is in range. | minor | M5 |
| 15 | **Deterministic cross-layer checks are missing:** <ul><li>requirement → test *results* (JUnit/jest JSON);</li><li>`satisfies` target has code;</li><li>OpenAPI vs `api`;</li><li>event publishers and subscribers;</li><li>config reads;</li><li>`lifecycle: planned/deprecated` enforcement;</li><li>superseded decisions with live links.</li></ul> | M5 | M5, M6 |
| 16 | **The pilot is not powered to decide anything except harm or upkeep.** <ul><li>Fable: about 75 paired tempting tasks are needed for a 50% violation reduction, and the template has 8.</li><li>Sonnet's simulation: a true +10 pp gain gives GO 12% of the time, and a true halving of violations with 12 tempting tasks gives GO 7%.</li><li>Yet 6 one-sided tempting tasks suffice for GO (p ≈ 0.03).</li></ul> | C6 | M9 |
| 17 | **Pilot gaming and confounds:** <ul><li>the UCN authors write the tempting tasks and annotate the needed facts;</li><li>GO has two routes with no multiplicity control;</li><li>a single run per task despite nondeterministic agents;</li><li>the percentile bootstrap is anti-conservative at small n;</li><li>the power formula is off;</li><li>validator precision and CI data are collected but never enter `decide()`.</li></ul> | C6 | M9 |
| 18 | **Upkeep, the one decisive criterion, is weak:** self-reported, not differential against the light stack's own upkeep, and with no rule for where model-diff review time is counted. The last-two-weeks window hides setup cost. | C6 | M9 |
| 19 | **The 60–70% value estimate for the lightweight stack is a guess.** Teams adopt UCN only if the model *replaces* their rule files; they reject it if it is a second file to maintain next to `.dependency-cruiser.js`. | M8 | M10 |
| 20 | Example inconsistency: the model records adoption at `baseline: 6794ead`, yet the adopt gate blocks on it. `6794ead` is a commit of this research repo. The README linked a missing doc. | nits | M8, nit 1 |

## 6.3 Points raised by only one reviewer

**Only Fable 5.1:**

- **"Code justifies itself" (C1), the most important single finding.** The validator builds its allowed set from relations declared anywhere below the depending element, including **function-level `calls`/`uses`/`reads`/`writes` edges**. Those belong to the logic layer, which is code-authoritative in both modes and generated *from* the code. In Shortly, Links → Codes, Guard, Db and Cache pass only because of `fn` edges. An adapter that writes `fn check calls Links.isHttpUrl` would silently "fix" the planted Guard → Links violation, and an `[inferred]` edge is enough. Fix: permissions come only from **model-authoritative, non-inferred architecture-layer relations**; `fn` edges are observations to check.
- **The model file is itself an attack surface.** An agent can turn CI green by editing the model (adding a relation or a deviation). Fix: a `--diff BASE` report of permissions a PR *widens*, with code-owner approval required on the model file.
- **Information parity in the pilot.** The light arm must contain the same constraints. Generate its `AGENTS.md` and dependency-cruiser/import-linter rules **from the same UCN model**, so the measured delta is exactly what UCN adds.
- Use k ≥ 3 runs per task with clustered analysis. Allow EXTEND at most once, then KILL. Add Kiro/Spec Kit-style specs as a second baseline.
- The core is still too big for "core" (M9).
- Prior art: **Tach**, **Spring Modulith**, Nx boundaries, StrictDoc.

**Only Sonnet 5.5:**

- **Simulated the decision rule** (300 replications per scenario). It found the pilot detects large *harm* well (true −20 pp gives KILL 76% of the time) but confirms benefit rarely. Its conclusion: say plainly that the pilot can only confirm large effects.
- Net-benefit upkeep formula instead of a flat 10%. Count LLM token cost for agent-proposed model diffs, and setup cost.
- Re-baselining is the main **laundering path**: flip to reverse, edit the model to match the code, flip back with a new baseline. It needs rules for what happens to deviations, accepted conflicts and planned requirements, and who may do it.
- `approved:` is free text, so authors can approve their own waivers. Bind it to CODEOWNERS or review identity.
- Measure hybrid convergence: share of files under model authority, age of the oldest MODEL-UPDATE.
- **Emit config for existing linters** so UCN is the single source of truth.
- A command that prints the effective authority map.
- Spec/code disagreement on `rule` (the spec says Logic, the validator says Intent). A forgotten `mode:` silently defaults to the weakest setting.
- A first read of a fresh clone is slow for *users* too (antivirus, CI cache restore). Calling it an "artifact" understates it.
- Prior art: **import-linter**, **Deptrac**, **OpenFastTrace** (requirement-ID tracing to code and tests with coverage, direct prior art for `satisfies`/`verifies` completeness), GitHub Spec Kit, ArchCNL.

## 6.4 Corrections applied immediately

Three statements in v0.3 were factually wrong, so they are corrected in this commit, not deferred:
- **Performance** (05 §5.3, 03 §3.7): the 4.6 s / 1.5 s figures hold for a mostly conforming repository with sparse relations. Violation-heavy, dense graphs take 25–40 s because `allowed()` is quadratic. A fresh-clone first read is OS-dominated and real for users.
- **Staleness** (05 §5.3): hash-based staleness is specified, not implemented.
- **"Misses never block wrongly"** (03 §3.13): false. Regex false positives do block.

## 6.5 What v0.4 should do (consolidated plan)

Ordered by how much each item affects the core claim. Every reproduction in both reviews becomes a regression test.

1. **Change the strategy: a governance layer over existing checkers** (both, top recommendation).
   - Read normalized dependency edges from dependency-cruiser, madge, grimp/import-linter, SCIP or tree-sitter with tsconfig resolution, instead of regex-scanning. Keep the regex only as a labelled fallback that reports its blind spots.
   - **Compile** the model's allowed, forbidden and layer rules into those tools' configs, so the model is the single source of truth, not a second rules file.
2. **Fix what "allowed" means** (Fable C1, both on authority).
   - Permissions come only from model-authoritative, non-inferred architecture relations; `fn` edges are checked, never trusted.
   - The finding class is decided by the *stricter* of the two ends' authority, so target-side rules become expressible.
   - Coverage uses per-subtree authority.
3. **Fail closed on governance.**
   - Integrity errors (dangling refs, relation-table violations, invalid deviations, malformed ISO dates, overlapping ownership) fail CI in any mode.
   - Deviations require `expires` and `approved`, and their breadth and horizon are capped.
   - The `allows` relation is compared with the observed dependency type.
   - Suppressing conflicts get `expires`, `approved` and an *asserted* code value, and they stop suppressing when the code moves.
   - `--diff BASE` reports widened permissions, and owner approval is required on the model file.
4. **A real adopt gate.**
   - `--gate adopt --scope X` simulates model authority for the scope.
   - It blocks on inferred facts, any mismatch, MODEL-UPDATEs, coverage gaps and open conflicts.
   - `--apply` writes the authority change and the baseline commit into an append-only adoption log.
   - Re-baseline gets the same treatment, with explicit rules for deviations, conflicts and planned requirements.
5. **Sound incremental runs and linear performance.**
   - Normalize `--changed` paths and fail if a path matches nothing; run fully when the model changes.
   - Cache raw specifiers only and re-resolve each run; version the cache.
   - Precompute ancestors and an allowed-pair matrix; group the output.
   - Add a violation-heavy benchmark with published hardware, Python version and medians.
6. **Rule vocabulary.**
   - `forbids`, `layer` ordering, `acyclic`, `independent`.
   - Entry-point encapsulation for components, not only containers.
   - Resolve re-exports, so barrels can't launder dependencies.
   - Gitignore-compatible globs, with overlap warnings.
7. **The highest-value deterministic cross-layer checks.**
   - Requirement → test → last result (from JUnit/jest JSON).
   - `satisfies` target has code.
   - OpenAPI ⇄ `api`.
   - `lifecycle` enforcement.
   - Content-hash staleness for `src:`.
   - `bind` by AST with literal evaluation only (anything else is INFO "not statically evaluable") and unit normalization.
8. **Pilot redesign.**
   - **Design:** one pre-registered primary endpoint with a computed sample size; Holm correction if a second is kept; information parity, with the light arm generated from the same model.
   - **Anti-gaming:** tempting tasks written outside the UCN team, with a minimum n; k ≥ 3 runs per task, clustered by task; exact (Newcombe/Tango) intervals.
   - **Decision inputs:** differential, net-benefit upkeep that includes model-diff review and setup; validator precision *and recall* (on seeded violations) in `decide()`.
   - **Limits:** at most one EXTEND, then KILL; Kiro/Spec Kit specs as a second baseline.
   - State plainly that a single-repo pilot can confirm only large effects.
9. **Freeze until GO:** the custom syntax, the knapsack projection, and the logic and runtime modules. Keep only what the pilot needs: the core model, the validator, and a default projector.

## 6.6 Final result

- **Is it useful?** Yes, for a narrower thing than v0.1 imagined. The valuable and novel part is **governance over consistency**:
  - which side is authoritative, per part of the system, and the gated switch between modes;
  - approved, expiring deviations;
  - known conflicts;
  - requirement values bound to code;
  - traceability;
  - all fed into agents' context.

  Plain dependency checking is a solved problem that UCN should *delegate*, not reimplement.
- **Is the code layer important?** It is important as *input* (dependencies, signatures, constants, test results) to be checked, not as content to maintain. Both reviewers confirmed this demotion.
- **How much can tools do?** Every recurring check can be deterministic, and both reviewers agreed. But "deterministic" isn't enough; the checks must also **fail closed**. In v0.3 several didn't, and that is the main thing to fix.
- **Is it worth the effort?** Not proven, and the v0.3 pilot could not prove it either. After the v0.4 fixes, a redesigned pilot can at least **kill** it cheaply if upkeep or precision is bad, and confirm a *large* benefit if there is one.
- **Maturity:** v0.1 scored 5 and 6, and v0.3 scores 5 and 6 against a harder, more honest goal. The concept has converged: both reviewers independently describe the same product. The implementation hasn't caught up yet.

## 6.7 Status after v0.4

Items 1–4 of §6.5 are implemented, and every reproduction from both reviews that they cover is a regression test in [tests/test_tools.py](../tests/test_tools.py) (60 tests). The tools were then run against three real repositories ([07](07-trial-results.md)).

| Plan item | Status |
|---|---|
| 1. Governance layer over existing checkers | `--deps` reads dependency-cruiser, madge or plain edge lists. `ucn_export.py` compiles the model to dependency-cruiser and import-linter configs (generated, not yet run in those tools). The fallback scan is now Python `ast`, plus comment-aware TS/JS with tsconfig paths, ESM `.js`→`.ts`, asset classification and reported blind spots. |
| 2. What "allowed" means | Permissions only from non-inferred architecture relations (Fable C1); `fn` relations are checked as observations. The stricter end's authority decides the class. Exposure is required to enter an element (implementation files are no longer exposed through `implements`). Barrels can't launder a dependency. Coverage class comes from the nearest element. |
| 3. Fail closed | Integrity errors fail CI in every mode. ISO dates, required fields, lifecycle enums, horizon and breadth caps. `allows` must name a dependency relation. Accepted conflicts need `expires`/`approved` and stop suppressing when the code moves away from the asserted value. `--diff REV` reports widened permissions. |
| 4. Real adopt gate | Simulates model authority for `--scope`; blocks on violations, MODEL-UPDATEs, inferred facts and open conflicts. `--apply` writes the header or the subtree authority plus an adoption log. `--gate rebaseline` requires `--reason` and reports what loses enforcement. `--authority-map`. |
| also | `--changed` path normalization; the cache stores raw specifiers; gitignore-style globs with `{a,b}`; overlap errors; linear performance; `--propose`; `bind` by literal evaluation with unit scaling. |
| 5–9 | Open. The trials add evidence for item 6 (`forbids`: bootstrapping launders prose rules otherwise) and for the pilot redesign (item 8: tasks must target rules that aren't visible in the code). |
