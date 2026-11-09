# 3. Proposal: Unified Context Notation (UCN) v0.6

> **One-line summary.** UCN is **a checked, traceable intent and architecture layer that keeps coding agents (and humans) consistent with requirements and architecture.** Technically it is a profile, concrete syntax, projection and toolchain over existing semantics (mainly SysML v2 and C4, plus EARS, Design-by-Contract, ADRs and W3C PROV). Deterministic tools check it against the code on every commit. A projection turns it into compact context for agents, and every relevant fact left out is **named** in a stub.

The core idea: **the contribution is the metamodel profile + provenance convention + projection, not the syntax.** The syntax is one rendering, chosen as a hypothesis about small-LLM legibility and tested against alternatives (§3.12). The same model is stored as canonical JSON and can be exported to SysML v2, C4 DSLs, Mermaid, or Markdown.

What changed from v0.1 to v0.2 is in [04-review-synthesis.md](04-review-synthesis.md). The v0.3 restructuring (core vs modules, authority and modes, deterministic validation) follows the usefulness analysis in [05-usefulness-and-tooling.md](05-usefulness-and-tooling.md).

## 3.0 Structure: core and modules

| | Contents | When |
|---|---|---|
| **Core** | Intent (`goal`, `req` with typed `param:`, `decision`, `rule`, `convention`, `term`); architecture skeleton (`system`, `container`, `component` with `code:` globs, `api`, `actor`); traces (`refines`, `satisfies`, `verifies`, `test`); governance (`conflict`, `deviation`); provenance; authority and modes (§3.6); **deterministic validator** (§3.7); default projection (§3.5) | Always |
| **Module: logic** | `fn` contracts, `machine`, `flow`. Contracts only for public APIs, cross-service interfaces and pinned invariants; LLM inference per function is off by default | Where code alone doesn't show the behavior |
| **Module: runtime** | `event`, `config`, `env`, `data` | Event-driven or configuration-heavy systems |
| **Module: small-model projection** | Budgeted knapsack with personalized PageRank (§3.5) | Consumers with 1–4B models |
| **Module: SysML v2 export** | §3.11 | Regulated domains |

Signatures and call graphs are core *inputs* but are not maintained as UCN text. They come from existing tools (LSP, SCIP, tree-sitter) at validation and projection time. **All recurring checks are deterministic**. LLMs are used for bootstrapping and for proposing changes, never as a gate (§3.7, [05 §5.3](05-usefulness-and-tooling.md#53-how-much-can-tools-do-without-an-llm)).

---

## 3.1 Design principles

1. **Borrow semantics, don't invent them.** Every node kind maps to an established concept (§3.11). Provenance vocabulary comes from W3C PROV.
2. **One fact per line.** Facts can be added, diffed, ranked, and dropped independently.
3. **Familiar words over symbols.** No new operators. Whether this helps small models is measured, not assumed.
4. **Inference is never silent.** Every line has an origin (stated, derived, inferred). Defaults keep the text short, but an LLM-produced line is always marked `[inferred]` where it appears, and projections must show it.
5. **Defaults come from how a fact was produced, not where it came from.** Only deterministic tools produce `derived`. A contract an LLM wrote while reading code is `inferred`, even though its `src:` is a code file.
6. **Nothing relevant is dropped silently.** Projection replaces what doesn't fit with stubs that **name** what was omitted. Only the irrelevant tail may be summarized as counts.
7. **Source code stays the source of truth for behavior.** UCN indexes it and adds intent. It does not replace it.
8. **Extracted text is data.** Text from tickets, emails and wikis is shown as content, never as instructions, and it cannot pin itself (§3.13).
9. **Checks are code, not prompts.** Every recurring consistency check is a deterministic tool that runs in seconds, outside the build (§3.7).
10. **Authority is explicit.** For every part of the model it is recorded whether the model or the code wins on disagreement, and that can change over time (§3.6).

---

## 3.2 Metamodel

### Node kinds (21, plus `side` inside a conflict)

| Layer | Kind | Meaning | Borrowed from |
|---|---|---|---|
| Intent | `goal` | A stakeholder objective (the *why*) | KAOS (lite), SysML v2 `concern` |
| | `req` | A requirement, written as an EARS sentence | EARS, FRETish timing |
| | `decision` | An architecture decision and its rationale | ADR (MADR) |
| | `term` | A domain term and its meaning (glossary) | DDD ubiquitous language |
| Structure | `actor` | A person or external system | C4 Person / External system |
| | `system` | The software system in scope (one per model) | C4 Software System |
| | `container` | A deployable or runnable unit (service, app, DB, queue) | C4 Container |
| | `component` | A logical module inside a container | C4 Component |
| | `data` | An entity, type, or schema | ER / JSON Schema (summary) |
| | `api` | An exposed interface; details live in an external IDL | OpenAPI / Protobuf / signatures |
| | `event` | A message or domain event | AsyncAPI, DDD domain event |
| | `config` | A setting or feature flag that changes behavior | 12-factor config |
| | `env` | A deployment environment (where containers run) | C4 deployment node, IaC |
| Logic | `fn` | An operation: signature + contract | Design-by-Contract (JML/ACSL/Dafny) |
| | `rule` | An invariant or business rule that must always hold | DbC invariants, SysML `constraint` |
| | `machine` | A state machine (states, initial state, transitions) | Statecharts / SCXML |
| | `flow` | An ordered interaction across elements | Sequence diagrams / SysML actions |
| Practice | `convention` | How to work on the system: build/test commands, required patterns, forbidden patterns | `AGENTS.md` content, CONTRIBUTING files |
| Evidence | `test` | A verification artifact (test, check, proof) | SysML `verification`, Gherkin |
| | `conflict` | Two or more sources disagree. Has `side` children (each with its own `src`) and `about` links to the facts concerned | Truth maintenance, argumentation |
| Governance | `deviation` | An approved, expiring waiver that allows code to depart from the model: `allows <ref> <relation> <ref>` | MISRA deviation records, ArchUnit freeze |

Each kind is in the metamodel because v0.1 reviewers found agent-relevant facts with nowhere to go (events, flags, the "premium user" term, conventions, deployment). The metamodel is **not** claimed to be minimal. RQ3 is answered by "drop kind K" ablations in the benchmark, and kinds that don't pay for themselves are removed before v1.0.

### Relations (15), with allowed endpoints

| Relation | From | To | Borrowed from |
|---|---|---|---|
| `refines` | req | goal, req | SysML `refine`, KAOS refinement |
| `satisfies` | structure or logic node | req, goal | SysML `satisfy` |
| `verifies` | test | req, fn, rule, machine, component, api, flow | SysML `verify` |
| `uses` | actor, container, component, fn | actor, container, component, api, config, env | C4 relationship (runtime dependency) |
| `calls` | fn | fn, api | call graph (SCIP) |
| `reads` / `writes` | container, component, fn | data, config | data flow |
| `exposes` | container, component | api | C4 / ports |
| `implements` | component, fn | api | interface realization |
| `emits` / `consumes` | container, component, fn | event | AsyncAPI |
| `deploysTo` | container | env | C4 deployment |
| `affects` | decision | any non-decision node | ADR scope |
| `supersedes` | decision | decision | ADR status |
| `about` | conflict | any node | — |
| `forbids` | structure node | structure node | a stated "never" (import-linter `forbidden`, ArchUnit `noClasses().should()`); overrides permissions |

Inside a `deviation`, `allows Stats uses Db` names a relation the model does not declare but tolerates until the deviation expires (§3.7).

The linter enforces this table. A projector may render an edge **at its target** under an inverse name (`satisfiedBy`, `verifiedBy`, `refinedBy`, `calledBy`, `affectedBy`, `implementedBy`) so that a small model finds it next to the fact it concerns. Inverse lines are the same edge, not a new fact.

**Code linkage.** Components and containers carry `code:` path globs (`code: api/links.ts`). This is what reflexion-model drift checks and `src` hash propagation need.

### Contract clauses (inside `fn`, `component`, `container`, `data`)

| Clause | Meaning |
|---|---|
| `pre:` | Precondition |
| `post:` | Postcondition. `result` names the return value. |
| `err:` | Error behavior: `condition -> error` |
| `inv:` | Invariant local to this element |
| `assume:` / `guarantee:` | Assume/guarantee contract for a component (AADL/AGREE) |
| `effect:` | Side effects in prose. **Never the only carrier of an edge**: if a function writes data or emits an event, that is also a `writes` / `emits` relation. |

**Expressions are informal.** Clauses use code-like notation where it is natural (`result.length == 7`) and plain English otherwise (`unknown code -> 404`). They are documentation for agents and humans, not checkable specifications. v0.1's claim that property-based tests "check contracts" is withdrawn. A clause can *point to* a checkable artifact, such as a test via `verified:` or an `icontract` / JML annotation via `src:`.

**When to use which.** One concept, one place:

| Fact | Use |
|---|---|
| A system-wide rule that must always hold, stated by a human | `rule` |
| A property of one element's state | `inv:` on that element |
| What a component promises to others, given what it assumes | `assume:` / `guarantee:` |
| Why something is the way it is | `decision` with `why:`, linked by `affects` |

If a `decision` and a `rule` state the same thing, keep both but link them (`affects`). Projections render only the rule in the core.

### Attributes

| Attribute | Example | Meaning |
|---|---|---|
| `src:` | `src: api/links.ts:40` | A source: file:line, `doc#section`, `ticket#123`, `person:alice`. **Repeatable**: a fact stated by several sources keeps every `src:` line. |
| `tech:` | `tech: node/express` | Technology |
| `owner:` | `owner: team-links` | Ownership |
| `why:` | `why: ...` | Rationale |
| `lifecycle:` | `lifecycle: planned` | `planned`, `active`, `deprecated` for elements (as-is vs to-be); `proposed`, `accepted`, `superseded` for decisions; `open`, `accepted`, `resolved` for conflicts; `proposed`, `accepted`, `revoked` for deviations |
| `authority:` | `authority: source` | Which side wins on disagreement for this node and everything under it: `model` or `source` (§3.6) |
| `param:` | `param: maxLinksPerHour = 100 per hour` | A typed, comparable value of a requirement: `name = number [unit]` |
| `bind:` | `bind: RateLimit.maxLinksPerHour = api/guard.ts#LIMIT_PER_HOUR` | The code constant that implements a requirement parameter (checked, §3.7) |
| `check:` | `check: only api/db.ts imports pg` | A machine-checkable form of a convention or rule (§3.7) |
| `expires:` / `approved:` | `expires: 2027-03-31` | Required on a deviation |
| `layers:` | `layers: Linter > Rules > Parser > Helpers` | On a parent: each child may use every lower one; a lower one must never reach a higher one, **directly or through any chain of module imports** (import-linter semantics) |
| `independent:` | `independent: HString, HSlice, HDict` | On a parent: the named children must not depend on each other |
| `acyclic:` | `acyclic: yes` | On a parent: no dependency cycle among its children |
| `inherit:` | `inherit: yes` | On a child: it gets the permissions declared on its parent |
| `verified:` | `verified: CreateTests` | Evidence that confirms this node (test ids) |
| `code:` | `code: api/links.ts` | Path globs of the code that implements this element |
| `aka:` | `aka: short code, slug` | Aliases, used by entity resolution |
| `states:` / `initial:` | `states: active, expired` | Machine states and initial state |
| `note:` | `note: nothing verifies Alias yet` | A finding written by a tool (lint, projector). Always tool-generated. |

### Labels (in square brackets)

Labels sit after the id on node lines, and at the end of a `fn` signature, clause or relation line. There are four **disjoint** word sets. They share one bracket to save tokens, and the canonical JSON keeps them in separate fields.

| Axis | Words | Meaning |
|---|---|---|
| Category | `nfr`, `security`, `safety`, `legal`, `privacy` | Requirement category. `security`, `safety`, `legal`, `privacy` make a node a **scoped pin**. |
| EARS pattern | `event`, `state`, `unwanted`, `option`, `complex` | Ubiquitous is the default and is omitted. `complex` = several patterns combined. |
| Pin | `pin` | **Global pin**: always inline in every projection. Capped (lint: ≤ 15 per model). |
| Origin and freshness | `stated`, `derived`, `inferred`, `stale` | How the line was produced; `stale` is set by drift detection. |

**Origin rules.** A line's origin is its own origin label, else its nearest ancestor's, else the header's `origin:`. A clause label applies to that line only. A node label applies to the node and everything under it. Renderers must always show `inferred` and `stale`, and may hide `stated` and `derived`.

### Pins: global and scoped

v0.1 pinned every security, safety and legal fact, so a real system's core would overflow any small budget. v0.2 separates *must not be silently dropped* from *must be inline*:

- **Global pins** (`[pin]`): a few hand-chosen facts, such as the system's purpose, safety invariants and open conflicts about them. They are always inline. Capped, and the cap is linted.
- **Scoped pins** (category `security`, `safety`, `legal`, `privacy`): inline when the slice **touches** them, meaning a selected node satisfies, implements or is affected by them. Otherwise they are **named** in a stub (`more: req Blocklist [security], …`). For a large set the stub may name a group node instead (`more: 42 req [security] -> expand Security@L1`), but only for facts outside the task's relevant set.
- **Trust.** A source can only produce a pin if it is in the trusted tier (code, reviewed docs, human authors). Text from tickets or emails can be *labelled* `security` by a reviewed classifier, but it cannot pin itself (§3.13).

### Identity

- A node's **canonical id** is its name qualified by its container path, excluding the single `system` root: `Api`, `Api.Links`, `Api.Links.create`. Top-level nodes (goals, reqs, decisions, tests, conflicts) are unqualified.
- References may use any **unique dotted suffix** (`Links.create`, `Guard.limit`). An ambiguous or dangling reference is a lint error.
- Re-declaring an id with a different kind is an error. A line that repeats a node without text (`container Api`) **re-opens** it, so children can be added in another place. This is how projections show nested items without repeating summaries.
- Entity resolution across sources (the "billing service" in a doc = container `Billing`) uses ids, `aka:` aliases, `term` nodes and `code:` globs (§3.8).

---

## 3.3 Syntax

### Grammar

```ebnf
file       = header NEWLINE { line } ;
header     = "ucn" version "system:" Id { hkey ":" hval } ;
hkey       = "level" | "origin" | "task" | "budget" | "mode" | "baseline" | "root" | "policy" | "tsconfig" ;
                                                         (* task is "quoted"; budget an integer; mode reverse|forward;
                                                            root = code directory relative to the model file;
                                                            policy allow (default: undeclared dependencies are
                                                            violations) | deny (only stated rules are enforced) *)
line       = indent ( node | fnnode | relation | clause | attr | transition | stub | allows | comment ) NEWLINE ;
allows     = "allows" ref relkw ref ;                       (* only inside a deviation *)

node       = kind Id [ labels ] [ ":" text ] ;
fnnode     = "fn" ( Id ":" signature | signature ) [ labels ] ;   (* id = leading identifier of the signature *)
relation   = ( relkw | invkw ) ref { "," ref } [ labels ] ;
clause     = clausekw ":" expr [ labels ] ;
attr       = attrkw ":" text ;
transition = "on" event ":" State "->" State ;              (* only inside a machine *)
stub       = "more:" item { "," item } [ "->" "expand" ref "@" level ] ;
item       = kind ref [ labels ] | int kind ;              (* named item, or a count for the irrelevant tail *)
comment    = "#" text ;

labels     = "[" labelword { "," labelword } "]" ;
indent     = { "  " } ;                                    (* 2 spaces per level, max 6 levels, one level per step *)
Id         = Word ;  ref = Word { "." Word } ;
Word       = letter { letter | digit | "_" } ;
level      = "L0" | "L1" | "L2" | "L3" ;

kind       = "goal" | "req" | "decision" | "term" | "actor" | "system" | "container" | "component"
           | "data" | "api" | "event" | "config" | "env" | "fn" | "rule" | "machine" | "flow"
           | "test" | "convention" | "conflict" | "side" | "deviation" ;
relkw      = "refines" | "satisfies" | "verifies" | "uses" | "calls" | "reads" | "writes" | "exposes"
           | "implements" | "emits" | "consumes" | "deploysTo" | "affects" | "supersedes" | "about" | "forbids" ;
invkw      = "satisfiedBy" | "verifiedBy" | "refinedBy" | "calledBy" | "affectedBy" | "implementedBy" ;
clausekw   = "pre" | "post" | "err" | "inv" | "assume" | "guarantee" | "effect" ;
attrkw     = "src" | "tech" | "owner" | "why" | "lifecycle" | "verified" | "code" | "aka" | "note"
           | "states" | "initial" | "authority" | "param" | "bind" | "check" | "expires" | "approved"
           | "asserts" | "breadth" | "layers" | "independent" | "acyclic" | "inherit" ;
labelword  = (* the four label sets in §3.2 *) ;
```

**Lexical rules.**

- **A line's role is decided by its first word.** The keyword sets above, plus `on`, `more`, `allows` and `#`, are disjoint. Transitions start with `on`, so a state named `data` or `test` cannot be misread as a node.
- In a node line, the summary starts after the **first** `:` following the id and labels. Later colons are text.
- A trailing `[ … ]` is read as labels **only if every word in it is a label word**. Otherwise it is part of the text or expression (so `int[]` or `xs[i]` are safe).
- In stub and relation lists, items are separated by commas outside brackets.
- `text` and `expr` run to the end of the line (minus trailing labels). There is no escaping, because no later field follows them.
- `fn` signatures use the host language's notation, which LLMs know best. If the signature doesn't start with the function name (Go receivers, Java modifiers), write `fn Id: <signature>`.

### Small example

```ucn
ucn 0.3 system: Shortly level: L2 origin: stated

goal Share: users share short links that keep working
req Create [event]: WHEN a user submits a valid URL THE system SHALL return a unique 7-char code
  refines Share

system Shortly [derived]: URL shortening service
  container Api: HTTP API
    tech: node/express
    component Links: create and resolve short links
      code: api/links.ts
      satisfies Create
      fn create(url: string, owner: UserId): Code
        pre: isHttpUrl(url) [inferred]
        post: result.length == 7 [inferred]
        err: rateLimited(owner) -> 429 [inferred]
        calls Codes.generate
        verified: CreateTests
        src: api/links.ts:40
      rule CodeImmutable [pin, stated]: a code never changes its target after creation
        src: docs/adr/003.md

conflict RateLimitValue [pin]: the ticket and the code disagree on the hourly limit
  about RateLimit, Guard.limit
  lifecycle: open
  side Ticket: 100 links per hour
    src: ticket#14
  side Code [derived]: 1000 links per hour
    src: api/guard.ts:44
```

The full example is [examples/shortly/model.ucn](../examples/shortly/model.ucn).

---

## 3.4 Levels of detail (LoD)

Each node can be rendered at three levels. The projection picks a level **per node**. L3 is not a rendering: it is the raw source, fetched on demand.

| Level | Content per node | Purpose |
|---|---|---|
| **L0** | kind, id, labels, one-line text. No relations, attributes or clauses. | Orientation. The system card is the L0 rendering of goals, the system, containers, global pins and open conflicts. |
| **L1** | + relations, `fn` signatures, `lifecycle`, inverse edges where useful | Navigation and impact analysis |
| **L2** | + contract clauses, machine details, all attributes including `src` | The logic needed to change code safely |
| **L3** | pointer to raw source / full IDL / full ADR (`expand` returns it) | Ground truth |

**L0 and L1 are rendered deterministically from fields**, by per-kind templates. LLM-written summaries are used only for text that no source states (for example a container's one-line purpose when no doc gives one). Such text is `[inferred]`, and errors cannot be laundered upward as "faithful abstractions".

**Hash propagation.** Each node stores a hash of its sources. A summary or derived node also stores the hashes of the nodes it was built from (Merkle style). A change at the bottom marks every dependent node above it `stale`.

---

## 3.5 Projection `π(M, T, B)`

### Default projection (core), implemented by `tools/ucn_project.py`

For frontier models, and as the default:
1. the core card (L0), including global pins, accepted or open conflicts, and active deviations;
2. **the whole intent layer and architecture skeleton at L1**, if it fits; otherwise the part reachable from the task's seeds;
3. the seeds' neighborhood at L2;
4. named stubs for every relevant node left out, and counts for the rest.

No ranking model is needed. Seeds come from ids and paths in the task and from BM25, and the neighborhood is a bounded typed-graph walk. The guarantees below apply unchanged, and the same checker verifies them. The rest of this section describes the **small-model module**, for budgets where the default does not fit.

### Budget

`B` is the UCN share of the effective window (§1.4), counted in the target model's tokenizer. Defaults:

| Model class | Effective window (assumed, to be measured) | `B_ucn` | Of which core | Of which stub reserve |
|---|---|---|---|---|
| 1–4B | ~4k | 1.2k–1.6k | ≤ 500 | ≥ 10% |
| 7–8B | ~8k–16k | 2.5k–4k | ≤ 800 | ≥ 10% |

### Algorithm

The selection is a **multiple-choice knapsack with precedence constraints**: each node is either absent or rendered at exactly one level, a child requires its ancestors to be rendered (at least as a re-open line), and a reserved part of the budget is kept for stubs.

```
inputs: model M, task T, budget B, task_type ∈ {change, fix, explain, review} (default: change),
        tokenizer, seed config (fixed embedding model + version, or none)

1. Core.  core = L0(goals, system, containers) + L0(global pins) + L0(open conflicts about pins)
          if tokens(core) > B − B_stub_min:
              degrade in order: drop container lines into a named stub → render pins as id-only lines
              if still too big: fail with the minimum budget (a global pin is never dropped silently)

2. Seeds. seeds = ids and paths named in T  ∪  top BM25 matches of T over ids, text, aka, code globs
          (optional) ∪ top embedding matches, only if the embedding model is pinned in the seed config

3. Relevance. score = personalized PageRank from seeds over typed edges,
          fixed iterations, edge weights from a published table per task_type,
          × criticality (category, pin, open conflict, fan-in);  ties broken by canonical id
          R = top-k by score ∪ {n : score(n) ≥ τ}
          R += scoped pins touched by R          (touch = satisfies / implements / affects / about)

4. Selection. for each n in R, options = {absent, L0, L1, L2}
          cost(n, L)  = tokens of its lines at level L  + tokens of ancestor re-open lines not yet charged
          value(n, L) = score(n) × gain(kind, L)          (gain: a published table per kind and level)
          greedy over incremental upgrades (absent→L0→L1→L2) by Δvalue/Δcost,
          respecting precedence and B − B_stub; then compare with the best single item (standard 1/2 bound)

5. Closure and stubs.
          for every relation in C whose other end is not in C: name that node in a stub
          for every n in R \ C: name it in a stub (kind, id, category labels)
          everything outside R: count it per kind in one tail stub
          if tokens(stubs) > B_stub: downgrade the lowest-value selected node one level and redo step 5
          (only the irrelevant tail may ever become a count)

6. Denormalize for small models (optional, per model class): render key inverse edges at their targets
          (satisfiedBy, verifiedBy), and repeat a short definition rather than referencing a distant line.

7. Order.  header → core (stable prefix, cacheable) → task slice → tail stub.
           The task's central nodes are placed last.
```

### Guarantees (precise)

Each of these is checked mechanically by `ucn_parse.py --against MODEL` (`check_projection`):

1. `tokens(C) ≤ B`, in the stated tokenizer.
2. Every global pin is present.
3. Every scoped pin is present or named.
4. **Closure:** every id referenced in `C` resolves to a node present in `C` or named in a stub.
5. **Accounting:** every node of `M` is exactly one of: present, named, or counted.
6. **No invented facts:** every node and edge in `C` exists in `M`.
7. **Determinism** for a fixed `(M, T, B, task_type, tokenizer, seed config)`.

What is **not** guaranteed: that `R` contains everything the task needs. `R` comes from a heuristic, and a needed fact outside `R` ends up only in a count. That is the residual silent-loss risk. The benchmark measures it directly as the silent-absence rate (§3.12). Seed retrieval quality (recall@k of the annotated needed facts) is measured separately from the LLM.

### Expansion and multi-turn

An agent that can call tools sends `expand Links.resolve@L2` or `expand Shortly@L1` (via MCP or the CLI). The response is a projection of the requested nodes. The expanded content **replaces** its stub, and later projections are computed with the remaining budget. An agent that can't call tools still sees *what* exists, by name, and can ask a human.

---

## 3.6 Authority and modes (forward, reverse, and switching)

UCN supports both **reverse engineering** (building context for an existing system) and **forward engineering** (the model leads, the code follows). The choice is explicit, recorded, and can change later.

**Origin vs authority.** *Origin* records how a fact was produced (stated, derived, inferred). *Authority* records which side wins when the model and the code disagree:

| Authority | On disagreement | The code is read in order to… |
|---|---|---|
| `source` | the model is stale, so update it (MODEL-UPDATE) | **update** the model |
| `model` | the code is wrong unless a deviation allows it (VIOLATION) | **check conformance** |

**Modes are presets**, set in the header (`mode: reverse | forward`):

| Mode | Intent | Architecture | Logic | Tests | Governance |
|---|---|---|---|---|---|
| `reverse` | source | source | source | source | model |
| `forward` | model | model | source | source | model |

Function signatures and call graphs always come from the code. In forward mode they are what the code is checked *with*. `authority:` on a node overrides the preset for its subtree, so a legacy container can stay in reverse while the rest is forward. That mixed state is a **hybrid** model, and it is how most real systems will look during adoption.

**Switching is an explicit event with a gate** (implemented in v0.4).
- **Adopt** (reverse → forward, for the whole model or one subtree) runs `ucn_validate.py --gate adopt [--scope ID]`. The gate **simulates** model authority for the scope and runs every check under it, so it is meaningful while the model is still in reverse mode. It blocks on:
  - any VIOLATION under the simulated authority, including integrity errors and coverage gaps;
  - any remaining MODEL-UPDATE in the scope (the model is known to be behind the code);
  - any inferred node, clause or relation in the scope's intent and architecture;
  - any open conflict `about` something in the scope.

  `--apply` writes the change only if the gate passes. For the whole model it sets `mode: forward baseline: <rev>` in the header; for a subtree it sets `authority: model` on the scope node. Either way it appends a line to an append-only adoption log.
- **Re-baseline** (`--gate rebaseline --scope ID --reason TEXT [--apply]`) goes back to `authority: source`. It requires a reason and reports what loses enforcement: deviations, conflicts, bindings and checks in the scope. It is recorded the same way.
- **Widening is visible.** `--diff REV` compares the model with the version at git REV and reports every permission the change *widens* as WIDENED, failing CI unless `--allow-widening` is passed after code-owner approval of the model file:
  - new relations;
  - new or extended deviations;
  - lowered authority;
  - newly accepted conflicts;
  - removed checks, bindings and parameters.

  This closes the path where an agent turns CI green by editing the model.
- **`--authority-map`** prints the effective authority of every node and where it comes from.

**Daily work in forward mode.**
- To change behavior, change the model first. The change starts as `lifecycle: planned`; then the code follows, and CI checks it.
- The agent that changes the code proposes the model diff in the same PR.
- Every code change lands in one of four classes: **conforming**, **waived** by a deviation, **violation** (fails CI), or **observed new fact**. New functions and files are added as `derived` within an existing component; a file no element claims is a coverage violation.
- The mode goes into the agent's context. In forward mode, planned facts are targets and a mismatch is a defect to fix. In reverse mode, the same mismatch means the model is stale.

## 3.7 Consistency validation (deterministic)

`tools/ucn_validate.py` checks the model against the code with no LLM, no build, and no network. It runs as its own CI job and as a pre-commit hook on changed files.

| Check | Between | How | On mismatch |
|---|---|---|---|
| **Model integrity** | model | Dangling or ambiguous references, relation-table violations, invalid lifecycles, malformed ISO dates, deviations without `expires`/`approved`/`allows`, blanket or container-wide waivers without `breadth: wide`, expiry more than 365 days ahead, overlapping `code:` ownership, a missing `mode:` when bindings/checks/deviations exist | VIOLATION in every mode (fail closed) |
| **Architecture conformance** | architecture ↔ code | Dependency edges come from a build tool's exported graph (`--deps`: dependency-cruiser, madge, or a plain edge list) or, as a labelled fallback, from a scan: Python by `ast`; TS/JS by regex after removing comments, with tsconfig `paths`, ESM `.js`→`.ts` and asset classification. Edges are lifted to elements through gitignore-style `code:` globs (with `{a,b}`). **Permissions come only from non-inferred architecture relations**, never from `fn`-level relations, which are observations. Entering another element requires `exposes`; `implements` works both ways; tests may depend on what they `verify`. Imports through container-level files (barrels) are followed, so they can't launder a dependency. | VIOLATION if **either end** is model-authoritative, otherwise MODEL-UPDATE. WAIVED if an active deviation covers it; an expired or unaccepted deviation is a VIOLATION |
| **Stated rules** | architecture ↔ code | `forbids`, `layers` (direct and **transitive** on the file graph), `independent`, `acyclic`. Under `policy: deny`, these are the only architecture checks, as in import-linter | VIOLATION if either end is model-authoritative. **CONFLICT** if both are code-authoritative: the code contradicts a stated rule, which needs a decision, not a model update, and blocks adoption. KNOWN-CONFLICT if a `conflict` is `about` both ends |
| **Unused deviations** | governance | A deviation whose dependency no longer exists | INFO (remove it, or it will hide a future violation) |
| **Logic vs architecture** | logic ↔ architecture | A `fn`-level relation that implies a dependency the architecture doesn't allow | INFO |
| **Declared but unused** | architecture → code | A declared relation that no code dependency realizes (reflexion "absence") | INFO |
| **Parameter consistency** | requirements ↔ code | `param:` vs the constant named by `bind:` (optional `* k` or `/ k` unit scaling). The constant must be a single top-level definition and a numeric literal expression (`0x64`, `1e2`, `60 * 60`); anything else is INFO "not statically evaluable", never a violation | VIOLATION / MODEL-UPDATE by the requirement's authority. KNOWN-CONFLICT only if an *accepted* conflict with `expires`/`approved` is `about` it **and a side `asserts` the current code value** (when the code moves, it stops suppressing) |
| **Convention checks** | conventions ↔ code | `check: only <glob> imports <module>` | by the convention's authority |
| **Executable evidence** | requirements ↔ code | `--results junit.xml`: each element with verifying `test` nodes is *met* (a verifying test passed), *not met* (one failed) or *without evidence*. Test nodes map to JUnit cases by their `src:` file (pytest classname suffix or a `file` attribute) and an optional `case:` glob. `--require-evidence` makes missing evidence a violation | not met: VIOLATION if model-authoritative and not `planned`, else INFO |
| **Provenance** | model ↔ code | `src:` file exists and the line is in range. With `src: file:line@hash` (8-hex hash of the whitespace-normalized line, written by `--stamp`), a moved line is followed and changed content is flagged as stale. `--stamp` never re-hashes changed content without `--accept-changed` | MODEL-UPDATE |
| **Rationale links** | model ↔ docs | `rationale: path#anchor`: the file and its heading anchor (GitHub slug) exist | MODEL-UPDATE |
| **Coverage** | code → architecture | Code files no element claims | by the authority of the nearest element |
| **Trace completeness** | requirements ↔ architecture ↔ tests | Linter rules | INFO |
| **Adopt / re-baseline gate**, **widening diff** | — | §3.6 | gate blocked / WIDENED |

**Incremental runs.**
- `--changed` accepts repo-relative, root-relative or absolute paths, and errors on a code path outside the root.
- A changed model or tsconfig triggers a full run.
- `--cache` stores raw import specifiers keyed by mtime and size; resolution is redone on every run, so adding a file is always seen.

**Model maintenance.**
- `--propose` prints the exact `uses` lines that would make the current MODEL-UPDATE findings conforming. Violations need a human decision. It **never proposes a dependency that a stated rule forbids**; it drafts a `conflict` record instead, so bootstrapping from code can't launder a contradiction ([07 §7.1](07-trial-results.md#71-sqlfluff-a-project-that-already-has-the-lightweight-stack)).
- `tools/ucn_export.py` compiles the same permission semantics into a **dependency-cruiser** config (`allowed` rules plus `forbidden` rules for conventions) or an **import-linter** config (`forbidden` contracts). The model can then be the single source of truth instead of a second rules file. Neither generated config has been run through its tool yet ([07](07-trial-results.md)).

**Behavioral consistency** (does the running code meet a requirement?) is not decidable in general. It is covered by evidence: tests that *assert* a requirement (`verifies` plus `verified:`), runtime monitors for `machine` definitions (module), and, for critical kernels, formal tools via export. Prose-level contradictions ("the doc says X, the code does Y") are found by bound parameters where possible, and otherwise by LLM-proposed conflict candidates that a human reviews.

**Example output** (Shortly, [examples/shortly](../examples/shortly), mode forward):

```
VIOLATION      architecture Api.Guard depends on Api.Links, which the model does not allow  [api/guard.ts -> api/links.ts]
KNOWN-CONFLICT parameters   RateLimit.maxLinksPerHour = 100 per hour vs api/guard.ts#LIMIT_PER_HOUR = 1000 (conflict RateLimitValue)
WAIVED         architecture Api.Stats -> Db waived by deviation StatsDirectDb (expires 2027-03-31)  [api/stats.ts -> api/db.ts]
WAIVED         architecture Web.Form -> Api.AliasesEnabled waived by deviation WebReadsFlag (expires 2027-02-28)  [web/app.tsx -> api/config.ts]
MODEL-UPDATE   architecture Web.Form depends on Web.Client (both ends authority: source): add a relation or a deviation  [web/app.tsx -> web/client.ts]
```

**Performance** (v0.4, medians, pure Python): ~1 s on real repositories of 269–723 files. On 20,000-file synthetic repositories: ~6 s cold, ~2 s with the cache, ~1 s pre-commit, **independent of how many violations there are** (33,000 in the dense case). The permission check is now memoized over precomputed ancestors ([07 §7.4](07-trial-results.md#74-performance-on-real-repositories)).

---

## 3.8 Extraction pipeline `E(S)` (source-agnostic)

```
 sources ──▶ 1. Adapters ──▶ 2. Normalize ──▶ 3. Link & resolve ──▶ 4. Validate ──▶ 5. Store ──▶ 6. Project / render
            (deterministic)  (LLM / mining)   (mixed)               (checks + LLM   (canonical    (deterministic)
                                                                     candidates)     JSON)
```

| Stage | Inputs → Outputs | Origin of output |
|---|---|---|
| **1. Adapters** | Code via tree-sitter/SCIP → `fn` signatures, `calls`, modules, `code:` globs. OpenAPI/AsyncAPI/Protobuf → `api`, `event`. IaC/Backstage → `container`, `env`, `owner`. Config files → `config`. Tests → `test` + `verifies` (from names, tags, coverage). ADRs → `decision`. Structurizr/LikeC4 → C4 nodes. ReqIF / issue tracker → `req` text as written. CONTRIBUTING/`AGENTS.md` → `convention` candidates. | `derived` (from code and specs) or `stated` (human text as written) |
| **2. Normalize** | Free-text requirements → EARS sentences. *(Logic module, off by default:)* code bodies → candidate `pre/post/inv/err` (LLM), plus **Daikon-style dynamic invariants** from test runs. Implicit state handling → `machine` (LLM, or k-tails/Synoptic mining from traces). Module clusters → `component` if no architecture model exists (clustering such as ACDC/Bunch, reviewed). | `inferred`. Promotion rules are below. |
| **3. Link & resolve** | Entity resolution by id, `aka:`, `term`, `code:` globs and embeddings. Trace-link recovery (req ⇄ component ⇄ test) from names, test coverage, commit/ticket references, and LLM candidates. Each link records its method. | `derived` for deterministic links (coverage, explicit references), `inferred` otherwise |
| **4. Validate** | Deterministic checks: schema, relation table, dangling and ambiguous ids, trace gaps, pin cap, machine consistency, hash-based staleness, **reflexion-model check** (declared `uses` vs extracted dependencies). LLM-assisted: **conflict candidates** ("the doc says X, the code does Y"). This is semantic comparison and probably the hardest step in the pipeline. Candidates become `conflict` nodes only after review, or when two derived values contradict each other outright (two constants). | checks: deterministic; conflicts: `inferred` until reviewed |
| **5. Store** | Canonical JSON graph: nodes, edges, provenance, hashes, per-level renderings. Text UCN is a rendering of it. | — |
| **6. Project / render** | `π` (§3.5) → UCN text for agents. Markdown + Mermaid for humans. SysML v2 / Structurizr / LikeC4 export. | deterministic |

**Promotion.** An inferred line becomes `verified: <test>` only if that test **asserts** the property (checked by linking the clause to a test assertion, not just to a passing test file). It becomes `stated` only through human review. A passing test that doesn't exercise the property confirms nothing.

**Merging (G2).** When several sources state the same fact, they merge into one node with several `src:` lines. When they disagree, the result is a `conflict` node with one `side` per source and `about` links to the facts concerned. A merge never drops a source.

**Two machines.** The *extraction machine* may need a mid-size or frontier model for stage 2, run once and then incrementally on CI. The *consumption machine* is the cheap one. Published results on LLM contract inference (nl2postcond, SpecGen, AutoSpec) are for strong models, often with verifier feedback. There is no evidence yet that a 1–8B local model produces useful `post:` clauses, so stage 2 on a small model is an open question (RQ7), not an assumption.

**Per-stage targets** (to be measured in a pilot on one real repository before more design work): adapter precision ≈ 100%; EARS normalization judged correct ≥ 90%; contract clauses precision and recall reported against a hand-annotated gold set; trace links precision ≥ 0.8 at reported recall; conflict candidates precision reported (recall is hard to define).

---

## 3.9 Human readability (G6)

- UCN text is meant to be read directly. It reads like a structured outline.
- `ucn render --md` (roadmap) produces Markdown: headings per container and component, EARS requirement tables, Mermaid C4 and state diagrams, an ADR list, and a conventions section.
- **Round-trip claim, narrowed.** *Full* model text ⇄ canonical JSON is meant to be lossless (comments excepted). A round-trip test is on the roadmap. Projections are lossy by design: they are checked against the model (§3.5), not round-tripped.

## 3.10 Small-LLM legibility rules (G7)

These are hypotheses, each with an ablation in §3.12.

1. Indentation depth ≤ 6 (trials showed 4 was too shallow). One fact per line. Every line's role is given by its first word.
2. Ids are meaningful words (`Links.create`), not opaque codes.
3. English keywords, no new symbols. (Tokenization of keywords and identifiers is measured per tokenizer: o200k, Llama 3, Qwen, Gemma.)
4. Fixed section order: header → core → task slice → tail stub.
5. Core first (cacheable prefix), task's central nodes last (positional bias).
6. **Few hops.** Render key inverse edges inline (`satisfiedBy`, `verifiedBy`) and avoid making the model join facts across distant lines.
7. Budgets as in §3.5, in the model's own tokenizer, leaving room for code, task and output.

## 3.11 Interoperability and formal anchor

**Intended mapping, not yet validated.** A round-trip test against the SysML v2 pilot implementation is on the roadmap. Until then this table is a design intent.

| UCN | SysML v2 (textual) | C4 (Structurizr/LikeC4) | Other |
|---|---|---|---|
| `goal` | `concern def` / top-level `requirement` | — | KAOS goal |
| `req` | `requirement def` / `requirement` | — | EARS text, ReqIF SpecObject |
| `term` | `doc` / `alias` on a definition | — | DDD glossary |
| `system` / `container` / `component` | `part def` / `part` | softwareSystem / container / component | Backstage component |
| `actor` | `part` (external) / actor | person / external system | |
| `api` | `interface def` / `port` | (relationship technology) | OpenAPI / Protobuf reference |
| `event` | `item def` + `flow` | — | AsyncAPI message |
| `config` | `attribute` | — | |
| `env` | `part` (deployment) | deploymentNode | Terraform, Kubernetes |
| `data` | `item def` / `attribute def` | — | JSON Schema |
| `fn` | `action def` / `calc def` + constraints | — | signature + JML/ACSL-style contract |
| `rule` | `constraint def` / `assert constraint` | — | invariant |
| `machine` | `state def` | — | SCXML / XState |
| `flow` | `action` with successions | dynamic view | Mermaid sequence diagram |
| `test` | `verification def` | — | Gherkin scenario / test id |
| `decision` | metadata annotation (no native concept) | ADR link | MADR |
| `convention` | — (comment) | — | `AGENTS.md` section |
| `conflict` | metadata annotation | — | — |
| `satisfies` / `verifies` / `refines` | `satisfy` / `verify` / `refine` | — | ReqIF SpecRelation |
| origin, `src`, `verified`, `stale` | user-defined `metadata def` | — | W3C PROV (`wasDerivedFrom`, `wasGeneratedBy`) |

This makes UCN a **lightweight, LLM-oriented profile** of SysML v2 + C4. Teams that need formal analysis can export to SysML v2; teams that don't never see it.

---

## 3.12 Evaluation: measuring "no important context lost" (RQ6)

**Reconstruction test** (after Ensemble's fresh-student test, adapted to existing code; `tools/recon.py`): an agent gets a task plus only its condition's context, and a **hidden behavioral grader** (shown to fail on unchanged code and to pass on a reference solution) decides whether the behavior was built. The project's own checker and the UCN validator decide whether the architecture was kept. This measures whether the context was *sufficient* by experiment, not by proxy.

The full benchmark comes after a **pilot** on one real repository that decides go / kill / extend on upkeep cost, violations caught, tempting-task violations and silent absence ([05 §5.5](05-usefulness-and-tooling.md#55-pilot-protocol), `tools/pilot_eval.py`).

### Questions and tasks

- **Sources of questions** (not written by the UCN authors alone, to avoid bias toward what UCN represents): real GitHub issues and the facts their fixes depended on, bug-fix commits, and existing benchmarks (SWE-QA, RepoQA, SWE-bench localization subsets, CodeWikiBench rubrics). Six categories: locate, explain, impact, constraint, trace, why.
- **Downstream tasks**, not just questions: small issue resolutions and changes, scored by tests.
- **Tempting tasks** that invite violating a pinned constraint (for example "make codes editable"). Metric: violation rate.
- **Repositories:** 3–5 of different sizes, including at least one **post-cutoff or private** repository, plus a **no-context** condition to measure what models already memorized.

### The direct measure of silent loss

For each question or task, annotators mark the **facts needed** to answer it, independently of UCN. For each condition, every needed fact is classified as **present**, **stubbed (named)**, or **silently absent**.

- *Silent-absence rate* = absent ÷ needed. This is the G5 metric.
- *Stub usefulness* = how often expanding a named stub recovers a needed fact.
- *Importance ranking*: leave-one-fact-out ablation estimates which facts change outcomes (§1.4), and checks that projections keep the high-importance ones.

### Conditions

All at the same `B_ucn ∈ {1k, 2k, 4k}`, unless stated:

| Condition | What it tests |
|---|---|
| (a) raw BM25/embedding retrieval of files | naive RAG |
| (b) repo map (signatures + PageRank), Repomix `--compress` | code-only packing |
| (c) LLMLingua-compressed raw files | token compression |
| (d) hand-written `AGENTS.md` | state of practice |
| (e) generated wiki (DeepWiki/CodeWiki style) truncated to `B` | generated prose |
| (f) **agent with grep/read/ls tools on the raw repo, at equal total token spend** | the strongest baseline (§1.4) |
| (f2) **lightweight stack**: structured `AGENTS.md` + ADRs + architecture rules in CI + requirement IDs in tests | the cheap alternative UCN must beat ([05 §5.4](05-usefulness-and-tooling.md#54-is-it-worth-it)) |
| (g) UCN projection | static context |
| (h) UCN projection + `expand` tool | context + retrieval |
| (i) the same UCN graph rendered as plain Markdown prose | content vs syntax |
| upper bound: a frontier model with the full repository | ceiling |

### Harm and faithfulness

- **Seeded errors:** inject wrong inferred contracts, wrong links and false conflicts into `M` at controlled rates. Measure the harm compared with no UCN. Stale or wrong UCN must not do worse than none.
- **Extraction audit:** a gold set per stage with two annotators, inter-rater agreement reported. "Correctly labelled" means a wrong fact marked `inferred` counts as labelled, and a wrong fact shown as stated or derived counts as an error.

### Models, metrics, statistics

- **Models:** open models at 1–4B and 7–8B, quantized and CPU-runnable, plus a frontier reference.
- **Metrics:** accuracy and task success, silent-absence rate, pinned-violation rate, hallucination rate, tokens **in each model's own tokenizer**, expansion calls, **prefill latency and total time on a reference CPU**, extraction cost, and maintenance cost per commit.
- **Statistics:** paired comparisons across conditions with confidence intervals. Question counts are chosen by power analysis for the +15 pp target per category, not fixed in advance.

### Ablations

Without stubs; counts-only stubs vs named stubs; without origin labels; without L2 contracts; normalized vs denormalized (inverse edges inline); "drop kind K" for each kind (RQ3); **syntax variants**: UCN text vs JSON vs YAML vs Markdown vs **SysML v2 textual notation** (G7, and a fair test of SysML v2's verbosity).

---

## 3.13 Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM-inferred contracts or summaries are wrong | Line-level `[inferred]`, always shown. Promotion only through asserting tests, proofs or review. Seeded-error harm tests. Daikon-style mining as an evidence-backed alternative. |
| Stage 2 doesn't work on affordable models | Separate extraction machine from consumption machine. Pilot on one real repo before designing further around it. |
| The relevant set misses a needed fact (residual silent loss) | Measured as the silent-absence rate; seeds and weights tuned on it. Closure under references limits the damage. |
| Pinned set grows with system size | Global pins capped; categories become scoped pins; group stubs for the irrelevant tail. |
| Model drifts from code | Source hashes with Merkle propagation to summaries; reflexion-model checks; CI re-extraction; `stale` shown in projections. |
| **Prompt injection through extracted text** (a ticket that says "ignore previous instructions", or tries to pin itself) | Extracted free text is data. Trust tiers by source. Pins and `convention`s only from trusted sources (code, reviewed docs, maintainers). Agents are told that UCN text is content, not instructions. |
| Metamodel too small or too large | Kinds added in v0.2 for concrete gaps; "drop kind K" ablation removes the ones that don't pay off. Extension via `x-` kinds only after evidence. |
| Small models cannot use the expansion loop | The static projection stands alone; stubs name what exists, so a human can help. Conditions (g) and (h) are measured separately. |
| Yet another format nobody adopts | UCN is generated, not hand-written. Imports from and exports to C4 DSLs, SysML v2, OpenAPI, ADRs and `AGENTS.md`. |
| **Upkeep costs more than the model pays back** (how model-driven engineering failed) | Agents propose model diffs in the same PR; recurring checks are deterministic. The pilot's kill criterion is upkeep > 10% of review time. |
| **The regex import scan misses dependencies** (path aliases, dynamic imports, dependency injection) | Read the build tool's exported dependency graph where one exists; config-aware resolution; tree-sitter for exactness. *Correction ([06](06-review-synthesis-v0.3.md)):* the regex also produces false positives (imports inside comments or strings), which do block CI. v0.4 replaces it with exported dependency graphs. |
| **Waivers become permanent** | Every deviation needs `expires:` and `approved:`; an expired deviation fails CI. |
| **The lightweight stack is good enough** | It is the pilot's baseline. If UCN is within noise of it, stop. |

## 3.14 Roadmap

| Version | Scope |
|---|---|
| v0.1 | First specification and hand-written example (reviewed: [04-review-synthesis.md](04-review-synthesis.md)) |
| v0.2 | Revised spec; parser, linter and **projection checker**; example machine-checked |
| v0.3 | Reframed goal; core vs modules; authority and modes; `deviation`, `param`/`bind`, `check`; validator; pilot harness (reviewed: [06](06-review-synthesis-v0.3.md)) |
| v0.4 | Review fixes 1–4: governance layer over existing checkers (`--deps` input; export to dependency-cruiser and import-linter); permissions only from architecture relations; fail-closed integrity; real adopt and re-baseline gates with `--apply`; widening diff; `--propose`; linear performance; trials on sqlfluff, excalidraw and cosmicpython ([07](07-trial-results.md)) |
| v0.5 | Rule vocabulary (`forbids`, transitive `layers`, `independent`, `acyclic`), `policy: deny`, `inherit`, depth 6, CONFLICT class, unused-deviation detection, `--propose` refuses forbidden dependencies; exporter maps rules to import-linter layers/independence/forbidden and dependency-cruiser circular rules; second trial round and agent experiment v2 ([07 §7.6](07-trial-results.md#76-second-round-v05-rule-vocabulary-deny-list-policy-and-agents-on-hidden-rules)) |
| v0.5.1 | Generated configs run in import-linter and dependency-cruiser (containers); agent arm with import-linter feedback ([07 §7.8](07-trial-results.md#78-third-party-checkers-in-containers-v051)) |
| **v0.6 (this)** | Executable evidence (`--results`), content-hash staleness (`--stamp`), rationale links, default projector (`ucn_project.py`), reconstruction harness (`recon.py`), pilot on sqlfluff with independently written tasks ([08](08-pilot.md)) |
| v0.6 | **Pilot** on a larger, older repository with rules that aren't visible in the code, against the lightweight stack. Go / kill / extend by `pilot_eval.py` |
| *only on GO:* v0.7 | MCP server; logic module (contracts for public APIs); small-model projection module; Context Sufficiency Benchmark (§3.12) |
| v1.0 | Freeze the core metamodel based on pilot and benchmark evidence; SysML v2 export module |
