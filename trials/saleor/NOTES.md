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

- **Draft model:** [model.ucn](model.ucn) contains 3 requirements and 2 decisions taken from ADRs 0001 and 0010,
  3 rules from AGENTS.md, the signals convention, 7 components and 2 test links.
- **The model validates on the clean checkout:** 0 violations.
- **Evidence:** the two linked test files ran in the container (30 passed, 4.4 min including test-database setup).
  `--results` reports both requirements verified.
- **The signals convention works:** a probe file importing `django.db.models.signals` is reported.
  - This needed a validator fix. Python third-party imports were recorded by top-level package only, so
    `only X imports django.db.models.signals` could never fire.
  - The fix has a regression test.

## Gaps found in UCN

1. **Rules that are not imports.**
   - `NoSiteIdReads` (attribute access `settings.SITE_ID`) and `GiftCardNoLeak` (error text) cannot be checked by the
     validator.
   - A small `check: only <glob> uses <regex>` would cover the first.
   - Behaviour rules like the second are only covered through linked tests (evidence).
2. **`from django.db.models import signals`** records `django.db.models`, so the convention misses this form.
3. **Speed:** 23–100 s on 4,374 files with the built-in scanner, against the "about 1 s" measured on smaller repos.
   This needs `--deps` from a real dependency tool or a faster scanner before CI use.

## Next steps

1. Extend the model to all 12 ADRs and the AGENTS.md rules. Add `check: only <glob> uses <regex>`.
2. Write the pre-registration, committed **with** the tasks and graders (or their hashes).
3. Write about 20 tempting tasks, ideally by a non-Claude author, where the shortcut breaks an ADR or a rule. Examples:
   - "show customers their transactions": the shortcut opens `Order.transactions`;
   - "react to an order save": the shortcut is a signal;
   - "explain why a gift card was rejected": the shortcut leaks the owner.

   Hidden graders check the **requirement**.
4. Screen the tasks with no-docs agents (keep those broken in at least half the runs). Then run four arms: no docs,
   AGENTS.md + tests, size-matched prose, and the UCN context + validator.
