# Instructions for agents working on this repository

This repository defines a governance Skill. Treat every modification as high risk because it can weaken controls in every adopting repository.

## Mandatory startup

1. Begin in read-only mode.
2. Identify base, head, integrable commit, branch, and tree state.
3. Read `skills/asi-verifiable-engineering/SKILL.md`.
4. Read `.asi/policy.yml` and `.asi/change-budget.json`.
5. Declare intended paths, tests, risks, stop conditions, and rollback before editing.
6. Keep builder, reviewer, and target-observation evidence distinct and traceable.

## Approval principle

Code is not approved because a human or AI read it. Approval is derived from measured evidence bound to a specific commit and package.

Line-by-line review is not the default gate. Use targeted review for high risk and forensic review only when integrity, scope, binary, or contradictory-evidence signals require it.

## Prohibited actions

- Do not push directly to `main`.
- Do not merge or approve your own change.
- Do not weaken policy, tests, CI, CODEOWNERS, thresholds, or evidence validation in the same change that benefits from the weakening.
- Do not synthesize exit codes, durations, logs, digests, approvals, target observations, or branch-protection state.
- Do not treat `continue-on-error` or a green step label as proof that a measured gate passed.
- Do not use an example manifest as evidence for a real commit.
- Do not promote T4 to T5 from review alone.
- Do not accept target observation unless its external JSON is SHA-256 verified and matches reviewer, repository, head, environment, age, result, and package digest.

## High-risk promotion path

A high-risk change requires all of the following:

1. Technical gates produce E6 / T4 / I2.
2. A distinct human collaborator approves the current head with `ASI-TARGETED-REVIEW-V1`.
3. The approval links a valid external report using `ASI-TARGET-OBSERVATION-V1`.
4. The report matches `assets/target-observation.example.json` and the exact package digest.
5. Effective `main` protection passes the GitHub API check.
6. The manifest reaches E7 / T5 / I3 with no unverified items or unresolved required gates.
7. `evaluate_change.py` derives `APPROVED` independently of the manifest's written claim.

## Required local validation

The example manifest is intentionally blocked:

```bash
python tools/validate_skill_package.py skills/asi-verifiable-engineering
python skills/asi-verifiable-engineering/scripts/validate_policy.py .asi/policy.yml
python skills/asi-verifiable-engineering/scripts/validate_evidence.py \
  skills/asi-verifiable-engineering/assets/evidence-manifest.example.json
python skills/asi-verifiable-engineering/scripts/evaluate_change.py \
  .asi/policy.yml \
  skills/asi-verifiable-engineering/assets/evidence-manifest.example.json \
  --expect BLOCKED
python -m unittest discover -s tests -p 'test_*.py' -v
```

## Decision language

Every evaluation ends with exactly one decision:

- `APROBADO`
- `APROBADO CONDICIONALMENTE`
- `BLOQUEADO`
- `RECHAZADO`

Missing or unexecuted evidence is `NO VERIFICADO` and cannot be converted into a warning through narrative explanation.
