# Solo-Operator Mode

## Purpose

Solo-Operator Mode is for repositories controlled by one human owner who delegates implementation and verification to separate AI conversations or agents.

Its objective is to let future chats work safely without requiring the owner to inspect every changed line.

## Separation of roles

### Builder context

The builder may inspect and modify the repository. It must declare a stable `builder_context_id` in the change budget. It may produce evidence, but it cannot issue or fabricate the independent audit attestation and cannot claim owner authorization.

### Auditor context

The auditor must be a different chat or agent context with a different `auditor_context_id`.

The audit must:

- begin in read-only mode;
- target the exact PR head;
- reproduce or inspect the required evidence;
- report checks and findings;
- record `write_actions: []`;
- stop and return findings instead of correcting code;
- publish a JSON attestation whose SHA-256 is independently verified by CI.

The same GitHub account may publish the audit comment because independence is established by context identity, permissions, behavior, commit binding, and evidence—not by account ownership alone.

## Independence levels

- `I0`: builder self-assessment only; never independent.
- `I1`: separate AI context, read-only, distinct context ID, commit-bound attestation.
- `I2`: deterministic tools and CI recompute primary evidence.
- `I3`: external competent human or organizational verifier. Required only for critical changes or when policy explicitly escalates.

## Human authorization levels

Human authorization is separate from technical independence:

- `H0`: no human authorization needed after the engine derives `APPROVED`; applies only to eligible low or medium risk.
- `H1`: the repository owner authorizes a high-risk change by manually merging the exact approved head. The owner does not need to read every line.
- `H2`: dual human authorization for critical changes. Solo operation cannot satisfy H2 without an external person.

An AI agent cannot claim H1 or H2 and cannot merge on behalf of the owner unless a separate explicit policy and authorization permit it.

## Approval by risk

### Low and medium

Approval may be automatic only when all policy gates pass, the change reaches at least E6/T4/I1+I2, rollback is tested, evidence is bound to the integrable commit, and no incompatible uncertainty remains.

### High

The engine may derive `APPROVED` when all required gates pass, the change reaches E7/T5/I1+I2, a separate AI audit is valid, target-environment observation matches the exact package digest, and no blockers remain.

The final action is H1: the owner chooses whether to merge. That click is authorization, not a line-by-line code review.

### Critical

Critical changes require E8/T6/I1+I2+I3 and H2. They remain blocked for a solo operator until a qualified external human participates.

## Audit attestation contract

A PR review comment must contain:

```text
ASI-SOLO-AUDIT-V1
ASI-AUDIT-EVIDENCE-URL: https://raw.githubusercontent.com/...
ASI-AUDIT-EVIDENCE-SHA256: sha256:<64 lowercase hex characters>
```

The referenced JSON must include:

- `attestation_version: 1`;
- `operator_mode: solo`;
- repository and exact head commit;
- builder and auditor context IDs;
- read-only audit result, checks, findings, timestamp, and empty write actions;
- optional target observation for `chatgpt`, `codex`, or `openai-api`;
- exact portable package digest when target observation is claimed.

Any stale head, matching context IDs, write action, invalid digest, unsupported environment, failed result, or expired evidence blocks promotion.

## Forensic review

Line-by-line review remains exceptional. It activates only for integrity conflicts, forbidden paths, unexpected binaries, unbounded changes, obfuscation, contradictory evidence, incidents, or critical properties that lack executable verification.

## Owner responsibilities

The owner handles only decisions that cannot be delegated safely:

- authorizing high-risk merge after the engine derives `APPROVED`;
- approving policy changes and exceptions;
- controlling secrets, production access, destructive operations, money, and irreversible actions;
- obtaining external human participation for critical changes.
