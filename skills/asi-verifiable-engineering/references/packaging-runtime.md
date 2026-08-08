# Packaging / Runtime Projection v7

Status: `DERIVED / PLANNED` until built and observed.

The portable package is a fixed normative identity for one execution. Runtime cannot hot-edit the Universal Skill Core to change its own decision.

## Package identity

A package binds at least:

- Skill version;
- doctrine version;
- architecture version;
- packaging contract version;
- closed file allowlist;
- file content digests;
- canonical domain registry;
- norm registry / `norm_ref` set;
- Specification Snapshot;
- portable profiles included;
- package ZIP digest after build.

The repository package manifest is `manifest.json`. The build artifact digest is produced by CI and is not predeclared in source.

## Closed allowlist

Packaging is allowlist-based, not “copy everything under docs”. A missing, ambiguous, recycled, or mismatched `norm_id`/file digest fails package validation. Human section numbers are reading aids, not stable identities.

## Specification Snapshot

`assets/specification-snapshot.json` binds this candidate to doctrine v3.3, architecture v16, packaging v7, the master Notion page identity, and the local norm registry digest.

The Notion source export digest is explicitly `NOT_VERIFIED` in this draft because the current connector does not expose an immutable export digest. The package must not invent one. Full distribution conformance therefore remains blocked until a build process can bind the source snapshot strongly enough for the claimed assurance level.

## Runtime bootstrap

Runtime implements `ASI-NORM-BOOTSTRAP-001` exactly. Packaging may serialize inputs and outputs; it may not reorder normative bootstrap preconditions.

## Output serialization

Machine-readable outputs use canonical fields such as:

- `control_result`;
- `evidence_freshness`;
- `evaluator_aggregate`;
- `candidate_decision`;
- `candidate_decision_reason_codes`;
- `capability_availability`;
- `control_maturity`.

Aliases may exist only as display fields. A generic `status` cannot replace canonical domains.

## Project Policy Overlay

Project policy may be file-backed, service-backed, runtime-injected, or convention-based. `.asi/policy.yml`/`.asi/policy.json` is optional. The representation must have identity/version, required-field validation, Work Context binding, and authority provenance.

## Normative update / distribution immutability

Counterevidence may open `DOCTRINE_REVIEW_REQUIRED`. Approved normative change produces a new doctrine/package version, new snapshot and digests, and new integrity/authenticity validation. Never hot-swap rules under the same package identity.

## Full-conformance boundary

A structurally installable ZIP is not automatically a fully conformant ASI distribution. Full conformance additionally requires the applicable distribution trust binding, source/snapshot integrity, runtime capability truthfulness, required control evidence, target-environment observation where required, and Trust Anchor decision.
