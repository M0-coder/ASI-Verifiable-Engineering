# Instructions for agents working on this repository

This repository defines a governance Skill. Changes to it can weaken controls across every repository that adopts the Skill, so treat modifications as high risk by default.

## Repository objective

The system must allow code to be accepted because it survived a strict, evidence-producing verification chain—not because the owner reviewed every line.

Line-by-line review is not the default approval gate. It is reserved for forensic investigation, evidence manipulation, unbounded generated code, incidents, or critical properties that cannot yet be protected automatically.

## Mandatory startup

1. Begin in read-only mode.
2. Identify branch, exact commit, and working-tree state.
3. Read `skills/asi-verifiable-engineering/SKILL.md`.
4. Read `.asi/policy.yml`.
5. Declare the intended files, tests, risks, stop condition, and rollback before editing.
6. Keep builder and auditor identities and contexts separate.

## Prohibited actions

- Do not push directly to `main`.
- Do not merge or approve your own change.
- Do not weaken validation, tests, CI, CODEOWNERS, or policy in the same change that benefits from that weakening.
- Do not claim a command ran unless its result is available.
- Do not hide failures, delete evidence, or use repeated retries to manufacture a green result.
- Do not treat the manifest's claimed `decision` as authoritative.
- Do not require exhaustive line-by-line review as a substitute for missing automated controls.

## Required validation

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

`evaluate_change.py` derives the decision from policy and primary evidence. A written `APPROVED` claim cannot override a failed gate, missing artifact, weak assurance level, exceeded budget, shared builder/auditor context, untested rollback, or mismatched commit.

For low or medium risk, the engine may return automatic eligibility and `line_by_line_review_required: false`.

For high or critical risk, use targeted human review of intent, architecture, permissions, data, secrets, irreversible effects, exceptions, observability, and rollback. Do not silently convert targeted review into approval by reputation.

## Decision language

Every review must end with exactly one decision:

- `APROBADO`
- `APROBADO CONDICIONALMENTE`
- `BLOQUEADO`
- `RECHAZADO`

Missing or unexecuted evidence must be marked `NO VERIFICADO` and cannot be silently treated as passed.
