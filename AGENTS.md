# Instructions for agents working on this repository

This repository defines a governance Skill. Changes to it can weaken controls across every repository that adopts the Skill, so treat modifications as high risk by default.

## Mandatory startup

1. Begin in read-only mode.
2. Identify branch, exact commit, and working-tree state.
3. Read `skills/asi-verifiable-engineering/SKILL.md`.
4. Read `.asi/policy.yml`.
5. Declare the intended files, tests, risks, stop condition, and rollback before editing.

## Prohibited actions

- Do not push directly to `main`.
- Do not merge or approve your own change.
- Do not weaken validation, tests, CI, CODEOWNERS, or policy in the same change that benefits from that weakening.
- Do not claim a command ran unless its result is available.
- Do not hide failures, delete evidence, or use repeated retries to manufacture a green result.

## Required validation

```bash
python tools/validate_skill_package.py skills/asi-verifiable-engineering
python -m unittest discover -s tests -v
python skills/asi-verifiable-engineering/scripts/validate_policy.py .asi/policy.yml
```

## Decision language

Every review must end with exactly one decision:

- `APROBADO`
- `APROBADO CONDICIONALMENTE`
- `BLOQUEADO`
- `RECHAZADO`

Missing or unexecuted evidence must be marked `NO VERIFICADO` and cannot be silently treated as passed.
