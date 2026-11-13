# 11. Next phase: where agents break rules, and what prevents it cheaply

Status: **design, not yet pre-registered or run.** This document turns the results so far, two outside sources and the
reader questions on the article into one plan.

## 11.1 What we know, and what changed the question

Phase 1 asked: *does a formal context language make agents follow a project's rules better?* The answer was no
([08](08-pilot.md), [10](10-saleor-screen.md)). Three observations from it shape the next question:

1. **Agents copy the code next to their change.** With no docs, they kept the rules in 27 of 33 measurable runs.
2. **The 6 violations were not random.** In all three tasks with violations, the right pattern was *not* next to the
   change:

   | Site condition | Example (saleor) | Violations |
   |---|---|---|
   | **Contradicting:** nearby code shows the wrong pattern | 24 call sites resolve the site the single-site way, against the documented rule | 3 of 3 runs |
   | **Elsewhere:** the right pattern exists, but in other modules | gift cards are deactivated in every GraphQL deletion path; the task added deletion in a background job | 2 of 3 |
   | **Different kind:** the rule lives in mutations, the change was a query | app-only webhook identifier | 1 of 3 |
   | **Consistent:** the right pattern is next to the change | 8 other tasks | 0 of 24 |

   With 6 runs this is a lead, not a finding.
3. **All 6 were behaviour rules.** None could be caught by an import or pattern check, only by tests.

So the question for phase 2 is no longer about a notation:

> **What decides whether an agent breaks a project rule, and what is the cheapest thing that prevents it?**

## 11.2 Ideas taken from outside

### Ron Pressler, "Why Writing Correct Software Is Hard" (2016)

| Point in the article | What it means for this project |
|---|---|
| Verification is the hardest problem there is; "there are no easy solutions to hard problems" | A reason to doubt that any single notation, prompt or tool makes agents correct in general. It is an argument, not evidence about agents |
| "Correctness does not decompose": verified modules do not give a verified whole | Rules that span modules (the "elsewhere" case above) are where local reasoning fails, for agents as for people |
| Language abstractions do not make arbitrary properties cheaper to verify | A richer context language was never likely to help in general. Phase 1 found this the expensive way |
| Yet "some programs, some of the time, for some properties": restrict the property | Check **local, cheap properties** (imports, patterns) mechanically, and leave the rest to tests |
| A call for empiricism: study the programs and bugs people actually write. The essay cites a University of Toronto study in which a simple linter for one error-handling pattern would have prevented 33% of catastrophic failures in four distributed systems | Build a **taxonomy of the rule violations agents actually make**, by cause and by the cheapest detector. Then build the few checks that pay off |

### Sarkar and Mondal, "Autonomous Coding is Exponentially Costly" (SSRN 7531259)

| Claim in the paper | What it means for this project |
|---|---|
| Token cost stays manageable while tests are weakly interdependent, and grows exponentially past a threshold of interdependency (the "wall") | Phase 1 tasks were small and local, below the wall. A prediction we can test: **the cost of a checker in the loop grows with how coupled the task is** |
| Rejecting bad changes (checks, harnesses) raises the number of tries; domain-specific languages lower it | Guidance and checks may be complements. Guidance might not change the final violation rate when a check is present, but it could **cut retries**. Phase 1 never measured retries |
| Restricting a change to one component bounds the interdependency | Enforced architecture boundaries might lower agent cost, not just protect structure |

The paper is a theoretical bound with strong assumptions, and it is not peer-reviewed. Its "interdependency of
tests" is not the same thing as "rules touched per task", so H3 and H4 below are **inspired by** the paper, not
derived from it. They stand or fall on the data.

### Reader questions on the article

| Question | Where it goes |
|---|---|
| "What kinds of rule violations did the checker catch?" | The taxonomy (study D). It also exposed a miscount, now corrected |
| "Did the violations cluster in less consistent parts of the codebase?" | The main hypothesis (study A) |
| "Checks will destroy your token budget through retries" | Measured directly (studies B and C) |

## 11.3 Hypotheses

The **site condition** is defined on one axis: the precedents for the rule inside the package being changed.

- **consistent:** most precedents follow the rule;
- **none:** there is no precedent in the package (phase 1's "elsewhere" and "different kind" cases);
- **contradicting:** most precedents break the rule.

| # | Role | Hypothesis | Refuted if |
|---|---|---|---|
| H1 | **primary** | Unguided agents break rules more often at *none* and *contradicting* sites than at *consistent* sites | The lower 95% bound of the difference (contradicting − consistent, and none − consistent) is not above 0 |
| H2 | **primary** | At non-consistent sites, the project's **existing checks in the loop** (its own tests and the validator) prevent fewer behaviour-rule violations than **written guidance** does, because existing tests rarely cover the rule at a new site | Generic-check-only has a violation rate at least 15 points below prose-only |
| H3 | secondary | With a rule-specific check in the loop, adding guidance lowers cost: fewer tokens and fewer failed check runs | Median tokens and failed check runs are not lower with guidance |
| H4 | exploratory | The token overhead of a check in the loop grows with the number of rules a task touches | Reported as a direction only |
| H5 | descriptive | A few cheap local checks would catch a large share of the observed violations | Fewer than 30% of violations are detectable by an import or pattern check |

H2 changed after review. In the first draft the check arm could run tests close to the hidden grader, so it could not
fail. The check is now split into **generic** (what the project already has) and **rule-specific** (a test written for
the rule, never the hidden one).

## 11.4 Design

Four studies, run in order. Each has a gate, so a null result stops the spending early.

### Study A: does the site condition cause violations? (about 150 runs)

- **Factor:** the site condition, three levels, for the same rule and the same kind of task.
- **How the levels are made:**
  - Where saleor already has all three kinds of site for a rule, use them as they are.
  - Otherwise apply a small, pre-registered **seeding patch**. Patches go in **both directions** (making a consistent
    site contradicting, and a contradicting one consistent), so that "being patched" is not confused with the
    condition. A **patched-but-consistent control** (a neutral refactor of the same size) is added for each seeded rule.
  - Each seeded base must still pass saleor's tests.
- **Rules:** 8 to 10. Half come from phase 1; **half are a new sample**, chosen by the task author from the ADRs
  without seeing phase 1 results. The two halves are reported separately, to control for selection.
- **Runs:** 5 per cell, agents with no docs, on **both Haiku and Sonnet**.
- **Analysis:**
  - a mixed-effects logistic regression: violation ~ site condition, with a random intercept per rule;
  - a permutation test over rules, because 8 to 10 clusters estimate the variance poorly;
  - odds ratios with confidence intervals, and a leave-one-rule-out check.
- **Decision:** continue to study B if H1 is not refuted for at least one non-consistent level. Otherwise the phase
  ends, and that result is reported.

### Study B: what prevents violations where they happen? (about 250 runs)

- **Sites:** the *none* and *contradicting* cells from study A.
- **Arms:**

  | Arm | Guidance | Check in the loop |
  |---|---|---|
  | none | no | no |
  | prose | the relevant doc excerpt, size-matched | no |
  | generic check | no | the project's existing tests and the validator |
  | rule check | no | a test written for the rule (never the hidden one) |
  | prose + rule check | yes | the rule test |
  | UCN + rule check | UCN context | the rule test |

- **New in this phase:** agents can run the project's tests in a container. This removes the biggest gap in phase 1.
- **Measures:** violations, task success, tokens, tool calls, and **check runs before the first pass** (retries).
- **Reading:**
  - H2 compares *prose* with *generic check* on violations.
  - H3 compares *rule check* with *prose + rule check* on tokens and failed check runs.
  - *UCN + rule check* against *prose + rule check* is the last, cheap test of the notation.
- **Grader sensitivity** is reported per rule, from the three-way proof: a violation only counts as far as the hidden
  tests can see it.

### Study C: does check overhead grow with coupling? (about 60 runs, exploratory)

- **Factor:** the number of documented rules a single task touches: 1, 2 or 4, built by combining study A tasks in one
  ticket.
- **Arms:** *none* and *rule check*.
- **Measure:** the token ratio check/none at each level. H4 predicts that the ratio rises.
- **Status:** exploratory, because three levels cannot show an exponential curve. A flat ratio would still be useful
  evidence against "checks destroy the budget" at this scale.

### Study D: a taxonomy of agent rule violations (analysis, no new runs)

- **Input:** every violating run from phase 1 and from studies A to C.
- **Coding per violation:**
  - rule type: import, code pattern or behaviour;
  - site condition;
  - the cheapest detector that would have caught it: import check, pattern check, existing test, new test, or review
    only.
- **Output:** a table of violation classes by frequency and detector cost, and the list of checks that would have
  caught the most for the least. This tests H5, and it decides what the `ucn` tool should grow next.

### Method rules carried over from phase 1

- Tasks and graders come from an author that never sees UCN. Every grader is proven three ways: it fails on the
  base, passes on the reference, and a naive shortcut passes the behaviour tests but fails a rule test.
- The pre-registration is committed with SHA-256 hashes of tasks, graders and seeding patches, with line endings
  fixed in `.gitattributes` so the published files match the hashes.
- Graders are reviewed by a model from another family. Because the last reviewer over-flagged, a flag now needs a
  one-line concrete counter-example (a reasonable implementation that would fail). Flags without one are recorded but
  not applied.
- A ceiling or a floor counts as inconclusive.
- Tool-call logs are published. The validator is hashed at grading time, not at preparation.
- **Agents:** Claude Haiku as the main agent. One stronger model (Sonnet) and one non-Claude model run a subset, to
  see whether effects shrink with capability and hold outside one model family.

## 11.5 Cost and order

| Step | Runs | Decision after it |
|---|---|---|
| 0. Build: test-running container for agents, seeding patches, retry logging | 0 | The base and each seeded base pass saleor's tests |
| 1. Study A | about 150 | Decision on H1; then split the repository (§11.7) |
| 2. Study B | about 250 | H2, H3, and the notation's last test |
| 3. Study C | about 60 | Exploratory |
| 4. Study D and the write-up | 0 | Tool roadmap |

One run on saleor used a median of 82k tokens in the screen. Agents that can run tests will use more.

## 11.6 Review of this plan

Weak points found while writing it, and what is done about each:

| Risk | Mitigation |
|---|---|
| **Seeding patches are artificial.** A patched neighbourhood may not look like real erosion | Prefer natural sites; report natural and seeded cells separately; keep patches minimal and published |
| **"Site condition" is judged by the experimenter** | Define it operationally before the runs: the count of correct and incorrect precedents within the changed file and its package. Have a second model code the sites blind |
| **Task wording can leak the rule or the site** | The author sees only the ticket template and the code, never the hypothesis. The grader reviewer also checks the ticket for hints |
| **Few runs per cell** | 5 runs per cell; analyse by condition across rules, with rules as the cluster. No per-rule claims |
| **Letting agents run tests changes the baseline** | That is the point: it is closer to real use. The *none* arm gets the same container, without the rule tests |
| **Rule tests in the loop are close to the hidden grader** | The in-loop tests are the project's own existing tests plus the validator. The hidden rule tests stay hidden, and the overlap is reported |
| **Study C cannot show an exponential** | Labelled exploratory. Only the direction of the ratio is reported |
| **Same model family for authors, agents and reviewers** | A non-Claude grader reviewer and a non-Claude agent subset. Still a stated limit |
| **The SSRN paper's model may not apply** | It is used only to generate H3 and H4, which stand or fall on the data |

### Independent review (Claude Sonnet, a fresh instance)

A second model reviewed the first draft. What it changed:

| Finding | Change |
|---|---|
| H2 could not fail: the check arm could run tests close to the hidden grader | The check is split into generic and rule-specific, and H2 is restated so that either side can win |
| No hypothesis had a refutation threshold; no primary or secondary roles | Added in §11.3 |
| The three site levels were not on one axis; "silent" had no phase 1 evidence | One axis: precedents in the package. "Elsewhere" and "different kind" become *none* |
| Seeding changes more than the condition | Patches in both directions, plus a patched-but-consistent control |
| Rules came from sites that already produced violations (selection) | Half the rules are a new, blind sample, reported separately |
| The 40% / 15% gate was arbitrary; 3 runs per cell is thin | A decision on the confidence bound; 5 runs per cell; a stated model and a permutation test |
| Haiku-only main results | Study A runs on Haiku and Sonnet |
| Overreach in the use of both sources | Wording corrected in §11.2: the 33% figure is attributed to the study the essay cites, and H3 and H4 are "inspired by" the paper |
| Moving to a new repository now is premature | Accepted: see §11.7 |

Not adopted: a formal power calculation. Phase 1 gives too few events (6) to estimate an effect size honestly, so
study A is sized by budget and its confidence intervals are reported as they come.

## 11.7 Where this work should live

**Decision: study A is prepared and run from this repository. If H1 survives, phase 2 moves to a new repository,
split from a tagged commit.**

The first draft proposed moving at once. The review argued that this was premature, and it is right: before the
decision on H1 there may be nothing to move, and copied scripts would drift from the originals.

| Consideration | Stay here | New repository |
|---|---|---|
| The question | It was about UCN | From study B on it is about agent behaviour in general. UCN is one arm out of five |
| Readers | People looking for the tool find 300 research files | Tool users and experiment readers each get a clean repository |
| Data growth | Fine for study A | Studies B and C would outgrow the tool many times over |
| Overhead | None | Only worth paying once the phase is known to continue |

When the split happens:

- **Tagged starting point:** this repository gets a tag, and the new repository starts from it. That keeps one
  provenance chain for the phase 1 tasks and their hashes.
- **Harness:** it becomes a small package that installs `ucn` as a dependency. It is not a copy that can drift.
- **What stays here:** the tool, its tests, the example, the article and the phase 1 record, with a link forward.
- **Proposed name:** `agent-rule-compliance`.
