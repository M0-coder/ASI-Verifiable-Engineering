# ASI Trust Anchor

This directory contains the verifier that is trusted from the repository's
default branch. It is deliberately separated from pull-request code.

## Security boundary

- `Validate ASI Skill` runs candidate code without privileged write access.
- `ASI Trust Anchor` is triggered by `workflow_run` from the default branch.
- The guardian downloads evidence but never executes code from the pull request.
- The guardian creates the required `ASI Trust Anchor` check on the exact PR head.
- Branch protection must bind that check to the same GitHub App that created it.
- Pull requests that modify control-plane paths are rejected unless the default
  branch contains an exact, time-limited exception for that PR, base, and head.
- The exact portable Skill ZIP must be present in the workflow artifact.
- Raw pull-request, artifact, check-run, and branch-protection responses are
  preserved in a separate trust-anchor artifact with the verification report.

## Check-name contract

The following values must be identical:

- workflow name;
- `verify` job name published as the GitHub check;
- `required_check` in `guardian/trust-policy.json`;
- `EXPECTED_CHECK` in `guardian/verify_protection_binding.py`.

`guardian/verify_contract.py` and its regression tests block any drift between
those values.

## Safe registration

After this repair is merged, run `ASI Trust Anchor` once with
`workflow_dispatch` from `main`. Registration only validates the trusted
contract and publishes the successful check name. It refuses any non-`main`
reference or any SHA that does not equal the checked-out `main` commit.

After that successful registration, select `ASI Trust Anchor` as the required
status check in the classic protection rule for `main`.

## Bootstrap rule

The first merge of this directory was a one-time owner-authorized trust-root
bootstrap. This repair remains a separate draft PR and must not be merged
without a new explicit H1 authorization.
