# Control-plane bootstrap transition — dual lock

This is a one-time transition procedure for a pull request that changes the Trust Anchor/control plane while `main` still enforces an older verifier/policy. It is a procedure, not merge authorization.

## Why a transition exists

The installed Trust Anchor on `main` cannot allow a new exception mechanism to authorize the change that installs that mechanism. Treat that circularity as a bootstrap constraint, not as permission to bypass the required check.

## Preconditions

Before Phase A, obtain fresh administrative evidence for `main`:

- current branch-protection/ruleset state;
- required check name and producing app binding;
- strict/up-to-date behavior;
- administrator enforcement;
- conversation-resolution requirement where applicable;
- force-push and deletion blocked;
- current repository owner stable GitHub user ID;
- exact reconciliation PR base SHA and head SHA;
- successful `Guardian Bootstrap` for that exact head.

If any fact is unavailable or stale, stop.

## Phase A — establish an independent temporary lock

Create a temporary ruleset/control that:

- applies to `main`;
- requires pull requests;
- requires the successful `Guardian Bootstrap` check for the exact control-plane candidate;
- blocks force pushes and deletion;
- has no broad bypass actor that defeats the purpose of the transition.

Verify the temporary lock is active before touching the classic/installed protection.

## Phase B — exact one-time transition

Only after Phase A and a separate explicit owner H1 authorization bound to the exact reconciliation PR/head:

1. keep `ASI Trust Anchor` configured as a required check;
2. temporarily allow only the minimum administrator bypass required by the older installed rule;
3. merge only the exact authorized head using the separately authorized merge method;
4. do not use the temporary exception for any other PR or head.

The H1 protected-path exception used by the candidate has `merge_authorized: false`; it is not the Phase B merge authorization.

## Phase C — re-anchor and restore

After the authorized merge:

1. record the new `main` SHA;
2. manually dispatch `ASI Trust Anchor` from `main` and require registration/contract success under the new policy/verifier;
3. restore the classic rule to no-bypass/enforce-admin posture;
4. verify the required check remains app-bound and strict;
5. only after the restored lock is verified, disable/remove the temporary transition ruleset;
6. rerun any dependent candidate evidence whose base/trust identity changed.

If re-anchoring fails, keep the temporary lock active and stop. Do not weaken both locks at once.

## Stop conditions

Stop if:

- reconciliation PR head/base changes after authorization;
- repository owner stable user ID does not match policy;
- Guardian Bootstrap is not successful for the exact head;
- temporary lock is missing/ineffective;
- force push/deletion becomes allowed;
- required check is removed or loses app binding;
- any step would authorize a different PR/head/path set;
- evidence becomes stale and cannot be refreshed.
