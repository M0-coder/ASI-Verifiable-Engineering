# ASI Verifiable Engineering

**Status:** bootstrap draft (`0.1.0-draft.2`). Do not treat this branch as adopted policy until the pull request is independently verified, merged, and tagged.

ASI Verifiable Engineering is an Agent Skill and verification framework for approving software changes through measured evidence rather than trust or exhaustive manual reading.

## Core rule

A change is not approved because a human or AI read it, explained it, or wrote `APPROVED`. A specific integrable commit is approved only when the decision engine derives that result from evidence bound to the exact policy, diff, commands, artifacts, package, review, and target observation.

Line-by-line review is not the default gate. High-risk changes require targeted human review. Forensic reading activates only when integrity, scope, binary, or contradictory-evidence signals require it.

## Assurance path

The pull-request workflow has an explicit reachable path:

1. Technical and security gates produce E6 / T4 / I2.
2. A human collaborator distinct from the builder approves the current head with `ASI-TARGETED-REVIEW-V1`, producing I3.
3. The same approval may link an external target-environment report with `ASI-TARGET-OBSERVATION-V1`.
4. CI downloads that report from GitHub Raw, verifies its SHA-256, age, reviewer, repository, head, target environment, result, and package digest.
5. A valid observation promotes the manifest to E7 / T5.
6. Effective `main` protection is verified through the GitHub API.
7. `evaluate_change.py` independently derives the final decision. The manifest's written decision remains non-authoritative.

## Target observation contract

The independent reviewer executes the exact verified package in `chatgpt`, `codex`, or `openai-api`, creates a JSON report following:

```text
skills/asi-verifiable-engineering/assets/target-observation.example.json
```

The report must be publicly retrievable through `raw.githubusercontent.com`. The approval body must contain:

```text
ASI-TARGETED-REVIEW-V1
ASI-TARGET-OBSERVATION-V1
ASI-TARGET-EVIDENCE-URL: https://raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>.json
ASI-TARGET-EVIDENCE-SHA256: sha256:<64-lowercase-hex>
```

The observation expires after seven days and is invalidated by any head or package-digest change.

## Branch protection prerequisite

The repository secret `ASI_GITHUB_ADMIN_TOKEN` must contain a fine-grained token with read access to repository administration metadata. CI verifies that `main` requires:

- at least one approval;
- stale-review dismissal;
- CODEOWNERS review;
- strict required status checks;
- `Verify measured gates and derive decision`;
- admin enforcement;
- conversation resolution;
- no force pushes or deletion.

## Workflows

- `.github/workflows/validate-skill.yml` evaluates pull requests and review events.
- `.github/workflows/main-integrity.yml` evaluates commits after merge and verifies the associated PR attestations. It does not invent a synthetic PR number.

## Validation

The blocked example must remain blocked:

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

`tests/test_birth02_promotion.py` constructs complete high-risk E7 / T5 / I3 evidence and proves that the engine can derive `APPROVED` even when the manifest still claims `BLOCKED`.

## Repository layout

```text
.asi/
├── policy.yml
└── change-budget.json

.github/workflows/
├── validate-skill.yml
└── main-integrity.yml

skills/asi-verifiable-engineering/
├── SKILL.md
├── references/
├── assets/
└── scripts/

tests/
tools/
```

## Authority during bootstrap

Until this draft is adopted:

1. Notion doctrine version `1.2` remains the adopted source.
2. This repository is the candidate canonical implementation.
3. A tagged GitHub release becomes normative only after explicit adoption.

Notion source:

- https://app.notion.com/p/3b3eb559c05c81b5b971ee384164aa10

## Non-goals

The Skill does not make an AI infallible, prove the absence of every defect, or remove targeted human governance for high-risk work. It makes approval claims measurable, reproducible, independently reviewable, and difficult to falsify.
