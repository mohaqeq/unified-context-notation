# Unified Context Notation (UCN)

**What it is (v0.3):** a checked, traceable **intent and architecture layer** that keeps coding agents, and humans, consistent with a system's requirements and architecture. It records requirements, decisions, invariants, conventions, an architecture skeleton, trace links, conflicts and approved deviations, each with its provenance. **Deterministic tools** check this model against the code on every commit, fast enough for pre-commit hooks and without touching the build. A projection turns the model into compact context for agents, and anything relevant it leaves out is named.

**The research question it came from:** is there a formal language that captures *requirements*, *architecture* and *code logic* together, as accurate and compact context for AI agents? *Semantically almost, practically no.* SysML v2 can express nearly everything, and OMG KDM was built for extraction from code. But no existing language combines unification with provenance, budgets, named omissions, consistency checks and LLM legibility. UCN is therefore a **profile, syntax, projection and toolchain** over existing semantics, not a new language.

**Status:** a specification with working prototypes, not yet validated on a real repository. The v0.3 reviews (5/10 and 6/10, both "conditionally worth building") found that the validator fails open in several places; the fix plan is in [docs/06](docs/06-review-synthesis-v0.3.md). Whether it is worth its upkeep is decided by a pilot with pre-registered kill criteria ([docs/05](docs/05-usefulness-and-tooling.md)).

## Contents

| Doc | |
|---|---|
| [docs/01-problem-statement.md](docs/01-problem-statement.md) | Problem, goals G1–G12 with priorities, formal framing, research questions, success criteria |
| [docs/02-investigation.md](docs/02-investigation.md) | Survey of each layer, unification attempts, LLM context work, small-LLM evidence, scored rubric |
| [docs/03-proposal.md](docs/03-proposal.md) | UCN v0.3: core and modules, metamodel, syntax, projection, **authority and modes**, **consistency validation**, extraction, evaluation |
| [docs/04-review-synthesis.md](docs/04-review-synthesis.md) | Two independent reviews of v0.1 and what changed in v0.2 |
| [docs/05-usefulness-and-tooling.md](docs/05-usefulness-and-tooling.md) | Is it worth it? What to keep or cut; what deterministic tools can do; performance; pilot protocol |
| [docs/06-review-synthesis-v0.3.md](docs/06-review-synthesis-v0.3.md) | Two independent reviews of v0.3 |
| [examples/shortly/](examples/shortly/) | Worked example: model, a small real TypeScript codebase, L0 card, task slice |
| [examples/pilot/template.json](examples/pilot/template.json) | Pilot data format (illustrative numbers, not results) |
| [tools/](tools/) | `ucn_parse.py` (parser, linter, projection checker), `ucn_validate.py` (consistency validator), `pilot_eval.py` (pilot decision) |
| [tests/](tests/) | Tests for all three tools |
| [reviews/](reviews/) | The raw reviews |

## Try it

```sh
python tools/ucn_validate.py examples/shortly/model.ucn --today 2026-11-05            # model vs code
python tools/ucn_validate.py examples/shortly/model.ucn --today 2026-11-05 --gate adopt
python tools/ucn_parse.py examples/shortly/slice.alias.ucn --against examples/shortly/model.ucn
python tools/pilot_eval.py examples/pilot/template.json
python -m unittest discover -s tests
```

Python 3.10+ with no dependencies. `pip install tiktoken==0.14.0` is optional, for exact token counts.
