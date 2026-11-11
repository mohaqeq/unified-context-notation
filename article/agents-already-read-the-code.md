---
title: "I built a context language for AI coding agents. Three experiments said they didn't need it"
date: 2026-11-10
tags: [ai-agents, software-architecture, experiments, negative-results]
---

# I built a context language for AI coding agents. Three experiments said they didn't need it

Every team that uses coding agents ends up writing the same file. It's called `AGENTS.md`, `CLAUDE.md` or
`.cursorrules`: a few kilobytes of prose that say "the API layer must not import the CLI", "never use Django signals",
"gift cards are bearer instruments". The agent is supposed to read it and behave.

Prose is ambiguous, it drifts from the code, and it costs tokens on every run. So I asked a question that seemed
obviously worth asking:

> Can a formal, compact language for requirements, architecture and decisions make coding agents follow them better
> than prose does?

I spent a few weeks building that language, a checker for it, and the experiments to test it. The result was negative,
and I think the reason is more interesting than the language.

## What I built

**UCN (Unified Context Notation)** is a line-oriented text format. It sits on top of existing ideas rather than
replacing them: C4-style containers and components, EARS-style requirements, ADR-style decisions and design-by-contract
rules. A model looks like this:

```text
component Api: public Python API
  code: sqlfluff/api/**
  forbids Cli
convention NoDjangoSignals: call logic explicitly, never through signals
  check: only saleor/*/{migrations/**,apps.py} imports django.db.models.signals
req PaymentHistoryProjection: customers see payment history only through an allowlisted projection
  rationale: docs/adr/0010-order-payment-history-is-a-projection.md
deviation ErrorsTypeImports: errors may import rules, for type checking only
  expires: 2027-11-01
```

It comes with three tools:

1. **A deterministic validator** that checks the model against the code: the import graph, conventions, links from
   requirements to tests, expiring deviations, and conflicts between what the docs say and what the code does.
2. **A projector** that cuts a task-specific slice of the model to fit a token budget, and names everything it leaves
   out.
3. **An exporter** that compiles the same rules to import-linter and dependency-cruiser configs.

The idea was simple: give the agent the projection and the validator, and it will do better than with a wall of prose.

## The tools worked

Before any agent experiment, I pointed the validator at real repositories. It found real problems:

- **sqlfluff:** its own `AGENTS.md` says never import dialect modules directly. 12 modules do. Neither the docs nor the
  project's import-linter contracts catch this.
- **excalidraw:** circular, undeclared runtime dependencies between published packages.
- **Agreement with the established tools:** run in containers against the real import-linter and dependency-cruiser,
  the exported configs gave identical results, after five bugs that only running the real tools could expose.
- **Upkeep:** replaying 600 commits of sqlfluff history, a deny-list model needed zero edits.

So the checker is real. The question was whether the *context* helps agents.

## Experiment 1: the pilot (60 runs)

I pre-registered the hypotheses and decision rules, then ran a pilot on sqlfluff:

- **Tasks:** 12, written by a *different* model that had never seen UCN. 9 were "tempting": the obvious implementation
  breaks an architecture rule.
- **Graders:** each task had a hidden grader, proven to fail on the unchanged code and to pass on a reference
  solution.
- **Arms:** a Claude Haiku agent got one of three setups:
  - nothing;
  - the project's AGENTS.md plus import-linter in the loop;
  - the UCN projection plus the validator in the loop.

| Arm | Success | Rule breaks (tempting tasks) | Median tokens |
|---|---|---|---|
| No docs | 11/12 | 1 of 9 | 44.8k |
| AGENTS.md + import-linter | 24/24 | 0 of 18 | 55.2k |
| UCN + validator | 24/24 | 0 of 18 | 51.1k |

By my own pre-registered rules, UCN was "supported": as successful, no more violations, cheaper. Then two independent
reviews pointed out what I should have seen myself:

- **A ceiling.** Both checked arms were perfect, and even the no-docs agents almost never broke a rule, so the
  hypotheses could not fail.
- **The token saving was just size.** The UCN context was 2 KB, the AGENTS.md files 65 KB.
- **Not the hard cases.** The tasks only tested rules import-linter already enforces.

I rewrote the conclusion: *inconclusive*.

## Experiment 2: a codebase where requirements matter (42 runs)

The obvious objection was that sqlfluff is a developer tool with technical rules. UCN should shine where *product
requirements and architecture decisions* decide what is correct. So I scanned 31 repositories for customer-facing
products with written decisions, and picked **saleor**, an e-commerce API with ADRs like these:

- *A gift card is a bearer instrument. Rejecting a restricted card must never reveal who it belongs to.*
- *Customer payment history is an allowlisted projection, never the raw transaction.*
- *Balance changes must be atomic; never read, decide and write back.*
- *Never use Django signals. Never read `settings.SITE_ID`.*

These are exactly the rules an agent cannot infer from types or imports. I modelled all 12 ADRs, linked them to 253 of
saleor's tests as evidence, and had two separate model instances write 20 tasks whose shortcuts break those rules.

This time every grader had to pass three checks in a container:

- the behaviour tests fail on the unchanged code;
- the reference passes everything;
- a deliberately naive shortcut **passes the behaviour tests but fails a rule test**.

A model from a different family (Nemotron, via OpenRouter's free tier) reviewed every grader for assertions the ticket
did not justify. The task hashes were committed before any run.

The pre-registration included a screen. First, run agents with **no docs at all**, 3 times per tempting task, and keep
only the tasks where they break the rule at least twice. Only then compare the arms.

**2 of 14 tasks survived the screen.** Agents with no AGENTS.md and no ADRs kept the documented rules in 27 of the 33
runs where a rule could be measured, and broke one in only 6. (In the other 9 runs, the grader review had removed
every rule test.) The experiment stopped there, as pre-registered.

## Why: the agents read the code

The interesting part is *how* they kept rules they had never been told:

- **Race-safe balance updates:** the agent found saleor's existing `gift_card_qs_select_for_update` helper and used it.
- **"No signals":** the agent called the new logic explicitly from the existing balance paths, because that is what
  the surrounding code does.
- **A new management command:** the agent created the related settings row explicitly, not through a `post_save` hook.

The task authors expected the shortcut: a signal, a read-modify-write loop, a module-level cache. An agent that reads
the code next to its change doesn't take it. In a well-kept codebase, the correct pattern sits right where the change
goes, and the code itself is the context.

Across three repositories (sqlfluff, cosmicpython, saleor) I saw the same thing:

1. **The code is the strongest context.** Agents copy local patterns. A rule that the surrounding code already follows
   needs no documentation for an agent.
2. **When a rule does get broken, a check catches it.** In every experiment, the arm with a checker in the loop had
   zero violations, whether the checker was import-linter or UCN's validator. The checker did the work, not the
   context.
3. **Shorter context is cheaper.** That's true, but any tight summary would do; it isn't an argument for a new
   notation.

## What I kept

UCN is now a checker and governance tool, not an agent-context format. That part solved real problems in every trial:

- **One file for the rules**, compiled to import-linter and dependency-cruiser configs.
- **Checks for rules that are not imports:** `only <glob> uses <regex>`, convention checks, and requirements linked to
  test results.
- **Governance the existing tools lack:** approved deviations that expire, and recorded conflicts between docs and code.

## What I'd still like to know

Guidance could still matter where there is no good code to copy:

- **Eroded codebases**, where the code next to a change shows the *wrong* pattern.
- **Greenfield work**, where nothing exists yet.
- **Weaker agents.**
- **Rules whose correct pattern lives far from the change.**

The harness for testing that is ready and published: pinned tasks, proven graders, cross-model grader review and
screening.

## Lessons about running these experiments

- **Pre-register, but make a ceiling count as "inconclusive".** My first decision rules turned "nothing happened" into
  "supported".
- **Screen before you compare.** Forty-two cheap runs saved me from about 150 runs comparing arms on tasks nobody
  fails.
- **Prove the temptation.** A grader must fail on a naive shortcut, or you're measuring nothing.
- **Get a reviewer from another model family.** Same-model authors and reviewers share blind spots.
- **Publish the tool-call logs.** "The agent ran the checker" should be something anyone can verify.

---

Everything is open: the tool, the format, both pre-registrations, all 32 tasks with their hidden graders, the results,
and the agents' tool-call logs. See [github.com/mohaqeq/unified-context-notation](https://github.com/mohaqeq/unified-context-notation).

*The task authors, agents and most reviewers in these experiments were Claude models (Haiku, Sonnet, Fable). One
grader review used Nvidia Nemotron.*

*Correction (2026-11-11): an earlier version said the no-docs agents kept the rules in "33 of 42 runs". The right figure is 27 of the 33 runs where a rule could be measured (6 broke a rule; in 9 runs every rule test had been excluded by the grader review).*
