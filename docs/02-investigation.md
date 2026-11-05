# 2. Investigation: State of the Art

This survey covers each layer separately (§2.1–2.3), then attempts to unify them (§2.4), work on LLM context for code (§2.5), and evidence on small-model behavior (§2.6). §2.7 scores the strongest candidates against the goals in [01-problem-statement.md](01-problem-statement.md) with an explicit rubric, and §2.8 answers Q1 and Q2.

**Per-layer scoring key** (§2.1–2.3): ● strong · ◐ partial · ○ weak. These are author judgments, to be replaced by measurements where marked.

- **Expr** = expressiveness for that layer
- **Dens** = token density
- **Fam** = familiarity to LLMs (how much appears in training data). *Untested proxy* for G7; the syntax ablation in §3.10 measures it.
- **Det** = can it be extracted **deterministically** from real sources (parsers, compilers, tools)?
- **LLM** = can an LLM produce it from free text or code (output is *inferred*, not derived)?
- **Read** = human readability

---

## 2.1 Code logic layer

| Candidate | What it is | Expr | Dens | Fam | Det | LLM | Read | Notes |
|---|---|---|---|---|---|---|---|---|
| **TLA+, Alloy, Z, VDM, B / Event-B** | Full formal specification languages | ● | ◐ | ◐ | ○ | ◐ | ○ | Precise and verifiable. Inferring them from existing code is still a research problem. Quint offers TLA+ semantics in programmer-friendly syntax. Event-B's *refinement* is a valuable idea. |
| **Design-by-Contract** (JML, ACSL, Dafny, SPARK, Eiffel, Python `icontract`) | Pre/postconditions and invariants on functions and types | ◐ | ● | ◐ | ○ | ◐ | ● | The best ratio of meaning to tokens for function-level logic. LLMs can propose contracts (nl2postcond, SpecGen, AutoSpec), but published results are mostly for strong models, often with a verifier loop. Daikon infers likely invariants *dynamically* from test runs, which is a deterministic, evidence-backed alternative. |
| **Signatures / stubs** (`.pyi`, `.d.ts`, C headers) | Types and APIs without bodies | ◐ | ● | ● | ● | — | ● | Fully automatic (tree-sitter, compilers). Aider's repo map and Repomix `--compress` are built on this idea. Says *what* the API is, not what it guarantees. |
| **Code indexes** (SCIP/LSIF, Kythe, Glean, tree-sitter tags) | Symbol definitions, references, call graph | ○ | ● | ○ | ● | — | ○ | Accurate structure with no semantics. The right *backbone* for extraction. |
| **Code Property Graph / CodeQL** (Joern, CodeQL Datalog) | AST + control flow + data flow as a queryable graph | ● | ○ | ○ | ● | — | ○ | Powerful for analysis (for example taint flows). Far too low-level for context. |
| **State machines** (statecharts, SCXML, XState) | Explicit state, events, transitions | ◐ | ● | ◐ | ◐ | ◐ | ● | The most compact way to describe stateful behavior. Usually *implicit* in code. Specification mining (k-tails, Synoptic) recovers them from logs or traces. |
| **Sequence / flow diagrams** (Mermaid, PlantUML, BPMN) | Interaction order | ◐ | ◐ | ● | ◐ | ◐ | ● | Mermaid is very familiar to LLMs. Good for key flows only. |

**Best of breed for code logic:** *signatures* (deterministic) + *contracts* (pre/post/invariants, from Daikon-style mining or LLMs, always labelled) + *state machines* for stateful parts. Use code indexes as the extraction backbone. Link to TLA+/Alloy/Quint only for critical kernels.

---

## 2.2 Architecture layer

| Candidate | What it is | Expr | Dens | Fam | Det | LLM | Read | Notes |
|---|---|---|---|---|---|---|---|---|
| **C4 model** + **Structurizr DSL / LikeC4** | Context → Container → Component (→ Code), as text | ◐ | ● | ● | ◐ | ◐ | ● | Small, popular vocabulary. Both have MCP servers for agents. C4 does not cover behavior or requirements. |
| **SysML v2 / KerML** (OMG; adopted June 2025, announced July 2025) | Systems modeling language with a *textual notation* and a standard API | ● | ◐ | ? | ○ | ◐ | ◐ | The most complete *semantic* coverage: parts, ports, actions, calcs, states, constraints, **requirements**, verification, and user-defined `metadata`. Verbosity and LLM familiarity are untested here; they are an arm of the syntax ablation (§3.10). |
| **AADL** (+ AGREE contracts) | Architecture language for embedded and real-time systems | ● | ◐ | ○ | ○ | ○ | ◐ | Assume/guarantee contracts at component level are a valuable idea. Niche. |
| **ArchiMate** | Enterprise architecture | ◐ | ○ | ◐ | ○ | ◐ | ◐ | Business/application/technology layers. Verbose XML exchange format. |
| **UML / PlantUML / Mermaid** | General diagrams | ◐ | ◐ | ● | ◐ | ◐ | ● | Familiar, but weak semantics and diagram-centric. |
| **ADRs** (MADR, Nygard) + **arc42** | Decision records and a documentation template | ◐ | ◐ | ● | ◐ | ◐ | ● | The only widely used place that records **rationale (why)**, which agents need so they don't "fix" deliberate choices. |
| **Interface definition languages** (OpenAPI, AsyncAPI, Protobuf, GraphQL SDL, JSON Schema) | Exact interface contracts | ● | ◐ | ● | ● | — | ● | Precise and extractable. Usually too long to inline, so *summarize and reference* them. |
| **IaC / service catalogs** (Terraform, Kubernetes, Backstage `catalog-info.yaml`) | Deployment and ownership | ◐ | ○ | ● | ● | — | ◐ | Ground truth for the deployment view. |
| **Context Mapper (CML)** | DSL for DDD bounded contexts, aggregates, domain events | ◐ | ● | ○ | ○ | ◐ | ● | Covers domain concepts (aggregates, events, ubiquitous language) that C4 lacks. |
| **Architecture conformance tools** (reflexion models; ArchUnit, jQAssistant, dependency-cruiser, Sonargraph) | Check code dependencies against intended architecture | ◐ | ◐ | ◐ | ● | — | ◐ | Reflexion models (Murphy, Notkin & Sullivan, 1995) compare a hypothesized architecture with extracted dependencies and report convergences, divergences and absences. This is **drift detection between an intent layer and code**, which UCN needs (G8). |

**Best of breed for architecture:** the *C4 vocabulary* for structure, *IDLs by reference* for interfaces, *ADRs* for rationale, *AADL/AGREE-style assume/guarantee* for component contracts, and *reflexion-model checks* for architecture drift.

---

## 2.3 Requirements layer

| Candidate | What it is | Expr | Dens | Fam | Det | LLM | Read | Notes |
|---|---|---|---|---|---|---|---|---|
| **EARS** | Sentence templates: ubiquitous, event-driven (`WHEN`), state-driven (`WHILE`), unwanted behavior (`IF…THEN`), optional feature (`WHERE`), and complex combinations | ◐ | ● | ● | ○ | ● | ● | Semi-formal, compact, readable. Normalizing free text into EARS is LLM work, so the result is *inferred*. Used by AWS Kiro. |
| **Gherkin / BDD** (Given/When/Then) | Executable acceptance scenarios | ◐ | ◐ | ● | ● | ◐ | ● | Links requirements to tests. Wordy for many cases. |
| **User stories + acceptance criteria** | "As a… I want… so that…" | ○ | ◐ | ● | ◐ | ● | ● | Captures *who* and *why*. Ambiguous. |
| **NASA FRET (FRETish)** / Dwyer property patterns | Structured English → temporal logic | ● | ● | ○ | ○ | ◐ | ● | Adds precise timing ("within 50ms", "always", "until"). Can be checked formally. |
| **Goal models** (KAOS, i\*) / **GSN** assurance cases | Goals → sub-goals → requirements; obstacles; arguments | ● | ◐ | ○ | ○ | ◐ | ◐ | Captures the *why* hierarchy. Heavy in its full form. |
| **SysML v2 requirements** | `requirement def` with subject, assumptions, constraints; `concern def` for stakeholder concerns | ● | ◐ | ? | ○ | ◐ | ◐ | Formal, linked to architecture by `satisfy` and `verify`. |
| **Traceability formats** (ReqIF, OSLC, Sphinx-needs, StrictDoc, Doorstop, Eclipse Capra) | IDs, attributes, typed links | ○ | ◐ | ◐ | ● | — | ◐ | Not languages for *content*. They provide the **ID + typed link** discipline. Trace-link *recovery* (IR-based and LLM-based) has well-documented precision/recall limits. |

**Best of breed for requirements:** *EARS* sentences, optional *FRETish* timing qualifiers, *Gherkin-lite* acceptance examples, a lightweight *goal → requirement* hierarchy, and *ReqIF/Sphinx-needs-style* IDs and typed links.

---

## 2.4 Attempts at unification

| Candidate | Covers | What it lacks for LLM context |
|---|---|---|
| **SysML v2 / KerML** | Requirements, architecture, behavior, function-level actions and constraints. Formal semantics, textual syntax, `satisfy`/`verify`, user-defined `metadata` | Not designed for extraction from existing code or documents. No notion of budget, level of detail, or omission. Provenance *can* be carried as metadata, but no convention exists. Verbosity and small-LLM legibility unmeasured. |
| **OMG KDM** (Knowledge Discovery Metamodel, ISO/IEC 19506) + Architecture-Driven Modernization | A standard metamodel for **existing** software: code, actions, data, structure/architecture, UI, conceptual and business rules. Built for extraction from legacy code | The closest prior art for "one model extracted from source". Serialized as XMI, heavy, and weak on requirements and rationale. Not budgeted or LLM-oriented. Little current tooling. |
| **FAMIX / Moose** | A language-independent metamodel of code and its structure, with 20+ years of analysis tooling | Code and architecture only. No requirements, rationale, or contracts. Not aimed at LLMs. |
| **ISO/IEC/IEEE 42010** | Architecture *description*: stakeholders, concerns, viewpoints, views, correspondences | A framework for organizing descriptions, not a language. Its "correspondence" concept is what UCN's cross-layer links are. |
| **jQAssistant** | Code, build and architecture concepts in one queryable graph (Neo4j), with rules | Code-centric. Requirements and rationale are absent. Query, not context. |
| **Event-B + Rodin** | Requirements → abstract machine → refinement toward implementation | Heavyweight. Forward-engineering only. |
| **Capella / Arcadia (MBSE)** | Operational → system → logical → physical layers | Graphical and tool-locked. Systems-engineering focus. |
| **AADL + AGREE** | Architecture + compositional contracts | Embedded niche. No requirements text layer. |
| **RDF/OWL knowledge graphs, OSLC, W3C PROV-O** | Anything (generic linked data). PROV-O models provenance (entity, activity, agent, `wasDerivedFrom`). RDF-star and named graphs attach metadata to single statements | No fixed software vocabulary, so each team invents its own. Serializations are token-heavy. But **per-statement provenance is solved here**: UCN should borrow PROV's vocabulary instead of claiming novelty. |
| **RPG: Repository Planning Graph** (Microsoft, 2025) | One graph of capabilities, files, data flows and functions, used to plan and generate repositories | The closest recent "unified graph for agents". Forward generation, not extraction of intent from existing sources. No provenance or budgeted projection. |
| **Spec-driven development** (Kiro: `requirements.md` / `design.md` / `tasks.md`; GitHub Spec Kit; OpenSpec, Tessl, BMAD) | Requirements (EARS in Kiro) + design + tasks, as Markdown | Informal. Forward-only. No trace graph or budgeted projection. Conventions are converging here, so UCN should import them. |
| **Agent context files** (`AGENTS.md`, stewarded by the Linux Foundation's Agentic AI Foundation; `CLAUDE.md`; `llms.txt`) | Whatever the author writes, typically conventions, commands, and gotchas | Unstructured prose. No schema, provenance, or drift detection. But their content (how to build, test, and what not to do) is what agents ask for first, and UCN v0.1 had no place for it. |
| **LLM-oriented serializations** (TOON, compact YAML, Markdown tables) | Token-efficient encoding of data | Only syntax. TOON's own benchmarks claim large savings on *uniform arrays*. Independent results disagree on accuracy, and some find TOON less accurate than JSON. Lesson: token density alone does not improve comprehension. |

---

## 2.5 LLM context for code (the closest working systems)

| Work | What it does | Relation to UCN |
|---|---|---|
| **Aider repo map** (tree-sitter + PageRank), **Repomix** (`--compress`), gitingest, code2prompt | Pack a repo into a budgeted, signature-level text | The baseline at the code layer. No intent, rationale, or contracts. |
| **Code-graph MCP servers** (codebase-memory-mcp, repo-graph, code-review-graph), **Serena** (LSP-based) | Query code structure on demand | Like UCN's expand loop, code layer only. Savings figures mostly self-reported. A stale graph can mislead. |
| **RepoGraph**, CodexGraph, LocAgent | Repository graphs to help SWE agents navigate | Code-layer graphs evaluated on SWE-bench-style tasks; evidence that graphs help agents. |
| **SWE-agent** (agent-computer interface), **Agentless** (hierarchical file → class → function localization) | Tool-based retrieval; Agentless is level-of-detail navigation in practice | The baseline UCN must beat or complement: an agent that retrieves with tools (§1.4). |
| **HippoRAG** | Personalized PageRank over an extracted knowledge graph, seeded from query concepts | The same technique as UCN's relevance step (§3.5 step 3). Prior art, cite and reuse. |
| **RAPTOR**, Microsoft **GraphRAG** | Hierarchical summarization over text chunks or entity communities | UCN's levels of detail do this over a typed architecture graph. |
| **DeepWiki** (Cognition), **CodeWiki / CodeWikiBench** | Generated, hierarchical repository documentation | The strongest "generated human-readable context" baseline. Prose, no provenance, no budget. |
| **LLMLingua / LongLLMLingua** | Prompt compression by dropping low-information tokens | A baseline: compress raw files to the same budget. |
| **MemGPT / Letta** | Hierarchical memory with explicit paging in and out | Conceptually close to stubs + expansion. |
| **Trace-link research** (LLM-assisted architecture-entity recognition for doc⇄code links; LLM linking of requirements to formal specs; TraceDev) | Recover links between layers | Extraction techniques for UCN stage 3, with known accuracy limits. |

---

## 2.6 Evidence on small-model context behavior

These findings constrain the design (G4, G7):

- **Effective context is much shorter than advertised.** RULER (Hsieh et al., 2024) shows most models fall well short of their advertised length on retrieval, multi-hop tracing and aggregation tasks, and smaller models fall short sooner. Multi-hop tracing over references is exactly what a normalized graph notation asks for. (v0.1 attributed this to LIFBench, which is about instruction-following stability. It also cited a "1.3B models struggle beyond 1.5k tokens" result about *pretrained base* models, which says little about today's instruction-tuned 4–8B models. Budgets must be measured per model, not taken from either.)
- **Length alone hurts.** Accuracy drops as input grows, even when the evidence sits right next to the question (EMNLP 2025 Findings). → *Smaller context is better in itself, not only cheaper.*
- **Position matters.** "Lost in the middle": information at the start and end of the context is used best. → *Core first, task slice last.*
- **Format matters, unpredictably.** He et al. (2024) find that plain text vs Markdown vs JSON vs YAML changes accuracy substantially, and differently per model. Exotic encodings (TOON in some tests) can cost accuracy even when they save tokens. → *No format choice can be assumed. The syntax ablation (§3.10) is essential, not optional.*
- **On cheap hardware, prefill time is often what users wait for.** Inference engines (llama.cpp, vLLM) can reuse the KV cache of an identical prompt prefix across turns. → *A stable core placed first is computed once.* This is a second, independent argument for core-first ordering.

---

## 2.7 Scored comparison (rubric)

**Rubric.** Each goal is scored 0 (not addressed), 1 (partly, or possible by convention), 2 (addressed by design). `?` = untested; counts as 0 until measured. Scores are author judgments; G4 and G7 will be replaced by measurements (§3.10).

| Candidate | G1 Unified | G2 Provenance | G3 Accurate / conflicts | G4 Compact / budgeted | G5 Named omissions | G6 Readable | G7 Small-LLM | G8 Drift | G9 Trust |
|---|---|---|---|---|---|---|---|---|---|
| SysML v2 (+ metadata) | 2 | 1 | 1 | 0 | 0 | 1 | ? | 0 | 0 |
| KDM | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| FAMIX / Moose | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 |
| RDF + PROV-O | 1 | 2 | 1 | 0 | 0 | 0 | ? | 1 | 0 |
| C4 DSL (Structurizr / LikeC4) | 0 | 0 | 0 | 1 | 0 | 2 | 2 | 0 | 0 |
| Spec-driven Markdown (Kiro, Spec Kit) | 1 | 0 | 0 | 1 | 0 | 2 | 2 | 0 | 0 |
| `AGENTS.md` | 0 | 0 | 0 | 1 | 0 | 2 | 2 | 0 | 0 |
| Code graphs / repo maps (Aider, RepoGraph, MCP) | 0 | 1 | 1 | 2 | 1 | 1 | 2 | 2 | 0 |
| RPG | 1 | 0 | 0 | 1 | 0 | 1 | ? | 0 | 0 |
| *UCN (design target, unproven)* | 2 | 2 | 2 | 2 | 2 | 2 | ? | 1 | 1 |

**Reading.** No candidate scores at least 1 on every goal. The candidates that unify the layers (SysML v2, KDM, FAMIX) score 0 on budgeting (G4), named omissions (G5) and small-LLM legibility (G7). The candidates that are compact and legible (code graphs, C4, Markdown specs, `AGENTS.md`) score 0 on unification (G1) or accuracy (G3). Nobody addresses untrusted sources (G9).

---

## 2.8 Answers

**Q1: Is there a single formal language for all three?**
**Semantically, almost. Practically, no.** No existing language *jointly* meets G1–G5 and G7 for knowledge extracted from existing systems.

- **SysML v2** is semantically almost sufficient. Every UCN node kind except `decision` maps to a native construct (§3.9), and provenance could be carried in user-defined `metadata`. What it lacks is extraction tooling for software, a provenance convention, budgets, levels of detail and omission, and evidence of small-LLM legibility.
- **KDM** is the standard built for extraction from existing code, but it is XMI-serialized, heavy, and weak on requirements and rationale.
- The rest are code-only (FAMIX, code graphs), structure-only (C4), schema-less (RDF), forward-only (Event-B, RPG, spec-driven Markdown), or informal (`AGENTS.md`).

v0.1 said SysML v2 "does not model code-level logic". That was overstated: SysML v2 can express function-level actions, calculations and constraints. The gap is tooling and form, not expressiveness.

**Q2: Can the best of each area be combined into one?**
**Yes, and the gap is mostly *not* about new semantics.** The parts already exist:

| Concern | Borrow from |
|---|---|
| Requirement sentences | EARS (+ FRETish timing) |
| Goals / why-hierarchy | KAOS-lite, SysML v2 `concern` |
| Acceptance examples | Gherkin-lite |
| Structure vocabulary | C4 (Structurizr/LikeC4) |
| Domain vocabulary, events | DDD ubiquitous language, Context Mapper |
| Interfaces | OpenAPI / AsyncAPI / Protobuf / signatures, by reference |
| Rationale | ADRs |
| Function and component logic | Design-by-Contract, AADL/AGREE assume/guarantee, Daikon-style invariants |
| Stateful behavior | Statecharts |
| Trace links | SysML v2 (`satisfy`, `verify`, `refine`) + ReqIF/Sphinx-needs ID discipline |
| Provenance vocabulary | W3C PROV-O |
| Architecture drift | Reflexion models |
| Relevance ranking | Personalized PageRank (HippoRAG, Aider) |
| Formal anchor (interop) | SysML v2 / KerML as the export target |

So the honest contribution is **a profile, a concrete syntax, a projection, and a toolchain** over existing semantics (mainly SysML v2 + C4), not a new language. What has to be added is:

1. **One small metamodel profile** that ties these pieces together with typed links, including the agent-facing concepts that formal languages leave out (conventions, glossary, conflicts).
2. **A provenance convention** (origin, verification, freshness, multiple sources) borrowed from PROV, plus dependency hashes for drift detection.
3. **Levels of detail and named omission stubs**, so compaction is explicit, reversible, and mechanically checkable.
4. **A budget-aware projection algorithm** with precise, testable guarantees.
5. **A syntax tuned for small LLMs**, as a hypothesis to test against SysML v2 text, JSON, YAML and Markdown.

The proposed design is in [03-proposal.md](03-proposal.md).

---

## Sources

Links checked by the reviewers on 2026-11-05 unless marked otherwise.

- SysML v2: [OMG press release, Jul 2025](https://www.omg.org/news/releases/pr2025/07-21-25.htm) · [OMG SysML spec](https://www.omg.org/spec/SysML) · [sysml-v2-release](https://github.com/systems-modeling/sysml-v2-release)
- KDM: [OMG KDM spec](https://www.omg.org/spec/KDM) · ISO/IEC/IEEE 42010: [iso.org/standard/74393](https://www.iso.org/standard/74393.html) (not checked)
- Provenance: [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- RPG: [arXiv 2509.16198](https://arxiv.org/abs/2509.16198) · Context Mapper: [contextmapper.org](https://contextmapper.org/)
- Structurizr AI/MCP: [docs.structurizr.com/ai](https://docs.structurizr.com/ai) · LikeC4 MCP: [mcp.so/servers/mcp-likec4](https://mcp.so/servers/mcp-likec4) (secondary)
- Spec-driven development (secondary sources): [Spec Kit vs Kiro](https://codemyspec.com/blog/spec-kit-vs-kiro) · [Kiro & SDD overview](https://www.morphllm.com/spec-driven-development)
- AGENTS.md governance (secondary sources): [Linux Foundation Agentic AI hub](https://itbrief.news/story/linux-foundation-launches-agentic-ai-open-standards-hub) · [AGENTS.md as open standard](https://codex.danielvaughan.com/2026/04/07/agents-md-open-standard-cross-tool-portability)
- Code context: [Repomix](https://repomix.com/guide/) · [RepoGraph (arXiv 2410.14684)](https://arxiv.org/abs/2410.14684) · [SWE-agent (arXiv 2405.15793)](https://arxiv.org/abs/2405.15793) · [HippoRAG (arXiv 2405.14831)](https://arxiv.org/abs/2405.14831) · [CodeWiki (arXiv 2510.24428)](https://arxiv.org/abs/2510.24428) · [LLMLingua (arXiv 2310.05736)](https://arxiv.org/abs/2310.05736) · [repo-graph](https://github.com/James-Chahwan/repo-graph) · [code-review-graph](https://github.com/tirth8205/code-review-graph) · [codebase-memory-mcp overview](https://dev.to/arshtechpro/stop-making-your-ai-coding-agent-grep-your-whole-repo-try-codebase-memory-mcp-4g8l) (secondary)
- Contract inference: [nl2postcond (arXiv 2310.01831)](https://arxiv.org/abs/2310.01831) · [SpecGen (arXiv 2401.08807)](https://arxiv.org/abs/2401.08807)
- TOON: [toon-format/toon](https://github.com/toon-format/toon) · [critical analysis of TOON benchmarks](https://dev.to/ikaganacar/toon-benchmarks-a-critical-analysis-of-different-results-5h66) (secondary)
- Traceability research: [Architecture Entity Recognition (arXiv 2511.02434)](https://arxiv.org/pdf/2511.02434) · [NL requirements ⇄ formal specs (Springer)](https://link.springer.com/chapter/10.1007/978-3-032-30693-7_1) · [TraceDev (arXiv 2607.18886)](https://arxiv.org/pdf/2607.18886)
- Long-context and format behavior: [RULER (arXiv 2404.06654)](https://arxiv.org/abs/2404.06654) · [Lost in the Middle (TACL 2024)](https://aclanthology.org/2024.tacl-1.9.pdf) · [Context Length Alone Hurts (EMNLP 2025 Findings)](https://aclanthology.org/2025.findings-emnlp.1264.pdf) · [Prompt formatting impact (arXiv 2411.10541)](https://arxiv.org/abs/2411.10541) · [LIFBench](https://arxiv.org/pdf/2411.07037) · [Effective context length falls short](https://arxiv.org/html/2410.18745v1)
- Benchmarks for §3.10: [SWE-QA (arXiv 2509.14635)](https://arxiv.org/abs/2509.14635)
- Background (well established, not re-verified here): EARS (Mavin et al., RE'09), NASA FRET, C4 model, MADR, JML/ACSL/Dafny, Quint, Daikon, k-tails/Synoptic, reflexion models (Murphy, Notkin & Sullivan, FSE'95), ArchUnit, jQAssistant, FAMIX/Moose, Bunch/ACDC/ARCADE, SCIP, Joern/CodeQL, KAOS, GSN, ReqIF, Sphinx-needs, Eclipse Capra, Agentless, CodexGraph, LocAgent, Serena, RAPTOR, GraphRAG, MemGPT, DeepWiki, RepoQA, SWE-bench.
