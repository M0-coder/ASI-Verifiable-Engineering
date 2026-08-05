# ASI Verifiable Engineering

**Status:** bootstrap draft (`0.1.0-draft.2`). Do not treat this branch as adopted policy until the draft pull request is reviewed and merged.

ASI Verifiable Engineering is an Agent Skill for auditing, modifying, verifying, and approving software changes through evidence rather than trust. It combines test-driven development, risk-based approval, independent review, reproducible CI, security controls, evidence-derived decisions, operational observation, and rollback.

## Core rule

Code is not approved because a human or an AI read it and found it convincing. A specific commit is approved only when it survives the controls required for its risk level and an independent decision engine derives approval from evidence tied to that exact commit.

## Operational objective

The owner should not need to inspect every line produced by an AI.

The normal approval path replaces exhaustive manual reading with:

- observable acceptance criteria;
- TDD or equivalent defect-detection evidence;
- a declared change budget;
- mandatory deterministic gates;
- digest-bound policy, diff, commands, and artifacts;
- independent builder and auditor contexts;
- evidence that tests detect the defect;
- risk-based E/T/I requirements;
- tested rollback;
- a machine-derived final decision.

Low- and medium-risk changes may become automatically eligible when every strict condition passes. High- and critical-risk changes require targeted human risk review, not automatic line-by-line inspection.

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
python skills/asi-verifiable-engineering/scripts/validate_policy.py .asi/policy.yml
python skills/asi-verifiable-engineering/scripts/validate_evidence.py \
  skills/asi-verifiable-engineering/assets/evidence-manifest.example.json
python skills/asi-verifiable-engineering/scripts/evaluate_change.py \
  .asi/policy.yml \
  skills/asi-verifiable-engineering/assets/evidence-manifest.example.json \
  --expect APPROVED
python -m unittest discover -s tests -v
```

## Decision authority

The `decision` field inside an evidence manifest is only a claim. `evaluate_change.py` independently derives the result from policy and primary evidence.

A claimed approval is blocked when any required gate fails, the assurance level is too low, evidence is missing, the budget is exceeded, builder and auditor are not independent, rollback is untested, or the claim conflicts with the derived decision.

The engine reports:

- `decision`;
- `automatic_approval_eligible`;
- `line_by_line_review_required`;
- `human_review_mode`;
- `human_action`;
- blockers and notes.

## Skill behavior

The skill begins in read-only mode, fixes the repository baseline, classifies risk, declares a change budget, requires a failing test or equivalent evidence before correction, executes applicable gates, preserves primary artifacts, requires independent verification, derives the decision, and returns exactly one result:

- `APROBADO`
- `APROBADO CONDICIONALMENTE`
- `BLOQUEADO`
- `RECHAZADO`

## Non-goals

This skill does not make an AI infallible, replace CI, eliminate targeted human approval for high-risk work, or prove the absence of every possible defect. It removes line-by-line review as the default approval mechanism; it does not remove risk governance.
