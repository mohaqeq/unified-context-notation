# 8. Pilot: reconstruction tests on sqlfluff

The pilot follows the pre-registration in [trials/pilot/PREREGISTRATION.md](../trials/pilot/PREREGISTRATION.md), which was
committed before any run (commit `fcc29eb`). Everything needed to rerun it is in [trials/pilot/](../trials/pilot/): the
tasks with hidden graders and reference patches, the spec, the B contexts, the per-run results and the JUnit files.

## 8.1 Setup

| Item | Value |
|---|---|
| Repository | sqlfluff at `1682e11` (269 package files, 4 import-linter contracts) |
| Model | [trials/sqlfluff/model.deny.ucn](../trials/sqlfluff/model.deny.ucn) (deny-list policy) |
| Tasks | 12 written by two Claude Sonnet instances that never saw the UCN model or tools: 9 *tempting* (the direct route breaks one of the 4 rules), 3 *control* |
| Graders | Each author showed that the grader **fails on the clean checkout** and **passes on the reference patch**, and that the reference keeps all 4 contracts. I re-ran 5 of the 12 independently (T03, T05, T08, T10, T12) with the same result, and applied T01's "naive" route to confirm both checkers catch it (import-linter: 3 contracts broken; validator: `Core forbids Cli` plus transitive layer breaks) |
| Agents | Claude Haiku, one fresh agent per run. C × 1, L × 2, B × 2 per task = 60 runs |
| Arms | **C**: no agent docs (AGENTS.md removed). **L**: the project's AGENTS.md files plus import-linter (in a container) in the loop. **B**: `context.ucn` from `tools/ucn_project.py` (budget 2500; actual 460–650 tokens) plus `tools/ucn_validate.py` in the loop; AGENTS.md removed |
| Grading | `tools/recon.py grade`: hidden grader in a container (success = all tests pass), import-linter in a container plus the validator with the pristine model (violation = any broken contract or new validator finding), tampering check (edits to the model or the contracts) |

### Changes after pre-registration, all made before the first run

- **Harness fix:** the projector put the task text twice into the context header, which wasted about 300 tokens of
  B's budget. The fix was committed before any run (`ea94212`).
- **Sealing:** the graders, reference solutions and prompts were moved out of the directory that holds the workspaces,
  so an agent could not find them by listing nearby folders.

### Weaknesses the reviews found in the setup ([09](09-review-synthesis-v0.6.md))

- **The pre-registration pinned only the prose.** The tasks, graders and reference patches were written after
  `fcc29eb` and first committed with the results (`d6c95b0`). Nothing proves they were fixed before the runs. They
  were not changed, but the record cannot show that.
- **"Fails on unchanged code" is weak evidence for 11 of 12 tasks.** Those tasks add a new function, so the grader fails
  on an ImportError. Only T12 fails on behaviour.
- **The bar set in docs/07 was lowered.** [07 §7.7](07-trial-results.md) asked for at least 30 tempting tasks by
  external authors with k ≥ 3. The pilot ran 9 tempting tasks with k = 2, and all authors were Claude models.

### Compliance and contamination audit (after the runs, from the agent transcripts)

The tool calls of every run are in [trials/pilot/transcripts/](../trials/pilot/transcripts/) (commands and paths
only).

- **Every checked agent ran its checker:** all 24 L runs ran import-linter, and all 24 B runs ran the validator.
- **No run read the sealed graders, the reference patches or another run's workspace.**
- **No C or L run touched the UCN repository.** Three B runs referred to it beyond running the validator:
  - T03-B2 listed `tools/`;
  - T07-B1 referred to the validator's path;
  - T04-B1 read its own `context.ucn` through a relative path.

  None of them read a model or a doc.
- **Tampering, re-checked by hash:**
  - every B workspace's `model.ucn` equals the pristine model;
  - every `context.ucn` equals a fresh projection (the projector is deterministic);
  - no run changed `pyproject.toml`, `setup.cfg` or `.importlinter`;
  - every import-linter run reported all 4 contracts.

## 8.2 Results

| Arm | Runs | Success | Violations (tempting runs) | Median tokens | Median seconds | Median tool calls |
|---|---|---|---|---|---|---|
| C (no docs) | 12 | 11 | 1 of 9 | 44,814 | 53 | 8.5 |
| L (AGENTS.md + import-linter) | 24 | 24 | 0 of 18 | 55,213 | 66 | 9 |
| B (UCN context + validator) | 24 | 24 | 0 of 18 | 51,054 | 63 | 10 |

- **Tampering:** none in any arm. No run edited `model.ucn`, `context.ucn` or the contracts in `pyproject.toml`.
- **The one violation (T05-C1):** the C agent made `core.rules.context` import `sqlfluff.utils.identifers`, which was
  the shortcut the task author predicted. import-linter reported 1 contract broken. The validator independently
  reported `Core forbids Utils` and the cycle it creates. Every L and B agent on T05 moved the logic into core instead.
- **The one failure (T04-C1):** the only failing grader test was `test_later_duplicate_wins`. The task text does not say
  what should happen when a key is repeated, and the agent chose to raise `ValueError`. That test checks behaviour the
  spec leaves open. Under the pre-registered rule, a grader that fails a correct implementation is excluded. With
  T04 excluded, C succeeds in 11 of 11. The exclusion does not change L or B, which passed all of T04.

### Hypotheses (decision rules fixed in the pre-registration)

| # | Rule | Observed | Holds? |
|---|---|---|---|
| H1 | B − L success ≥ −10 points | 100% vs 100% (0 points); exact McNemar p = 1.0, no discordant pairs | yes |
| H2 | B violations on tempting tasks ≤ L | 0 of 18 vs 0 of 18 | yes |
| H3 | median tokens B < L | 51,054 vs 55,213. B is lower in 22 of 24 paired runs and in **12 of 12 tasks** (task means, sign test p = 0.0005); median per-task difference −11.5% | yes |
| H4 | B < C and L < C on tempting violations | 0 and 0 vs 1 of 9 | not tested: a single event |

**Pre-registered outcome: supported**, because H1, H2 and H3 hold. **But H1 and H2 held only because both arms hit a
ceiling** (100% success, 0 violations), and so did the no-docs arm on 11 of 11 valid tasks. A decision rule that turns
a null experiment into "supported" is a design flaw; both reviewers flagged it. The honest reading:

- **H1 and H2 are inconclusive.**
- **H3 holds**, but it is explained by document size (§8.3).
- **Supported** is what the pre-registered rules return. It is not evidence that UCN keeps agents more consistent.

The next pre-registration counts a ceiling as *inconclusive*.

As predicted in the pre-registration, `tools/pilot_eval.py` returns **EXTEND**. It has no upkeep minutes, and its
success comparison uses only the 6 control-task pairs (H1 above uses all 24). Pairing run k of L with run k of B is
arbitrary, because the runs are independent agents, so the McNemar test is formal only. The per-task sign test on
tokens is the appropriate cluster test.

**Cost against no docs:** B used about 14% more tokens than C (median 51.1k vs 44.8k). L used about 23% more. Against
the baseline, B is the cheaper of the two checked arms, not cheap in absolute terms. Of a 42–45k base, the saving over
L is about 6k tokens per task. Token counts are the agent harness's total per agent run.

## 8.3 What this does and does not show

**It shows:**

1. **The method works end to end.**
   - The tasks and hidden graders were written independently, and every grader was proven to fail before the change
     and pass after it.
   - All third-party code ran in containers.
   - Grading took 9 minutes for 60 runs, with no manual judgement.
2. **B is cheaper than L on every task** (about 11%, or 6k tokens). This is mostly because B reads a 2 KB summary
   instead of 65 KB of prose.
3. **The validator agrees with import-linter** on the one real violation. This is partly by construction: the model
   was written to mirror those 4 contracts.

The pilot does **not** show that B is "not worse" than L in any useful sense. Even the no-docs arm succeeded on every
valid task.

**It does not show:**

1. **That UCN prevents violations better than AGENTS.md.**
   - Both checked arms scored 0. Even unguided agents took the shortcut in only 1 of 9 tempting runs.
   - The tasks were less tempting for Haiku than their authors expected, so the pilot has a **ceiling effect** on
     violations. It cannot tell B and L apart there.
2. **That the UCN *format* causes the token saving.**
   - The five AGENTS.md files total about 65 KB, against about 2.2 KB for `context.ucn`.
   - The saving may come from giving the agent *less, targeted* text rather than from the notation. Targeted context
     is the projector's purpose, but a fair test needs a size-matched prose excerpt as a control.
3. **Generality.**
   - The pilot covers one repository and one agent model.
   - Task authors, agents and the reviewers are all Claude models.
   - Agents could not run the project's tests, which removes a feedback loop real agents have.

4. **Anything about UCN's differentiators.** All 9 temptations target the 4 rules import-linter already enforces. None
   targets the prose-only `LazyDialects` rule, the click and jinja conventions, a deviation, evidence or staleness.
   The grading also could not have counted a new `LazyDialects` break, because it is filed under the known conflict.
5. **Anything about the projector.**
   - The whole model is 4.1 KB, so the 2500-token budget never came into play.
   - Every context carries essentially the same 4 contracts.
   - The task text names the modules involved, so seed selection was easy.

**Other threats:**

- **Agent shells started in the UCN repository**, so an agent could have read UCN files. The audit above shows none
  read a model or a doc, and the hidden graders were never there.
- **Dev-set overlap.** The model and the validator were developed on this same repository (docs/07).
- **Over-constrained graders.** T04 tested behaviour the task leaves open. It was found only because C failed. Other
  graders may also over-constrain, but L and B happened to pass them.
- **Small sample.** Each arm had at most 24 runs, clustered by task. Any effect smaller than "large" is out of reach.

**Grading bugs found by the reviews, and their effect here:**

- import-linter crashing, or reporting fewer contracts, was counted as clean;
- a stale JUnit file could be re-read;
- edits to `context.ucn` could not be flagged as tampering.

All three are fixed in `tools/recon.py`, with tests. None affected this pilot: every run reported 4 contracts, the
JUnit folder was new, and the hash audit above found no tampering.

## 8.4 Next steps (gating any new feature)

Based on what the pilot could not resolve, and on both reviews:

1. **Commit the tasks and graders (or their hashes) with the pre-registration**, and count a ceiling as inconclusive.
2. **Harder tasks.**
   - Choose temptations where the rule-breaking route is clearly shorter and the correct route needs a refactor. T05
     was the only task of that kind.
   - Keep only tasks where C breaks the rule in at least half the runs.
   - At least half the temptations target what import-linter lacks: the prose-only rule, the conventions, and a
     requirement with a test.
   - Have an independent reviewer check each grader for behaviour the task text does not specify.
3. **A size-matched control (L-short).** Give the agent the AGENTS.md paragraphs relevant to the task, trimmed to the
   size of `context.ucn`, plus import-linter. This separates "less text" from "UCN text".
4. **A non-Claude agent and non-Claude task authors**, a second repository, and agents that can run tests in a
   container.
5. **Publish the tool-call logs** with the results, as was done here after the fact.
