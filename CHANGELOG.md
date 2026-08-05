# Changelog

All notable changes to ASI Verifiable Engineering are recorded here.

## [0.1.0-draft.2] - 2026-08-05

### Added

- Evidence-derived decision engine that does not trust the manifest's claimed decision.
- Measured gate results with timestamps, durations, exit codes, logs, and digests.
- Cryptographic recomputation of policy, diff, changed files, results, and artifacts.
- Change-budget enforcement with forbidden paths, binary detection, and size limits.
- Dedicated format, lint, type, secret, supply-chain, rollback, and package controls.
- Independent GitHub review attestation bound to the current head.
- BIRTH-02 target-environment observation contract bound to reviewer, head, package digest, age, and external SHA-256 evidence.
- Explicit E6 / T4 / I2 to E7 / T5 / I3 promotion path.
- GitHub API verification of effective `main` protection.
- Separate post-merge `main-integrity.yml` workflow that verifies the associated merged PR rather than using a synthetic PR number.
- Tests proving self-review, bots, stale review, missing markers, altered package digests, weak branch protection, and contradictory decision claims are rejected.
- A complete high-risk fixture proving that the engine can derive `APPROVED` from E7 / T5 / I3 evidence.

### Changed

- Line-by-line review is no longer the normal approval gate.
- High-risk review is targeted; forensic review activates only from concrete integrity or scope signals.
- A human approval alone produces I3 but cannot produce T5.
- The written manifest decision is informational and cannot veto or manufacture the independently derived result.
- Pull-request and post-merge verification now use separate event semantics.
- The blocked example is documented with `--expect BLOCKED`.

### Corrected

- Removed circular evidence and synthesized command results.
- Replaced nominal security scans with dedicated controls.
- Prevented stale integrable states from being accepted.
- Added a reachable path beyond T4 instead of declaring permanent installation and protection blockers.
- Removed the invalid PR-number-zero path from `push` verification.

## [0.1.0-draft.1] - 2026-08-05

### Added

- Initial Agent Skill package following the Agent Skills open specification.
- Evidence-driven engineering workflow with read-only audit startup.
- E0-E8 evidence model, T0-T6 assurance model, and I0-I3 independence model.
- Risk-based approval matrix and mandatory stop conditions.
- Policy-as-code template, evidence manifest, and audit templates.
- Repository and policy validators.
- Pull-request CI for structural validation and tests.

### Doctrine source

- Migrated from Notion doctrine version `1.2`.
- Notion remains the adopted authority until this draft is reviewed, merged, and tagged.
