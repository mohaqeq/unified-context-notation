# Review of UCN v0.6 (Fable 5.1)

## Verdict

The engineering is honest and mostly careful, and docs/08 §8.3 states the main limits itself. But the pilot result
"pre-registered outcome: supported" is close to vacuous. H1 and H2 were bound to hold at ceiling (C, with no docs at
all, succeeded 11/11 and violated 1/9). The only hypothesis that told the arms apart, H3 (tokens), is explained by
document size, and the author names that confound. The pilot did not exercise the one thing UCN claims to add over
AGENTS.md + import-linter: prose-only rules, governed deviations, evidence and staleness. On the evidence so far, UCN
is a well-made **config generator and governance wrapper** for import-linter. It has not shown that it keeps agents
more consistent. Two v0.6 checks have real correctness bugs: staleness misses deleted code, and evidence matches the
wrong test file.

## Findings, by severity

### 1. High: the pilot cannot discriminate, and "supported" mostly follows from the decision rules

- Recomputed from `trials/pilot/results/results.json`:
  - Success: C 11/12, L 24/24, B 24/24.
  - Tempting-task violations: C 1/9, L 0/18, B 0/18.
  - Median tokens: C 44,814, L 55,213, B 51,054. B is below L in 22/24 runs and 12/12 tasks (sign test p = 0.0005
    two-sided).
  - The docs' numbers are correct.
- H1 (B − L ≥ −10 pts) and H2 (B ≤ L) hold trivially when both arms are at 100% and 0%. The rules made "supported" the
  default outcome of an experiment where nothing happens. A null experiment should yield *inconclusive*.
- The task notes in `meta.json` admit that 8 of 9 temptations have a trivial clean route:
  - T01: `textwrap`
  - T09: `slice(i, i+len)`
  - T02: `sys`/`__version__`
  - and so on.

  Only T05 forces a refactor, and it produced the only violation.
- docs/07 §7.7 said the pilot needed "≥ 30 tempting tasks with external authors, k ≥ 3". The pilot ran 9 tempting
  tasks, k = 2, all Claude authors. The pre-registration quietly lowered the author's own bar.
- docs/08 §8.3 claim 2 is vacuous: "the projection is about 30 times smaller … and nothing the tasks needed was lost."
  The tasks needed no docs: C succeeded on all valid tasks.
- H4 is reported as "yes, but 1 event". It should read "not tested".

### 2. High: the pilot does not test UCN's claimed differentiators

- All 9 tempting tasks target the 4 rules import-linter already enforces. None targets:
  - `LazyDialects`, the prose-only rule;
  - the click/jinja conventions;
  - a deviation, an expiry, evidence or staleness.
- The grading also could not have caught a LazyDialects break:
  - Rule→dialect imports are already reported as `KNOWN-CONFLICT` under `LazyDialectsVsCode`.
  - `recon.py:118` counts only VIOLATION/CONFLICT.
  - Findings are keyed by an element-pair message, so a 13th offending module gives no new message.
- "Validator agrees with import-linter" (§8.3 item 4) holds by construction: the model was hand-built to mirror those 4
  contracts (`model.deny.ucn` line 4).
- The projector was never stressed:
  - The whole model is 4.1 KB, and contexts are 1.9–2.6 KB. The budget of 2500 never binds.
  - Every context carries essentially the same 4 contracts (compare `trials/pilot/contexts/T01` and `T09`).
  - So the pilot compares "the 4 contracts in 2 KB" with "65 KB of AGENTS.md". The proposed L-short control (§8.4.2)
    is the necessary next step, not a nice-to-have.

### 3. High: the token saving is small in absolute terms and not uniquely UCN

- Per-task medians over C:
  - B adds +4.7k tokens.
  - L adds +10.7k.
  - C already sits at ~42–45k of fixed overhead.
- So the "11% saving" is ~6k tokens per task. It is fully explained by L being told to read five AGENTS.md files.
- docs/07 §7.8 already saw the same pattern ("the check in the loop is what prevents violations, not UCN as such").
- The pilot repeats that result. It adds no new evidence for the notation.

### 4. Medium: reproducibility and process gaps

- **Tasks were not locked by the pre-registration.**
  - `fcc29eb` contains only PREREGISTRATION.md.
  - Tasks, graders and reference patches first appear in `d6c95b0`, with the results.
  - Nothing proves the graders were fixed before the runs.
  - Example: T04's `test_later_duplicate_wins` tests behaviour the spec leaves open. It was then excluded post hoc,
    which was reasonable but post hoc.
  - Commit the tasks, or their hashes, with the pre-registration.
- **"Fails on unchanged code" proves almost nothing.** 11 of 12 tasks add a new function, so the grader fails on an
  ImportError. Only T12 has a real "fail before" check.
- **The published `spec.json` is not the spec that ran.**
  - `repo` is a placeholder.
  - `validator` is the relative path `tools/ucn_validate.py`. Used as-is, the B prompt (`recon.py:58`) tells the agent
    to run `python tools/ucn_validate.py model.ucn` from the *sqlfluff* root, where that file does not exist.
- **Compliance is unverified.** No transcripts are published, so nothing shows that B agents ran the validator or that
  L agents ran docker. "In the loop" is asserted, not shown.
- **Token provenance is unclear.** `usage.json` comes from outside the harness, and the metric (cache reads included or
  not?) is not defined.
- **Contamination risk.**
  - Agent shells started in the UCN repo, where `trials/sqlfluff/model.deny.ucn` and the docs describing the rules
    live. Arms C and L could read UCN material.
  - `spec.json`'s `tasks: trials/pilot/tasks` suggests graders and reference patches were inside that repo at grading
    time. The claim "never there" needs evidence: shell logs, or the file paths used at run time.

### 5. Medium: bugs in `tools/recon.py`

- **Silent import-linter pass (`recon.py:111-113`).**
  - If import-linter crashes, there is no `Contracts:` line, so `broken = -1` and nothing is counted. One example is a
    syntax error in the agent's code.
  - A new `.importlinter`/`setup.cfg` with zero contracts gives `0 kept, 0 broken`, which also passes. New files are
    not checked for tampering.
  - Treat a missing line, or a total ≠ 4, as a violation.
- **Stale JUnit results (`recon.py:101-106`).**
  - `_junit/{run}.xml` is not deleted before the docker run.
  - If the container fails to start, for example from a mount error or a missing image, the previous grading's XML is
    re-read and can report success.
- **Tampering of `context.ucn` is never detected (`recon.py:124-126`).**
  - The expression requires `c == "model.ucn"`, so edits to `context.ucn` cannot be flagged.
  - The pre-registration defines tampering to include `context.ucn`, and docs/08 claims none occurred. The harness
    cannot support that claim.
  - Deleting `model.ucn` is also invisible: an untracked deleted file does not appear in `git status`.
- **New violations are diffed by message text (`recon.py:118`).** Any new import between an already-violating element
  pair is invisible. This is harmless on sqlfluff's clean baseline, but wrong in general.

### 6. Medium: content-hash staleness can miss deleted code

`ucn_validate.py:1062-1065` and `stamp` at `:1350-1353` "follow" a reference to the *first* line anywhere in the file
whose whitespace-normalized hash matches. I reproduced this with a `src: app/a/x.ts:5@…` pointing at `  return;`
inside `g()`:

- Insert one line in `g`: the validator reports "moved to line 2" (inside `f`), and `--stamp` rewrites the reference to
  line 2.
- Delete `g()` entirely: **no provenance finding at all**, because `f`'s `return;` still matches.

Any common line breaks staleness: `}`, `return`, `pass`, a decorator, a blank-ish line.

- Hashing one line also means a body change under an unchanged signature is never stale. The tests stamp signature
  lines (`tests/test_tools.py:452`).
- **Fix:** hash a span (the referenced line through the end of its block), require a unique match before following,
  and prefer the nearest match.
- **Smaller issue:** with `--accept-changed`, a reference past the end of the file is left unchanged and not reported
  (`:1358`).

### 7. Medium: evidence matches the wrong test file

In `cases_for` (`ucn_validate.py:563`), `c["file"].endswith(test_file.lstrip("./"))` has no path-boundary check.
Verified:

- `src: tests/test_api.py` matches a JUnit case from `tests/legacy_tests/test_api.py`.
- `src: test_api.py` also matches `tests/unit/mytest_api.py`.
- So a requirement can be reported *met* by an unrelated passing test.

Two related problems:

- `lstrip("./")` strips characters, not a prefix.
- Evidence has no freshness binding. A JUnit file from any old commit counts as "latest results", so the CI gate needs
  a commit or timestamp check.

### 8. Low

- `pilot_eval.py` computes "success" on control tasks only (n=6), while H1 in docs/08 uses all 24 runs. Say which one
  the decision used.
- The "exact McNemar on paired runs" pairs arbitrary run indices (L1 with B1). These are independent agents, not
  matched pairs. A per-task cluster test is the honest choice.
- `stamp` rewrites the whole model file even when nothing changed, which also normalizes line endings.
- The 77 unit tests pass. None covers `recon.py`, which is the code that produced the headline result.

## Usefulness: UCN vs AGENTS.md + import-linter/dependency-cruiser

What the evidence supports:

- The validator matches import-linter and dependency-cruiser semantics on real repos (docs/07 §7.8).
- It exports working configs for both.
- It found one real prose-vs-code contradiction (LazyDialects).
- Deny-list upkeep is near zero.
- A short, checked rule summary is cheaper for agents than long prose, by about 6k tokens per task.

What the evidence does not support:

- That UCN prevents violations better than the checker alone. In two experiments the checker in the loop did all of
  that work.
- That the notation, as opposed to brevity, matters.
- That the requirements/evidence/rationale layer helps agents at all. It is untested.

Recommendations:

1. **Reposition.** Present UCN as "one rules file that generates import-linter/dependency-cruiser configs, adds expiring
   approved deviations, and emits a compact agent summary". Do not present it as an agent-consistency layer until a
   trial shows that.
2. **Next trial (gate further features on it):**
   - Only tasks where C violates in ≥50% of runs.
   - At least half the temptations target rules the existing checker *lacks* (LazyDialects, the click/jinja
     conventions, a requirement with a test).
   - An L-short arm.
   - A non-Claude agent and non-Claude task authors.
   - Tasks committed with the pre-registration.
   - Transcripts published.
   - A decision rule where a ceiling means *inconclusive*.
3. **Fix before relying on them:**
   - the `recon.py` silent-pass, stale-XML and tampering bugs;
   - span hashing with a uniqueness check in staleness;
   - path-boundary matching and freshness in evidence.
4. **Cut or freeze until justified by data:** the large-model projector machinery (budgets, stubs, accounting), which
   no real model has exercised. Also freeze the growing vocabulary (authority modes, gates, rationale). Each feature
   adds spec surface with no measured agent benefit.
