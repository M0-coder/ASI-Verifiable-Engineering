# Unprivileged ASI evidence producer

`producer/**` runs without privileged repository credentials and produces evidence for `ASI Trust Anchor`.

## Separation of authority

The producer may measure source-owned controls and transport evidence. It may not establish trusted administrative facts such as branch protection, and its `decision.json` is a non-authoritative claim.

A green `Validate ASI Skill` workflow means evidence production/transport completed and no **executed** source gate returned `FAIL`. It does **not** mean the candidate is accepted: external controls may remain `NOT_VERIFIED`, and trusted controls remain Trust Anchor inputs.

## Current measured gates

- integrity / candidate identity / repository change budget;
- format check;
- AST lint;
- strict mypy typecheck over the current producer/tools and v4 Guardian contract surface;
- Python compile/build check;
- portable package installability/structure validation;
- producer and package-validator unit tests;
- producer/Guardian integration tests;
- high-confidence secret scan;
- stdlib/repository-local dependency scan;
- reverse-apply rollback check;
- external independent-audit attestation admission;
- external target-environment observation attestation admission.

The CI typechecker is version-locked by `requirements-ci.lock`; the exact scope is recorded in the gate command. Controls for which no honest measurement exists remain `not_verified`; they are not converted to warnings or fabricated PASS values.

## External attestation contract

`producer/verify_external_attestation.py` consumes GitHub pull-request **review submissions**. The current constructor context identifier is:

`asi-constructor-reconcile-20260808-01`

A separate audit context must inspect the exact PR head without modifying the candidate. The audit may publish its evidence **after** the read-only analysis; publication actions are recorded separately from `audit.write_actions`.

The review must be anchored to the exact current head and contain:

```text
ASI-EXTERNAL-ATTESTATION-V1
ASI-ATTESTATION-URL: https://raw.githubusercontent.com/M0-coder/ASI-Verifiable-Engineering/<immutable-40-char-commit>/evidence/<file>.json
ASI-ATTESTATION-SHA256: sha256:<64-hex>
```

The external JSON uses this shape:

```json
{
  "schema": "asi.external_attestation.v1",
  "repository": "M0-coder/ASI-Verifiable-Engineering",
  "pull_request": 8,
  "head_sha": "<exact-pr-head>",
  "builder_context_id": "asi-constructor-reconcile-20260808-01",
  "auditor_context_id": "<distinct-context-id>",
  "audit": {
    "mode": "read_only",
    "result": "PASS",
    "checks": ["<what was actually checked>"],
    "findings": [],
    "write_actions": [],
    "publication_actions": ["publish immutable attestation"],
    "created_at": "<UTC timestamp>"
  },
  "target_observation": {
    "target_environment": "chatgpt",
    "result": "PASS",
    "package_digest": "sha256:<exact-portable-package-digest>",
    "checks": ["<what was actually observed>"],
    "limitations": [],
    "executed_at": "<UTC timestamp>"
  }
}
```

Admission is fail-closed:

- no marked review/attestation → gate remains `NOT_VERIFIED`;
- marked evidence that is stale, mutable, malformed, same-context, modified-during-audit, from the wrong repository/head, or digest-mismatched → `FAIL`;
- valid immutable evidence → `PASS`.

The evidence URL must point to this same repository and be pinned to an immutable commit SHA, not a mutable branch name. The target observation must match the deterministic portable package SHA-256 recomputed by CI.

This mechanism provides an admissible **context-separated attestation**, not cryptographic proof of ChatGPT conversation identity. That limitation must remain visible in the audit/Proof Bundle.

## Package

The producer packages the real `skills/asi-verifiable-engineering/` tree. The old BIRTH-06 marker fixture is not part of the reconstructed source.

The ZIP is deterministic by file order, timestamp, storage method, and file mode. CI records its SHA-256 in the evidence manifest.

## Change budget

Repository scope comes from `.asi/change-budget.json`. The budget is project policy, not a universal ASI norm. The producer records the exact live changed-file set and fails integrity when a path escapes the budget.
