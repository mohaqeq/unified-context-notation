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
| H4 | B < C and L < C on tempting violations | 0 and 0 vs 1 of 9 | yes, but 1 event |

**Pre-registered outcome: supported** (H1, H2 and H3 hold). As predicted in the pre-registration, `tools/pilot_eval.py`
returns **EXTEND**: it has no upkeep minutes, and the success difference cannot be resolved at this sample size.

## 8.3 What this does and does not show

**It shows:**

1. **The method works end to end.**
   - The tasks and hidden graders were written independently, and every grader was proven to fail before the change
     and pass after it.
   - All third-party code ran in containers.
   - Grading took 9 minutes for 60 runs, with no manual judgement.
2. **B is not worse than the real lightweight stack on task success.** The projection is about 30 times smaller than
   the AGENTS.md files, and nothing the tasks needed was lost.
3. **B is consistently cheaper.** It used fewer tokens on every task (about 11% less).
4. **The validator agrees with import-linter** on the one real violation, as it did in the earlier trials
   ([07 §7.8](07-trial-results.md)).

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

**Other threats:**

- **Agent shells started in the UCN repository.** The agents' shells started in the UCN repository's directory, so an
  agent could have read UCN files. The hidden graders were never there, and no run wrote to that repository.
- **Small sample.** Each arm had at most 24 runs, clustered by task. Any effect smaller than "large" is out of reach.

## 8.4 Next steps

Based on what the pilot could not resolve:

1. **Harder tasks.** Choose temptations where the rule-breaking route is clearly shorter and the correct route needs a
   refactor (T05 was the only task of that kind). Keep only tasks where C breaks the rule in at least half the runs
   before comparing B and L.
2. **A size-matched control (L-short).** Give the agent the AGENTS.md paragraphs relevant to the task, trimmed to the
   size of `context.ucn`, plus import-linter. This separates "less text" from "UCN text".
3. **A different agent family** and a second repository, using `recon.py` unchanged.
4. **Let agents run tests** in a container, which is closer to real use.
