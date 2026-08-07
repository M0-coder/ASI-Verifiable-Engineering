# ASI Trust Anchor

This directory contains the verifier trusted from the immutable workflow commit,
not from pull-request code.

## BIRTH-07 authority split

Policy v3 partitions required gates into two disjoint authorities:

- `source_required_gates`: evidence the unprivileged `Validate ASI Skill` workflow
  must measure and bind.
- `trusted_required_gates`: evidence that only the trust anchor may establish.

`branch_protection` is the sole trusted gate. The producer must leave it
`not_verified` and must not publish gate evidence for it. `verify_run_v3.py`
observes branch protection with the read-only administrative token and validates
that `ASI Trust Anchor` is strict, app-bound, enforced for administrators, and
cannot be bypassed by force-push or deletion settings.

The source `decision.json` is explicitly a non-authoritative claim. The trust
anchor derives acceptance from verified source gates, trusted gates, exact
artifact identity, protected-path authorization, and package bytes.

## H1 control-plane exceptions

A protected-path exception may still come from a static policy entry, but policy
v3 additionally supports `owner_comment_v1`. The trust anchor accepts a PR
Conversation comment only when:

- the GitHub author is listed in `h1_authorizers`;
- GitHub reports `author_association: OWNER`;
- the comment begins with `ASI-H1-EXCEPTION-V1`;
- the JSON payload binds exact PR number, base SHA, head SHA, complete protected
  path set, reason, and unexpired timestamp;
- `authorization_level` is `H1`;
- `authorization_scope` is `control-plane-exception-only`;
- `merge_authorized` is exactly `false`.

This exception permits the trust anchor to evaluate a protected control-plane
change. It is **not** merge authorization. A separate explicit owner decision is
still required before any H1 merge.

No H1 exception is created by BIRTH-07 for PR #6.

## Bootstrap boundary

Because the currently installed policy v2 has an empty `bootstrap_exceptions`
list and `ASI Trust Anchor` is already mandatory on `main`, BIRTH-07 itself
cannot be merged by pretending to satisfy the old trust anchor. That circular
bootstrap is intentionally reported rather than bypassed.

BIRTH-07 must remain draft until there is a separately authorized transition
that preserves the required check. The legacy PR #1 remains frozen.

## Artifact identity and archive safety

Artifact identity remains v2:

`asi-evidence-<run_id>-attempt-<run_attempt>-<head_sha>-<evaluated_sha>`

Archive extraction keeps the BIRTH-05 limits for path traversal, duplicates,
symlinks, encryption, compression methods, file count, member size, total
expanded size, and compression ratio. Trust-anchor provenance remains bound to
the immutable workflow SHA and workflow/policy/verifier digests.
