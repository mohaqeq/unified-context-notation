# Example: Shortly (URL shortener)

A small, fictional system that shows UCN v0.3 end to end: a model, a small **real TypeScript codebase** it is checked against, and two projections for agents.

| File | What it shows | Tokens (o200k) |
|---|---|---|
| [model.ucn](model.ucn) | The full model. Mode `forward` since baseline `6794ead`; container `Web` is still reverse engineered (`authority: source`). 7 requirements (two with typed `param:`), 4 containers, 4 components, 5 functions, 3 decisions, 2 conventions (one with a machine `check:`), 3 tests, 1 accepted conflict, 1 deviation | 2,049 |
| [src/](src/) | The code: `api/*.ts`, `web/app.tsx`, tests, a k6 script | — |
| [card.L0.ucn](card.L0.ucn) | System card: goals, containers, global pins, the conflict, the active deviation; scoped pins named; the rest counted | 299 |
| [slice.alias.ucn](slice.alias.ucn) | Projection for "implement custom aliases", budget 1200: core first, task slice last, relevant omissions named | 843 |

## Consistency validation (model vs code)

```sh
python tools/ucn_validate.py examples/shortly/model.ucn --today 2026-11-05
```

```
mode forward, baseline 6794ead, 13 code files (13 scanned), 12 conforming dependencies/bindings, 6 ms
VIOLATION      architecture Api.Guard depends on Api.Links, which the model does not allow  [api/guard.ts -> api/links.ts]
KNOWN-CONFLICT parameters   RateLimit.maxLinksPerHour = 100 per hour vs api/guard.ts#LIMIT_PER_HOUR = 1000 (conflict RateLimitValue)
WAIVED         architecture Api.Stats -> Db waived by deviation StatsDirectDb (expires 2027-03-31)  [api/stats.ts -> api/db.ts]
MODEL-UPDATE   architecture Web depends on Api.AliasesEnabled (authority: source): add a relation or a deviation  [web/app.tsx -> api/config.ts]
INFO           traces       req Resolve / Expire / Blocklist / RateLimit: nothing verifies it; Alias planned
```

Each finding class is planted on purpose:

- **Violation.** `guard.ts` imports a helper from `links.ts`. The architecture doesn't allow Guard → Links, and the Api container is model-authoritative, so CI fails. Fix the code or record a deviation.
- **Known conflict.** `RateLimit` says 100 per hour and the bound constant says 1000. Because `conflict RateLimitValue` (accepted at adoption) is `about` RateLimit, this is reported, not failed.
- **Waived.** `stats.ts` reads Postgres directly. `deviation StatsDirectDb` allows it until 2027-03-31; with `--today 2027-04-01` it becomes a violation.
- **Model update.** `web/app.tsx` imports a server flag. `Web` is still `authority: source`, so the finding says the *model* is behind, not the code.
- **Conforming.** Everything else: `create` and `generate` against `codeLength = 7`, `DbAccess` (`only api/db.ts imports pg`), test files against what they verify, `src:` references to code.

Switching modes changes the reading of the same code. With `mode: reverse`, the Guard → Links finding becomes a MODEL-UPDATE. The adopt gate (`--gate adopt`) blocks while the violation remains.

## Projections

```sh
python tools/ucn_parse.py examples/shortly/card.L0.ucn --against examples/shortly/model.ucn
python tools/ucn_parse.py examples/shortly/slice.alias.ucn --against examples/shortly/model.ucn
```

Both pass the projection check: budget, global pins present, scoped pins present or named, every reference closed, nothing invented, every model node present, named, or counted. They are hand-written following §3.5; a generated version comes with the default projector (roadmap v0.4).

Things to notice:

- **Inference is visible.** Contract clauses an LLM wrote while reading code are `[inferred]`, line by line. Logic is code-authoritative even in forward mode, so these don't block the adopt gate.
- **As-is vs to-be.** `req Alias` is `lifecycle: planned`. The code has no alias yet, and the slice says nothing satisfies or verifies it.
- **Governance in context.** The accepted conflict and the active deviation are in the card, so an agent neither copies the deviation nor "fixes" it.

Caveats: token counts use o200k (tiktoken 0.14.0). The codebase is a toy written to exercise each check; real repositories bring path aliases, generated code and dependency injection (see [05 §5.3](../../docs/05-usefulness-and-tooling.md#53-how-much-can-tools-do-without-an-llm)).
