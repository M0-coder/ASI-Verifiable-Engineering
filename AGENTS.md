# AGENTS.md

This repository is itself governed by ASI.

## Authority and source hierarchy

1. External platform/security/legal constraints.
2. The current ASI master doctrine version identified by the package Specification Snapshot.
3. Repository-specific policy and Trust Anchor controls.
4. Procedures and implementation details.

The portable package is a versioned derivative. It may implement or serialize doctrine, but it must not silently invent a second universal norm.

## Required working method

Before modifying:

- fix repository, base SHA, head/candidate identity, scope, constraints, and Work Context;
- identify claims and risk;
- inspect applicable capabilities and protected paths;
- define a change budget and rollback;
- start from read-only inspection.

During work:

- keep machine states namespaced;
- never convert `FAIL`, `NOT_VERIFIED`, or `INFRA_FAILURE` into narrative PASS;
- do not reuse evidence from another candidate without explicit binding;
- preserve raw tool/CI results;
- keep unprivileged producer code separate from the privileged Trust Anchor.

## Audits

A read-only audit must record its candidate identity, inspected surface, executed controls, inherited evidence, unavailable controls, and uninspected surface. An audit that performs writes is not independent for the changed candidate.

## Protected control plane

Changes under `.asi/**`, `.github/workflows/**`, `guardian/**`, `producer/**`, `tools/**`, tests, or Skill verification scripts are high-risk repository-control changes. Follow the Trust Anchor exception contract exactly. A control-plane exception permits evaluation only; merge still requires a separate explicit decision when policy requires it.

## Merge boundary

Do not enable auto-merge. Do not merge while `candidate_decision = BLOCKED` or `ESCALATE`. Do not claim merge authorization from a CI result, issue comment, or exception whose scope says `merge_authorized: false`.
