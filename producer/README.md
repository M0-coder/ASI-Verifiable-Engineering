# Unprivileged ASI evidence producer

`producer/**` runs without privileged repository credentials and produces evidence for `ASI Trust Anchor`.

## Separation of authority

The producer may measure source-owned controls and transport evidence. It may not establish trusted administrative facts such as branch protection, and its `decision.json` is a non-authoritative claim.

A green `Validate ASI Skill` workflow means evidence production/transport completed. It does **not** mean the candidate is accepted.

## Current measured gates

- integrity / candidate identity / repository change budget;
- format check;
- AST lint;
- Python compile/build check;
- portable package installability/structure validation;
- producer and package-validator unit tests;
- producer/Guardian integration tests;
- high-confidence secret scan;
- stdlib/repository-local dependency scan;
- reverse-apply rollback check.

Controls for which no honest measurement exists remain `not_verified`; they are not converted to warnings or fabricated PASS values.

## Package

The producer now packages the real `skills/asi-verifiable-engineering/` tree. The old BIRTH-06 marker fixture is removed.

The ZIP is deterministic by file order, timestamp, storage method, and file mode. CI records its SHA-256 in the evidence manifest.

## Change budget

Repository scope comes from `.asi/change-budget.json`. The budget is project policy, not a universal ASI norm. The producer records the exact live changed-file set and fails integrity when a path escapes the budget.
