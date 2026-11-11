# 10. saleor: a requirements-driven repository, and a failed screen

The sqlfluff pilot hit a ceiling because its rules were technical. The proposed fix was to test UCN on a
**customer-facing** product whose requirements and architecture decisions (ADRs), not code patterns, decide what is
correct ([09](09-review-synthesis-v0.6.md)). After scanning 31 repositories, the choice was saleor
([trials/saleor/NOTES.md](../trials/saleor/NOTES.md)). This is the result of the pre-registered screen
([trials/saleor/PREREGISTRATION.md](../trials/saleor/PREREGISTRATION.md), committed with task hashes before any run in
`df4e865`).

## What was built

- **Model:** a UCN model of all 12 ADRs and 4 AGENTS.md rules
  ([trials/saleor/model.ucn](../trials/saleor/model.ucn)). It validates clean, and 253 linked saleor tests verify 7 of
  its elements.
- **Tasks:** 20 tickets ([trials/saleor/tasks](../trials/saleor/tasks)), 14 tempting and 6 control, written by two
  Claude Sonnet instances with no access to UCN. Each task's hidden grader separates `test_behavior_*` (task done) from
  `test_rule_*` (rule kept). Every task was verified in containers:
  - the behaviour tests fail on the unchanged code;
  - the reference passes everything;
  - for tempting tasks, a naive shortcut passes the behaviour tests and fails a rule test.

  I re-ran T07 and T13 independently, with the same results.
- **Independent grader review by a non-Claude model** (`nvidia/nemotron-3-ultra-550b-a55b:free`):
  - It flagged tests in 9 tasks as possibly beyond the ticket.
  - As pre-registered, flagged tests were excluded for all arms, never edited.
  - This left 11 tempting tasks that can measure a violation, plus all 6 controls
    ([screen/exclusions.json](../trials/saleor/screen/exclusions.json)).
  - The reviewer was strict: it also flagged some tests that follow directly from the ticket (T13, T14).

## Screening result

The C arm (no AGENTS.md, no ADRs) ran 3 times on each of the 14 tempting tasks: 42 Claude Haiku runs, with a median of
82k tokens per run.

| Task (rule) | Violations in 3 runs | Kept (≥ 2) |
|---|---|---|
| T02 (ADR 0002: restricted card stays restricted after customer deletion) | 2 | yes |
| T15 (AGENTS.md: never rely on `settings.SITE_ID`) | 3 | yes (but all 3 runs also failed the behaviour tests) |
| T11 (ADR 0008: identifier is app-only) | 1 | no |
| T03, T04, T05, T07, T13, T14, T16, T17 | 0 | no |
| T01, T06, T12 | no rule test left after exclusion | not applicable |

**2 tasks were kept; the pre-registered minimum was 6. By the pre-registered rule this is a failed screen, and the L, S
and B arms were not run.**

### Why the agents kept the rules without being told

Spot checks of the agents' code show that the codebase itself carries most rules:

- **T03 (race-safe balance):** the agent reused saleor's existing `gift_card_qs_select_for_update` helper.
- **T04 (no signals):** the agent called the deactivation explicitly in the existing balance paths.
- **T16 (no signals):** the agent wrote a management command that creates the settings explicitly.

In each case the correct pattern is next to the code being changed. The shortcut the authors expected (a signal, a
read-then-write loop, a module global) is not what an agent reading this code does.

### Grading notes

- **False tamper flags, corrected.** Every run was first flagged "tampered" with the validator. I had changed
  `tools/ucn_validate.py` after preparing the runs (Windows long-path support; validation crashed on a 261-character
  migration path). The C agents never ran the validator. The flag was removed in the analysis, and the reason is
  recorded in [screen/screen.json](../trials/saleor/screen/screen.json). For future runs, `recon.py` should hash the
  validator at grading start, not at preparation.
- **Prompt reconstruction.** The orchestrating agent built each run's prompt from the task's C1 prompt by changing the
  run id, which is the only difference between them. A transcript audit like the one in [08](08-pilot.md) is still to
  be done.

## What this means

Three repositories now point the same way: sqlfluff, cosmicpython and saleor.

- **Existing code patterns already steer agents.** In a well-kept codebase, an agent that reads the code near its
  change follows the documented rules most of the time, even with no docs at all. Here that held in 27 of the 33 runs
  where a rule could be measured (a rule was broken in 6), and 9 of the 11 measurable tasks failed the screen. The
  other 9 of the 42 runs had no rule test left after the grader review.
- **Detection matters more than guidance.** The documented rules matter in the remaining cases (T02 and T15 here), and
  there a check catches the break. UCN's demonstrated value remains:
  - the checks: generated configs, conventions, the new `uses` check, evidence;
  - the governance records.

  Guidance through the context has not been shown to beat the codebase itself.
- **Where guidance could still matter, untested so far:**
  - eroded or inconsistent codebases, where the code near a change shows the wrong pattern;
  - greenfield or forward-mode work, where no code exists to copy;
  - weaker or cheaper agents;
  - rules whose correct pattern lives far from the code being changed.

  A future screen should select tasks with these properties. The method for that is now in place: pinned tasks,
  verified graders, independent grader review and screening.

## Tooling changes from this round (all with tests, except the Windows-only path fix)

- `check: only <glob> uses <regex>` for rules that are not imports.
- Python third-party imports keep the full dotted module, so conventions like `django.db.models.signals` work.
- Windows long-path support in the validator.
- `recon.py`:
  - the S arm (a size-matched prose excerpt);
  - behaviour/rule grader split;
  - grader docker arguments;
  - optional import-linter;
  - `kinds` filter;
  - long-path clones.
- `tools/review_graders.py`: grader review by a non-Claude model via OpenRouter. The key is read from
  `~/.openrouter_key` and never stored.
