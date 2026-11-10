Reviewer: Fable 5.1 (claude-fable-5-1) · 2026-11-05

# Independent review of Unified Context Notation (UCN) v0.1

Scope: README.md, docs/01-problem-statement.md, docs/02-investigation.md, docs/03-proposal.md, examples/shortly/*, tools/ucn_parse.py. I ran the parser (`--lint --tokens`, `--json`) on all three example files. I did not read reviews/review-sonnet.md.

## Verdict

The proposal asks the right question and gives a defensible top-level answer. The "inherent tension" reframing (core card + task slice + visible omissions) is correct and is the most valuable idea in the repository. But v0.1 is weaker than its prose suggests, in four ways. (1) The headline guarantees of the projection algorithm (budget respected, nothing relevant silently dropped) do not hold as written: stubs are added after the budget is spent, and "relevant" has no definition. (2) The provenance story, the main thing UCN adds over existing formats, cannot be expressed where it matters most. A `fn` line cannot carry tags, contract clauses cannot carry status, and the "defaults are silent" rule labels LLM-inferred contracts extracted from code as `derived`. (3) The low-end-LLM budget arithmetic ignores that the agent's window must also hold code, the task, tool output and the answer, and the pinned set grows with system size. (4) The worked example contradicts itself: the conflict it advertises is contradicted by its own derived contract, and its stub counts are wrong. The Q1 answer ("no single language fits") is correct in practice, but the argument against SysML v2 is partly undercut by the proposal's own interop table. UCN is better described as a SysML v2/C4 *profile plus tooling* than as a new language. The evaluation plan is a good start, but its main metric (pinned-fact recall = 100%) holds by construction, and it does not directly measure silent loss. **Score: 5/10**: a sound research framing with a promising design direction, but the core mechanisms are not yet specified rigorously enough to deliver the stated guarantees.

## Strengths

- Correct reframing (docs/01-problem-statement.md §1.4): it turns an impossible goal into a testable one (core + slice + addressable omissions) and makes loss *visible* rather than pretending to eliminate it.
- Sensible "borrow semantics" stance (03 §3.1): EARS, C4, DbC, statecharts, ADRs and SysML trace verbs are the right parts to borrow, and each kind is mapped back to its origin.
- Provenance and conflict as first-class concepts (03 §3.1 principle 5, §3.6 stage 4). This really is underserved in existing formats.
- Ordering for positional bias (03 §3.5 step 6, §3.8) is grounded in cited evidence.
- The evaluation plan includes the right baselines (repo map, AGENTS.md) and, importantly, a **syntax ablation** (03 §3.10), so G7 is tested rather than assumed.
- Honest caveats in examples/shortly/README.md (tokenizer, toy size).
- A runnable parser exists already and found real gaps (missing `verifies`).

---

## Critical issues (must fix)

### C1. The projection algorithm does not guarantee `tokens(C) ≤ B`
**Location:** docs/03-proposal.md §3.5, steps 4–5 and "Guarantees".
**Problem:** Step 4 fills the budget greedily. Step 5 then *adds* `more:` stubs for every relevant omitted node. Stubs cost tokens, so the output can exceed `B` whenever step 4 filled the budget, which is the normal case. Ancestor "re-opening" lines (`container Api`, `component Links` in examples/shortly/slice.alias.ucn:22–30) are also not charged in `cost(n, L)`. On top of that, `ancestors_included_or_stubbed` is checked in step 4, before any stubs exist, so the "or stubbed" branch can never be true.
**Fix:** Reserve a stub budget up front, for example `B_stub = min(0.1·B, k)`, and charge every rendered line, including ancestor headers. Then compute stubs from the final selection and, if they overflow, coarsen them (merge sibling stubs into a parent stub) until the output fits. State the invariant formally and test it in the prototype.

### C2. The knapsack can choose a node twice and has no real optimization semantics
**Location:** 03 §3.5 step 4.
**Problem:** Candidates contain both `(n, L1)` and `(n, L2)`. Nothing prevents both being added, and `cost(n, L2)` is not defined as incremental over L1. `gain(L)` is undefined. Greedy-by-ratio has no approximation bound unless you add the standard "best single item" check. This is a multiple-choice knapsack with precedence constraints (a child requires its ancestor) and should be specified as one.
**Fix:** Define each node's levels as mutually exclusive upgrades with *incremental* cost and value. Enforce precedence (an ancestor must be at least L0/L1 before a child can be selected, with the ancestor's cost charged). Specify `gain`, `criticality` and tie-breaking (needed for the determinism claim). Write it as a precise algorithm, not pseudo-Python that cannot run.

### C3. "Every relevant omission is visible as a stub" is vacuous
**Location:** 03 §3.5 step 5 (`relevant(score)`), "Guarantees"; 01 §1.4 constraint `∀ n ∉ C relevant to T`.
**Problem:** "Relevant" is never defined. It is whatever crosses an unspecified threshold, so the guarantee is circular (anything not stubbed was, by definition, irrelevant). The stubs also carry only **counts** ("7 req, 3 actor…", card.L0.ucn:16), which tells the agent nothing about *which* omitted thing matters. A small model cannot decide whether to expand "2 component". Worse, the example slice stubs the **irrelevant** nodes ("not relevant to task", slice.alias.ucn:49) and silently drops a relevant one: `component Guard` is called by `Links.create`, and aliases must still pass the blocklist and rate limit, yet it appears neither in the slice nor in a stub. The parser's own lint then reports `dangling target: Links.create calls Guard.check` on the slice.
**Fix:** Define relevance operationally, for example the PPR score ≥ τ or the top-k by score, plus every node one typed hop from a selected node. Stubs must name omitted ids (meaningful ids are cheap: `more: Guard (check, limit), CacheAside -> expand …`) and should carry a criticality hint (`[security]`). Add a linter rule that every edge target referenced in a projection is either present or stubbed ("closure under references"). That is a checkable form of G5.

### C4. Provenance status cannot be attached to function contracts, and the defaults hide inference
**Location:** 03 §3.2 "Tags" + principle 4; §3.3 grammar (`node = kind Id [tags] ...`, but `fn` uses a signature); tools/ucn_parse.py:52–54 (`fn` → `tags = None`); 03 §3.11 risk 1.
**Problem:** The main mitigation for hallucinated logic is "tag them `[inferred]`" (§3.11). But (a) the parser and grammar give `fn` no tag slot, so a function cannot be `[inferred]` or `[pin]`. (b) Contract clauses (`pre/post/err/effect`) have no status at all, even though in practice each clause has its own origin (a signature is derived; `post: unique(result)` is inferred). (c) The default rule ("`derived` for code and specs") means that any clause whose `src:` is a code file is rendered as derived *without any marker*. In examples/shortly/model.ucn:51–89 nearly every `post:`/`err:`/`effect:` line would in reality come from stage 2 (LLM normalization) and be inferred, yet it reads as derived. This is exactly the "silent" failure that G3 forbids.
**Fix:** Make status per line, not per node. Give `fn` a tag slot (for example `fn create(...): Code [inferred]` or a trailing `~` convention, then test it). Make the default depend on the **producing method**, not the source type: only deterministic adapters yield `derived`, and everything else is `inferred` unless confirmed. A block-level default (`status-default: inferred` under a node) avoids per-line token cost.

### C5. The pinned set does not scale, so the core breaks first on real systems
**Location:** 03 §3.2 ("`security`, `safety`, and `legal` imply `[pin]`"); §3.4 (L0 = 150–500 tokens); §3.5 step 1 (`raise BudgetTooSmall`).
**Problem:** A real product has dozens to hundreds of security, privacy and compliance requirements. Each pinned req is about 30–40 tokens in EARS (card.L0.ucn:11–12 are ~35 tokens each). With 100 such requirements the "core" is ~3.5k tokens, which is the whole 4k budget for a 1–4B model (§3.8). The algorithm then fails loudly every time. The 150–500 token core is only plausible for toy systems like Shortly. In addition, pinned facts are rendered at **L1** (§3.5 step 1) while the card renders them at L0 (card.L0.ucn), and pinned facts unrelated to the task (a GDPR retention rule during a CSS fix) waste the scarcest budget.
**Fix:** Separate *must-not-silently-drop* from *must-inline*. Introduce pin scopes: global pins (few, hand-chosen, capped, for example ≤ 15 lines) versus scoped pins (inlined only when the slice touches an element they `affects`/`satisfies`, otherwise rendered as one aggregate stub: `more: 42 security reqs [pinned, not touching this slice] -> expand Security@L1`). Report the global-core size in lint and fail CI if it exceeds its cap.

### C6. The budget targets equal the entire effective window of the target model
**Location:** 01 §1.3 G4 (2k–8k "context"); 03 §3.8 rule 6 (≤4k for 1–4B, ≤8k for 7–8B); §2.5.
**Problem:** G4 and §3.8 treat `B` as the model's whole usable context. But an agent also needs the system prompt and tool schemas (often 1–3k tokens alone), the task text, the **code it will edit** (L3 is "fetched on demand", and fetched into what?), tool outputs, and room to generate the answer or patch. If the effective window of a 3B model is ~4k (by the doc's own §2.5 argument), UCN can have perhaps 1–1.5k of it. That is close to the core alone. The doc never does this arithmetic.
**Fix:** Define `B_ucn = B_window − B_system − B_task − B_code − B_output` and report UCN budgets as a fraction (for example 25–40%) of the effective window. Add a target such as "L0 core ≤ 600 tokens, task slice ≤ 1k for 1–4B models". Note the positive side as well: a static core placed first is reused through prefix/KV caching (llama.cpp, vLLM). This is a real argument for the core-first layout on cheap machines, where prefill dominates latency, and the doc does not mention it.

### C7. The worked example contradicts itself on its showcase conflict
**Location:** examples/shortly/model.ucn:87–90; card.L0.ucn:15; examples/shortly/README.md ("Conflict surfaced").
**Problem:** `fn limit` has `err: count(owner, last 1h) > 100 -> 429` with `src: api/guard.ts:42`, which is a *derived-from-code* contract saying the code uses 100. Two lines later, `conflict: ... code uses 1000/hour (api/guard.ts:44)`. The model therefore asserts both values for the code. `test GuardTests` says "101st link in an hour → 429", which would fail if the code really used 1000. This is exactly the faithfulness failure (G3) UCN is meant to prevent, and it sits in the reference example.
**Fix:** Make the contract match the code (`> 1000`) and link the conflict to both nodes (`RateLimit` req and `Guard.limit`). Give conflicts an id so they can be referenced, pinned and resolved (see M3). Note in the example whether the test currently passes.

### C8. Stub counts in the example are wrong
**Location:** card.L0.ucn:16; slice.alias.ucn:49.
**Problem:** The card shows 2 of 7 reqs but stubs "7 req" (should be 5). It also omits 5 `fn`, 1 `data`, 1 `api` and 1 `machine` from the stub entirely, so these are silently dropped by the doc's own definition. The slice shows 3 of 7 reqs but stubs "6 req" (should be 4), and stubs "2 component" when only `Guard` is missing (1). A hand-simulated example of an algorithm whose purpose is accurate omission accounting should not get the accounting wrong. This also shows that even the authors cannot reliably compute stubs by hand, so stubs must be machine-generated and checked.
**Fix:** Generate the card and slice with a (prototype) projector, or add a lint `--against model.ucn` that checks a projection's stub counts against the full model.

---

## Major issues (should fix)

### M1. The Q1 argument against SysML v2 is partly undercut by the proposal itself
**Location:** 02 §2.4, §2.6, §2.7; 03 §3.9.
SysML v2 is said to have "no code-level logic". Yet §3.9 maps **every** UCN kind, including `fn` (→ `action def`/`calc def` + constraints), `rule`, `machine`, `flow` and `test`, to native SysML v2 constructs, and only `decision` lacks one. Per-fact provenance and status could be carried with SysML v2 `metadata def` (user-defined metadata annotations), and `concern def` is a closer match for `goal` than `requirement`. So the honest finding is: **SysML v2 is semantically almost sufficient, but pragmatically unfit** (verbosity, tooling built for forward engineering, no extraction adapters, no budgeted projection, unknown small-LLM legibility). That still justifies building something, but it is a *concrete syntax + profile + tooling* contribution, not a new language. The proposal half-says this ("lightweight, LLM-friendly profile", §3.9). Say it in README and §2.7, because it changes how reviewers will judge novelty. Also, "Fam ○" for SysML v2 is an untested claim, and UCN's own familiarity is zero by construction (it is new). Its legibility rests on English keywords, a hypothesis that needs the same test. Add SysML v2 textual notation as a syntax-ablation arm in §3.10.

### M2. `status` is overloaded and conflates independent dimensions
**Location:** 01 §1.4 (`status(n) ∈ {stated, derived, inferred, conflict}`); 03 §3.2 (attribute `status:` = lifecycle, e.g. `accepted`, `proposed`), §3.6 stage 4 ("stale").
"Status" means three different things: provenance method (stated/derived/inferred), epistemic state (conflict, stale/fresh), and lifecycle (proposed/accepted/superseded). `conflict` is a relation between facts, not a property of one fact. "Stale" (drift) is not in the status set at all. A small model will confuse `status: proposed` with the `[inferred]` tag.
**Fix:** Use separate axes: `origin ∈ {stated, derived, inferred}`, `verified ∈ {no, test, review, proof}`, `fresh ∈ {yes, stale}`, `lifecycle`. Make `conflict` an identified node that links its competing facts.

### M3. `conflict` and `more` are unstructured strings
**Location:** 03 §3.3 grammar; tools/ucn_parse.py:86–87.
A conflict has no id, no typed links to the facts it concerns (`Guard.limit` appears only inside the text), and no structured sides or sources. It cannot be pinned, expanded, resolved or diffed, and its placement under `Guard` versus the top level differs between files (model.ucn:90 vs card.L0.ucn:15). `more:` has the same problem: the parser does not parse `-> expand Id@L`, so the expansion protocol is not machine-checkable. The `|` separator collides with text containing `|` (regexes, shell). Also, `conflict` is a required concept (G3), but the parser keeps it in `meta`, outside the graph.
**Fix:** Use `conflict RateLimitValue: ...` with `side: 100/hour  src: ticket#14` and `side: 1000/hour  src: api/guard.ts:44` lines, plus `about RateLimit, Guard.limit`. Use `more` with structured `ids:` and an `expand:` target.

### M4. Grammar holes and the "first word decides role" claim
**Location:** 03 §3.3; tools/ucn_parse.py:47–94.
- Transitions start with a *state name*, so a state named `data`, `test`, `api`, `flow`, `system`, `owner`, `status`, `more`, … makes the line unparseable or misparsed. That breaks the disjointness claim. States are also listed only in free text (`states active, expired, disabled`, model.ucn:69), with no initial/final states, guards, actions or hierarchy. That is far less than "statecharts" (§3.2).
- `fn` has no production in the EBNF. The parser takes `sig.split("(")[0]` as the id, which breaks for Go (`func (s *Svc) Create(...)`), Java/C# (`public Code create(...)`), generics (`create<T>(...)`), Python `def` and overloads (duplicate ids are merged silently by `setdefault`).
- `:` has five roles (header keys, node summary, attribute, transition, type annotations in signatures), and `->` has four (transition, `err` mapping, `more` expansion, free text such as `hot code -> target map`, model.ucn:96). This is parseable, but it adds decoding work for exactly the small models §3.8 targets.
- The `expr` in clauses is undefined. The example mixes code (`link.expiresAt < now`) and English (`alias taken`, `unknown code`), and `->` is not host-language notation in TypeScript.
- Re-opening a node (`container Api` declared again at top level in slice.alias.ucn:25) is undocumented. Is it a reference or a new declaration?
- The header is not parsed (tools/ucn_parse.py:30 stores it raw), so `level:`, `task:` and `budget:` are unchecked.
**Fix:** Write a real grammar (Lark or tree-sitter), with an explicit `fn` production that accepts "signature as opaque string up to the tag or end of line", plus an explicit `id:` override. Make transitions keyword-led (`on expiresAt passed: active -> expired`) and add `states:` and `initial:` lines.

### M5. Relation endpoints are not typed or checked, and the example violates them
**Location:** 03 §3.2 Relations table; model.ucn:65, 85; tools/ucn_parse.py:99–111.
`reads` is "element → data", yet `fn resolve` `reads Cache` (a container). `calls` is "fn → fn", yet `Guard.check` `calls SafeBrowsing` (an actor). `effect: writes Link` (model.ucn:58) duplicates the `writes` relation as free text, so the graph lacks the edge, and there are two ways to say one fact (against principle 2 and G2's canonical form). Edges store raw strings rather than resolved ids. Lint resolves by **short-name suffix** (`split(".")[-1]`), so two components each with a `create` function would both "resolve". `Link` (data) and `Links` (component) are a confusable pair for small models.
**Fix:** Add a domain/range table to the spec and enforce it in lint. Resolve references to canonical ids in the JSON and flag ambiguity. Either move effects into relations (`writes Link`, `emits LinkCreated`) or define `effect:` as free text that is never the only carrier of a graph edge.

### M6. Metamodel gaps (and some redundancy)
**Location:** 03 §3.2.
Missing concepts that agents routinely need:
- **Events/messages** (`emits LinkCreated`, model.ucn:58, has no node kind; AsyncAPI is cited in §2.2 but not modeled).
- **Configuration / feature flags** (`WHERE custom aliases are enabled`, model.ucn:28; the flag is not a node).
- **Deployment/environment** (IaC is listed as a source in §3.6, but there is no node for where things run).
- **Glossary/term** (domain vocabulary is what entity resolution in §3.6 stage 3 needs most, and small models benefit from definitions: what is a "premium user"? The model has no user tier anywhere, yet `req Alias` depends on it).
- **Known issues / tech debt / TODO** and **assumptions**.
- **Data sensitivity** (PII classification) for security reasoning.

Redundancy: `rule CodeImmutable`, `decision ImmutableCodes` and `inv: code unique` restate overlapping facts. `calls` is a subtype of `uses`. `flow` is never exercised. Missing relations: `implements` (fn → api operation), `emits`/`consumes`, `conflictsWith`, `deploysTo`, and explicit inverses for rendering (see M8). The §3.11 "14 kinds is close to C4+EARS+DbC" argument is not evidence of sufficiency. Count the kinds needed by the Context Sufficiency questions instead.

### M7. Round-trip and merge claims are false for the prototype
**Location:** 03 §3.7 ("round-tripping loses nothing"), §3.6 ("the fact keeps every `src`"); tools/ucn_parse.py:85.
Attributes are stored in a dict, so a second `src:` **overwrites** the first. That makes multi-source merge, the core of G2, impossible to represent. Comments carrying semantics (`# satisfied by: Links`, `# lint: no test verifies Alias yet`, slice.alias.ucn:45–46) are discarded. The header is opaque, conflict/more text is unparsed, and summary text with folded tech (`single-page UI (react)` in the card vs `tech: react` in the model) is not reversible.
**Fix:** Make `src` (and similar attributes) multi-valued. Promote inverse relations and lint notes to first-class lines (`satisfiedBy Links` rendered by the projector, `warn:`). Add a round-trip test (`ucn → json → ucn` byte-equal modulo formatting) to CI.

### M8. Small-LLM legibility is asserted, not argued, and relational indirection is the likely failure mode
**Location:** 03 §3.8; 01 G7.
The rules cover surface syntax (keywords, depth ≤ 4), but the hard part for 1–4B models is **multi-hop joins over ids**. The trace req ← `satisfies` ← component ⊃ fn ← `verifies` ← test (examples README) requires 3–4 hops across distant lines, which is exactly where small models fail (RULER multi-hop tracing; the "1.5k tokens away" finding the doc itself cites). Relations are rendered only at the source end, so "what satisfies Alias?" requires scanning the whole context. The slice already works around this with a comment.
**Fix:** Let the projector *denormalize* for small models: render inverse edges inline at the target (`req Alias … satisfiedBy: Links; verifiedBy: none`) and repeat key facts locally instead of referencing them. Ablate normalized against denormalized rendering in §3.10.

### M9. The extraction pipeline under-states what is non-deterministic and what a cheap machine can do
**Location:** 03 §3.6 stage 4 ("Deterministic"), stage 2, §3.11 ("can run with a small local model").
"Conflict detection: the doc says X, the code does Y" is semantic comparison of a natural-language claim against code behavior. It is LLM- or analysis-based, not deterministic, and it is probably the hardest step in the whole pipeline. Entity resolution (stage 3) is waved through in one sentence. Contract inference quality is known mainly from frontier models: nl2postcond reports GPT-4 results, and SpecGen/AutoSpec rely on strong LLMs plus verifier feedback. There is no evidence that a 1–8B local model produces useful `post:` clauses. The deterministic alternatives that do exist are not mentioned: dynamic invariant detection (Daikon), specification mining of state machines (k-tails/Synoptic), and architecture recovery/clustering.
**Fix:** Separate the *extraction machine* (may need a mid-size model or a one-off cloud pass) from the *consumption machine* (cheap). Mark stage 4 as "deterministic checks + LLM-assisted conflict candidates". Add Daikon-style mining and test-confirmed promotion as the main way facts reach `derived` status. Budget an extraction-accuracy study per stage, not only end-to-end.

### M10. Bottom-up LLM summaries are drift-prone and status-laundering
**Location:** 03 §3.4 ("each level is a faithful abstraction of the level below").
L0/L1 summaries are produced by an LLM from lower levels, so they are `inferred`, and errors propagate upward. "Faithful" is asserted, not checked. A source hash change at the bottom must invalidate every ancestor summary (§3.6 says only "the fact is marked stale"). L3 is a pointer, not a level of content. L0 is defined only for the system card, not per node, which contradicts "each node can be rendered at four levels".
**Fix:** Define per-kind templates for L0/L1 that are *rendered deterministically* from fields (id + kind + first sentence + tags) wherever possible, and use LLM summaries only for container/system text, marked inferred. Specify hash propagation to ancestors.

### M11. The evaluation plan does not directly measure "no important context lost"
**Location:** 03 §3.10; 01 §1.7.
- **Pinned-fact recall = 100%** holds by construction (§3.5 raises otherwise), so it is not a result. Measure instead whether pinned facts were *respected* (for example, did the model's answer or patch violate `CodeImmutable`?).
- The key G5 metric is missing. For each question, annotate the facts needed to answer it (independently of UCN), then classify each needed fact in the projection as **present / stubbed / silently absent**. The silent-absence rate is the direct measure of "nothing important lost". The stub-to-expansion success rate measures whether stubs are actionable.
- Questions written by the UCN authors will be biased toward what UCN represents (the six categories map one-to-one onto UCN kinds). Source questions from real artifacts: GitHub issues (as SWE-QA does), bug-fix commits ("which facts did the fix depend on?"), and existing benchmarks (SWE-QA, RepoQA, CodeWikiBench rubrics).
- Contamination: open-source repos are memorized by the frontier reference and partly by small models. Include post-cutoff or private repositories, and a "no context" condition to measure the memorization floor.
- Budgets must be measured in **each model's own tokenizer**. o200k counts (examples README) can differ by 10–30% from Llama/Qwen/Gemma tokenizers.
- Missing baselines: Repomix `--compress`, LLMLingua-style prompt compression of raw files, a DeepWiki/CodeWiki-style generated wiki, and the *same UCN graph rendered as plain Markdown* (to separate content from syntax).
- Missing cost metrics for the "cheap machine" goal: extraction wall-clock and cost, prefill latency on CPU, and maintenance cost per commit (drift).
- Faithfulness (≥95% in §1.7) needs a human audit protocol with inter-rater agreement. "Correctly labelled" needs a definition.
- No statistical plan (CIs, paired tests across conditions). 50–100 questions × 3–5 repos is borderline for detecting +15 pp per category.

### M12. The problem formulation omits two real-world constraints
**Location:** 01 §1.3–§1.6.
- **Untrusted sources.** Tickets, emails and wiki pages are attacker-influenced. Extracted text placed into an agent's context is a prompt-injection channel. Provenance helps but is not enough: add a goal or non-goal about sanitization and about marking human-sourced free text.
- **Multi-turn and agent-loop budgeting.** Context is consumed across turns, and expansions accumulate. The formal framing treats π as one-shot. At minimum, note that `π` must be re-run with the remaining budget after each expansion, and that an expanded node should replace its stub rather than add to it.
- Also: `U(T | C)` and `faithful(C, S)` (entailment of free text by code) are not computable. Say that they are operationalized only through the benchmark and the audit, not by the algorithm.

---

## Minor issues / nits

1. README.md links `docs/04-review-synthesis.md`, which does not exist.
2. Token counts in examples/shortly/README.md (1,289 / 247 / 624 o200k) cannot be reproduced without `tiktoken`. The parser silently falls back to `len/4` (tools/ucn_parse.py:119) and still labels the output "tokens (o200k)". On my run without tiktoken it printed 1248/250/607. Label the fallback as an estimate, or fail.
3. `--lint` on the card and slice produces false warnings (Blocklist "nothing satisfies it"). The comment at tools/ucn_parse.py:133 admits this. Add a `--projection` mode that checks reference closure and stub accounting instead.
4. The parser accepts any indentation jump (for example 0 → 6 spaces), and an attribute under a transition-less machine is fine. No check that clauses appear only under `fn`/`component`/`container` (§3.2), or that `transition` only appears under `machine` beyond a kind check.
5. 03 §3.2 calls `more`/`conflict` "meta-lines" that "can appear anywhere", but the grammar allows them only as indented lines like any other, and the parser attaches them to whatever node is open, which affects meaning (see M3).
6. `req Alias [event, option]` combines two EARS patterns, which is legal "complex" EARS. But the tag scheme has no `complex`, and §2.3 says "five templates" (EARS also defines the complex combination).
7. 02 §2.3 scores EARS "Extr ●". That is LLM normalization (inference), whereas "Extr ●" for signatures means deterministic extraction. Use two columns (deterministic vs LLM-assisted), otherwise the scoring flatters the intent layer.
8. 02 §2.5: "Most models degrade past roughly 16k–32k tokens" is attributed to LIFBench, which is about instruction-following stability. The canonical source for effective context length is RULER (Hsieh et al., COLM 2024). I could not confirm the "1.3B models struggle beyond ~1.5k tokens" paraphrase of arXiv 2410.18745. Re-check the exact claim.
9. 02 §2.4 cites `telekom/toon`. The canonical TOON project is `toon-format/toon` (spec at `toon-format/spec`). The 30–60% savings figure is the project's own claim.
10. 02 sources lean on blogs (codemyspec, morphllm, itbrief, danielvaughan, dev.to) for factual claims. Replace them with primary sources (Kiro docs, Spec Kit repo, Linux Foundation AAIF announcement).
11. 02 §2.2: "SysML v2 / KerML (OMG, adopted 2025)" is correct (formally adopted 30 June 2025, announced 21 July 2025, published September 2025). Also mention the standardized Systems Modeling API & Services, which matters for tooling interop.
12. 03 §3.3 says English keywords "usually cost one token each, the same as a symbol". That holds for o200k but not for all small-model tokenizers, and with leading spaces and casing it varies. Measure it.
13. 03 §3.5 determinism also requires a pinned embedding model and version plus deterministic tie-breaks.
14. examples/shortly/card.L0.ucn folds `tech` into summary text (`(react)`) and drops `src:`. The L0 rendering rules are not specified.
15. `decision ImmutableCodes [pin]` and `rule CodeImmutable [pin]` both sit in the core, saying the same thing twice in a ~250-token budget. Dedup across `affects`/`satisfies` pairs is an easy win.
16. 01 §1.7 "Compression ≥ 10× at L1" is a weak metric: L1 is lossy by design, so any ratio is achievable. Report accuracy per token, or accuracy at a fixed budget, instead.

---

## Missed prior art

Verified via web search (links checked 2026-11-05) unless marked "well known".

**Unified repository representations / LLM code context**
- **RPG: Repository Planning Graph** (Microsoft, arXiv 2509.16198). One graph encoding capabilities, files, data flows and functions, used to plan and generate whole repositories. It is the closest recent "unified graph for agents" and should be in §2.4. https://arxiv.org/abs/2509.16198
- **HippoRAG** (NeurIPS 2024). Personalized PageRank over an extracted KG with query-concept seeds, which is exactly §3.5 step 3. Cite it as prior art for the relevance step. https://arxiv.org/abs/2405.14831
- **CodeWiki / CodeWikiBench** (arXiv 2510.24428) and **DeepWiki** (Cognition). Hierarchical repository documentation generation at multiple granularities, which is the strongest "generated human-readable context" baseline. https://arxiv.org/abs/2510.24428
- **Repomix** (`--compress`, tree-sitter signature extraction, token counts per file). The de facto "pack a repo for an LLM" tool and an obvious baseline. https://repomix.com/guide/
- Well known: RepoGraph (ICLR 2025), CodexGraph, LocAgent, Agentless (hierarchical file → class → function localization, i.e. LoD in practice), AutoCodeRover, SWE-agent's ACI, Serena (LSP-based symbolic MCP), Sourcegraph code-graph context.
- Well known: **LLMLingua / LongLLMLingua** prompt compression (baseline), **RAPTOR**, **MemGPT/Letta** (hierarchical memory with explicit paging, conceptually close to stubs plus expansion).

**Benchmarks to reuse in §3.10**
- **SWE-QA** (repository-level code QA from real GitHub issues, ACL 2026 Findings). https://arxiv.org/abs/2509.14635
- **RULER** (effective context length, multi-hop tracing). https://arxiv.org/abs/2404.06654
- Well known: RepoQA, LongCodeArena, SWE-bench (Lite/Verified) localization subsets.

**Format / legibility evidence**
- **He et al., "Does Prompt Formatting Have Any Impact on LLM Performance?"** (arXiv 2411.10541). Plain text vs Markdown vs JSON vs YAML changes accuracy substantially, and smaller models are more sensitive. This directly supports running the syntax ablation and contradicts any assumption that the "familiar-looking" format wins. https://arxiv.org/abs/2411.10541
- Well known: Sui et al., "Table Meets LLM" (WSDM 2024), on serialization formats for structured data.

**Contract / spec extraction (stage 2)**
- **nl2postcond** (Endres et al., FSE 2024). LLM → postconditions; GPT-4 reaches up to 96% correct, with no small-model evidence. https://arxiv.org/abs/2310.01831
- **SpecGen** (ICSE 2025) and AutoSpec (CAV 2024). LLM + verifier loop for JML specs. https://arxiv.org/abs/2401.08807
- Well known: **Daikon** (dynamic invariant detection, a deterministic and test-grounded source of `inv`/`pre`/`post`), Houdini, and spec mining for state machines (k-tails, Synoptic, Perracotta) as a route to `machine` other than "LLM inferred".

**Architecture recovery and drift (G8)**
- Well known and important: **Reflexion models** (Murphy, Notkin & Sullivan, FSE 1995). Hypothesized architecture vs extracted code dependencies, with convergences, divergences and absences. This is precisely "drift between intent layer and code", and §2.6's claim that "intent layers have no drift detection against code" is too strong.
- Well known: ArchUnit, jQAssistant (code + architecture concepts in one queryable graph, with rules), dependency-cruiser, Sonargraph/Structure101. Architecture-recovery research: ARCADE, Bunch, ACDC clustering (relevant to "module clusters → component", §3.6 stage 2).
- **Context Mapper (CML)**. A DSL for DDD bounded contexts and aggregates, with generators to PlantUML/C4-like views. It covers domain concepts (aggregates, events) that UCN's metamodel lacks. https://contextmapper.org/

**Traceability**
- Well known: the traceability-link-recovery literature (IR-based VSM/LSI, Cleland-Huang et al., the "Software Traceability" grand challenges), Eclipse **Capra**, and the Traceability Information Model (TIM) concept. Relevant to stage 3 and to M5's typed-endpoint table.

**Formal / spec-language choices**
- Well known: **Quint** (TLA+ semantics with programmer-friendly syntax, more LLM-legible than TLA+), the P language, Lean/Dafny. Relevant to "link formal specs for critical kernels".

**Spec-driven development**
- Well known: OpenSpec, Tessl, BMAD alongside Kiro and Spec Kit. These are forward-only, but they are where requirement/design/task Markdown conventions are converging, and UCN should import them.

---

## Top 5 recommended changes (priority order)

1. **Make the projection guarantees real (C1–C3, C8).** Specify π as a precise multiple-choice knapsack with precedence, a reserved stub budget, charged ancestor lines, an operational relevance definition, and *named* stubs. Add a projection linter (budget respected, reference closure, stub accounting checked against the full model). Generate card and slice from the prototype instead of by hand.
2. **Fix provenance so inference is never silent (C4, M2, M3, M7).** Use per-line status with block defaults, give `fn` tags, base defaults on the producing method rather than the source type, keep `origin`/`verified`/`fresh`/`lifecycle` separate, and make conflict an identified node with sides. Make `src` multi-valued.
3. **Redo the low-end budget model (C5, C6, M8).** Budget UCN as a fraction of the effective window after code, task, tools and output. Cap global pins and scope the rest. Add denormalized rendering of inverse edges for small models. Exploit prefix caching of the core.
4. **Rewrite the evaluation around silent loss (M11).** Annotate needed facts independently, measure present/stubbed/absent rates and expansion success, use real-issue questions (SWE-QA-style) and uncontaminated repos, count tokens per model tokenizer, add Repomix, LLMLingua, generated-wiki and Markdown-rendering baselines, and include cost and latency on cheap hardware.
5. **Reposition against SysML v2 and fill the prior-art gaps (M1, M6, M9).** State that UCN is an LLM-oriented profile, concrete syntax and toolchain over SysML v2/C4 semantics. Add SysML v2 textual notation to the syntax ablation. Add events, config/flags, glossary and deployment to the metamodel. Ground extraction in Daikon/spec-mining/reflexion-model techniques and cite RPG, HippoRAG, CodeWiki, nl2postcond and SpecGen. Fix the self-contradicting example (C7) and write a real grammar (M4).
