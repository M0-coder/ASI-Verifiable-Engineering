# ASI Verifiable Engineering

ASI is a portable verifiable-engineering Skill for AI agents and software teams. It does not promise error-free software; it prevents confidence from becoming stronger than the available evidence.

## Current candidate

- Portable Skill: `0.2.0-draft.1`
- Doctrine source: `v3.3`
- Architecture projection: `v16`
- Packaging/runtime contract: `v7`
- Canonical decision: `PASS | BLOCKED | ESCALATE`
- Canonical control result: `PASS | FAIL | NOT_VERIFIED | INFRA_FAILURE`

The master doctrine remains the Notion page `00 — Doctrina ASI de Ingeniería Verificable v3.3`. This repository contains a versioned portable derivative and its verification/control plane. A repository snapshot never silently overrides the master doctrine; a semantic change requires a new doctrine version and a new package identity.

## Repository layout

- `skills/asi-verifiable-engineering/` — portable Skill candidate.
- `producer/` — unprivileged evidence producer for pull requests.
- `guardian/` — privileged Trust Anchor verifier and branch-protection binding.
- `tools/` — local package validators.
- `.github/workflows/` — unprivileged evidence workflow and Trust Anchor workflows.
- `.asi/change-budget.json` — repository-specific change-budget policy.

## Core model

`Claim → Risk → Control → Evidence → Decision`

A candidate may be iterated and repaired, but only the Trust Anchor may derive the repository Candidate Decision from admissible evidence. CI success is not itself approval.

## Important boundaries

- No auto-merge.
- A protected-path exception is not merge authorization.
- The constructor cannot certify its own work as independently audited.
- Evidence from another SHA is stale for the current candidate unless the binding explicitly proves equivalence.
- `NOT_VERIFIED` is not a warning synonym for PASS.
- Human words such as “approved”, “tested”, or “verified” never create a machine state.

## Status

This tree is a reconstruction candidate. Until the exact package is built, observed in a target environment, independently audited as required, and accepted by the Trust Anchor, the repository must not claim full conformance or production readiness.
