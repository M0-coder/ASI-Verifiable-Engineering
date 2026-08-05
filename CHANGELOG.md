# Changelog

All notable changes to ASI Verifiable Engineering are recorded here.

## [0.1.0-draft.2] - 2026-08-05

### Added

- Evidence-derived decision engine that does not trust the manifest's claimed decision.
- Measured gate results with timestamps, durations, exit codes, logs, and digests.
- Cryptographic recomputation of policy, diff, changed files, results, and artifacts.
- Change-budget enforcement with forbidden paths, binary detection, size limits, and builder context identity.
- Dedicated format, lint, type, secret, supply-chain, rollback, and package controls.
- Solo-Operator Mode for one human owner using separate builder and auditor AI contexts.
- Read-only AI audit attestation bound to repository, head, builder context, auditor context, timestamp, checks, findings, and zero write actions.
- Target-environment observation bound to the same auditor context and exact package digest.
- Explicit E6/T4/I2 to E7/T5/I1+I2 promotion path.
- Separate human authorization levels H0, H1, and H2.
- H1 owner-merge verification for high-risk changes.
- I3 and H2 reservation for critical changes requiring external human participation.
- GitHub API verification of effective `main` protection without requiring a second human account.
- Separate post-merge `main-integrity.yml` workflow that verifies audit, observation, and owner merge.
- Tests rejecting matching builder/auditor contexts, audit writes, stale heads, invalid package digests, weak branch protection, and contradictory decision claims.
- A complete high-risk fixture proving that the engine can derive `APPROVED` and request H1 owner authorization.
- Regression tests preserving E6/T4 when only external governance gates are pending and downgrading when a technical gate fails.

### Changed

- Independence is based on separate context, read-only behavior, evidence, and deterministic CI—not a second GitHub username.
- Line-by-line review is no longer the normal approval gate.
- High-risk changes require a separate AI audit, target observation, E7/T5/I1+I2, and manual owner merge.
- Critical changes still require I3 and dual human authorization.
- A separate AI audit cannot modify code or claim owner authorization.
- The written manifest decision is informational and cannot veto or manufacture the independently derived result.
- Pull-request and post-merge verification use separate event semantics.
- External branch protection, AI audit, and target observation remain blocking gates without erasing valid E6/T4 technical evidence.

### Corrected

- Removed the incorrect assumption that a solo owner must find a second human for ordinary high-risk repository work.
- Removed circular evidence and synthesized command results.
- Replaced nominal security scans with dedicated controls.
- Prevented stale integrable states from being accepted.
- Added a reachable path beyond T4 instead of declaring permanent installation and protection blockers.
- Removed the invalid PR-number-zero path from `push` verification.
- Synchronized the Skill, README, agent instructions, policy template, and observation example with Solo-Operator Mode.

### Verified state

- Current verified workflow run: `31045970332`.
- Current verified head: `b8adca686992054fd2a82126f5336f5f75c7cc37`.
- Current integrable commit: `dfee0833c2ea9dea1466fa2a35a379f98a92c2f7`.
- All internal technical gates passed.
- 36 tests passed.
- Evidence reached E6/T4/I2.
- Branch protection, separate-context audit, and target observation remained the only failed gates.

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
