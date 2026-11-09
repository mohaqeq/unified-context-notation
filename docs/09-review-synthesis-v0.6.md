# 9. Review synthesis for v0.6 and the pilot

Two independent reviews were written by different models, neither of which wrote the pilot tasks:

- [reviews/v0.6/review-fable.md](../reviews/v0.6/review-fable.md) (Claude Fable 5.1)
- [reviews/v0.6/review-sonnet.md](../reviews/v0.6/review-sonnet.md) (Claude Sonnet, a fresh instance)

Both re-computed the pilot numbers from `trials/pilot/results/` and found them correct.

## 9.1 Where the reviews agree

| Point | Fable | Sonnet | Verdict |
|---|---|---|---|
| "Supported" is close to vacuous. H1 and H2 held at a ceiling, which even the no-docs arm almost reached | yes | yes | **Accepted.** docs/08 now calls H1 and H2 inconclusive. The next pre-registration counts a ceiling as inconclusive |
| H3 (tokens) is explained by document size, not by the notation | yes | yes | **Accepted.** An L-short control is required before any claim about the format |
| The pilot does not test UCN's differentiators (prose rules, conventions, deviations, evidence, staleness) | yes | yes | **Accepted.** At least half the next temptations must target what import-linter lacks |
| The pre-registration pinned only the prose, not the tasks and graders | yes | yes | **Accepted.** Stated in docs/08. Next time the tasks or their hashes are committed with the rules |
| `recon.py` fails open when import-linter gives no result, and cannot flag `context.ucn` edits | yes | yes | **Fixed**, with tests |
| Evidence matching has no path boundary, so an unrelated test can mark a requirement met | yes | yes | **Fixed**, with tests |
| Staleness follows the first identical line, so common lines are re-pointed wrongly | yes | yes | **Fixed**, with tests |
| Compliance is unverified (did agents run their checker?) | yes | partly | **Checked:** 24/24 L runs ran import-linter and 24/24 B runs ran the validator. Tool-call logs are published |
| UCN's demonstrated unique value is governance (conflicts, deviations), not the notation or the projector | yes | yes | **Accepted** as the current positioning (§9.3) |

## 9.2 Findings and what was done

| # | Finding | Action |
|---|---|---|
| 1 | `recon.py`: a missing `Contracts:` line meant no violation | A missing line, or a contract count different from `contracts` in the spec, now counts as a violation and is reported as a `grading_error` |
| 2 | `recon.py`: a stale JUnit file could be re-read if the container failed | The file is deleted before each grading |
| 3 | `recon.py`: tampering check (dead `context.ucn` clause; deleted model invisible; other contract files and the validator unchecked) | `prepare` records hashes of `context.ucn` and the validator. `grade` compares the model, the context and the validator by hash, and flags any change to `pyproject.toml`, `setup.cfg`, `.importlinter` or dependency-cruiser config. Tampering counts as a violation |
| 4 | `recon.py`: a relative validator path in the spec breaks the B prompt | The path is made absolute in `prepare` and `grade` |
| 5 | `cases_for`: plain `endswith`, and `lstrip("./")` strips a character set | Paths now match only on a `/` boundary, and leading `./` and `../` segments are removed as a prefix |
| 6 | Staleness: follows the first identical line; ignores duplicates; follows trivial lines | A move is followed only when exactly one distinctive line (at least 10 non-space characters) matches. Several matches mean "fix by hand". `}`, `return;` and `pass` are never followed |
| 7 | `src: f:0@hash` indexed the last line | Line numbers outside 1..N are reported, and `--stamp` leaves them for review |
| 8 | `--stamp --accept-changed` silently skipped a reference past the end of the file, and rewrote the model even with no change | It now reports "past the end of the file", and writes only when a reference changed |
| 9 | Single-line hashing misses body changes under an unchanged signature | **Documented, not changed.** Span hashing is deferred until a trial shows staleness matters at all |
| 10 | Evidence is not tied to a commit (old JUnit files count) | **Deferred.** CI produces fresh results per run. A commit check fits when evidence is used in a gate |
| 11 | A bare pytest classname (`test_a`) can match two modules | **Deferred.** It matches pytest's own ambiguity. A `file` attribute (`junit_family=xunit2`) resolves it |
| 12 | Validator findings are diffed against the baseline by message text | **Documented.** Harmless on a clean baseline. A new import between already-violating elements is hidden |
| 13 | docs/08 over-claims ("not worse", "nothing lost", agreement with import-linter) and omits threats (dev-set overlap, the docs/07 bar lowered, ImportError graders, C cheaper than B, arbitrary McNemar pairing) | **Corrected** in docs/08 |

Tests: 77 → 85, all passing. New tests cover the boundary matching, ambiguous and trivial moves, invalid line numbers,
and three `recon.py` cases with the containers faked: failing closed, not re-reading old results, and catching
tampering.

## 9.3 Decisions

1. **Positioning.** On current evidence, UCN is:
   - **one rules file** that generates working import-linter and dependency-cruiser configs (shown to agree with both
     tools on real repositories);
   - with **governance** those tools lack: approved, expiring deviations, and recorded conflicts between documented
     rules and code (the `LazyDialects` catch);
   - plus a **compact, checked summary** for agents, which is cheaper than long prose.

   It is **not yet shown** to keep agents more consistent than the checker alone. In both agent experiments
   ([07](07-trial-results.md), [08](08-pilot.md)), the check in the loop did the work.
2. **Freeze.** No new vocabulary, projector features (budgets, stubs, multi-level detail) or governance modes until a
   trial shows an agent benefit. Keep them in the spec as they are. The tools stay maintained.
3. **Next experiment.** Run the design in [08 §8.4](08-pilot.md#84-next-steps-gating-any-new-feature) before anything
   else:
   - tasks committed with the pre-registration;
   - temptations that work (C breaks the rule in at least half the runs) and target non-import rules;
   - an L-short control;
   - a non-Claude agent;
   - a ceiling counted as inconclusive.

## 9.4 Limits of this review

- **The reviewers are Claude models**, like the agents and the task authors. Shared blind spots are possible. A review
  by a different model family or a human expert is still missing.
- **The reviewers could not run docker**, so they checked the grading logic by reading it and by re-computing the
  numbers from the published results.
