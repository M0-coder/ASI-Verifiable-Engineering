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

## Bootstrap rule

The first merge of this directory is a one-time owner-authorized trust-root
bootstrap. After it is merged, branch protection must require `ASI Trust Anchor`
instead of the candidate workflow's own check.
