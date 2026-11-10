# UCN: check your code against its architecture rules, decisions and requirements

UCN (Unified Context Notation) is a small text format plus a command-line tool. You write down a system's
architecture rules, decisions, requirements and approved exceptions in one file. On every commit, `ucn check` tells you
where the code disagrees with them.

It started as a research question: *can a formal, compact context language make AI coding agents follow a project's
requirements and architecture?* After about 130 agent runs on three real codebases, the answer was **no, but not for
the reason we expected**. The research record is in [research/](research/README.md). The rest of this page is about the
tool that survived it.

## What the tool does

```text
# model.ucn (an illustrative excerpt, with rules taken from two of the trial repositories)
container Package: the sqlfluff Python package
  code: sqlfluff/**
  acyclic: yes
  component Api: public Python API
    code: sqlfluff/api/**
    forbids Cli
  component Core: parser, lexer, config
    code: sqlfluff/core/**
    layers: Linter > Rules > Parser > Helpers
rule NoSiteIdReads: never read settings.SITE_ID; only the site picker may
  check: only saleor/site/** uses settings\.SITE_ID\b
convention NoDjangoSignals: call logic explicitly, never through Django signals
  check: only saleor/*/{migrations/**,apps.py} imports django.db.models.signals
req PaymentHistoryProjection: customers see payment history only through an allowlisted projection
  rationale: docs/adr/0010-order-payment-history-is-a-projection.md
test TransactionSummaryTests: the projection's tests
  src: saleor/graphql/order/tests/queries/test_order_transaction_summaries.py
  verifies PaymentHistoryProjection
deviation ErrorsTypeImports: errors may reference rules and parser for type checking only
  expires: 2027-11-01
  approved: maintainers
```

```console
$ ucn check model.ucn --results junit.xml        # illustrative, shortened output
  VIOLATION   conventions  saleor/order/hooks.py imports django.db.models.signals, but NoDjangoSignals allows only ...
  CONFLICT    ...          AGENTS.md forbids direct dialect imports; 12 modules do it
  summary: 1 violation, 0 conflict, 2 waived ...
  evidence: 253 test cases; 7 verified, 0 failing
```

- **Architecture rules:** `forbids`, `layers`, `independent` and `acyclic` are checked on the real import graph
  (Python and TypeScript/JavaScript).
- **Conventions:** `only <glob> imports <module>` and `only <glob> uses <regex>`, for rules that are not imports.
- **Evidence:** requirements link to tests. With `--results junit.xml`, each requirement is reported as *met*, *not
  met* or *without evidence*.
- **Governance:** approved deviations with expiry dates, and recorded conflicts between documented rules and the code.
  Neither exists in import-linter or dependency-cruiser.
- **Staleness:** `src: file:line@hash` references are followed when code moves and flagged when it changes
  (`ucn stamp`).
- **Rationale links:** `rationale: docs/adr/...#section` must resolve.
- **Export:** the same rules compile to working **import-linter** and **dependency-cruiser** configs, so one file is
  the source of truth. On real repositories the exports gave identical results to those tools.

## Install and use

Python 3.10 or newer, no dependencies:

```console
pip install git+https://github.com/mohaqeq/unified-context-notation
ucn lint    model.ucn                         # syntax and references
ucn check   model.ucn [--results junit.xml]   # model vs code; exit code 1 on violations
ucn stamp   model.ucn                         # add or refresh content hashes on src: references
ucn export  model.ucn --to import-linter --package mypkg > .importlinter
ucn project model.ucn --task "add rate limiting" --budget 2500   # a compact task context for an agent
```

In CI (GitHub Actions):

```yaml
- run: pip install git+https://github.com/mohaqeq/unified-context-notation
- run: ucn check model.ucn --results test-results.xml
```

A complete worked example, with a small TypeScript codebase, deviations, a conflict and projections, is in
[examples/shortly](examples/shortly/README.md). The format is specified in
[research/docs/03-proposal.md](research/docs/03-proposal.md).

## What the experiments found

The full write-up is in [article/](article/agents-already-read-the-code.md); the details are in
[research/](research/README.md).

1. **The checks work.** UCN found a rule in sqlfluff's own AGENTS.md that 12 modules contradict, and circular
   undeclared package dependencies in excalidraw. Its exports matched import-linter and dependency-cruiser exactly. With
   a deny-list model it needed 0 edits over 600 commits.
2. **As guidance for agents, it did not beat the alternatives.**
   - In a pre-registered pilot (60 runs), agents given a UCN context and the validator matched agents given AGENTS.md
     and import-linter: 24/24 success and 0 violations each.
   - The UCN arm used 11% fewer tokens, but that is explained by its shorter text.
3. **The codebase already guides agents.** On saleor, a customer-facing commerce API whose rules live in ADRs, agents
   with **no docs at all** kept the documented rules in 33 of 42 runs. They copied the patterns next to their change.
   The pre-registered screen therefore stopped the experiment.

So a check in the loop prevents violations, and a well-kept codebase shows agents the way. A context language adds
little on top of both. UCN is kept as the checker and governance tool above.

## Repository layout

| Path | Contents |
|---|---|
| [ucn/](ucn/) | The tool (standard library only): parser, validator, exporter, projector, `ucn` CLI |
| [tests/](tests/) | 88 tests, including a regression test for every bug the external reviews reproduced |
| [examples/shortly/](examples/shortly/README.md) | A worked example |
| [article/](article/agents-already-read-the-code.md) | The blog article about the experiments |
| [research/](research/README.md) | The research record: design documents, reviews, trials, pre-registrations, tasks, graders, results, agent tool-call logs, and the harness that ran them |
