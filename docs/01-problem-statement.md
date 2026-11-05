# 1. Problem Statement

## 1.1 Context

An AI agent that works on a software system needs to understand three things:

| Layer | Question it answers | Typical sources |
|---|---|---|
| **Requirements** | *What* must the system do, and *why*? | tickets, PRDs, user stories, emails, meetings, regulations |
| **Architecture** | *How* is it structured, and why was it built this way? | diagrams, ADRs, READMEs, IaC, API specs, wiki pages |
| **Code logic** | *What does it actually do?* | source code, tests, schemas, configs, runtime traces |

Today that knowledge is scattered across these sources. It comes in different formats, at different levels of abstraction, and it is often contradictory or out of date. The agent either:

- reads raw sources, which is expensive, noisy, and impossible for large systems on small models, or
- reads a hand-written summary (`AGENTS.md`, `CLAUDE.md`, `llms.txt`), which is unstructured, incomplete, and drifts away from the code.

## 1.2 The question

> **Q1.** Is there a formal (or semi-formal) language that can represent *requirements*, *architecture*, and *code logic* together, in one model with links between the layers?
>
> **Q2.** If not, can we combine the best existing language from each area into one language built for this purpose?

## 1.3 Goal

Produce a **representation `M`** of a software system, plus a **projection `π`** that turns `M` into context for an agent, such that:

| # | Requirement | Meaning |
|---|---|---|
| **G1** | Unified | One model covers requirements, architecture, and code logic, with explicit **trace links** between them (requirement ⇄ component ⇄ code ⇄ test). |
| **G2** | Source-agnostic | The same fact produces the same representation whether it came from code, a document, a ticket, or a person. Each fact records its **provenance** (where it came from). |
| **G3** | Accurate | Facts are faithful to their sources and can be checked against them. Uncertain or inferred facts are labelled. Conflicts between sources are surfaced, not hidden. |
| **G4** | Compact | The context fits a fixed token budget `B`, including small budgets (≈2k–8k tokens) suitable for low-end local models (≈1–8B parameters on CPU or consumer GPUs). |
| **G5** | Lossless where it matters | Shrinking to fit `B` never *silently* drops important information. Anything omitted is listed as a stub the agent can expand on request. |
| **G6** | Human-readable | The text can be read directly by a person, or rendered losslessly into Markdown and diagrams. |
| **G7** | Small-LLM-legible | A small model can parse and use it without training: familiar words and syntax, shallow nesting, little reasoning needed to decode. |
| **G8** | Maintainable | The model can be updated incrementally as sources change, and drift between model and source can be detected. |

## 1.4 Formal framing

Let

- `S = {s₁…sₙ}` be heterogeneous sources (code files, docs, tickets, specs, tests, …).
- `E : S → M` be an **extraction** function that builds a typed graph `M = (N, R)`. `N` is a set of facts (nodes) and `R` is a set of typed relations (edges). Every node `n` carries `src(n) ⊆ S` and `status(n) ∈ {stated, derived, inferred, conflict}`.
- `T` be a task (for example "fix bug #123", "add a rate limiter", or "explain the payment flow").
- `π(M, T, B) → C` be a **projection** that returns a context `C` with `tokens(C) ≤ B`.

We want `E` and `π` such that

```
maximize   U(T | C)                 -- the agent's expected task success given C
subject to tokens(C) ≤ B
           ∀ n ∈ Pinned(M): n ∈ C    -- critical facts are always present (invariants, safety/security reqs, public contracts)
           ∀ n ∉ C relevant to T: stub(n) ∈ C   -- nothing relevant is silently dropped
           faithful(C, S)            -- every statement in C is entailed by S or is labelled inferred/conflict
```

### Inherent tension (why the goal must be reframed)

For any system that is large enough, the information needed to understand it **cannot** fit into a few thousand tokens. A 500k-line codebase has more essential logic than 8k tokens can hold. The literal goal, "the whole context in a small LLM without losing anything important", is therefore impossible in general. The achievable version is:

1. A **task-independent core** (the "system card") that always fits within a small fixed budget.
2. **Task-conditioned slices** of the model, chosen by relevance and importance to fill the rest of the budget.
3. **Explicit, addressable omissions.** What did not fit is visible as stubs, so the agent (or a tool loop) can expand it. Loss becomes *visible and recoverable* instead of silent.

"Importance" therefore has to be defined operationally. We define it as `pinned > task-relevant > structurally central > other`.

## 1.5 Research questions

- **RQ1.** What existing languages and formats cover each layer, and how well do they meet G1–G8?
- **RQ2.** Does any single existing language cover all three layers? If so, what does it lack for LLM context?
- **RQ3.** What is the smallest **metamodel** (set of node and edge types) that covers the three layers without losing semantics that agents need?
- **RQ4.** What **syntax** gives the best trade-off between token density, human readability, and legibility for small LLMs?
- **RQ5.** How should **projection** (level of detail, ranking, stubs) work so that compactness does not cost the important facts?
- **RQ6.** How do we **measure** "no important context lost"?

## 1.6 Non-goals

- Full formal verification of the system. Formal methods can be *linked to*, not required.
- Replacing source code as the source of truth. The model is a *derived index plus intent layer*.
- Generating code from the model. That is possible later, but it is out of scope here.

## 1.7 Success criteria

| Metric | Target (initial hypothesis) |
|---|---|
| Accuracy on system-understanding questions for a small model (≤8B), compared with raw-file retrieval **at the same token budget** | ≥ +15 percentage points |
| Compression (raw relevant source tokens ÷ context tokens) | ≥ 10× at L1 |
| Extraction faithfulness (share of statements in `M` that are correct or correctly labelled) | ≥ 95% on stated/derived facts |
| Pinned-fact recall in any projection | 100% |
| Human readability (developer rating, 1–5) | ≥ 4 |
