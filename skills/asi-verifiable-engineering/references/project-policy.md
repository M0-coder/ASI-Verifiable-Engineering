# Project Policy Overlay

Normative owner: `ASI-NORM-POLICY-001` in the master doctrine. This reference explains how a project supplies policy without changing universal semantics.

## Purpose

Project Policy defines project-specific requirements that ASI cannot infer universally: protected paths, required checks, risk escalation, environments, merge/deploy authority, acceptable tools, mandatory tests, security boundaries, and exceptions.

## Required properties

A policy representation should identify:

- `policy_id` and version;
- Work Context binding;
- owner/authority provenance;
- required controls and their maturity/authority;
- risk escalation rules;
- protected paths/assets;
- environment/target requirements;
- merge/deploy/release authority;
- exception schema and expiry/revocation behavior;
- rollback/recovery expectations where applicable.

## Constraints

Project Policy:

- may escalate risk but cannot narratively downgrade it to evade universal controls;
- cannot fabricate unavailable runtime capabilities;
- cannot reinterpret canonical `FAIL`, `NOT_VERIFIED`, or `INFRA_FAILURE` as PASS;
- cannot make CI success equivalent to Candidate Decision;
- cannot grant the Constructor authority reserved to the Trust Anchor;
- cannot silently replace a `norm_ref`.

## File-backed policy

A repository may choose `.asi/policy.yml`, `.asi/policy.json`, or another validated representation. No particular filename is a universal ASI requirement.

The ASI-Verifiable-Engineering repository itself uses `guardian/trust-policy.json` for the privileged control plane and `.asi/change-budget.json` for repository-specific diff scope. Those are project implementation artifacts, not portable universal norms.

## Exceptions

Exception records must preserve the raw measured control results. A protected-path exception authorizes only its explicit scope. If its payload says `merge_authorized: false`, it cannot be reused as merge authorization.
