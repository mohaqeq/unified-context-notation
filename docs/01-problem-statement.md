# 1. Problem Statement

## 1.1 Context

An AI agent that works on a software system needs to understand three things:

| Layer | Question it answers | Typical sources |
|---|---|---|
| **Requirements** | *What* must the system do, and *why*? | tickets, PRDs, user stories, emails, meetings, regulations |
| **Architecture** | *How* is it structured, and why was it built this way? | diagrams, ADRs, READMEs, IaC, API specs, wiki pages |
| **Code logic** | *What does it actually do?* | source code, tests, schemas, configs, runtime traces |

Today that knowledge is scattered across these sources. It comes in different formats, at different levels of abstraction, and it is often contradictory or out of date. The agent has three options:

- read raw sources, which is expensive, noisy, and impossible for large systems on small models;
- read a hand-written summary (`AGENTS.md`, `CLAUDE.md`, `llms.txt`), which is unstructured, incomplete, and drifts away from the code;
- **retrieve on demand** with tools (grep, read, code search), which is the state of practice for strong agents but depends on reliable tool use and many turns, both weak points of small models.

## 1.2 The question

> **Q1.** Is there a formal (or semi-formal) language that can represent *requirements*, *architecture*, and *code logic* together, in one model with links between the layers?
>
> **Q2.** If not, can we combine the best existing language from each area into one language built for this purpose?

## 1.3 Goal

**Reframed in v0.3** (see [05-usefulness-and-tooling.md](05-usefulness-and-tooling.md)): the primary goal is **a checked, traceable intent and architecture layer that keeps coding agents (and humans) consistent with requirements and architecture**. Compact context for agents is one feature of it. The small-model budget (G4, G7) is a module for a niche, not the main driver. Frontier models can hold the whole intent and architecture layer even for large systems.

Produce a **representation `M`** of a software system, a **projection `π`** that turns `M` into context for an agent, and **deterministic checks** that keep `M` and the code consistent, such that:

| # | Requirement | Meaning |
|---|---|---|
| **G1** | Unified | One model covers requirements, architecture, and code logic, with explicit **trace links** between them (requirement ⇄ component ⇄ code ⇄ test). |
| **G2** | Source-agnostic | The same fact gets the same node and id whether it came from code, a document, a ticket, or a person. Each fact keeps **every** source it came from. |
| **G3** | Accurate | Facts are faithful to their sources and can be checked against them. How each fact was produced (stated, derived, inferred) is always visible. Conflicts between sources are surfaced, not hidden. |
| **G4** | Compact | The context fits a budget `B_ucn`, the share of the model's *effective* window left after the system prompt, task, code and output (§1.4). For 1–8B models on CPU or consumer GPUs this is roughly 1k–4k tokens. |
| **G5** | Lossless where it matters | Shrinking to fit never *silently* drops information the task needs. Anything relevant that is omitted is **named** in a stub the agent can expand. |
| **G6** | Human-readable | The text can be read directly by a person, or rendered into Markdown and diagrams. |
| **G7** | Small-LLM-legible | A small model can parse and use it without training: familiar words, shallow nesting, few hops between related facts. This is a hypothesis to measure, not a property to assert. |
| **G8** | Maintainable | The model can be updated incrementally as sources change, and drift between model and source is detected, including for summaries built on many files. |
| **G9** | Trustworthy | Text extracted from untrusted sources (tickets, emails, wikis) is treated as data. It cannot raise its own priority (for example, mark itself pinned) or act as instructions to the agent. |
| **G10** | Consistent | The layers are checked against each other: architecture against code dependencies, requirement parameters against code constants, conventions against code, traces for completeness. Code may depart from the model only through an explicit, approved, expiring **deviation**. All recurring checks are deterministic tools, fast enough for pre-commit and with no effect on build and test time. |
| **G11** | Directional | For every part of the model it is explicit whether the model or the code is authoritative (forward vs reverse engineering). The choice is made at the start, recorded, and can change later through a gated, recorded event. |
| **G12** | Worth it | Upkeep stays a small fraction of review time, and the benefit over a lightweight stack (structured `AGENTS.md`, ADRs, architecture rules in CI) is measured, with pre-registered kill criteria. |

**Priorities.** When goals conflict: **G3, G9 > G10 > G12 > G5 > G11 > G4 > G7 > G1, G2 > G6, G8.** Wrong or silently missing facts are worse than a larger context. Unchecked consistency is worth little. A framework that costs more than it saves is not worth building. A larger context is worse than an unfamiliar format.

**Known tensions.**

- *G2 vs G3.* Canonicalizing facts from different sources can hide how reliable each source is. Resolution: merging never discards a source, and a disagreement becomes a conflict node, not a silent overwrite.
- *G4 vs G5 vs G6.* Compactness pushes toward dense, normalized text. Losslessness pushes toward more stubs. Readability pushes toward prose. The projection makes this trade-off explicitly per task.
- *G7 vs G4.* Small models handle repeated local facts better than references across distant lines (multi-hop), but repetition costs tokens. The projector may denormalize (render inverse links inline) and the benchmark decides how much.

## 1.4 Formal framing

Let

- `S = {s₁…sₙ}` be heterogeneous sources (code files, docs, tickets, specs, tests, …).
- `E : S → M` be an **extraction** function that builds a typed graph `M = (N, R)`. `N` is a set of facts (nodes) and `R` is a set of typed relations (edges). Every node `n` carries:
  - `src(n) ⊆ S`, the sources it came from (one or more);
  - `origin(n) ∈ {stated, derived, inferred}`, how it was produced (by a human source, by a deterministic tool, or by an LLM or heuristic);
  - `verified(n) ∈ {no, test, review, proof}`;
  - `fresh(n) ∈ {fresh, stale}`, set when a source it depends on has changed;
  - `lifecycle(n)`, such as planned, active, deprecated, or for decisions proposed, accepted, superseded.

  A **conflict** is a node of its own that links the facts it concerns and records each side with its source.
- `T` be a task (for example "fix bug #123", "add a rate limiter", or "explain the payment flow").
- `B_ucn` be the token budget for UCN content:

  ```
  B_ucn = B_window_eff − B_system − B_task − B_code − B_output
  ```

  `B_window_eff` is the model's effective window, which is much shorter than the advertised one (§2.5). `B_code` is the code the agent must read or edit, and `B_output` is room for the answer or patch. Tokens are counted in the **target model's own tokenizer**.
- `π(M, T, B_ucn) → C` be a **projection** with `tokens(C) ≤ B_ucn`.
- `R(T) ⊆ N` be the **relevant set**: the nodes whose task-conditioned relevance score is in the top `k` or above a threshold `τ`, plus every node one typed hop from a selected node (§3.5).

We want `E` and `π` such that

```
maximize   U(T | C)                        -- the agent's expected task success given C
subject to tokens(C) ≤ B_ucn
           GlobalPinned(M) ⊆ C              -- a small, capped set of critical facts is always inline
           ∀ n ∈ ScopedPinned(M) ∩ touched(T): n ∈ C or named(n) ∈ C
           ∀ n ∈ R(T) \ C: named(n) ∈ C      -- relevant omissions are named, not just counted
           closed(C)                        -- every id referenced in C is in C or named in a stub
           faithful(C, S)                   -- every statement is entailed by its src, or is labelled inferred / conflict
```

`U` and `faithful` cannot be computed by the algorithm. They are made operational by the benchmark and the extraction audit (§3.12). The other constraints are mechanically checkable, and the prototype checks them (`tools/ucn_parse.py --against`).

**Importance.** The ordering `pinned > task-relevant > structurally central > other` is a heuristic *proxy*. The definition we measure against is counterfactual task loss:

```
importance(n) = E_T [ U(T | C) − U(T | C \ {n}) ]
```

It is estimated by leave-one-fact-out ablation in the benchmark. The task-independent core (the system card) optimizes the same quantity over a distribution of typical tasks, not a single task.

### Inherent tension (why the goal must be reframed)

For any large enough system, the information needed to understand it **cannot** fit into a few thousand tokens. A 500k-line codebase has more essential logic than 4k tokens can hold. The literal goal, "the whole context in a small LLM without losing anything important", is therefore impossible in general. The achievable version is:

1. A **task-independent core** (the "system card") that always fits within a small fixed budget. It comes first, so inference engines can cache it as a prompt prefix.
2. **Task-conditioned slices** of the model, chosen by relevance and importance to fill the rest of the budget.
3. **Explicit, addressable omissions.** What did not fit is named in stubs, so the agent (or a tool loop, or a human) can expand it. Loss becomes *visible and recoverable* instead of silent.

**The alternative we must beat: no preloading at all.** A strong agent can retrieve everything with tools. UCN's value is then less "a context blob" and more an **index and intent layer for retrieval**: the card orients the agent, stubs say what exists and where, and intent facts (requirements, rationale, contracts, conflicts) cannot be found by grepping code. The evaluation therefore compares UCN against a tool-using agent at equal total token spend (§3.12).

**Multi-turn use.** Context is consumed across turns. After each expansion, `π` is re-run with the remaining budget, and an expanded node *replaces* its stub rather than adding to it.

## 1.5 Research questions

- **RQ1.** What existing languages and formats cover each layer, and how well do they meet G1–G9?
- **RQ2.** Does any single existing language cover all three layers? If so, what does it lack for LLM context?
- **RQ3.** What is the smallest **metamodel** (set of node and edge types) that covers the three layers without losing semantics that agents need? (Measured by "drop kind K" ablation.)
- **RQ4.** What **syntax** gives the best trade-off between token density, human readability, and legibility for small LLMs?
- **RQ5.** How should **projection** (level of detail, ranking, stubs) work so that compactness does not cost the important facts?
- **RQ6.** How do we **measure** "no important context lost"?
- **RQ7.** How accurately can each extraction stage be done, and on what hardware? (Extraction may need a stronger machine than consumption.)
- **RQ8.** Which consistency checks between layers can be fully deterministic, and how fast can they run? (Answer so far: all recurring ones; see [05 §5.3](05-usefulness-and-tooling.md#53-how-much-can-tools-do-without-an-llm).)
- **RQ9.** Does the model pay for itself? What does upkeep cost per PR, and what does UCN add over a lightweight stack?

## 1.6 Non-goals

- Full formal verification of the system. Formal methods can be *linked to*, not required.
- Replacing source code as the source of truth. The model is a *derived index plus intent layer*.
- Generating code from the model. That is possible later, but it is out of scope here.
- Running extraction on the same cheap machine that consumes the context. Extraction may run once, on CI or a stronger model.

## 1.7 Success criteria

**First, the pilot** (decides whether to continue; pre-registered in [05 §5.5](05-usefulness-and-tooling.md#55-pilot-protocol) and applied by `tools/pilot_eval.py`):

| Metric | Target |
|---|---|
| Model upkeep, last two weeks of the pilot | ≤ 10% of review time (otherwise **kill**) |
| Constraint violations on tempting tasks vs the lightweight stack | ≥ 50% fewer, significant |
| Architecture violations caught by the validator in CI | reported, with precision ≥ 80% |
| Silent-absence rate | ≤ 5% |
| Validator run time | pre-commit < 1 s; full CI run < 10 s on 20k files; no effect on build and test time |

**Then, the benchmark** (only after a GO):

| Metric | Target (initial hypothesis) |
|---|---|
| Task accuracy for a small model (≤8B) with UCN, compared with **the same model using grep/read tools on the raw repo at equal total token spend** | ≥ parity, at lower latency on CPU |
| Task accuracy compared with raw-file retrieval **at the same context budget** | ≥ +15 percentage points |
| **Silent-absence rate**: share of facts needed for a question that are neither present nor named in a stub | ≤ 5% |
| Pinned-constraint **violation** rate in tasks designed to tempt violation | lower than all baselines |
| Harm from seeded errors (wrong inferred contracts injected into `M`) | measured and reported; stale or wrong UCN must not do worse than no UCN |
| Extraction faithfulness per stage, against a gold set with two annotators | ≥ 95% for stated/derived facts; precision and recall reported for inferred facts |
| Human readability (developer rating 1–5, N ≥ 10, fixed protocol) | ≥ 4 |
