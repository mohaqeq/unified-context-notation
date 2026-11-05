# Unified Context Notation (UCN)

**Research question:** Is there a formal language that captures *requirements*, *architecture*, and *code logic* together, as an accurate and compact context for AI agents that fits even a small local LLM? If not, can we build one from the best existing languages?

**Short answer:** No single existing language fits this purpose. SysML v2 comes closest semantically, but it lacks a code-logic layer, extraction, token budgets, and LLM legibility. The building blocks do exist (EARS, C4, Design-by-Contract, statecharts, ADRs, SysML trace links), and the missing parts are **provenance, levels of detail, explicit omission stubs, and budgeted projection**. UCN is a proposal that combines them.

## Contents

| Doc | |
|---|---|
| [docs/01-problem-statement.md](docs/01-problem-statement.md) | Problem formulation, goals G1–G8, formal framing, research questions |
| [docs/02-investigation.md](docs/02-investigation.md) | Survey of each layer, unification attempts, small-LLM evidence, gap analysis |
| [docs/03-proposal.md](docs/03-proposal.md) | UCN: metamodel, syntax, levels of detail, projection algorithm, extraction pipeline, evaluation plan |
| [docs/04-review-synthesis.md](docs/04-review-synthesis.md) | Results of independent reviews by two different models, and what changed |
| [examples/shortly/](examples/shortly/) | Worked example: full model, L0 card, task slice, token counts |
| [tools/ucn_parse.py](tools/ucn_parse.py) | Prototype parser/linter: UCN → canonical JSON |
| [reviews/](reviews/) | The raw reviews |

## Try it

```sh
python tools/ucn_parse.py examples/shortly/model.ucn --lint --tokens   # needs: pip install tiktoken (optional)
python tools/ucn_parse.py examples/shortly/model.ucn --json
```

## Status

v0.1: research and specification draft. See the roadmap in [docs/03-proposal.md §3.12](docs/03-proposal.md#312-roadmap).
