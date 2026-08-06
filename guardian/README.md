# ASI Trust Anchor

This directory contains the verifier trusted from the workflow file commit rather
than from a moving branch reference. Pull-request code remains unprivileged and
is never executed by the trust anchor.

## Security boundary

- `Validate ASI Skill` produces candidate evidence without privileged writes.
- `ASI Trust Anchor` is triggered by `workflow_run` from the default branch.
- The repository is checked out at `${{ github.workflow_sha }}` and the checked-out
  commit must equal `ASI_TRUST_ANCHOR_SHA`.
- `guardian/verify_run_v2.py` downloads evidence but never executes PR code.
- The required `ASI Trust Anchor` check is created on the exact PR head.
- Branch protection must bind that check to the producing GitHub App.
- Control-plane changes require an exact, unexpired H1 exception bound to PR,
  base SHA, head SHA, and the complete set of protected paths.
- The exact portable Skill ZIP must be present in the workflow artifact.

## Artifact identity v2

The unprivileged workflow must publish exactly one non-expired artifact named:

```text
asi-evidence-<run_id>-attempt-<run_attempt>-<head_sha>-<evaluated_sha>
```

This prevents evidence from an older attempt or merge commit from being selected
under the same run name.

## Archive safety

Before extraction, the v2 verifier rejects:

- path traversal, absolute paths, symbolic links, and duplicate names;
- encrypted entries and unsupported compression methods;
- excessive file count, member size, total expanded size, or compression ratio.

The limits are policy-as-code in `guardian/trust-policy.json`.

## Trust-anchor provenance

Every v2 report records:

- `trust_anchor_commit`;
- workflow digest;
- policy digest;
- verifier digest;
- source run ID and run attempt;
- exact source artifact name, ID, and digest.

Raw PR, artifact-list, selected-artifact, and branch-protection responses are
written into the trust-anchor evidence directory.

## Check-name contract

The workflow name, job/check name, policy `required_check`, and verifier
`EXPECTED_CHECK` must all equal `ASI Trust Anchor`. `verify_contract.py` also
rejects mobile `ref: main` checkout and any downgrade from verifier/policy v2.

## Registration

After an explicitly authorized merge, run `ASI Trust Anchor` once with
`workflow_dispatch` from `main`. Registration validates only the trusted
contract and publishes the check name. Configure branch protection only after
that run succeeds.

## Bootstrap rule

This hardening remains blocked for merge until a new explicit H1 authorization.
The legacy PR #1 remains frozen and must not be used as current evidence.
