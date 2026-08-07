# BIRTH-07 bootstrap transition — dual lock

## Status

This document defines a one-time transition procedure. It is not an authorization to merge PR #7 and it does not change repository protection by itself.

The transition exists because the currently installed policy v2 requires `ASI Trust Anchor` to pass for control-plane changes while `bootstrap_exceptions` is empty. The candidate BIRTH-07 mechanism cannot authorize the change that installs itself.

## Verified GitHub constraint

Classic branch protection does not provide an exception scoped to one exact pull request. GitHub ruleset bypass permissions are actor/role/app scoped, and rulesets layer with existing branch-protection rules rather than replacing them.

Therefore there is no purely in-band transition from the current policy v2 to BIRTH-07 while preserving every current rule unchanged.

## Safety invariant

At no point may `main` be left without an active merge barrier.

During the one-time transition:

- direct changes to `main` remain disallowed by an active rule;
- force pushes remain blocked;
- branch deletion remains blocked;
- a pull request remains required by the temporary transition rule;
- a successful GitHub Actions bootstrap check is required;
- PR #7 must remain bound to one exact base SHA and head SHA;
- a separate explicit H1 merge authorization is still required;
- no transition step authorizes PR #6 or PR #1.

## Proposed dual-lock ceremony

### Phase A — install a temporary independent lock

Before changing the existing classic branch-protection rule, create a temporary active branch ruleset targeting only `main` with no bypass actors and with these minimum controls:

1. require a pull request before changes enter `main`;
2. require `Guardian Bootstrap` from GitHub Actions;
3. require the branch to be up to date before merge;
4. require conversation resolution;
5. block force pushes;
6. block branch deletion.

Verify that PR #7 at the exact authorized head shows the temporary ruleset as satisfied only after the corresponding `Guardian Bootstrap` run is successful.

The temporary ruleset must be active before any change to the classic rule.

### Phase B — one-time classic-rule transition

Only after Phase A is verified and after a new explicit H1 authorization bound to the exact PR #7 head:

1. keep `ASI Trust Anchor` configured as the required check in the classic rule;
2. temporarily allow the repository administrator to bypass that classic rule;
3. do not enable force pushes or deletions;
4. do not merge any PR other than the exact authorized PR #7;
5. squash-merge PR #7 only if the temporary ruleset still requires and observes a successful `Guardian Bootstrap` for the exact head.

This phase bypasses the obsolete v2 trust-root decision for one exact bootstrap merge while the independent temporary ruleset remains enforced. It is not a normal steady-state merge path.

### Phase C — re-anchor immediately

After PR #7 is merged:

1. record the new `main` SHA;
2. manually dispatch `ASI Trust Anchor` from `main` and require registration success under policy v3 / contract v4;
3. restore the classic rule to disallow bypassing;
4. verify `ASI Trust Anchor` remains the required app-bound check;
5. only after the classic rule is restored, disable or remove the temporary `Guardian Bootstrap` ruleset;
6. verify force pushes and deletions remain disabled.

If any re-anchoring step fails, keep the temporary ruleset active and stop. Do not proceed to PR #6.

## PR #6 after BIRTH-07

Once Phase C is complete, PR #6 may be re-evaluated by the installed v3 trust anchor. Any control-plane exception for `.github/workflows/validate-skill.yml` must be a separate owner-comment H1 authorization bound exactly to PR number, base SHA, head SHA, complete protected-path set, expiry, and reason. That exception is not merge authorization.

## Stop conditions

Stop the transition if any of the following occurs:

- PR #7 head changes after H1 authorization;
- `main` changes and PR #7 is no longer up to date;
- `Guardian Bootstrap` is not successful for the exact head;
- the temporary ruleset has a bypass actor;
- force pushes or deletion become allowed;
- the temporary ruleset is not active before the classic-rule transition;
- registration of the post-merge BIRTH-07 trust anchor fails;
- the classic `ASI Trust Anchor` requirement cannot be restored before removing the temporary ruleset.

## Rollback

Before merge, rollback is to restore the original classic rule and remove the temporary ruleset; no repository code has changed on `main`.

After merge, if BIRTH-07 registration fails, retain the temporary ruleset and treat `main` as bootstrap-recovery mode. Do not merge PR #6. A new repair PR must be validated under the temporary lock before any further transition.
