# ASI Trust Anchor

`guardian/**` is the privileged verification boundary for this repository. Pull-request code remains unprivileged and is never executed with privileged repository credentials by the Trust Anchor.

## Current contract

- Trust policy schema: `v4`
- Trust policy instance revision: `5`
- Trust contract: `v6`
- Runtime verifier generation: `verify_run_v4.py`
- Artifact identity: `v2`
- Required trusted check: `ASI Trust Anchor`

The policy instance protects the whole active control plane and portable Skill source:

- `.asi/**`
- `.github/workflows/**`
- `guardian/**`
- `producer/**`
- `skills/asi-verifiable-engineering/**`
- `tools/**`

`policy_contract.py`, `verify_contract.py`, and `verify_run_v4.py` enforce that these protection domains cannot silently disappear from a future policy revision.

## Gate ownership

`source_required_gates` belong to the unprivileged `Validate ASI Skill` producer. `trusted_required_gates` belong to this boundary.

`branch_protection` is the sole trusted gate. The producer must leave it unverified and must not emit source evidence claiming it passed.

The producer's `decision.json` is non-authoritative. The Trust Anchor derives acceptance after verifying source gates, trusted gates, candidate/artifact identity, protected-path authorization, package bytes, and branch-protection binding.

## Stable H1 identity

Protected-path evaluation may use `owner_comment_v1`. H1 identity binds primarily to the stable numeric GitHub user ID; login is diagnostic metadata.

An accepted exception must bind exact repository owner stable user ID, PR number, base SHA, head SHA, complete protected path set, reason, unexpired timestamp, `authorization_level = H1`, `authorization_scope = control-plane-exception-only`, and `merge_authorized = false`.

An exception permits evaluation of a protected-path change. It is not merge authorization.

## Compatibility helpers

`verify_run_v4.py` validates the current policy instance and delegates the established evidence protocol to `verify_run_v3.py`. The v3 implementation imports `verify_run.py` and `verify_run_v2.py` for mature helper functions and artifact/archive compatibility. Those files are therefore **active compatibility modules**, not dead code. Do not delete them solely because their filenames are older.

The immutable trust-anchor commit binds the complete helper tree even when the compact provenance report highlights the top-level runtime verifier digest.

## Archive safety

Artifact extraction rejects path traversal, absolute/unsafe paths, duplicate names, symlinks, encrypted/unsupported entries, excessive compressed/uncompressed size, excessive member count, and excessive compression ratio according to `trust-policy.json`.

## Provenance

The trusted workflow checks out `${{ github.workflow_sha }}` and verifies that the checked-out commit equals the immutable workflow SHA. Reports bind the trust-anchor commit plus workflow, policy, and top-level verifier digests.

## Transition

Changes to this control plane can create a circular bootstrap when `main` still runs an older policy/verifier. Follow `BOOTSTRAP-TRANSITION.md`; never remove the required check or weaken branch protection as a shortcut.
