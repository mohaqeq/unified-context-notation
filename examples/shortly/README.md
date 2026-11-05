# Example: Shortly (URL shortener)

A small, fictional system that shows UCN end to end.

| File | What it shows | Tokens (o200k) |
|---|---|---|
| [model.ucn](model.ucn) | The full model at L2: 7 requirements, 4 containers, 3 components, 5 contracts, 1 state machine, 3 ADRs, 3 tests, 1 source conflict | 1,289 |
| [card.L0.ucn](card.L0.ucn) | System card, always in context: goals, containers, pinned facts, the open conflict, and one stub | 247 |
| [slice.alias.ucn](slice.alias.ucn) | Hand-simulated `π(M, "implement custom aliases", 1200)`: core first, task slice last, stubs for what was left out | 624 |

The same graphs serialized as JSON by the parser (`python tools/ucn_parse.py FILE --tokens`):

| File | UCN | JSON (compact) | JSON (pretty) |
|---|---|---|---|
| model | 1,289 | 2,056 (1.6×) | 3,513 (2.7×) |
| card L0 | 247 | 382 (1.5×) | 600 (2.4×) |
| slice | 624 | 843 (1.4×) | 1,364 (2.2×) |

Things to notice:

- **Cross-layer trace.** `req Create` ← `satisfies` ← `component Links` ⊃ `fn create` ← `verifies` ← `test CreateTests`.
- **Provenance.** Every fact has a `src:`. `machine LinkLife` is `[inferred]` because it was reconstructed from code, not stated anywhere.
- **Conflict surfaced.** ticket#14 says 100/hour and the code says 1000/hour. That is shown in every projection, not resolved silently.
- **Pinned facts** (`CodeImmutable`, `ImmutableCodes`, security requirements) appear in both the card and the slice.
- **Lint finds gaps.** `--lint` reports that `Resolve`, `Expire`, and `Alias` have no verifying test.

Caveats:

- Token counts use the o200k tokenizer. Small open models use other tokenizers, so the ratios are indicative only.
- This model is tiny. The real compression claim (raw source → UCN) can only be measured on real repositories (roadmap v0.5).
