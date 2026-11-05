# Example: Shortly (URL shortener)

A small, fictional system that shows UCN v0.2 end to end.

| File | What it shows | Tokens (o200k) |
|---|---|---|
| [model.ucn](model.ucn) | The full model at L2: 2 goals, 2 terms, 7 requirements, 4 containers, 3 components, 5 functions with contracts, 1 state machine, 1 event, 1 feature flag, 1 environment, 3 decisions, 2 conventions, 3 tests, 1 source conflict | 1,751 |
| [card.L0.ucn](card.L0.ucn) | System card: goals, containers, global pins, the open conflict; scoped pins named; the rest counted | 280 |
| [slice.alias.ucn](slice.alias.ucn) | `π(M, "implement custom aliases", 1200)`: core first, task slice last, relevant omissions named, the irrelevant tail counted | 821 |

The card and slice are **hand-written** following §3.5, then **machine-checked** against the model (budget, pins, closure, no invented facts, stub accounting):

```sh
pip install tiktoken==0.14.0        # optional; without it token counts are estimates and say so
python tools/ucn_parse.py examples/shortly/model.ucn --lint --tokens
python tools/ucn_parse.py examples/shortly/card.L0.ucn --against examples/shortly/model.ucn --tokens
python tools/ucn_parse.py examples/shortly/slice.alias.ucn --against examples/shortly/model.ucn --tokens
```

Both projections pass. A generated slice (by a prototype projector) replaces the hand-written one in v0.3.

The same graphs as canonical JSON (`--tokens`, o200k, tiktoken 0.14.0):

| File | UCN | JSON (compact) | JSON (pretty) |
|---|---|---|---|
| model | 1,751 | 3,080 (1.8×) | 5,345 (3.1×) |
| card L0 | 280 | 461 (1.6×) | 837 (3.0×) |
| slice | 821 | 1,465 (1.8×) | 2,469 (3.0×) |

These ratios compare *syntaxes* of the same content. Whether the denser one is also easier for small models to use is a separate question for the benchmark (§3.10).

Things to notice:

- **Cross-layer trace.** `req Create` ← `satisfies` ← `component Links` ⊃ `fn create` ← `verifies` ← `test CreateTests`. In the slice the link is shown at the requirement as `satisfiedBy Links, Codes`, so a small model doesn't have to search for it.
- **Inference is visible.** Every contract clause an LLM wrote while reading code is marked `[inferred]`, line by line. The signatures and relations come from deterministic tools (`derived`, inherited from `system Shortly [derived]`).
- **As-is vs to-be.** `req Alias` is `lifecycle: planned`. The current code has no alias parameter, and nothing satisfies or verifies Alias yet. The slice says so in a tool-written `note:`.
- **A structured conflict.** `conflict RateLimitValue` has an id, `about` links to `RateLimit` and `Guard.limit`, and one `side` per source: ticket#14 says 100 per hour, the code and its passing test say 1000. Because the test asserts 1000, `GuardTests` does **not** verify `RateLimit`, and lint reports that.
- **Pins in two scopes.** Global pins (`Abuse`, `CodeImmutable`, the conflict) are in every projection. The security requirements are scoped pins: *named* in the card, and *inlined* in the alias slice, because the slice touches `Guard`, which satisfies them.
- **Named omissions.** The slice names what is relevant but didn't fit (`event LinkCreated`, `fn Links.resolve`, `decision ImmutableCodes`, …) and only counts the irrelevant tail.
- **Lint finds real gaps.** `Resolve`, `Expire` and `RateLimit` have no verifying test; `Alias` is planned.

Caveats:

- Token counts use o200k. Small open models use other tokenizers, so per-model counts are needed (§3.10).
- This model is tiny. Compression and accuracy claims can only be measured on real repositories (roadmap v0.6).
