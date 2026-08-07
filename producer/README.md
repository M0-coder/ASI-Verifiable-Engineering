# BIRTH-06 evidence producer

BIRTH-06 reconstructs the **unprivileged** producer that feeds `ASI Trust Anchor`.
It is intentionally separated from `guardian/**` and does not receive privileged
repository secrets.

## Artifact identity v2

Every successful `Validate ASI Skill` pull-request run uploads exactly one artifact
named:

`asi-evidence-<run_id>-attempt-<run_attempt>-<head_sha>-<evaluated_sha>`

The producer also records the same identity in `artifact-identity.json` and binds
`manifest.json` to the PR base, live head, and exact integrable merge commit.

## Trust boundary

A green producer workflow means only that the evidence bundle was produced
correctly. It does **not** mean the change is approved. `ASI Trust Anchor`, running
from the trusted default-branch control plane, is the arbiter.

BIRTH-06 deliberately leaves these controls `not_verified` rather than fabricating
proof:

- privileged branch-protection observation;
- independent I1 execution/audit identity;
- target-environment observation of the exact package;
- technical gates that have not yet been reconstructed from the frozen PR #1.

Accordingly, BIRTH-06 emits `decision: BLOCKED`. Later work must add genuine
measurements; it must not convert these gaps into synthetic passing evidence.

## Package bytes

The bundle includes `package/asi-verifiable-engineering.zip` so the trust anchor can
bind exact portable bytes. For BIRTH-06 this ZIP contains only a producer-contract
marker. It is **not** a release artifact and is **not** target-observation evidence.

## Security properties

- no `ASI_GITHUB_ADMIN_TOKEN` in the producer workflow;
- pinned GitHub Actions revisions;
- exact PR merge commit checkout;
- deterministic ZIP metadata and ordering;
- exact live-diff budget for the five BIRTH-06 files;
- workflow success is separated from approval semantics.
