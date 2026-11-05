Reviewer: Sonnet 5.5 (claude-sonnet-5-5)
Date: 2026-11-05

# Review of Unified Context Notation (UCN) v0.1

## Verdict

The question is well framed, and the reframing from "everything in 4k tokens" to "core card + task slice + visible stubs" is the right one. The writing is clear. The proposal is a plausible design sketch, but it is not yet a research result. The investigation says "no single language fits" without a rubric, and it misses the one standard that is explicitly about extracting a unified model from existing software (OMG KDM). It also makes a false claim that "no per-fact provenance exists anywhere" (W3C PROV-O). The metamodel and syntax are reasonable but have grammar holes, and several promised properties (merge keeps all `src`, conflicts as first-class, deterministic guaranteed projection) are not supported by the spec or the parser. The hand-written examples contain factual inconsistencies, including wrong stub counts and a contract that contradicts its own source. The central feasibility risks are not discussed: unbounded pinned sets, LLM-inferred contracts at scale, and CPU prefill latency. The evaluation plan lacks the strongest baseline, which is an agent with grep/read tools, and cannot show that "no important context lost" holds. Fix the issues below before v0.2 tooling is built on this spec.

**Overall score: 6/10.** The framing and direction are good. Rigor, completeness of prior art, and spec/example/parser consistency are not there yet.

## Strengths

- The "inherent tension" reframing (01 §1.4) is honest and operational. Omission becomes visible and recoverable (G5, stubs).
- The explicit separation of stated, derived, inferred and conflict status (01 §1.4, 03 §3.1) is the most valuable original idea. It directly targets hallucinated summaries.
- Core-first and slice-last ordering is justified by cited evidence (02 §2.5, 03 §3.8). Choosing English keywords over sigils is consistent with that evidence.
- The syntax-variant ablation (03 §3.10) tests G7 instead of asserting it. The honest TOON caveat (02 §2.4) is good.
- The example is small but exercises trace, conflict, pin and stub. The linter finds real gaps (Resolve/Expire/Alias unverified).
- The repo is honest about limits (examples/shortly/README.md caveats: "model is tiny", "hand-simulated").

## Critical issues (must fix)

### C1. The Q1 "no" answer is not backed by a rubric, and the closest standard is missing (KDM)
- **Location:** 02 §2.4, §2.7, README "Short answer".
- **Problem:**
  - Candidates are scored with symbols (●◐○) in §2.1–2.3, but no rubric defines them, nothing is aggregated, and nothing feeds the conclusion. "Fam" is a proxy for LLM training-data presence that was never measured.
  - The survey omits the **OMG Knowledge Discovery Metamodel (KDM, ISO/IEC 19506)** and Architecture-Driven Modernization. KDM is a standardized metamodel for representing existing software (code, actions, data, structure/architecture, conceptual and business rules) and is explicitly designed for extraction from legacy code. It is the closest prior art to "one model of code logic + architecture extracted from source". It must be assessed. The likely finding is that it is semantically adequate but XMI-serialized, requirements-weak and LLM-hostile, so the gap UCN claims may hold, but that must be argued.
  - ISO/IEC/IEEE 42010 (architecture description: viewpoints, correspondences) and FAMIX/Moose (a unified code+architecture metamodel with 20 years of tooling) are also missing.
- **Fix:** Add a short "unifiers" subsection with KDM, FAMIX/Moose and 42010. Define the scoring rubric, for example an explicit 0/1/2 per goal G1–G8 with a one-line justification each, and publish the matrix. State clearly that "no" means "no existing language satisfies G1+G2+G4+G5+G7 jointly". It does not mean "no language covers all three layers".

### C2. SysML v2 is assessed unfairly or imprecisely
- **Location:** 02 §2.4 SysML row, §2.7 Q1.
- **Problem:**
  - "No code-level logic" is overstated. KerML/SysML v2 have an expression language, `action def`/`calc def`, `state def`, `constraint def`, `assert constraint`, `perform`, `doc`/comments and user-defined `metadata`. Function-level pre/post/err contracts are expressible (the proposal's own §3.9 maps `fn`, `rule` and `machine` onto them). The real gap is extraction tooling and idiomatic style, not expressiveness.
  - "Rarely appears in LLM training data" and "verbose" are asserted without measurement. There is 2025 work on LLM generation of SysML v2 that should be consulted.
  - Per-fact provenance and status could be carried by SysML v2 `metadata def`. UCN could arguably be a SysML v2 *profile with a compact concrete syntax* rather than a parallel metamodel.
  - The proposal later concedes this (§3.9 "lightweight LLM-friendly profile"). So 02 and 03 are in tension: if UCN maps 1:1 onto SysML v2, the Q1 answer is "yes but impractical", not "no".
- **Fix:** Reword Q1 as above. Measure verbosity directly. Encode the Shortly `Links.create` contract in SysML v2 textual notation and compare token counts with UCN. Drop "doesn't model code-level logic" or qualify it.

### C3. "No per-fact provenance/confidence anywhere" is false
- **Location:** 02 §2.6 G2/G3 rows, §2.7 missing item 2.
- **Problem:** W3C PROV-O/PROV-DM models exactly entity/activity/agent provenance. RDF-star and named graphs attach metadata to individual statements. Truth-maintenance systems, argumentation frameworks and KG-fusion work model conflicting sources. The claim "no mainstream format represents conflict between sources" is therefore wrong in spirit. The accurate claim is that no *software-engineering-context* format with a compact LLM-legible syntax does.
- **Fix:** Cite PROV-O and borrow its vocabulary (`wasDerivedFrom`, `wasGeneratedBy` with the extraction method). Narrow the claim.

### C4. The "pinned always present" guarantee is unbounded and will break first
- **Location:** 03 §3.2 tags (`security`, `safety`, `legal` imply `[pin]`), §3.5 step 1, 01 §1.7 "pinned-fact recall 100%".
- **Problem:**
  - Pins are author-assigned and implied by category. In a real system, security/legal requirements and invariants number in the hundreds. Pinned L1 content plus the system card will exceed a 2k–4k budget, and the algorithm then *raises* `BudgetTooSmall`. For the very users targeted (small budgets) that means the tool fails on any non-toy system.
  - LLM-inferred `[pin]` (via extraction) can inflate the set without bound.
  - The 100% pinned-recall metric is satisfied by construction, so it measures nothing.
- **Fix:**
  - Make pinning tiered (`pin` is ordered by criticality) and define a degradation order: pinned facts degrade to L0 one-liners before failing, and then to a stub that names the count.
  - Cap pins per kind and lint on overflow.
  - Replace the 100% recall metric with "does the agent respect pinned constraints in tasks that tempt violation" (adversarial tasks).

### C5. Stated guarantees are not guaranteed by the algorithm
- **Location:** 03 §3.5 "Guarantees".
- **Problem:**
  - "Every relevant omission is visible as a stub" is false when `relevant()` is thresholded on the same noisy PageRank score. Anything below the threshold is silently dropped. Because the stub is a `group_by_parent` count, long-tail loss is hidden behind a count.
  - Step 4 greedy ratio ordering is not a knapsack optimum. Items are not independent: choosing a node at L2 changes the cost of its L1 version, and `ancestors_included_or_stubbed` creates dependencies.
  - Step 4 can place a `fn` at L2 while the `calls` target is only stubbed. The shipped slice does exactly this (`Guard.check`, `Guard.limit` are referenced but Guard is neither shown nor stubbed).
  - "Deterministic" holds only if embeddings and PageRank are seeded and floating point is stable. Seeds from `match(task, M)` via embeddings depend on the embedding model version.
  - Task type classification (`task_type(task)`) is unspecified and is presumably an LLM call, which defeats determinism and the "small machine" goal.
  - Personalized PageRank edge weights are asserted ("`satisfies/verifies/calls` above `uses`") with no justification or tuning plan.
- **Fix:**
  - Reword guarantees precisely: "pinned present; every *selected-then-dropped* node is stubbed; unselected nodes are only covered by parent counts."
  - Add a **closure rule**: any edge target referenced by an included node must be included at L0 or appear in an explicit stub.
  - Specify the embedding model and seeding.
  - Make `task_type` a user-supplied enum with a default.
  - Add a retrieval-quality metric for step 3 (recall@k of ground-truth relevant nodes) evaluated independently from the LLM.

### C6. Silent identity and merge semantics contradict the stated source-agnostic merge
- **Location:** 03 §3.6 final paragraph ("they merge, and the fact keeps every `src`"), tools/ucn_parse.py `parse()`.
- **Problem:**
  - The parser stores attributes in a dict (`nodes[owner]["attrs"][word] = val`), so a second `src:` line overwrites the first. Multi-source facts cannot be represented in text, contrary to the spec.
  - `nodes.setdefault(fid, ...)` merges duplicate IDs silently with no check that `kind` agrees. Two different facts with the same id (e.g. a `req Create` and a `fn create` are distinct only by case) collapse or overwrite `text`.
  - Id qualification is inconsistent: `fn`/`rule`/`machine`/`flow` get an owner prefix, but `data`, `api`, `test`, `req` do not. `Link` (data) and `Link.hits` in prose, `LinksApi` and `Links` (component) look alike. Ids are not guaranteed unique across kinds.
  - Entity resolution ("the billing service in a doc = container `Billing`") is the hardest part of G2 and the spec gives it one sentence.
- **Fix:** Make attrs multi-valued (`src` as a list, with method and confidence per src). Specify identity: a global unique id namespace, explicit `aka:` aliases, and error on kind mismatch. Qualify every non-top-level id uniformly. Detail the entity-resolution algorithm and its failure modes in 03 §3.6.

### C7. The example data contain factual errors and internal contradictions
- **Location:** examples/shortly/*.
- **Problem:**
  - `card.L0.ucn` last line says `more: 7 req, ... 3 component, 2 decision, 3 test`. The model has 7 reqs and the card shows 2, so the stub should say 5. Hand-made counts are wrong even in the 11-line artifact meant to demonstrate "no silent loss".
  - `slice.alias.ucn` says `6 req, 2 component, 1 decision, 2 test not relevant`. The slice includes 3 of 7 reqs (omitted: Create, Resolve, Fast, Expire = 4), and shows 2 of 3 components (omitted: Guard = 1).
  - In model.ucn, `fn limit` declares `err: count(owner, last 1h) > 100 -> 429` with `src: api/guard.ts:42`, while the conflict line says the same file (line 44) *uses 1000/hour*. A fact marked as derived from code is thereby stated as 100 while the code does 1000. The contract is either wrong or the conflict is wrong.
  - `req Alias` is `status: proposed`, yet `Links` `satisfies Alias`, `fn create` already has the `alias?` parameter and `err: alias taken -> 409`, and no test exists. The model cannot tell implemented-from-code from planned. This reveals a **missing concept: as-is vs to-be (baseline/target/delta)**, essential for task context (see M3).
  - `req Blocklist [security]` is an IF/THEN (unwanted-behavior) sentence but lacks the `unwanted` tag that `RateLimit` has. EARS tagging is inconsistent.
  - The slice is not a valid model: it drops all `refines`/`satisfies` edges (kept as a comment `# satisfied by: Links`), so the projection format is lossy relative to the model, contradicting "canonical JSON maps one-to-one to the text" (03 §3.7). The linter run on it reports false positives (dangling targets, "nothing satisfies it"), so `--lint` is only meaningful on full models, as the parser comment concedes.
  - Slice token total is 624 of a 1200 budget. A greedy knapsack would fill the budget, so this was not produced by the algorithm. Claims that it is "hand-simulated `π`" make the example weak evidence.
  - README token numbers do not reproduce: I get ucn=1248, json-pretty=3038, json-compact=1927 (README: 1,289 / 3,513 / 2,056; ratios of 2.4x/1.5x rather than 2.7x/1.6x). The tokenizer version may differ, but the stated ratios should be reproducible.
- **Fix:** Correct the counts, resolve the 100-vs-1000 contradiction, add a `phase`/`status` dimension (as-is, planned, deprecated) and have projections preserve edges. Generate the slice with an actual implementation of `π` before claiming it as an example. Pin the tiktoken version in the README.

## Major issues (should fix)

### M1. Grammar has holes and is not LL-parseable as written
- **Location:** 03 §3.3 EBNF, tools/ucn_parse.py.
- **Problem:**
  - Undefined terminals: `Word`, `version`, `quoted`, `int`, `text`, `expr`, `State`, `relkw`, `attrkw`.
  - `node = kind Id [tags] [":" text]` does not describe `fn`, whose "signature in host language notation" is parsed ad hoc (`line[3:]`, id = text before "(").
  - `fn` ids are not even syntactically distinguished from their params, and overloads collide.
  - "Line role is decided by its first word" fails for transitions (`active -> expired: ...`): the first word is a user state name. A state named `data`, `test`, `uses` or `rule` (very plausible: `state rule`) is misparsed as a node or relation. The parser checks KINDS before the transition regex, so such a machine breaks.
  - `|` is the `conflict:` separator, but `|` appears in regexes and boolean expressions (e.g. `post: matches /a|b/`) and in text that follows `conflict:`. Quoting/escaping is unspecified.
  - `conflict` and `more` carry free text. The two sides of a conflict are not structured (no ids, no per-side `src` as grammar-promised), and a conflict has no lifecycle (open/resolved) nor can it be referenced. As a "meta-line" it cannot be targeted by a decision or a task.
  - No escaping rule for `:` in summary text. `api LinksApi: REST: POST ...` works only because the regex is greedy on the first colon.
  - Header: `budget:` and `task:` parse in the spec, but the parser keeps the header as an unparsed string. Version is not checked.
  - The 4-level depth cap is inconsistent with the shipped model: `system > container > component > fn > clause` is exactly depth 5 lines nested 4 deep (clauses at indent 8 = depth 4). Any `machine` transition under `component` in a `container` in a `system` hits the cap. Adding a `package` level or an `actor` grouping would exceed it.
- **Fix:** Give a complete EBNF with lexical rules. Use an unambiguous marker for transitions (`transition A -> B: on ...` or `on A -> B ...`). Make `conflict` a node kind with ids, two `claim` children each with `src`, and a state. Parse the header properly. Add a conformance test suite.

### M2. Contract expression language is undefined
- **Location:** 03 §3.1 principle 3, §3.2 contract clauses, model.ucn.
- **Problem:** "Expressions use ordinary programming notation" but the examples use unbound pseudo-functions: `unique(result)`, `exists(Link where code == result)`, `count(owner, last 1h)`, `alias taken`, `rateLimited(owner)`, and mix `or`/`==`. These are neither checkable (the roadmap's "property-based tests check contracts", 03 §3.11, is not feasible) nor unambiguous. `err:` mixes a predicate and prose.
- **Fix:** Pick one of: (a) explicitly informal natural-language clauses and drop the "checkable" claims, (b) a tiny defined expression subset (a Python/TS-like predicate subset with named total functions), or (c) delegate to a host-language contract syntax (JML/Dafny/icontract) via a reference. Be honest that LLM-inferred contracts are mostly (a).

### M3. Metamodel gaps and redundancies
- **Location:** 03 §3.2.
- **Problem:**
  - **Missing:**
    - as-is/to-be/change (a `change` or `task` node, `phase` attribute);
    - non-functional constraints as first-class (performance budgets, SLOs live only in req text);
    - **runtime/ops facts** (config, feature flags, env vars, deployment topology, traces; 01 §1.1 lists "runtime traces" as a source, but the pipeline has no adapter);
    - **risk/hotspot/ownership/churn** (strong predictors of what an agent must be careful with);
    - **glossary / domain terms** (the "billing service" resolution problem; DDD ubiquitous language);
    - **conventions and constraints on how to work** (coding conventions, forbidden patterns, build/test commands). This is the bulk of real `AGENTS.md` content and would be the first thing users ask for.
    - `event`/message as a node (`emits LinkCreated` appears only in `effect:` text);
    - dependencies on third-party libs.
  - **Redundant or underspecified:**
    - `rule` vs `inv:` vs `data` invariants vs `guarantee:` overlap, with no guidance on which to use.
    - `uses` vs `calls` vs `reads`/`writes` vs `effect: writes X` duplicate data (the example writes `effect: writes Link` as text but `reads Cache, Link` as an edge, so write edges are lost from the graph).
    - `status:` attribute and the `[inferred]`/`[conflict]` tag are two mechanisms for epistemic status. `[nfr]`/`[security]` tags are categories mixed in with EARS pattern tags and status. These are three orthogonal axes in one bracket.
    - `api` as a node versus `exposes` and the IDL by reference.
  - **Only 2 of 3 layers have the distinguishing relation:** `implements` (code symbol to component) is absent. `src:` is the only link to code, and a component is not tied to a file set / package path, which is what drift detection needs.
  - **Confidence:** the status enum is categorical only. Inferred facts need at least method, model, and score or review state.
- **Fix:** Add `phase`, `glossary` (term) and `convention` kinds, `emits`/`event`, `implements` with path globs. Separate three axes (status, category, EARS pattern) syntactically. Collapse `inv`/`rule`/`guarantee` guidance into one table. Represent `writes`.

### M4. Extraction pipeline feasibility is overstated
- **Location:** 03 §3.6, §3.11.
- **Problem:**
  - Stage 2 (LLM-inferred pre/post/inv, state machines, component clustering) carries the whole value of the "logic" layer and is exactly where research shows low precision. Specification-mining work (Daikon; nl2postcond, SpecGen, AutoSpec, ClassInvGen) shows that LLM-inferred specs are often weak, tautological or wrong, even for functions in isolation. The ≥95% faithfulness target (01 §1.7) is stated for "stated/derived" facts only, which are the easy ones, while all the hard facts are `[inferred]`.
  - "Promote inferred to derived via a test" is unspecified: a passing test does not confirm a postcondition unless it asserts it.
  - Architecture recovery from code without a model (component clustering) has a long literature (Bunch, ACDC, ARC, Structure101) with mediocre agreement with human architecture; none is cited.
  - Trace-link recovery (req to code) has well-known precision/recall limits (Cleland-Huang et al., TraceLab); the spec treats it as a pipeline stage.
  - Cost: running an LLM over every function of a large repo to produce summaries is not "cheap machines" friendly. For a repo with 50k functions it is a significant cost, and the "small local model" doing the normalization is the weakest extractor.
  - Drift: source hashes mark whole-file staleness, but summaries of components depend on many files. Transitive invalidation (Merkle-style dependency hashes) is not specified.
  - Conflict detection ("doc says X, code does Y") is an open research problem (semantic comparison of NL requirement vs code) presented as a deterministic validation step (stage 4 is labeled "Deterministic").
- **Fix:** Re-label stage 4's conflict detection as LLM-assisted. Add precision/recall targets for each stage. Add dependency-hash invalidation. Pilot Stage 2 on 1 repo before designing around it. Cite spec mining and architecture recovery literature.

### M5. Feasibility for low-end LLMs: budgets and claims
- **Location:** 03 §3.8 rule 6, 01 §1.7, 02 §2.5.
- **Problem:**
  - Latency, not only window size, limits cheap machines. CPU prefill for a 7–8B quantized model is often tens of tokens/s, so 8k tokens costs minutes per turn, and an expand loop multiplies that. Prefix (KV) caching of the stable core card is the obvious mitigation and a natural reason for "core first", but it is not mentioned. The "slice last" ordering is in fact compatible with prefix caching, which is a strong, unused argument.
  - The "effective context shorter than advertised" evidence (§2.5) is mostly about long-context retrieval. Using it to set 4k/8k targets is plausible but the targets themselves are unsupported guesses. A 1–4B model with 4k of dense notation plus the code to edit plus the task and tool outputs will have little room left; the budget must be split (context vs working space). The doc never subtracts the tokens needed for the actual code the agent must read or edit.
  - A small model that cannot do reliable tool calling will not use `expand` (acknowledged in §3.11), so condition (d) is what matters, and static 2–4k projections of a large system carry ~one component's worth of detail. The statement "without losing any important parts" is then only true for small systems.
  - The 10x compression target at L1 (01 §1.7) is vaguely defined (raw *relevant* source tokens; relevance depends on π). Real signature maps (Aider) already give 10–50x, so the target is neither novel nor tied to the value-added content (contracts, rationale).
  - "English keywords cost one token each, the same as a symbol" (03 §3.1.3) is not generally true across tokenizers (identifiers such as `Links.create`, `RateLimit`, CamelCase, and digits tokenize into several tokens), and the claim is untested (the example only measures o200k).
- **Fix:** Add a latency/prefill model (tokens/s on a reference CPU). Exploit prefix caching explicitly. Budget as `B_total = B_context + B_work`. Measure tokenization with at least Llama-3, Qwen and Gemma tokenizers. Re-define the compression metric.

### M6. Evaluation plan cannot show "no important context lost"
- **Location:** 03 §3.10, 01 §1.7.
- **Problem:**
  - **Missing strongest baseline:** an agent with grep/read/ls tools on the raw repo (the actual state of practice, e.g. SWE-agent/Agentless-style ACI), at an equal *total token spend*, not just equal context size. Conditions (a)–(c) are weak baselines and understate what a retrieval agent gets.
  - Questions are hand-written by the authors who also design the notation (bias). Answers about "locate/explain/impact" are checkable only if the ground truth is defined by construction. No mechanism to measure *loss*: accuracy on questions you thought of is not "no important thing missing". Use **downstream task success** (resolving real issues, e.g. SWE-bench-style or RepoQA/SWE-QA-style tasks) plus **counterfactual ablation**: remove a fact and measure task regression, to derive an empirical importance ranking, then check that the projection retains high-importance facts.
  - No metric for **stale or wrong UCN misleading the agent** (the risk named in 02 §2.4 for code-graph tools). Include seeded-error experiments (inject wrong inferred contracts, wrong conflicts) and measure harm. This is the biggest risk of an inferred layer.
  - Extraction faithfulness (01 §1.7, ≥95%) needs a gold standard and an annotation protocol; none is defined.
  - Pinned recall of 100% is tautological (C4).
  - 3–5 repos x 50–100 questions with a human-written upper bound is small and cost is not estimated. Contamination: popular OSS repos are in model training data; use recent or private repos.
  - Human readability (≥4 of 5) has no protocol or N.
  - Confounds: is gain from content (contracts, rationale) or from syntax? Add a "same content as prose" condition, not just JSON/YAML/Markdown syntax variants.
- **Fix:** Add agentic baseline, issue-resolution tasks, seeded-error harm test, a gold-standard extraction set, leave-one-fact-out importance estimation, and contamination controls.

### M7. Problem formulation weaknesses
- **Location:** 01 §1.3–1.4.
- **Problem:**
  - The utility maximization `U(T|C)` over `π` presupposes a known task `T`; the "task-independent core" has no objective (what is it optimizing?). "Importance" is defined as an ordering `pinned > task-relevant > structurally central > other` rather than derived from loss or utility. It is a priority list, not a definition.
  - G2 ("same fact produces same representation regardless of source") conflicts with G3 (conflicts surfaced): source-agnostic canonicalization is exactly what hides source-specific reliability. Provenance partially resolves this; the interaction is not discussed.
  - G1–G8 are not prioritized, and no goal trades off against another formally (G5 vs G4 vs G7 are in direct tension; G6 human-readable vs G4 compact).
  - The tension is correctly stated, but the reframing omits the strongest alternative: do not preload at all, let the agent retrieve (tools). UCN's value then lies in being an *index and intent layer for retrieval*, not a context blob. The proposal gestures at this (expand loop) but the problem statement never compares "context blob" and "tool access" as design options.
  - Non-goal "not replacing source as truth" vs G5 "lossless where it matters" are fine, but "faithful(C,S): every statement entailed by S" is an unattainable spec for `rationale` (`why:`) that is often not present in S.
- **Fix:** State priorities (e.g. G3 > G5 > G4 > G7). Reframe UCN's core as a retrieval index plus a card. Give a definition of importance from counterfactual task loss.

### M8. Interop mapping claims are too strong
- **Location:** 03 §3.9, §3.7.
- **Problem:** "UCN can serve as a lightweight profile of SysML v2" and "round-tripping loses nothing" (JSON). The mapping table is one-directional and approximate: `fn` to `action def`/`calc def`, `decision` has no home (conceded), `flow`, `conflict`, `more` and `status` provenance have none. No SysML v2 export is validated against a real SysML v2 parser (Pilot implementation). Also C4 DSL import loses non-C4 semantics, and Mermaid export is a one-way rendering. `goal` mapped to a top-level `requirement` conflates intent hierarchy. Roundtrip "loses nothing" is untested and contradicted by projection output (C7).
- **Fix:** Mark the table "intended mapping, unvalidated". Add a roundtrip test against the SysML v2 pilot parser for the Shortly model. Remove the "loses nothing" claim or limit it to canonical JSON <-> full text.

### M9. Security and trust of the model
- **Location:** 03 (absent).
- **Problem:** A UCN model built from tickets, docs, PR text and code comments is an indirect prompt-injection channel (an agent reads `why:` or `req` text extracted from untrusted tickets). Pinned status is also an attack surface (an attacker's ticket can mark itself `[pin]`/`[security]`). Not discussed.
- **Fix:** Treat extracted text as untrusted data. Require provenance-based trust tiers and forbid pin escalation from low-trust sources. Add this to §3.11.

## Minor issues / nits

- 02 §2.1: Fam ratings for TLA+/Alloy as ○ is not obviously right (LLMs read TLA+/Alloy reasonably). Dafny/Verus-style LLM verification is an active area; cite it.
- 02 §2.3: EARS Extr rated ●, but extracting EARS sentences from free text is LLM-based (inferred), not deterministic. Same for FRETish.
- 02 §2.4: telekom/toon vs toon-format/toon: both resolve (the Telekom repo is a fork or mirror); cite the canonical toon-format repo.
- 02 sources: several are blog or aggregator posts (dev.to, morphllm, mcp.so, itbrief) used as evidence for adoption facts. Prefer primary sources (agents.md, LF press release, OMG spec). The code-graph "savings figures self-reported" caveat is good, but the same standard should apply to the blog sources.
- 02 §2.5: "Pretrained 1.3B models struggle >1.5k tokens away" applies to pretrained base models, not instruction-tuned small models of today (Qwen/Llama/Gemma at 4–8B handle 8k+ with decent accuracy). The evidence is dated and weak for the target.
- 03 §3.4: L0 "150–500 tokens" and the `level:` header semantic is unclear: L3 is "pointer to source", which is not a rendering level.
- 03 §3.4 claims "summaries produced bottom-up, each level a faithful abstraction" while LLM summarization is unfaithful in general; the claim should be conditioned.
- 03 §3.5: `gain(L)` is undefined; criticality weights undefined.
- 03 §3.2: "14 kinds ... close to C4 + EARS + DbC" is not an argument for minimality. RQ3 asks for the *smallest* metamodel but no minimality analysis exists. A principled approach is to run the ablation "drop kind K" in the benchmark.
- Parser: `lint()` matches relation targets by last dotted segment of *any* id, so `x.y` is accepted if any `y` exists; dangling detection is weak. No lint for duplicate ids, kind/parent validity (`fn` inside `data`), unknown tags, unknown `status` values, `[pin]` caps, or machines with unreachable states.
- Parser: `fn` is special-cased without an id regex. Overloads, generics `fn map<T>(...)`, or arrows (`fn f = (x) =>`) break id extraction.
- Parser: no `--json` round trip back to text, so the "one-to-one mapping" claim is untested; there is no renderer.
- Parser: `CLAUSES`/`ATTRS` check happens by first word; an attribute named like an id (`tech`, `owner`, `why`) as a node name is impossible; reserved words are not documented.
- Parser: the `parent_at(indent)` pops entries with `>= indent`, so a line indented *less* than the declared children pops correctly, but a clause after a nested child (`fn` then `src:` after a nested `calls` is fine) is attributed to the last node at that depth; it relies on authors never writing clauses after child nodes. Document or enforce clause-before-child ordering.
- examples/shortly/model.ucn: `satisfies` appears on `container Cache` for `Fast` while `ResolveLatency` verifies `Fast`. OK, but no `test` covers the `Cache` guarantee `entries expire with the link`. Not a defect, but a good lint rule candidate (guarantee without verification).
- examples README says "7 requirements, 4 containers, 3 components, 5 contracts, 1 state machine..." The model has 7 req, 4 containers, 3 components, 5 fns, 1 machine, 3 decisions, 3 tests. "5 contracts" is the fn count; call it that.
- README.md status mentions docs/04-review-synthesis.md which does not exist yet (fine for a work in progress, but the link is dead).

## Missed prior art

Verified (URL resolves) unless marked otherwise.

**Unification / metamodels**
- OMG Knowledge Discovery Metamodel (KDM, ISO/IEC 19506) and Architecture-Driven Modernization: https://www.omg.org/spec/KDM . Most important miss (see C1).
- ISO/IEC/IEEE 42010 architecture description (viewpoints/correspondences; unverified link, ISO site blocked): https://www.iso.org/standard/74393.html
- FAMIX / Moose platform (Pharo) for unified code+architecture models (not link-checked).
- OMG SACM (assurance case metamodel) and SBVR / DMN for rules (not link-checked); partial overlap with `rule`.

**Provenance / conflict**
- W3C PROV-O / PROV-DM: https://www.w3.org/TR/prov-o/ . RDF-star / named graphs, truth-maintenance systems, argumentation frameworks (not link-checked).

**Code-logic / spec extraction**
- Daikon dynamic invariant detection (not link-checked).
- LLM postcondition/spec generation: nl2postcond https://arxiv.org/abs/2310.01831 ; SpecGen, AutoSpec, ClassInvGen (not link-checked). Needed to calibrate the extraction claims in M4.
- Architecture recovery tools/literature: Bunch, ACDC, ARC (Garcia et al.), Structure101, ArchUnit (architecture rules as tests; not link-checked).
- Runtime/ops: OpenTelemetry traces and service maps; Pact consumer contracts (not link-checked).

**LLM context / compression / repo-level work**
- LLMLingua / LongLLMLingua prompt compression: https://arxiv.org/abs/2310.05736 . Directly relevant to "compact context for LLMs" and a baseline (compress raw files at the same budget).
- Anthropic, "Effective context engineering for AI agents": https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- RepoGraph (repo-level code graph for SWE agents): https://arxiv.org/abs/2410.14684
- SWE-agent and its agent-computer interface (the retrieval-agent baseline): https://arxiv.org/abs/2405.15793
- Also to consider (not link-checked): Agentless, CodexGraph, RepoAgent, HippoRAG (personalized PageRank over KGs, close to step 3 of the projection), MemGPT/Letta, Microsoft GraphRAG, and auto-generated architecture wikis (DeepWiki, Google Code Wiki).
- Benchmarks usable for the evaluation plan (not link-checked): SWE-bench, RepoQA, SWE-QA, RepoBench, LongCodeArena.
- Repo packers (Repomix, gitingest, code2prompt) as additional baselines.

**Requirements side**
- ISO/IEC/IEEE 29148, Planguage, Volere, Specification by Example (not link-checked); DDD ubiquitous language for the missing glossary.
- Software traceability research (Cleland-Huang et al.; TraceLab) for the limits of link recovery.

## Top 5 recommended changes (priority order)

1. **Redo the Q1 analysis with a published rubric and add KDM, FAMIX/Moose, ISO 42010 and PROV-O** (C1, C2, C3). Re-state Q1 as "no existing language jointly satisfies G1+G2+G4+G5+G7", and give SysML v2 a fair test by encoding `Links.create` in SysML v2 and comparing tokens. Consider positioning UCN as a SysML v2 profile with a compact syntax.
2. **Make the projection guarantees real** (C4, C5): tiered pins with graceful degradation instead of failing, a closure rule for referenced nodes, honest wording of the stub guarantee, specified task typing and seeds. Add prefix-caching and latency to the feasibility argument (M5).
3. **Fix the data model and spec/parser/example inconsistencies** (C6, C7, M1): multi-valued `src`, global identity rules, a structured `conflict` node, a complete EBNF, a transition marker that cannot collide with keywords, a parsed header, corrected stub counts, the 100-vs-1000 contradiction, as-is/to-be phase, and a slice generated by actual code rather than by hand.
4. **Rebuild the evaluation plan around downstream tasks and harm** (M6): an agent with grep/read tools as the primary baseline at equal total token spend, issue-resolution or repo-QA tasks, seeded-error harm tests, leave-one-fact-out importance estimation, a gold standard for extraction faithfulness, and contamination controls.
5. **De-risk extraction and widen the metamodel** (M3, M4, M9): pilot Stage 2 (LLM contracts and clustering) on one real repo before further design, add conventions/glossary/runtime/event/`implements` and phase, treat extracted text as untrusted input (no pin escalation from low-trust sources), and define the contract expression language or openly declare the clauses informal.
