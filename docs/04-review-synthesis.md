# 4. Review Synthesis

UCN v0.1 (commit `129772b`) was reviewed independently by two different models. Each received the same brief and the same files. Neither saw the other's review. Each was asked to be critical, to cite file and section, and to check facts and prior art with web search.

| Reviewer | Score | One-line verdict | Raw review |
|---|---|---|---|
| **Fable 5.1** (`claude-fable-5-1`) | **5 / 10** | The framing is right, but the core mechanisms don't yet deliver the stated guarantees, and inference can be silent. | [reviews/review-fable.md](../reviews/review-fable.md) |
| **Sonnet 5.5** (`claude-sonnet-5-5`) | **6 / 10** | A plausible design sketch, not yet a research result: Q1 lacks a rubric and misses KDM and PROV-O, and the guarantees and examples are inconsistent. | [reviews/review-sonnet.md](../reviews/review-sonnet.md) |

## 4.1 What both reviewers said

**Both praised** the same things:

- the reframing in 01 §1.4 (task-independent core + task slice + visible omissions), which both called the most valuable idea;
- the explicit stated / derived / inferred / conflict distinction;
- core-first and slice-last ordering grounded in evidence;
- the syntax ablation, which tests legibility instead of asserting it;
- the honest caveats.

**Both found** the same problems independently. That makes these the most reliable findings:

| # | Finding | Fable | Sonnet | Resolution in v0.2 |
|---|---|---|---|---|
| 1 | The projection's guarantees don't hold. Stubs are added after the budget is spent, "relevant" is undefined, and a node can be chosen twice. The slice drops `Guard` while `Links.create` calls it. | C1, C2, C3 | C5 | §3.5 rewritten as a multiple-choice knapsack with precedence, a stub reserve, a closure rule, **named** stubs, and an operational relevant set. Guarantees narrowed to what is checkable, and checked by `--against`. |
| 2 | The pinned set doesn't scale. Every security/legal fact is pinned, so a real system's core overflows a small budget. | C5 | C4 | Global pins (capped, linted) vs scoped pins (inline when touched, otherwise named). Degrade before failing. |
| 3 | Pinned-fact recall = 100% holds by construction, so it measures nothing. | M11 | C4, M6 | Replaced by the pinned-constraint **violation** rate on tempting tasks. |
| 4 | The showcase conflict contradicts itself: the contract says the code uses 100, the conflict says 1000, and the test expects 429 at 101. | C7 | C7 | Fixed. The contract says 1000, the conflict has typed sides, and the test asserts 1000, so it no longer "verifies" `RateLimit`. |
| 5 | Stub counts in the card and slice are wrong. | C8 | C7 | Fixed. Card and slice are now **machine-checked** for accounting, closure, pins and budget. A negative test confirms the checker catches the v0.1 errors. |
| 6 | A second `src:` overwrites the first, so multi-source merge is impossible. | M7 | C6 | `src:` (and every attribute) is repeatable. Merge never drops a source. |
| 7 | `conflict` and `more` are unstructured strings. | M3 | M1 | `conflict` is a node with an id, `about` links, `side` children and a lifecycle. `more:` items are `kind Id` or `n kind`, and are parsed. |
| 8 | The grammar has holes: no `fn` production, transitions can collide with keywords, the header isn't parsed. | M4 | M1 | Complete EBNF with lexical rules. Transitions start with `on`. Explicit `fn Id: signature` form. Header parsed. |
| 9 | `status` conflates provenance, conflict and lifecycle. | M2 | M3 | Separate axes: origin, verified, freshness, lifecycle. Conflict is its own node. |
| 10 | Contract expressions are undefined, and "property-based tests check contracts" is not feasible. | M4 | M2 | Clauses are declared **informal**, and the claim is withdrawn. A clause can point to a checkable artifact. |
| 11 | The budget ignores code, task, tools and output. CPU prefill latency is ignored. Prefix caching is an unused argument for core-first. | C6 | M5 | `B_ucn = B_window_eff − B_system − B_task − B_code − B_output`, defaults per model class, prefix caching, latency in the benchmark. |
| 12 | The evaluation can't show "no important context lost". The strongest baseline (an agent with grep/read tools) is missing; so are contamination control, per-model tokenizers, and a content-vs-syntax control. | M11 | M6 | §3.10 rewritten around the **silent-absence rate** (needed facts: present / named / absent), the tool-using agent at equal spend, real-issue questions, post-cutoff repos, seeded-error harm tests, a Markdown-rendering control, and power analysis. |
| 13 | SysML v2 was assessed unfairly. The proposal's own mapping covers every kind but `decision`, so UCN is a profile, not a new language. | M1 | C2 | Q1 restated as "semantically almost, practically no". UCN is positioned as a profile + syntax + projection + toolchain. SysML v2 text added to the syntax ablation. |
| 14 | Extraction is overstated. Conflict detection is semantic, not deterministic. Contract-inference results are for strong models. Spec mining and architecture recovery are uncited. | M9 | M4 | Stage 4 split into deterministic checks + LLM conflict candidates. Daikon and k-tails mining added. Extraction machine separated from consumption machine. Per-stage targets and a pilot. |
| 15 | Metamodel gaps: events, glossary, conventions, config/flags, deployment, `implements`. | M6 | M3 | Added `term`, `event`, `config`, `env`, `convention`, `implements`, `emits`/`consumes`, `deploysTo`, and `code:` globs. |
| 16 | Relation endpoints are unchecked. `effect:` duplicates edges as free text. | M5 | M3 | Domain/range table, linted. `effect:` may never be the only carrier of an edge. |
| 17 | Ids are qualified inconsistently and resolution is weak. | M5 | C6 | Canonical ids by container path, references by unique suffix, ambiguity and kind mismatch are errors. |
| 18 | Extracted text is a prompt-injection channel, and pins can be self-assigned. | M12 | M9 | New goal **G9 Trustworthy**. Trust tiers. Pins and conventions only from trusted sources. |
| 19 | Citation problems: TOON repo, blog sources for adoption facts. | nits 9–10 | minor | Canonical `toon-format/toon`. Blogs marked as secondary. |

## 4.2 Points raised by only one reviewer

**Only Sonnet 5.5:**

- **OMG KDM** (ISO/IEC 19506), the standard for extracting models from existing software, plus FAMIX/Moose and ISO 42010. It called this "the most important miss". → Added to §2.4 and the rubric.
- **W3C PROV-O** makes the v0.1 claim "no per-fact provenance anywhere" false. → Claim removed; PROV vocabulary adopted.
- **No scoring rubric** behind the Q1 answer. → §2.7 rubric (0/1/2 per goal) and matrix.
- **As-is vs to-be** is missing: `req Alias` was "proposed" but already "implemented". → `lifecycle: planned`; the example's code no longer has the alias.
- **Importance should be defined by counterfactual task loss**, and goals need priorities. → §1.3 priorities and tensions, §1.4 importance definition, leave-one-fact-out ablation.
- **The retrieval alternative**: UCN as an index and intent layer for a tool-using agent. → §1.4.
- Interop claims too strong ("round-tripping loses nothing"). → Mapping marked unvalidated; round-trip claim narrowed to full model ⇄ JSON.
- Merkle-style dependency hashes for summaries. → §3.4.

**Only Fable 5.1:**

- **Inference was silent by default.** `fn` lines couldn't carry labels, clauses had no status, and "derived for code" labelled LLM-written contracts as derived. It called this the main threat to G3. → Line-level origin labels, defaults by producing method, renderers must show `inferred`.
- **Multi-hop joins over ids are the likely small-model failure**, more than surface syntax. → Denormalized rendering (`satisfiedBy` at the target) and an ablation.
- Bottom-up LLM summaries "launder" inferred status upward. → L0/L1 rendered deterministically from fields; LLM text marked inferred.
- Multi-turn budgeting (expansions accumulate). → Re-run `π` with the remaining budget; expansion replaces the stub.
- Prior art: **RPG**, **HippoRAG** (the same PPR relevance step), **CodeWiki/DeepWiki**, **Repomix**, **reflexion models** (architecture drift since 1995, so "intent layers have no drift detection" was too strong), Context Mapper, He et al. on format sensitivity. → All added.
- RULER, not LIFBench, is the right citation for effective context length. → Fixed.
- The parser silently fell back to a `chars/4` estimate but still printed "o200k". Both reviewers' token counts differed from the README for this reason; the README's numbers were correct with tiktoken installed. → The fallback is now labelled as an estimate, and the tiktoken version is pinned.

## 4.3 Where v0.2 deliberately departs from a recommendation

| Recommendation | Decision | Reason |
|---|---|---|
| Separate status, category and EARS pattern *syntactically* (Sonnet M3) | One bracket with four **disjoint** word sets. Canonical JSON keeps separate fields. | Tokens: separate attribute lines cost about 3× more per fact. Whether small models confuse the axes is an ablation in §3.10. |
| Fail softly instead of raising `BudgetTooSmall` (Sonnet C4) | Degrade first (container lines into a stub, then id-only pins), and fail only if global pins still don't fit | A global pin is never dropped silently. Failing loudly at that point is the honest outcome. |

## 4.4 Not yet done (deferred, not dismissed)

Some of the reviewers' top recommendations are only partly met in v0.2:

- **A generated slice.** Both asked for the card and slice to come from an implementation of `π`. v0.2 hand-writes them and **machine-checks** them, which addresses the accounting errors but not the "hand-simulated evidence" criticism. → Prototype projector in v0.3.
- **Measure SysML v2 verbosity directly** (Sonnet C2: encode `Links.create` in SysML v2 and compare tokens). → Part of the syntax ablation; SysML v2 export validated against the pilot implementation in v0.5.
- **Per-tokenizer measurements** (Llama 3, Qwen, Gemma). → Benchmark.
- **Stage 2 pilot** on a real repository before more design work (Sonnet top-5 #5, Fable M9). → v0.4.
- **Round-trip test** and JSON Schema. → v0.3.

## 4.5 Final result

**The answer to the research question did not change, but it became more precise.**

- **Q1:** No existing language jointly provides unification (G1), per-fact provenance (G2), visible inference and conflicts (G3), budgeting (G4), named omissions (G5), and small-LLM legibility (G7) for knowledge extracted from existing systems. SysML v2 is semantically almost sufficient, and KDM targets extraction from code, but neither is practical for this purpose.
- **Q2:** Yes. The best parts of each area can be combined, and the result is best described as a **profile + concrete syntax + budgeted projection + toolchain** over SysML v2 / C4 semantics, with PROV-style provenance.
- **On the original goal** ("the whole context in a low-end LLM without losing anything important"): it is impossible as stated for non-trivial systems, and both reviewers agreed with that reframing. The achievable goal is a small, cacheable core, plus a task slice, plus **named** omissions. Six of its seven guarantees are now mechanically checkable (§3.5); the seventh, determinism, follows from the algorithm's fixed inputs. One residual risk is not checkable: a needed fact outside the heuristic relevant set. That risk is now measured directly by the silent-absence rate.
- **Maturity:** v0.1 was scored 5/10 and 6/10, a sound research framing with an under-specified mechanism. v0.2 addresses every finding both reviewers shared and most single-reviewer findings, but **v0.2 itself has not been re-reviewed**, and nothing has been measured on a real repository. The decisive evidence is the stage-2 pilot and the benchmark (roadmap v0.4–v0.6).
