# saleor: the next verification repository

## Why this repository

The repo was chosen after scanning 31 repositories, including the author's own. The pilot showed that sqlfluff is the
wrong kind of test: its rules are technical import rules that agents pick up from the code anyway. The next test needs
a **customer-facing** product where **requirements and architecture decisions**, not code patterns, decide what is
correct.

saleor (headless e-commerce, Python/Django, 4,374 code files, commit `1d707dc`) fits:

| Property | saleor |
|---|---|
| Customer-facing domain | storefront checkout, orders, payments, gift cards, multi-site |
| Decisions with rationale | 12 ADRs in `docs/adr`, most of them business rules (gift cards are bearer instruments; payment history is an allowlisted projection; assignment survives user deletion) |
| Rules the code does not show | security and privacy (a rejected gift card must not reveal its owner), multi-tenancy (never read `settings.SITE_ID`), "no Django signals", "no in-process state". No import-linter or similar config exists |
| Baseline for the L arm | a 31 KB `AGENTS.md` |
| Tests | pytest with Postgres; runs in [trials/containers/saleor-tests](../containers/saleor-tests/Dockerfile) |

Runner-up: **openstatus** (TypeScript, 9 ADRs on services-layer isolation and audit trails). **Sylius** has 855
user-perspective Gherkin specs, but it needs a PHP import scanner.

## Done so far (verified)

- **Model:** [model.ucn](model.ucn) covers all 12 ADRs and 4 AGENTS.md rules:
  - 7 requirements, 7 decisions, 6 rules and 1 convention;
  - 8 components;
  - 7 test links.
- **Clean checkout:** 0 violations.
- **Evidence:** the 7 linked test files ran in the container (253 passed, about 4 min). `--results` reports 7 elements
  verified and none failing.
- **Three machine checks:**
  - `NoDjangoSignals`, an import check. A probe file importing `django.db.models.signals` is reported. This needed a
    validator fix, because Python third-party imports were recorded by top-level package only. The fix has a
    regression test.
  - `NoSiteIdReads`, the new `only <glob> uses <regex>` check. On first run it found 3 readers in tests and fixtures,
    which the rule does not target, so tests are exempt.
  - `NoBlockingWaits` (`time.sleep` outside tests): no findings.
- **Not covered by tests:** `GiftCardBearer`. The rules `AtomicBalance`, `NoInProcessState` and `ManualAssignmentOnly`
  are stated for agents only.

## Gaps found in UCN

1. **Behaviour rules are covered only through linked tests**, for example "a rejected gift card does not reveal its
   owner" (`GiftCardNoLeak`). Design rules like "atomic balance updates" have no check at all.
2. **`from django.db.models import signals`** records `django.db.models`, so the import convention misses this form.
3. **Speed:** 10–100 s on 4,374 files with the built-in scanner, depending on the OS file cache, against about 1 s on
   smaller repos. This needs `--deps` from a real dependency tool or a faster scanner before CI use.

## Next steps

1. Write the pre-registration, committed **with** the tasks and graders (or their hashes).
2. Write about 20 tempting tasks, ideally by a non-Claude author, where the shortcut breaks an ADR or a rule. Examples:
   - "show customers their transactions": the shortcut opens `Order.transactions`;
   - "react to an order save": the shortcut is a signal;
   - "explain why a gift card was rejected": the shortcut leaks the owner.

   Hidden graders check the **requirement**.
3. Screen the tasks with no-docs agents (keep those broken in at least half the runs). Then run four arms: no docs,
   AGENTS.md + tests, size-matched prose, and the UCN context + validator.
