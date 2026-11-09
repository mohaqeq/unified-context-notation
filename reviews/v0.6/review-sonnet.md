# UCN v0.6 review (Sonnet, independent, skeptical)

## Verdict

The v0.6 tooling is competent and the 77 tests pass. The pilot is honestly reported but nearly uninformative on the question UCN exists to answer. Its "supported" label is vacuous. H1 and H2 were satisfied by a ceiling (24/24 vs 24/24, 0 vs 0). The only discriminating hypothesis (H3, tokens) is confounded by context size and by unequal prompts. The one real signal is that Haiku on this repo rarely breaks the rules even with no docs (1/9). That is evidence against the need for any of this on this task class. On current evidence UCN's value over AGENTS.md plus import-linter is not demonstrated. Keep the checker and the conflict/deviation records; stop investing in the notation until a size-matched control is run.

## Findings, by severity

### 1. "Supported" is vacuous; H3 is confounded (high)
- I recomputed from `trials/pilot/results/results.json`. C: 11/12 success, 1/9 violations, median tokens 44,814. L: 24/24, 0/18, 55,213. B: 24/24, 0/18, 51,054. These match docs/08. B is lower than L in 22 of 24 pairs and on 12 of 12 task means.
- H1 (B-L >= -10 points) and H2 (B <= L) hold trivially at the ceiling. There was no discordant pair, so McNemar has no power. A rule that cannot fail is not a test.
- H3 compares an agent given about 65 KB of AGENTS.md (L) with one given a 460-650 token slice (B). docs/08 concedes this. Three confounds are not noted:
  - The prompts differ. L is told to run a docker import-linter command; B is told to run a python script.
  - The projection is built from the task text, so it hands the agent the relevant rule. T05's context lists `Core forbids ... Utils` because the task names those paths. A real agent has no such oracle.
  - The B prompt explains `forbids`, `deviation` and the deny-list policy, which is priming that L lacks.
- The no-docs arm C is the cheapest (44.8k). B costs about 14% more than C for one avoided violation in nine runs. docs/08 never says so, so "B is consistently cheaper" is true only against L.
- The sign test (p=0.0005) is correct arithmetic, but runs within a task are not independent. The source of `usage.json` (cache reads included or not) is undocumented.

### 2. Pre-registration is weaker than advertised (medium)
- The commit order is right (fcc29eb 09:42, ea94212 10:01, results d6c95b0 10:23). The prose rules predate the runs.
- The tasks, graders, `spec.json` and reference patches first appear in d6c95b0, after the results. Nothing pins the task set or graders before the runs, so "committed before any run" holds only for the prose.
- The T04 exclusion follows the pre-registered rule, but it was noticed only because C failed. The grader asserts `test_later_duplicate_wins`, which the task text never specifies. "Fails on clean, passes on reference" cannot catch over-constrained graders, because the same person writes both. Other graders may over-constrain too; L and B happened to pass.
- H4 rests on a single event (T05-C1). docs/08 says so.
- Only 5 of 12 graders were independently re-run.

### 3. Grading code has fail-open paths (medium)
- `tools/recon.py` `grade_one`: `broken = ... if "broken" in line else -1`, then `violations = bool(validator_new) or broken > 0`. If docker or import-linter fails to start, the line is empty and violations is 0. A failed checker reads as clean. All 60 lines here were well formed (only "4 kept, 0 broken" and "3 kept, 1 broken"), so this data is unaffected.
- Tampering is `pyproject.toml` changed, or `model.ucn` differing from the model. The `context.ucn` clause is dead code, because the expression also requires `c == "model.ucn"`. Other contract locations (`setup.cfg`, `.importlinter`, `tox.ini`) are not checked. The L violation count uses the workspace's possibly tampered config.
- Edits to `tools/ucn_validate.py` are not detected. B agents invoked it by absolute path outside the workspace. docs/08's "no run wrote to that repository" has no check behind it.
- Validator findings are baseline-subtracted by message text, so a new finding with identical text to a baseline one is hidden.
- Agents could not run the project's tests, which removes the main real-world feedback loop. Single repo, single weak model, all-Claude authors.

### 4. Validator evidence and stamp bugs (medium; items marked verified were run)
- `cases_for` (`tools/ucn_validate.py`, around line 560) uses a plain `endswith` with no path boundary. Verified: results for `mytest/test_x.py` count for a test node whose src is `test/test_x.py`.
- With no `file` attribute in JUnit, classname `test_a` matches both `tests/unit/test_a.py` and `other/test_a.py`. Verified: 1 match each. A pass in the wrong module can mark a requirement met.
- `test_file.lstrip("./")` strips a character set, not a prefix.
- A requirement is met if any verifying test passed, even when another verifier is missing or skipped. With no `case:` glob, a whole file counts, so one unrelated passing test in it suffices.
- Nothing checks that the JUnit results are fresh or belong to the current commit.
- Staleness hash covers one line. Changes to the rest of the function go undetected. When a line is not at its pinned position, `moved[0]` takes the first identical line, so common lines (`return None`, `}`) are silently re-pointed to the wrong place. `src: f:0@hash` indexes `lines[-1]`. `stamp` ignores `src:` lines with trailing text.

### 5. docs/08 over- and under-claims (low-medium)
- To its credit it states the ceiling effect and the size confound.
- Over-claims: "B is not worse than the real lightweight stack" (uninformative at 24/24); "nothing the tasks needed was lost" (the projection was built from the task); "the method works end to end" is fair.
- Missed threats: dev-set overlap (the validator and model were developed on this repo, docs/07); weak temptation (C violated in 1/9, so most "tempting" tasks do not tempt Haiku); task text itself names the rule-relevant modules; one model family; no repeat of failing runs.

### 6. Usefulness
- Across docs/07 and docs/08 the validator never found a violation that import-linter did not. What AGENTS.md plus import-linter lacks:
  - requirement -> test -> result links;
  - hash-pinned references, and rationale and deviation records with expiry;
  - open conflicts between documented rules and code. The `LazyDialectsVsCode` conflict is a real catch: AGENTS.md says never import dialects, yet 12 modules do.
- None of those has been shown to change agent behavior. The pilot's import-direction tasks cannot exercise them, because import-linter already covers that ground.
- The notation and the projector show no demonstrated advantage over a trimmed AGENTS.md. The L-short control that docs/08 proposes is the missing comparison.

## What to cut or change next
1. Run L-short (size-matched AGENTS.md excerpt plus import-linter) before any further claim about the format. Commit tasks, graders and rules together by hash.
2. Keep only tasks where C violates in at least half the runs. Add requirement-type tasks so evidence and rationale are actually exercised.
3. Fix `recon.py`: a missing "Contracts:" line is a grading error. Fix the tampering expression. Hash the validator and contract config.
4. Fix `cases_for`: path-boundary matching, and unique-module resolution.
5. Freeze stamp, rationale links and multi-level projection until a trial shows they matter. Keep conflict and deviation records, the only part with a demonstrated unique catch.
6. State in docs/08 that B costs more than C, and that "supported" was reached by rules sitting at a ceiling.

Evidence: recomputation from `trials/pilot/results/results.json`; `tools/pilot_eval.py` output (EXTEND); `python -m unittest tests.test_tools` (77 OK); snippets run against `cases_for`.
