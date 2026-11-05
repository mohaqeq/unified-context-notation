# 5. Usefulness, Scope, and Tooling

This document asks whether UCN is worth building, what to cut or add, how much can be done by deterministic tools instead of LLMs, and how a pilot decides whether to continue. It led to the v0.3 restructuring in [03-proposal.md](03-proposal.md).

---

## 5.1 Which problems are real

| Problem | Real? | Comment |
|---|---|---|
| Agents don't know *why*: rationale, requirements, invariants | **Yes, strong** | `AGENTS.md` / `CLAUDE.md` exist because of this. Agents "fix" deliberate choices and break unstated constraints. Code search cannot recover intent. |
| Hand-written context drifts from the code | **Yes** | Every team with an `AGENTS.md` sees it. |
| Architecture erosion | **Yes, and agents make it worse** | Known for decades (reflexion models, ArchUnit). Agents write code faster than humans review structure, so automatic conformance checks become *more* valuable. |
| Docs, tickets and code contradict each other silently | **Yes** | Nobody surfaces it today. |
| Fitting system context into 1–4B models | **Niche** | Matters for air-gapped, privacy- or cost-bound setups. Most agent work runs on large models. |
| Agents can't understand what the code does | **Mostly no** | Frontier agents read and search code well. Restating code as contracts adds little for them. |

**Model tiers.** The literal goal ("the whole context, nothing lost") is out of reach for small models on real systems. Frontier models change this. Rough sizing for a 500k-line system (assumed: ~10k functions, 300 components, 1,000 requirements, 100 decisions):

| Part | Approx. tokens | Fits a frontier model? |
|---|---|---|
| Core card | < 1k | yes |
| Intent layer (requirements, decisions, glossary, conventions, conflicts, deviations) | ~50k | yes |
| Architecture skeleton with relations | ~20k | yes |
| Function signatures with relations | ~250k | borderline |
| Function contracts in full | ~800k | no |

A ~50k-line system fits completely (~100k tokens). For large systems, intent and architecture fit, and only function-level detail needs slicing. Fitting is not the same as being used well: effective context is shorter than advertised for every model, and cost and latency grow with tokens. So the binding constraint moves from window size to attention quality and cost, and a stable core first stays useful (prefix caching).

## 5.2 What to keep, cut, and add

**Reframing.** From "compact context for small LLMs" to **"a checked, traceable intent and architecture layer that keeps coding agents consistent with requirements and architecture."** Compact context is one feature of it.

| Part | Decision | Why |
|---|---|---|
| Intent layer: `req` (with typed parameters), `decision`, `rule`, `convention`, `term` | **Core** | What agents cannot get from code. |
| Architecture skeleton: `system`, `container`, `component` with `code:` globs and allowed relations, `api` | **Core** | Needed for conformance checks and navigation. |
| Traces (`satisfies`, `verifies`, `refines`), `test` | **Core** | Cheap, mostly derivable, checkable. |
| Provenance, `conflict`, `deviation`, authority and modes | **Core** | The differentiators. |
| Deterministic validator | **Core, new** | Turns the model from documentation into guardrails. |
| Simple projection (card + slice + named stubs) | **Core** | Enough for frontier models. |
| Signatures and call graph | **Core, but not ours** | Taken from existing tools (LSP, SCIP, tree-sitter). Not stored as hand-maintained UCN. |
| Function contracts (`pre`/`post`/`err`) | **Module, off by default** | Only for public APIs, cross-service interfaces and pinned invariants. LLM inference per function is expensive, unreliable and changes with every commit. |
| `machine`, `flow`, `event`, `config`, `env`, `data` | **Module** | Useful where present; not needed to start. |
| Budgeted knapsack projection with personalized PageRank | **Module ("small-model")** | Only needed for 1–4B models. |
| SysML v2 export | **Module** | For regulated users. |
| Custom text syntax | **Kept, deprioritized** | One rendering. If the benchmark shows Markdown or YAML works as well, prefer them for adoption. |

**Is the code part important?** Code *facts* are important, but code is its own best representation and agents read it directly. UCN should **index** code (which component owns which files, which constants implement which requirement parameters) and **check** it, not restate it. The exception is knowledge that isn't visible locally in code: invariants spanning modules, implicit state machines, cross-service assumptions. Capture those selectively.

## 5.3 How much can tools do, without an LLM?

The requirement: the logic is coded, fast, and has a negligible effect on build and test time. The split:

| Function | Deterministic tool | LLM needed? |
|---|---|---|
| Parse, lint, canonical JSON, round-trip | yes (`ucn_parse.py`) | no |
| Projection checking: budget, pins, closure, accounting, no invented facts | yes (`--against`) | no |
| File → element mapping (`code:` globs) | yes | no |
| **Architecture conformance** (imports vs allowed relations, waivers, expiry, authority) | yes (`ucn_validate.py`) | no |
| **Parameter consistency** (requirement value vs code constant) | yes, via explicit `bind:` | no (an LLM may *propose* bindings once) |
| **Convention checks** (`only api/db.ts imports pg`) | yes | no |
| Provenance: `src` file/line exists (implemented); content-hash staleness (specified, **not yet implemented**) | yes | no |
| Coverage: code no element claims | yes | no |
| Trace completeness | yes | no |
| Adopt gate (no inferred facts or open conflicts in authoritative layers) | yes | no |
| Signatures, call graph, test-to-code links | yes (tree-sitter, SCIP, coverage) | no |
| Projection selection (card + slice) | yes (BM25 + graph walk) | no |
| Normalizing free-text requirements into EARS | — | **yes** (once, reviewed) |
| Inferring contracts and state machines from code | partly (Daikon from tests, k-tails from logs) | **yes** for the rest (module, off by default) |
| Entity resolution across documents | partly (ids, `aka:`, globs) | **yes** for prose |
| Detecting "doc says X, code does Y" in prose | only for bound parameters | **yes** (candidates, reviewed) |

So **all recurring checks are deterministic**. LLMs are only used for *bootstrapping* (reverse mode, reviewed once) and for *proposing* changes, never as a gate.

### Performance budget and measurements

**Targets:**
- **pre-commit** (changed files only): < 1 s;
- **CI full run:** < 10 s on 20k files;
- **zero coupling to the build:** no compilation, no type checking, no test execution. The validator reads source files and the model only, and runs as its own CI job in parallel with build and tests.

**Measured** (`ucn_validate.py`, pure Python, single-threaded, Windows laptop, synthetic repo with 20,000 TypeScript files, 120,000 imports, 200 components, **sparse relations and a mostly conforming import graph**):

| Run | Wall time |
|---|---|
| Cold, no cache | 4.6 s |
| Warm cache (mtime/size, unchanged files not re-read) | 1.5 s |
| Pre-commit, 1 changed file | 0.8 s |
| Shortly example (13 files) | 6 ms |

**v0.4 measurements** (medians of 3; [07 §7.4](07-trial-results.md#74-performance-on-real-repositories)):

| Repository | Files | Run |
|---|---|---|
| sqlfluff / excalidraw (real) | 269 / 723 | 1.1 s / 1.4 s |
| synthetic, sparse | 20,000 | 5.7 s cold, 1.8 s warm cache, 1.0 s pre-commit |
| synthetic, dense, 33,000 violations | 20,000 | 6.3 s cold, 2.4 s warm cache, 1.0 s pre-commit |

The run time no longer depends on the number of violations: the permission check is memoized over precomputed ancestors, and the absence check uses a lifted set. The v0.3 numbers below are kept for the record.

**Correction after review ([06](06-review-synthesis-v0.3.md)):** these numbers hold only for that favourable case. Both reviewers measured a *violation-heavy, densely related* 20k-file repo: **25–41 s cold and 23–33 s warm**. The cost is in `allowed()`, which is quadratic (distinct dependency pairs × declared edges × ancestor walks), not in file reading. Precomputing ancestors and an allowed-pair matrix makes it linear (v0.4). The first read of freshly written files (176–232 s here) is dominated by antivirus scanning. It is not an artifact for users: fresh clones, branch switches and CI cache restores hit it too. The one-file pre-commit time (~0.8 s) does reproduce.

Reading the files and running the import regex alone takes ~2.5 s of a warm-OS cold run. Remaining costs and how to remove them:
- the ~0.7 s fixed cost is interpreter start-up plus mapping 20k paths;
- parallel scanning or a compiled implementation (Go/Rust) would cut cold runs further;
- tree-sitter would make import extraction exact for edge cases the regex misses, such as imports inside comments, build-time aliases (`@/x`), and Python `importlib`.

**Known limits of the regex approach:** path aliases from `tsconfig` / bundler configs, dynamic imports with computed paths, and dependency injection (no import edge exists). Those need either config-aware resolution or an exported dependency graph from the build tool (for example `madge`, `dependency-cruiser --output-type json`, or `jdeps`), which the validator can read instead of scanning.

## 5.4 Is it worth it?

**The main risk is history.** Model-driven engineering and UML round-trip engineering largely failed in mainstream software. Keeping models in sync cost humans more than the models paid back.

**What's different now:**
1. Agents can do the synchronization work. The agent that changes the code proposes the model change in the same PR, and a human reviews one diff.
2. All recurring checks are deterministic and fast (§5.3), so the model enforces itself in CI instead of rotting.

If upkeep doesn't drop to minutes per PR, UCN fails like MDE did. **That is the assumption the pilot tests first.**

| Worth it for | Probably not worth it for |
|---|---|
| Large, long-lived systems with many contributors or agents | Small apps, prototypes, single-developer projects |
| Regulated domains that already pay for traceability | Short-lived code |
| Legacy modernization (reverse mode, then adopt) | Teams without CI discipline |

**The baseline to beat** is a cheap lightweight stack, not "nothing":
- a structured `AGENTS.md`;
- ADRs in the repo;
- an ArchUnit / dependency-cruiser rules file in CI;
- requirements in Markdown with IDs referenced by tests.

That probably gets 60–70% of the value. UCN must beat it by enough to justify itself.

## 5.5 Pilot protocol

**Setup.** One real repository (≥ 50k lines, ≥ 3 active contributors, an existing CI), UCN **core only**, run for 4–6 weeks. Two conditions on the same tasks: `light` (the lightweight stack) and `ucn`. Same agent and model per pair; the order is randomized.

**Work items:**
- **questions** from real issues;
- **changes**: small issues, scored by tests;
- **tempting tasks** that invite violating a constraint or the architecture.

**Measured, per week:**
- minutes spent maintaining the model vs total review minutes;
- architecture violations the validator caught in CI, and false positives;
- for each task, success, violations, tokens and time;
- for each needed fact (annotated independently), whether it was present, named or absent.

**Pre-registered decision** (`tools/pilot_eval.py`, criteria fixed before the pilot starts):

| Decision | Rule |
|---|---|
| **KILL** | Upkeep in the last two weeks > 10% of review time; **or** (n ≥ 30 and) the success-gain CI upper bound < +10 points and violations are not significantly reduced |
| **GO** | Upkeep ≤ 10%, silent absence ≤ 5%, and either a significant success gain ≥ +10 points (bootstrap CI lower bound > 0, exact McNemar p < 0.05) or a significant ≥ 50% reduction in constraint violations on tempting tasks |
| **EXTEND** | Otherwise; the harness estimates how many paired tasks would be needed |

**Statistical honesty.** With paired binary outcomes, detecting a +10 point difference typically needs **hundreds** of paired tasks: about 370 in the illustrative template, depending on how often the two conditions disagree. A 4–6 week pilot will not reach that. So the pilot decides mainly on the metrics that move fast and are cheap to measure:
- **upkeep cost** (the kill criterion);
- **violations caught** in CI;
- **violation rate on tempting tasks** (large effects need fewer tasks);
- **silent absence.**

Task-success gains are a secondary signal, accumulated across pilots.

**Data and harness:** [examples/pilot/template.json](../examples/pilot/template.json) shows the input format, with illustrative numbers that are *not* results:

```sh
python tools/pilot_eval.py examples/pilot/template.json
```
