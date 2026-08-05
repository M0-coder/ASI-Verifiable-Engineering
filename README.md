# ASI Verifiable Engineering

**Status:** bootstrap draft (`0.1.0-draft.1`). Do not treat this branch as adopted policy until the draft pull request is reviewed and merged.

ASI Verifiable Engineering is an Agent Skill for auditing, modifying, verifying, and approving software changes through evidence rather than trust. It combines test-driven development, risk-based approval, independent review, reproducible CI, security controls, operational observation, and rollback.

## Core rule

Code is not approved because a human or an AI read it and found it convincing. A specific commit is approved only when it survives the controls required for its risk level and the evidence is tied to that exact commit.

## Repository layout

```text
skills/asi-verifiable-engineering/
├── SKILL.md
├── references/
├── assets/
└── scripts/

.asi/policy.yml
.github/workflows/validate-skill.yml
tools/validate_skill_package.py
tests/
```

The installable skill directory is `skills/asi-verifiable-engineering/`. This directory name intentionally matches the `name` field in `SKILL.md`, as required by the Agent Skills specification.

## Authority during bootstrap

Until this draft is reviewed, merged, and tagged:

1. Notion doctrine version `1.2` remains the adopted source.
2. This repository is the candidate canonical, version-controlled implementation.
3. After adoption, a tagged GitHub release becomes the normative source and Notion becomes the human-readable mirror.

Notion source used for this bootstrap:

- https://app.notion.com/p/3b3eb559c05c81b5b971ee384164aa10

## Validation

```bash
python tools/validate_skill_package.py skills/asi-verifiable-engineering
python -m unittest discover -s tests -v
python skills/asi-verifiable-engineering/scripts/validate_policy.py .asi/policy.yml
```

## Skill behavior

The skill begins in read-only mode, fixes the repository baseline, classifies risk, declares a change budget, requires a failing test or equivalent evidence before correction, executes applicable gates, preserves primary artifacts, requires independent verification, and returns exactly one decision:

- `APROBADO`
- `APROBADO CONDICIONALMENTE`
- `BLOQUEADO`
- `RECHAZADO`

## Non-goals

This skill does not make an AI infallible, replace CI, eliminate human approval for high-risk work, or prove the absence of every possible defect.
