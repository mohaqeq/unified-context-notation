# 2. Investigation: State of the Art

This survey covers each layer separately and then looks at attempts to unify them. Each candidate is scored against the goals in [01-problem-statement.md](01-problem-statement.md).

**Scoring key:** ● strong · ◐ partial · ○ weak

- **Expr** = expressiveness for that layer
- **Dens** = token density
- **Fam** = familiarity to LLMs, i.e. how much of it appears in training data (a proxy for small-model legibility, G7)
- **Extr** = can it be extracted automatically from real sources?
- **Read** = human readability
- **Trace** = support for cross-layer links

---

## 2.1 Code logic layer

| Candidate | What it is | Expr | Dens | Fam | Extr | Read | Notes |
|---|---|---|---|---|---|---|---|
| **TLA+, Alloy, Z, VDM, B / Event-B** | Full formal specification languages | ● | ◐ | ○ | ○ | ○ | Precise and verifiable. Inferring them from existing code is still a research problem. Small models write and read them poorly. Event-B's *refinement* (abstract spec → concrete) is a valuable idea. |
| **Design-by-Contract** (JML, ACSL, Dafny, SPARK, Eiffel, Python `icontract`) | Pre/postconditions and invariants attached to functions and types | ◐ | ● | ◐ | ◐ | ● | The best ratio of meaning to tokens for function-level logic. Close to code, so LLMs can infer candidate contracts from code and tests, and property-based tests can check them. |
| **Signatures / stubs** (`.pyi`, `.d.ts`, C headers) | Types and APIs without bodies | ◐ | ● | ● | ● | ● | Fully automatic (tree-sitter, compilers). Very familiar to every LLM. Aider's repo map is built on this idea. Says *what* the API is, not what it guarantees. |
| **Code indexes** (SCIP/LSIF, Kythe, Glean, tree-sitter tags) | Symbol definitions, references, call graph | ○ | ● | ○ | ● | ○ | Accurate structure with no semantics. The right *backbone* for extraction, not a language for the agent to read. |
| **Code Property Graph / CodeQL** (Joern, CodeQL Datalog) | AST + control flow + data flow as a queryable graph | ● | ○ | ○ | ● | ○ | Very powerful for analysis (for example taint flows). Far too low-level for context. |
| **State machines** (statecharts, SCXML, XState) | Explicit state, events, transitions | ◐ | ● | ◐ | ◐ | ● | The most compact way to describe stateful behavior (protocols, workflows, UI). Usually *implicit* in code, so it must be recovered. |
| **Sequence / flow diagrams** (Mermaid, PlantUML, BPMN) | Interaction order | ◐ | ◐ | ● | ◐ | ● | Mermaid is very familiar to LLMs. Good for key flows only. |

**Best of breed for code logic:** *signatures* (automatic) + *contracts* (pre/post/invariants) + *state machines* for stateful parts. Use code indexes as the extraction backbone. Link to TLA+/Alloy only for critical kernels.

---

## 2.2 Architecture layer

| Candidate | What it is | Expr | Dens | Fam | Extr | Read | Notes |
|---|---|---|---|---|---|---|---|
| **C4 model** + **Structurizr DSL / LikeC4** | Context → Container → Component (→ Code), as text | ◐ | ● | ● | ◐ | ● | Small, popular vocabulary. Both have MCP servers for agents (Structurizr: validation and inspection; LikeC4: querying the model). C4 does not cover behavior or requirements. LikeC4 is flexible but does not enforce C4 semantics. |
| **SysML v2 / KerML** (OMG, adopted 2025) | Formal systems modeling language with a *textual notation* | ● | ◐ | ○ | ○ | ◐ | The most complete *semantic* coverage: parts, ports, interfaces, actions, states, constraints, **requirements**, verification. Its vocabulary comes from systems engineering. It is verbose for software and rarely appears in LLM training data. |
| **AADL** (+ AGREE contracts) | Architecture language for embedded and real-time systems | ● | ◐ | ○ | ○ | ◐ | Precise, with assume/guarantee contracts at component level, which is a valuable idea. Niche. |
| **ArchiMate** | Enterprise architecture | ◐ | ○ | ◐ | ○ | ◐ | Business/application/technology layers. Its XML exchange format is verbose. |
| **UML / PlantUML / Mermaid** | General diagrams | ◐ | ◐ | ● | ◐ | ● | Familiar, but semantics are weak and the format is diagram-centric. |
| **ADRs** (MADR, Nygard) + **arc42** | Decision records and an architecture documentation template | ◐ | ◐ | ● | ◐ | ● | The only widely used place that records **rationale (why)**, which agents badly need so they don't "fix" deliberate choices. Unstructured prose. |
| **Interface definition languages** (OpenAPI, AsyncAPI, Protobuf, GraphQL SDL, JSON Schema) | Exact interface contracts | ● | ◐ | ● | ● | ● | Precise, extractable, very familiar. Usually too long to inline, so *summarize and reference* them. |
| **IaC / service catalogs** (Terraform, Kubernetes manifests, Backstage `catalog-info.yaml`) | Deployment and ownership | ◐ | ○ | ● | ● | ◐ | A ground-truth source for the deployment view. |

**Best of breed for architecture:** the *C4 vocabulary* (as in Structurizr/LikeC4) for structure, *IDLs by reference* for interfaces, *ADRs* for rationale, and *AADL/AGREE-style assume/guarantee* for component contracts.

---

## 2.3 Requirements layer

| Candidate | What it is | Expr | Dens | Fam | Extr | Read | Notes |
|---|---|---|---|---|---|---|---|
| **EARS** (Easy Approach to Requirements Syntax) | Five sentence templates: ubiquitous, event-driven (`WHEN`), state-driven (`WHILE`), unwanted behavior (`IF…THEN`), optional feature (`WHERE`) | ◐ | ● | ● | ● | ● | Semi-formal, compact, readable. LLMs can normalize free text into it. Used by AWS Kiro for spec-driven development. Not executable. |
| **Gherkin / BDD** (Given/When/Then) | Executable acceptance scenarios | ◐ | ◐ | ● | ◐ | ● | Very familiar. Links requirements to tests. Wordy when used for many cases. |
| **User stories + acceptance criteria** | "As a… I want… so that…" | ○ | ◐ | ● | ● | ● | Captures *who* and *why*. Ambiguous. |
| **NASA FRET (FRETish)** / Dwyer property patterns | Structured English → temporal logic | ● | ● | ○ | ◐ | ● | Adds precise timing ("within 50ms", "always", "until") to EARS-like text. Can be checked formally. |
| **Goal models** (KAOS, i\*) / **GSN** assurance cases | Goals → sub-goals → requirements; obstacles; arguments | ● | ◐ | ○ | ○ | ◐ | Captures the *why* hierarchy, which is valuable for ranking importance. Heavy in its full form. |
| **SysML v2 requirements** | `requirement def` with subject, assumptions, constraints | ● | ◐ | ○ | ○ | ◐ | Formal and linked to architecture through `satisfy` and `verify`. |
| **Traceability formats** (ReqIF, OSLC, Sphinx-needs, StrictDoc, Doorstop) | IDs, attributes, typed links | ○ | ◐ | ◐ | ◐ | ◐ | Not languages for *content*. They provide the **ID + typed link** discipline we need. |

**Best of breed for requirements:** *EARS* sentences, optional *FRETish* timing qualifiers, *Gherkin-lite* acceptance examples, a lightweight *goal → requirement* hierarchy, and *Sphinx-needs/ReqIF-style* IDs and typed links.

---

## 2.4 Attempts at unification

| Candidate | Covers | What it lacks for LLM context |
|---|---|---|
| **SysML v2 / KerML** | Requirements ● Architecture ● Behavior ◐ — formal semantics, textual syntax, `satisfy` / `verify` links | No code-level logic or extraction from code. Verbose. Low LLM familiarity. No notion of budget or level of detail. No provenance/confidence per fact. |
| **Event-B + Rodin** | Requirements → abstract machine → refinement toward implementation | Heavyweight. Forward-engineering only. Not extractable from existing code. |
| **Capella / Arcadia (MBSE)** | Operational → system → logical → physical layers | Graphical and tool-locked. Systems-engineering focus. |
| **AADL + AGREE** | Architecture + compositional contracts | Embedded niche. No requirements text layer. |
| **RDF/OWL knowledge graphs, OSLC** | Anything (generic linked data) | No fixed vocabulary, so each team invents its own. Serialization (RDF/XML, JSON-LD) is token-heavy. Turtle is better but still verbose. |
| **Spec-driven development** (Kiro: `requirements.md` / `design.md` / `tasks.md`; GitHub Spec Kit: specify → plan → tasks) | Requirements (EARS in Kiro) + design + tasks, as Markdown | Informal. Forward-only (spec → code), not extraction from existing systems. No trace graph. No budgeted projection. |
| **Agent context files** (`AGENTS.md`, now stewarded by the Linux Foundation's Agentic AI Foundation; `CLAUDE.md`; `llms.txt`) | Whatever the author writes | Unstructured prose. No schema, provenance, or drift detection. Not budgeted. |
| **Code-graph context tools** (Aider repo map with tree-sitter + PageRank; MCP servers such as codebase-memory-mcp, repo-graph, code-review-graph) | Code structure, ranked by centrality. Some expose *character budgets* for small models. | Only the code layer. No requirements, rationale, or contracts. Savings figures are mostly self-reported. A stale graph can mislead more than no graph. |
| **Research on LLM traceability** (e.g. LLM-assisted architecture-entity recognition for documentation⇄code links; LLM linking of NL requirements to formal specs; requirement-to-code trace frameworks) | Recovering *links* between layers | Produces links, not a unified context language. Useful as extraction techniques. |
| **LLM-oriented serializations** (TOON, compact YAML, Markdown tables) | Token-efficient encoding of data | Only syntax. TOON saves ~30–60% on *uniform arrays*. Independent benchmarks disagree on accuracy, and some find TOON *less* accurate than JSON. Lesson: token density alone does not improve comprehension. |

---

## 2.5 Evidence on small-model context behavior

These findings constrain the design (G4, G7):

- **Effective context is much shorter than advertised.** Most models degrade past roughly 16k–32k tokens (LIFBench). Small models degrade earlier. Pretrained 1.3B models struggle to use information more than about 1.5k tokens away (*Why Does the Effective Context Length of LLMs Fall Short?*).
- **Length alone hurts.** Accuracy drops as input grows, even when the evidence sits right next to the question (EMNLP 2025 Findings). → *Smaller context is better in itself, not only cheaper.*
- **Position matters.** "Lost in the middle": information at the start and end of the context is used best. → *Put the core first and the task slice last.*
- **Format following is robust; unfamiliar notation is not.** Models keep format abilities across lengths. But exotic encodings (TOON in some tests, formal languages in general) can cost accuracy even when they save tokens. → *Use familiar words and Markdown/YAML-like structure. Avoid dense sigils.*

---

## 2.6 Gap analysis

| Goal | Best existing match | Gap |
|---|---|---|
| G1 Unified | SysML v2 | No code-logic layer. Too heavy. |
| G2 Source-agnostic + provenance | OSLC / ReqIF (links) | No per-fact provenance or confidence anywhere. |
| G3 Accurate / conflicts surfaced | Formal methods (for verified parts) | No mainstream format represents *conflict between sources* or *inferred vs. stated*. |
| G4 Compact | Aider repo map, TOON | Code-only or syntax-only. |
| G5 Explicit omissions | Code-graph MCP tools (partial: query on demand) | No language with first-class **omission stubs** and **levels of detail**. |
| G6 Human-readable | EARS, C4 DSLs, Markdown specs | Each covers only one layer. |
| G7 Small-LLM-legible | Signatures, Markdown, Mermaid, EARS | Formal unified languages fail here. |
| G8 Maintainable / drift | Code indexes (rebuild on change) | Intent layers (requirements, ADRs) have no drift detection against code. |

## 2.7 Answers

**Q1: Is there a single formal language for all three?**
**No, not one that fits this purpose.** SysML v2 comes closest in *semantic coverage*: it unifies requirements, architecture, and behavior, with formal `satisfy`/`verify` links. But it does not model code-level logic, is not designed to be extracted from existing code, is verbose, is unfamiliar to LLMs, and has no concept of token budgets, levels of detail, provenance, or explicit omission. The other unifying attempts are either heavyweight formal methods (Event-B), domain-specific (AADL), schema-less (RDF), or informal (spec-driven Markdown, `AGENTS.md`).

**Q2: Can the best of each area be combined into one?**
**Yes, and the gap is mostly *not* about new semantics.** The parts already exist:

| Concern | Borrow from |
|---|---|
| Requirement sentences | EARS (+ FRETish timing) |
| Goals / why-hierarchy | KAOS-lite |
| Acceptance examples | Gherkin-lite |
| Structure vocabulary | C4 (Structurizr/LikeC4) |
| Interfaces | OpenAPI / Protobuf / signatures, by reference |
| Rationale | ADRs |
| Function and component logic | Design-by-Contract, AADL/AGREE assume/guarantee |
| Stateful behavior | Statecharts |
| Trace links | SysML v2 relationship names (`satisfy`, `verify`, `refine`) + Sphinx-needs/ReqIF ID discipline |
| Formal anchor (interop) | SysML v2 / KerML as the export target, giving formal semantics |

What is genuinely **missing**, and what a new language must add, is:

1. **One small metamodel** that ties these pieces together with typed links.
2. **Per-fact provenance and status** (`stated | derived | inferred | conflict`) plus source hashes for drift detection.
3. **Levels of detail and first-class omission stubs**, so compaction is explicit and reversible.
4. **A budget-aware projection algorithm** that guarantees pinned facts and ranks the rest.
5. **A syntax tuned for small LLMs**: familiar keywords, line-oriented, shallow, with no new symbols to learn.

The proposed design is in [03-proposal.md](03-proposal.md).

---

## Sources

- SysML v2 adoption: [OMG press release, Jul 2025](https://www.omg.org/news/releases/pr2025/07-21-25.htm) · [OMG SysML spec](https://www.omg.org/spec/SysML) · [sysml-v2-release](https://github.com/systems-modeling/sysml-v2-release)
- Structurizr AI/MCP: [docs.structurizr.com/ai](https://docs.structurizr.com/ai) · LikeC4 MCP: [mcp.so/servers/mcp-likec4](https://mcp.so/servers/mcp-likec4)
- Spec-driven development: [Spec Kit vs Kiro](https://codemyspec.com/blog/spec-kit-vs-kiro) · [Kiro & SDD overview](https://www.morphllm.com/spec-driven-development)
- AGENTS.md governance: [Linux Foundation Agentic AI hub](https://itbrief.news/story/linux-foundation-launches-agentic-ai-open-standards-hub) · [AGENTS.md as open standard](https://codex.danielvaughan.com/2026/04/07/agents-md-open-standard-cross-tool-portability)
- Code-graph tools: [repo-graph](https://github.com/James-Chahwan/repo-graph) · [code-review-graph](https://github.com/tirth8205/code-review-graph) · [codebase-memory-mcp overview](https://dev.to/arshtechpro/stop-making-your-ai-coding-agent-grep-your-whole-repo-try-codebase-memory-mcp-4g8l) · [Codebase maps, not bigger prompts](https://www.developersdigest.tech/blog/codebase-knowledge-graphs-ai-coding-agents)
- TOON: [telekom/toon](https://github.com/telekom/toon) · [critical analysis of TOON benchmarks](https://dev.to/ikaganacar/toon-benchmarks-a-critical-analysis-of-different-results-5h66)
- Traceability research: [Architecture Entity Recognition (arXiv 2511.02434)](https://arxiv.org/pdf/2511.02434) · [NL requirements ⇄ formal specs (Springer)](https://link.springer.com/chapter/10.1007/978-3-032-30693-7_1) · [TraceDev (arXiv 2607.18886)](https://arxiv.org/pdf/2607.18886)
- Long-context behavior: [Lost in the Middle (TACL 2024)](https://aclanthology.org/2024.tacl-1.9.pdf) · [Context Length Alone Hurts (EMNLP 2025 Findings)](https://aclanthology.org/2025.findings-emnlp.1264.pdf) · [LIFBench](https://arxiv.org/pdf/2411.07037) · [Effective context length falls short](https://arxiv.org/html/2410.18745v1)
- Background (well established, not re-verified here): EARS (Mavin et al., RE'09), NASA FRET, C4 model (c4model.com), MADR, JML/ACSL/Dafny, SCIP, Joern/CodeQL, KAOS, GSN, ReqIF, Sphinx-needs.
