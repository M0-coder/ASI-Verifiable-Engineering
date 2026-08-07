# BIRTH-06 evidence producer

BIRTH-06 reconstructs the **unprivileged** producer that feeds `ASI Trust Anchor`.
It is separated from `guardian/**` and does not receive privileged repository
secrets.

## Artifact identity v2

Every successful `Validate ASI Skill` pull-request run uploads exactly one artifact
named:

`asi-evidence-<run_id>-attempt-<run_attempt>-<head_sha>-<evaluated_sha>`

The producer records the same identity in `artifact-identity.json` and binds
`manifest.json` to the PR base, live head, and exact integrable merge commit.

## BIRTH-06.1 measured gates

The source workflow now measures these controls and stores each command, exit code,
log and digest in the evidence bundle:

- `integrity`: exact Git identity and exact changed-file budget;
- `format_check`: UTF-8, LF, final newline and trailing-whitespace rules over changed text;
- `lint`: Python AST parse plus narrow unsafe-construct checks over changed Python;
- `build`: `py_compile` over every changed Python file;
- `unit_tests`: producer unit tests;
- `integration_tests`: producer/Guardian identity-v2 and ZIP-policy compatibility;
- `secret_scan`: high-confidence credential/private-key patterns over changed text;
- `dependency_scan`: changed Python imports must be stdlib or repository-local;
- `rollback_check`: the exact `base..evaluated` diff must pass reverse-apply validation.

`producer/run_gate.py` deliberately returns workflow success after recording a
measured command's exit code. This allows the evidence bundle to be uploaded even
when a gate fails. A green producer workflow therefore means **evidence transport
succeeded**, not that the change was approved.

## Controls still not verified

BIRTH-06.1 does not fabricate evidence for controls that are not yet genuinely
available:

- `branch_protection`: privileged observation belongs at the trust boundary;
- `typecheck`: no reproducibly locked external static type checker is installed yet;
- `package_installability`: the real Skill product has not yet been reconstructed;
- `independent_audit`: I1 execution identity remains unresolved;
- `target_environment_observation`: no signed observation of the exact package exists.

Accordingly, the producer continues to emit `decision: BLOCKED`, and
`ASI Trust Anchor` remains the trusted arbiter.

## Package bytes

The bundle still includes `package/asi-verifiable-engineering.zip` so the trust
anchor can bind exact portable bytes. In BIRTH-06.1 this ZIP contains only a
producer-contract marker. It is **not** a release artifact and is **not**
target-observation evidence.

## Security properties

- no `ASI_GITHUB_ADMIN_TOKEN` in the producer workflow;
- GitHub Actions pinned by commit SHA;
- exact PR merge-commit checkout;
- deterministic ZIP metadata and ordering;
- exact live-diff budget for the BIRTH-06/BIRTH-06.1 files;
- measured gate failures are preserved, not converted to narrative warnings;
- workflow success is separated from approval semantics.
