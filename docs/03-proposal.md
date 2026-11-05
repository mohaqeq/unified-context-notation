# 3. Proposal: Unified Context Notation (UCN)

> **One-line summary.** UCN is a small metamodel built from proven parts (EARS, C4, Design-by-Contract, statecharts, ADRs, SysML v2 trace links), written in a compact, line-oriented syntax that small LLMs can read. A **budgeted projection** lets it shrink to any token budget without silently dropping important facts.

The core idea: **the language is the metamodel + provenance + projection, not the syntax.** The syntax is just one rendering, chosen for small-LLM legibility. The same model can also be exported to JSON, SysML v2, C4 DSLs, Mermaid, or Markdown.

---

## 3.1 Design principles

1. **Borrow semantics, don't invent them.** Every node type maps to an established concept. Formal meaning comes from SysML v2 / KerML through the export mapping in §3.9.
2. **One fact per line.** Facts can be added, diffed, ranked, and dropped independently.
3. **Familiar words over symbols.** English keywords usually cost one token each, the same as a symbol, and small models already know them. No new operators. Expressions inside contracts use ordinary programming notation.
4. **Defaults are silent.** Status, level, and other attributes appear only when they differ from the default. This saves tokens.
5. **Every fact has provenance.** It is either *stated* (from a human-authored source), *derived* (computed deterministically from code or specs), *inferred* (produced by an LLM or a heuristic), or a *conflict* (sources disagree).
6. **Nothing is dropped silently.** Projection replaces what doesn't fit with **stubs** that say what was omitted and how to expand it.
7. **Source code stays the source of truth for behavior.** UCN indexes it and adds intent. It does not replace it.

---

## 3.2 Metamodel

### Node kinds (14)

| Layer | Kind | Meaning | Borrowed from |
|---|---|---|---|
| Intent | `goal` | A stakeholder objective (the *why*) | KAOS / i\* (lite) |
| | `req` | A requirement, written as an EARS sentence | EARS, FRETish timing |
| | `decision` | An architecture decision and its rationale | ADR (MADR) |
| Structure | `actor` | A person or external system | C4 Person / External system |
| | `system` | The software system in scope | C4 Software System |
| | `container` | A deployable or runnable unit (service, app, DB, queue) | C4 Container |
| | `component` | A logical module inside a container | C4 Component |
| | `data` | An entity, type, or schema | ER / JSON Schema (summary) |
| | `api` | An exposed interface; details live in an external IDL | OpenAPI / Protobuf / signatures |
| Logic | `fn` | An operation: signature + contract | Design-by-Contract (JML/ACSL/Dafny) |
| | `rule` | An invariant or business rule that must always hold | DbC invariants, SysML `constraint` |
| | `machine` | A state machine (states, events, transitions) | Statecharts / SCXML |
| | `flow` | An ordered interaction across elements | Sequence diagrams / SysML actions |
| Evidence | `test` | A verification artifact (test, check, proof) | SysML `verification`, Gherkin |

Two **meta-lines**, `more` (omission stub) and `conflict`, can appear anywhere.

### Relations (10)

| Relation | From → To | Borrowed from |
|---|---|---|
| `refines` | req → goal / req | SysML `refine`, KAOS refinement |
| `satisfies` | structure/logic → req | SysML `satisfy` |
| `verifies` | test → req / fn / rule | SysML `verify` |
| `uses` | element → element (runtime dependency) | C4 relationship |
| `calls` | fn → fn | call graph (SCIP) |
| `reads` / `writes` | element → data | data flow |
| `exposes` | container/component → api | C4 / ports |
| `affects` | decision → element | ADR scope |
| `supersedes` | decision → decision | ADR status |

### Contract clauses (inside `fn`, `component`, `container`)

| Clause | Meaning |
|---|---|
| `pre:` | Precondition (DbC) |
| `post:` | Postcondition. `result` names the return value. |
| `err:` | Error or exception behavior: `Condition -> Error` |
| `inv:` | Invariant local to this element |
| `assume:` / `guarantee:` | Assume/guarantee contract for a component (AADL/AGREE) |
| `effect:` | Side effects (I/O, state change, events emitted) |

### Common attributes

| Attribute | Example | Meaning |
|---|---|---|
| `src:` | `src: api/links.ts:40` | Provenance: file:line, `doc#section`, `ticket#123`, `person:alice` |
| `tech:` | `tech: node/express` | Technology |
| `owner:` | `owner: team-links` | Ownership |
| `status:` | `status: accepted` | Lifecycle state (for decisions and reqs) |
| `why:` | `why: ...` | Rationale (on a decision or anywhere) |

### Tags (in square brackets after the id, all optional)

| Tag | Meaning |
|---|---|
| `[pin]` | Always included in every projection |
| `[inferred]`, `[conflict]` | Status when it isn't the default. The default is `stated` for docs and tickets and `derived` for code and specs. |
| `[nfr]`, `[security]`, `[safety]`, `[legal]` | Requirement category. `security`, `safety`, and `legal` imply `[pin]`. |
| `[event]`, `[state]`, `[unwanted]`, `[option]` | EARS pattern. `ubiquitous` is the default and is omitted. |

---

## 3.3 Syntax

### Grammar (informal EBNF)

```ebnf
file      = header { line } ;
header    = "ucn" version "system:" Id [ "level:" ( L | "mixed" ) ] [ "task:" quoted ] [ "budget:" int ] ;
line      = indent ( node | clause | relation | attr | transition | more | conflict | comment ) NEWLINE ;
transition = State "->" State ":" "on" text ;          (* only inside a machine *)
node      = kind Id [ tags ] [ ":" text ] ;            (* one-line summary *)
clause    = ( "pre" | "post" | "err" | "inv" | "assume" | "guarantee" | "effect" ) ":" expr ;
relation  = relkw Id { "," Id } ;
attr      = attrkw ":" text ;
more      = "more:" text [ "->" "expand" Id "@" L ] ;
conflict  = "conflict:" text "|" text ;               (* two disagreeing statements, each with src *)
indent    = { "  " } ;                                (* 2 spaces = containment; max depth 4 *)
Id        = Word { "." Word } ;                        (* meaningful names, e.g. Links.create *)
tags      = "[" tag { "," tag } "]" ;
L         = "L0" | "L1" | "L2" | "L3" ;
```

Keyword sets (`kind`, `relkw`, clause words, `attrkw`) are disjoint, so a line's role is decided by its first word. Indentation means containment. `fn` signatures use the host language's notation, because LLMs know it best.

### Small example

```ucn
ucn 0.1 system: Shortly level: L2

goal Share: users share short links that keep working
req Create [event]: WHEN a user submits a valid URL THE system SHALL return a unique 7-char code
  refines Share
req Fast [nfr]: THE system SHALL resolve a code in under 50 ms at p99
  refines Share

container Api: HTTP API
  tech: node/express
  component Links: create and resolve short links
    satisfies Create
    fn create(url: string, owner: UserId): Code
      pre: isHttpUrl(url)
      post: result.length == 7 and unique(result)
      err: rateLimited(owner) -> 429
      src: api/links.ts:40
    rule CodeImmutable [pin]: a code never changes its target after creation
      src: docs/adr/003.md

decision RandomCodes: random base62 codes instead of hashing the URL
  why: the same URL from different owners must get different codes
  affects Links
```

---

## 3.4 Levels of detail (LoD)

Each node can be rendered at four levels. The projection picks a level **per node**.

| Level | Content per node | Typical total budget | Purpose |
|---|---|---|---|
| **L0** | id + kind + one-line text, only for the system card: goals, containers, pinned facts, key decisions | 150–500 tokens | Always present. "What is this system?" |
| **L1** | + relations, tags, signatures | 1k–3k | Inventory: navigation and impact analysis |
| **L2** | + contract clauses, state machines, attributes, `src` | per slice | Logic needed to change code safely |
| **L3** | pointer to raw source / full IDL / full ADR | (fetched on demand) | Ground truth |

Summaries are produced **bottom-up** (code → component → container → system), so each level is a faithful abstraction of the level below it. The hierarchy is that of RAPTOR/GraphRAG-style hierarchical summarization, but over a typed architecture graph instead of text chunks.

---

## 3.5 Projection algorithm `π(M, T, B)`

```python
def project(M, task, B):
    # 1. Core: system card + all pinned facts. Guaranteed.
    C = render(core(M), level="L0") + render(pinned(M), level="L1")
    if tokens(C) > B:
        raise BudgetTooSmall(min_budget=tokens(C))   # report it; never drop pinned facts

    # 2. Seed: what is the task about?
    seeds = match(task, M)    # explicit ids/paths > keyword (BM25) > embedding similarity

    # 3. Relevance: personalized PageRank from the seeds over typed edges.
    #    Edge weights depend on task type, e.g. a "change behavior" task
    #    weights satisfies/verifies/calls above uses.
    rel = personalized_pagerank(M, seeds, weights=edge_weights(task_type(task)))
    score = {n: rel[n] * criticality(n) for n in M}   # criticality: nfr/security, fan-in, conflicts

    # 4. Knapsack: choose (node, level) pairs, greedily by marginal score per token.
    candidates = [(score[n] * gain(L), cost(n, L), n, L) for n in M for L in ("L1", "L2")]
    for value, cost_, n, L in sorted(candidates, key=lambda c: c[0] / c[1], reverse=True):
        if fits(C, cost_, B) and ancestors_included_or_stubbed(n, C):
            C.add(n, L)

    # 5. Stubs: every relevant node left out becomes part of a 'more:' line on its parent.
    for parent, missing in group_by_parent(relevant(score) - C.nodes):
        C.add_stub(parent, summarize_counts(missing), expand_hint(parent))

    # 6. Order for small models: header + core first, task slice LAST (lost-in-the-middle).
    return order(C, core_first=True, task_slice_last=True)
```

**Guarantees.**

- Pinned facts are always present (or the call fails loudly).
- Every relevant omission is visible as a stub.
- Output is deterministic for a given `(M, T, B)`.

**Expansion loop.** An agent that can call tools sends `expand Links@L2` (via MCP or the CLI) to get the stubbed content. An agent that can't call tools still sees *that* something exists and can ask the human.

---

## 3.6 Extraction pipeline `E(S)` (source-agnostic)

```
 sources ──▶ 1. Adapters ──▶ 2. Normalize ──▶ 3. Link & resolve ──▶ 4. Validate ──▶ 5. Store ──▶ 6. Project / render
            (deterministic)  (LLM-assisted)   (graph)               (lint, drift)   (canonical JSON)
```

| Stage | Inputs → Outputs | Determinism |
|---|---|---|
| **1. Adapters** | Code via tree-sitter/SCIP → `fn` signatures, `calls`, modules. OpenAPI/Protobuf → `api`. IaC/Backstage → `container`, `owner`. Tests → `test` + `verifies` (from names, tags, coverage). ADRs → `decision`. Structurizr/LikeC4 → C4 nodes. ReqIF / issue tracker → `req`. | Deterministic → status `derived` or `stated` |
| **2. Normalize** | Free-text requirements → EARS sentences. Code bodies → candidate `pre/post/inv` and one-line summaries. Implicit state handling → `machine`. Module clusters → `component` (if no architecture model exists). | LLM → status `inferred` until a human or a test confirms it |
| **3. Link & resolve** | Entity resolution (the "billing service" in a doc = container `Billing`). Trace link recovery (req ⇄ component ⇄ test) via names, embeddings, test coverage, and commit/ticket references. | Mixed. Each link records its method. |
| **4. Validate** | Schema lint. Dangling ids. Every `req` has ≥1 `satisfies`, otherwise flagged. **Conflict detection**: the doc says X, the code does Y → `conflict:` line. **Drift**: a source hash changed → the fact is marked stale. Optionally, check contracts with property-based tests. | Deterministic |
| **5. Store** | Canonical JSON graph (nodes, edges, provenance, hashes, per-level summaries). Text UCN is a rendering of it. | — |
| **6. Project / render** | `π` (§3.5) → UCN text for agents. Markdown + Mermaid for humans. SysML v2 / Structurizr / LikeC4 export. | Deterministic |

Source-agnosticism (G2) comes from stage 3. Whichever source a fact came from, it lands on the same node type with the same id, and only `src:` differs. When several sources state the same fact, they **merge**, and the fact keeps every `src`. When they disagree, they become a **conflict**.

---

## 3.7 Human readability (G6)

- UCN text is meant to be read directly. It reads like a structured outline.
- `ucn render --md` produces Markdown: headings per container and component, EARS requirement tables, Mermaid C4 and state diagrams, and an ADR list.
- The canonical JSON maps one-to-one to the text, so round-tripping loses nothing.

## 3.8 Small-LLM legibility rules (G7)

1. Indentation depth ≤ 4. One fact per line.
2. Ids are meaningful words (`Links.create`), not opaque codes. They cost a few extra tokens but carry meaning.
3. English keywords, no new symbols. Contract expressions use host-language notation.
4. Fixed section order: header → goals/reqs → structure → decisions → task slice → stubs.
5. Core first, task slice last (positional bias).
6. Default budget targets: **≤4k tokens** for 1–4B models and **≤8k** for 7–8B models, even if the model advertises 32k+ (effective context is much shorter, §2.5).

## 3.9 Interoperability and formal anchor

| UCN | SysML v2 (textual) | C4 (Structurizr/LikeC4) | Other |
|---|---|---|---|
| `goal` | `requirement` (top-level, stakeholder concern) | — | KAOS goal |
| `req` | `requirement def` / `requirement` | — | EARS text, ReqIF SpecObject |
| `system` / `container` / `component` | `part def` / `part` | softwareSystem / container / component | Backstage component |
| `actor` | `part` (external) / actor | person / external system | |
| `api` | `interface def` / `port` | (relationship technology) | OpenAPI / Protobuf reference |
| `data` | `item def` / `attribute def` | — | JSON Schema |
| `fn` | `action def` / `calc def` + constraints | — | signature + JML/ACSL-style contract |
| `rule` | `constraint def` / `assert constraint` | — | invariant |
| `machine` | `state def` | — | SCXML / XState |
| `flow` | `action` with successions | dynamic view | Mermaid sequence diagram |
| `test` | `verification def` | — | Gherkin scenario / test id |
| `decision` | metadata annotation (no native concept) | ADR link (Structurizr supports ADRs) | MADR |
| `satisfies` / `verifies` / `refines` | `satisfy` / `verify` / `refine` (dependency) | — | ReqIF SpecRelation |

Because of this mapping, UCN can serve as a **lightweight, LLM-friendly profile** of SysML v2 + C4. Teams that need formal analysis can export to SysML v2. Teams that don't never see it.

---

## 3.10 Measuring "no important context lost" (RQ6)

**Context Sufficiency Benchmark (proposed).** Take 3–5 open-source repositories of different sizes. For each one, write 50–100 questions with verifiable answers in six categories:

| Category | Example |
|---|---|
| Locate | "Where is the code-collision check?" |
| Explain | "What happens when a code is resolved after expiry?" |
| Impact | "What breaks if `Links.create` returns 8 chars?" |
| Constraint | "What must never change about an existing code?" |
| Trace | "Which requirement does `RateLimiter` satisfy, and which test verifies it?" |
| Why | "Why are codes random instead of hashed?" |

**Conditions**, all at the same budget `B ∈ {2k, 4k, 8k}`:

- (a) raw BM25/embedding retrieval of files
- (b) a repo map (signatures + PageRank)
- (c) hand-written `AGENTS.md`
- (d) UCN projection
- (e) UCN projection with the expand tool
- Upper bound: a large model with the full repository

**Models:** several open models at 1–4B and 7–8B (quantized, CPU-runnable), plus a frontier model for reference.

**Metrics:** answer accuracy, **pinned-fact recall**, hallucination rate, tokens used, number of expansion calls.

**Ablations:** without stubs, without provenance tags, without L2 contracts, and **syntax variants** (UCN text vs JSON vs YAML vs Markdown), to test G7 empirically instead of assuming it.

---

## 3.11 Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM-inferred contracts or summaries are wrong (hallucinated logic) | Tag them `[inferred]`. Promote to derived/stated only via a test, a proof, or human review. Show the status in the projection. |
| Model drifts from code | Source hashes per fact. CI re-extraction. Stale facts are flagged, not trusted. |
| Metamodel is too small (missing concepts) or too large (hard to learn) | 14 kinds is close to C4 + EARS + DbC. Extension via `x-` prefixed kinds, but only after the benchmark shows a need. |
| Extraction cost on large repositories | Deterministic adapters first. LLM normalization is incremental (only changed files) and can run with a small local model. |
| Small models cannot use the expansion loop | The static projection must stand alone. Stubs still inform a human-in-the-loop. The benchmark measures condition (d) separately from (e). |
| Yet another format nobody adopts | Imports from and exports to existing formats (C4 DSLs, SysML v2, OpenAPI, ADRs, `AGENTS.md`). UCN can be *generated* and doesn't need hand authoring. |

## 3.12 Roadmap

| Version | Scope |
|---|---|
| **v0.1** | This specification, plus the hand-written example ([examples/shortly](../examples/shortly)) |
| **v0.2** | JSON Schema for the canonical form, parser and linter, Markdown/Mermaid renderer |
| **v0.3** | Adapters: Python/TypeScript (tree-sitter), OpenAPI, ADR (MADR), Structurizr/LikeC4 import, pytest/jest test linking |
| **v0.4** | Projection engine (`π`) + MCP server (`get_context(task, budget)`, `expand(id, level)`) |
| **v0.5** | Context Sufficiency Benchmark, first results on small models |
| **v1.0** | Freeze the metamodel based on benchmark evidence. SysML v2 export. |
