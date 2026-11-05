# Unified Context Notation (UCN)

**Research question:** Is there a formal language that captures *requirements*, *architecture*, and *code logic* together, as an accurate and compact context for AI agents that fits even a small local LLM? If not, can we build one from the best existing languages?

**Short answer:** *Semantically almost, practically no.* SysML v2 can express nearly everything needed, and OMG KDM was built to extract models from existing code. But no existing language combines unification with provenance, token budgets, named omissions, and small-LLM legibility. The building blocks exist: EARS, C4, Design-by-Contract, statecharts, ADRs, SysML v2 trace links, W3C PROV, personalized PageRank. So UCN is proposed as a **profile, concrete syntax, budgeted projection and toolchain** over existing semantics, not as a new language. Its central property, that nothing relevant is dropped silently, is stated as mechanically checkable guarantees, and the residual risk is measured in a benchmark.

## Contents

| Doc | |
|---|---|
| [docs/01-problem-statement.md](docs/01-problem-statement.md) | Problem formulation, goals G1–G9 with priorities, formal framing, research questions |
| [docs/02-investigation.md](docs/02-investigation.md) | Survey of each layer, unification attempts, LLM context work, small-LLM evidence, scored rubric |
| [docs/03-proposal.md](docs/03-proposal.md) | UCN v0.2: metamodel, syntax, levels of detail, projection with guarantees, extraction, evaluation plan |
| [docs/04-review-synthesis.md](docs/04-review-synthesis.md) | Two independent reviews of v0.1 (Fable 5.1, Sonnet 5.5), what they agreed on, and what changed |
| [examples/shortly/](examples/shortly/) | Worked example: full model, L0 card, task slice, all machine-checked |
| [tools/ucn_parse.py](tools/ucn_parse.py) | Prototype parser, linter and projection checker: UCN → canonical JSON |
| [reviews/](reviews/) | The raw reviews |

## Try it

```sh
pip install tiktoken==0.14.0   # optional, for exact o200k token counts
python tools/ucn_parse.py examples/shortly/model.ucn --lint --tokens
python tools/ucn_parse.py examples/shortly/slice.alias.ucn --against examples/shortly/model.ucn
python tools/ucn_parse.py examples/shortly/model.ucn --json
```

## Status

v0.2: specification revised after two independent reviews, and examples machine-checked. Nothing has been measured on real repositories yet. The next steps are a prototype projector, a stage-2 extraction pilot, and the benchmark. See [docs/03-proposal.md §3.12](docs/03-proposal.md#312-roadmap).
