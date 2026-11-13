# Research record

This folder holds the record of a research project. It asked whether a formal, compact context language can make AI
coding agents follow a project's requirements and architecture. The documents are kept as they were written, including
the claims that later evidence corrected. Read them in order, or start with the
[article](../article/agents-already-read-the-code.md).

## Timeline

| # | Document | What happened |
|---|---|---|
| 1 | [01 Problem statement](docs/01-problem-statement.md) | The goals: one notation for requirements, architecture and code logic, compact enough to use as agent context |
| 2 | [02 Investigation](docs/02-investigation.md) | Survey of SysML v2, C4, EARS, ADRs, KDM and LLM-context work. Nothing combines unification, provenance, budgets and checks |
| 3 | [03 Proposal](docs/03-proposal.md) | The UCN specification (format, projection, validation, governance) |
| 4 | [04 Review synthesis v0.1](docs/04-review-synthesis.md) | First external reviews (two models) |
| 5 | [05 Usefulness and tooling](docs/05-usefulness-and-tooling.md) | Re-framing as a checked layer, with tooling made fast and deterministic |
| 6 | [06 Review synthesis v0.3](docs/06-review-synthesis-v0.3.md) | Second reviews; governance (authority, deviations, conflicts) |
| 7 | [07 Trials](docs/07-trial-results.md) | sqlfluff, excalidraw and cosmicpython: real findings, upkeep over 600 commits, first agent experiments, results identical to import-linter and dependency-cruiser |
| 8 | [08 Pilot](docs/08-pilot.md) | Pre-registered: 60 agent runs on sqlfluff with independent tasks and hidden graders. UCN matched AGENTS.md + import-linter at a ceiling |
| 9 | [09 Review synthesis v0.6](docs/09-review-synthesis-v0.6.md) | Two independent reviews. "Supported" was close to vacuous; bugs fixed; new features frozen |
| 10 | [10 saleor screen](docs/10-saleor-screen.md) | A customer-facing, ADR-driven repository. 20 verified tasks; agents with no docs kept the rules, so the screen failed |
| 11 | [11 Next phase](docs/11-next-phase.md) | Plan, not yet run: where agents break rules (the code around the change) and what prevents it cheaply. Reviewed by a second model |

## Data and code

| Path | Contents |
|---|---|
| [trials/sqlfluff](trials/sqlfluff/) | Models (allow-list and deny-list), generated configs, upkeep history, agent experiment |
| [trials/excalidraw](trials/excalidraw/), [trials/cosmicpython](trials/cosmicpython/) | Models and results of the other two trials |
| [trials/pilot](trials/pilot/PREREGISTRATION.md) | Pre-registration, 12 tasks with graders, results, contexts, tool-call logs of all 60 runs |
| [trials/saleor](trials/saleor/NOTES.md) | Model of 12 ADRs, pre-registration with task hashes, 20 tasks with graders, non-Claude grader review, screening results |
| [trials/containers](trials/containers/README.md) | Dockerfiles: import-linter, dependency-cruiser, and the test and grader runners |
| [harness](harness/) | `recon.py` (prepare and grade reconstruction tests), `pilot_eval.py`, `review_graders.py` (OpenRouter), `replay.py` (upkeep over history) |
| [reviews](reviews/) | The raw external reviews |

## Method, in one paragraph

- **Tasks:** written by a model that never saw UCN.
- **Hidden graders:** proven to fail on the unchanged code and pass on a reference solution. On saleor a naive shortcut
  also had to break a rule test.
- **Pinning:** tasks and decision rules were committed before any run (on saleor with SHA-256 hashes).
- **Grader review:** a model from a different family reviewed the graders; flagged tests were excluded, not edited.
- **Containers:** everything third-party ran in containers.
- **Published:** results and the agents' tool-call logs.

## Known limits

- The task authors, agents and most reviewers were Claude models.
- Each experiment used one repository.
- Agents could not run the projects' test suites.
