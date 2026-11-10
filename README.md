# Unified Context Notation (UCN)

**What it is (v0.6):** a checked, traceable **intent and architecture layer** meant to keep coding agents, and humans, consistent with a system's requirements and architecture. It records requirements, decisions, invariants, conventions, an architecture skeleton, trace links, conflicts and approved deviations, each with its provenance.
- **Deterministic tools** check this model against the code on every commit, in about 1 s on real repositories, without touching the build.
- The same rules **compile to existing checkers** (dependency-cruiser, import-linter), so the model can be the single source of truth.
- A projection turns the model into compact context for agents, and anything relevant it leaves out is named.

**The research question it came from:** is there a formal language that captures *requirements*, *architecture* and *code logic* together, as accurate and compact context for AI agents? *Semantically almost, practically no.* SysML v2 can express nearly everything, and OMG KDM was built for extraction from code. But no existing language combines unification with provenance, budgets, named omissions, consistency checks and LLM legibility. UCN is therefore a **profile, syntax, projection and toolchain** over existing semantics, not a new language.

**Status and evidence ([docs/07](research/docs/07-trial-results.md)):** trialled on three real repositories, in two rounds.
- **sqlfluff:** UCN found a rule in the project's own `AGENTS.md` that 12 modules contradict, which neither its AGENTS.md nor its import-linter contracts catch. It reproduces their import-linter contracts and shows why each of their 4 exceptions is needed. With the deny-list policy, upkeep was **0 model edits in 600 commits**.
- **sqlfluff agent experiment** (rules that aren't visible locally): new architecture violations in **0/8** runs with UCN and the validator, **0/8** with the project's full lightweight stack (AGENTS.md plus import-linter in the loop), 1/8 with AGENTS.md alone, and 2/4 with no agent docs. The check in the loop is what matters. UCN matched the lightweight stack at about 12% fewer tokens.
- **Against the mature tools** (run in containers): identical results to import-linter on sqlfluff and to dependency-cruiser on excalidraw, after fixing five bugs that only running the real tools exposed.
- **excalidraw:** it found circular, undeclared runtime dependencies between published packages.
- **cosmicpython, agent experiment:** on a small, clean codebase it did **not** change agent behavior, and neither did an equivalent `AGENTS.md`, because even agents with no instructions followed the existing patterns.

**Pilot ([docs/08](research/docs/08-pilot.md)):** 60 agent runs on sqlfluff, using 12 tasks written by another model, each with a hidden behavioral grader.
- UCN with the validator in the loop matched AGENTS.md with import-linter in the loop: 24/24 success and 0 violations each.
- It used about 11% fewer tokens, lower on every task.
- **Limits:** both arms hit a ceiling, and the token saving is explained by document size. So the pilot does not show that UCN keeps agents more consistent than the checker alone.

Two independent reviews ([docs/09](research/docs/09-review-synthesis-v0.6.md)) agree: UCN's demonstrated value is one rules file that generates the checker configs, plus governance those tools lack (approved, expiring deviations, and recorded rule-vs-code conflicts). New features are frozen until a harder, size-controlled experiment shows an agent benefit.

## Contents

| Doc | |
|---|---|
| [docs/01-problem-statement.md](research/docs/01-problem-statement.md) | Problem, goals G1–G12 with priorities, formal framing, research questions, success criteria |
| [docs/02-investigation.md](research/docs/02-investigation.md) | Survey of each layer, unification attempts, LLM context work, small-LLM evidence, scored rubric |
| [docs/03-proposal.md](research/docs/03-proposal.md) | UCN v0.4: core and modules, metamodel, syntax, projection, **authority and modes**, **consistency validation**, extraction, evaluation, roadmap |
| [docs/04-review-synthesis.md](research/docs/04-review-synthesis.md) | Two independent reviews of v0.1 and what changed in v0.2 |
| [docs/05-usefulness-and-tooling.md](research/docs/05-usefulness-and-tooling.md) | Is it worth it? What to keep or cut; what deterministic tools can do; performance; pilot protocol |
| [docs/06-review-synthesis-v0.3.md](research/docs/06-review-synthesis-v0.3.md) | Two independent reviews of v0.3, the fix plan, and its status after v0.4 |
| [docs/07-trial-results.md](research/docs/07-trial-results.md) | Trials on sqlfluff, excalidraw and cosmicpython: findings, upkeep over history, agent experiments, container comparisons |
| [docs/08-pilot.md](research/docs/08-pilot.md) | The pilot: reconstruction tests on sqlfluff with independently written tasks and hidden graders |
| [docs/09-review-synthesis-v0.6.md](research/docs/09-review-synthesis-v0.6.md) | Two independent reviews of v0.6 and the pilot: findings, fixes and decisions |
| [docs/10-saleor-screen.md](research/docs/10-saleor-screen.md) | saleor (customer-facing, ADR-driven): model, 20 verified tasks, pre-registered screen. It failed: agents kept the rules from the code alone |
| [examples/shortly/](examples/shortly) | Worked example: model, a small real TypeScript codebase, L0 card, task slice |
| [trials/](research/trials) | Models, results and scripts from the real-repository trials |
| [tools/](ucn) | `ucn_parse.py` (parser, linter, projection checker), `ucn_validate.py` (consistency validator, evidence, staleness, gates, diff, propose), `ucn_project.py` (default projector), `ucn_export.py` (dependency-cruiser and import-linter configs), `recon.py` (reconstruction harness), `pilot_eval.py` (pilot decision) |
| [tests/](tests) | 85 tests, including a regression test for each reproduction from the v0.3 and v0.6 reviews |
| [reviews/](research/reviews) | The raw reviews |

## Try it

```sh
python tools/ucn_validate.py examples/shortly/model.ucn --today 2026-11-05             # model vs code
python tools/ucn_validate.py examples/shortly/model.ucn --today 2026-11-05 --gate adopt  # ready to switch to forward?
python tools/ucn_validate.py examples/shortly/model.ucn --propose                        # relation lines for MODEL-UPDATEs
python tools/ucn_validate.py examples/shortly/model.ucn --authority-map
python tools/ucn_export.py examples/shortly/model.ucn --to dependency-cruiser            # compile to an existing checker
python tools/ucn_parse.py examples/shortly/slice.alias.ucn --against examples/shortly/model.ucn
python tools/pilot_eval.py examples/pilot/template.json
python -m unittest discover -s tests
```

Python 3.10+ with no dependencies. `pip install tiktoken==0.14.0` is optional, for exact token counts.
