# Changelog

All notable changes to ASI Verifiable Engineering are recorded here.

## [0.1.0-draft.2] - 2026-08-05

### Added

- Evidence-derived decision engine: `evaluate_change.py`.
- Strict automated-acceptance policy for low- and medium-risk changes.
- Explicit objective of approval without default line-by-line review.
- Annex E defining targeted human review and forensic-only exhaustive reading.
- Commit, policy, diff, gate, artifact, budget, test-honesty, and reviewer bindings in the evidence manifest.
- Regression tests proving that deceptive `APPROVED` claims are blocked.

### Changed

- Required gates can no longer be disabled in the strict policy profile.
- Evidence validation now requires digest-bound primary artifacts and distinct builder/auditor contexts.
- CI now derives the approval result rather than trusting the manifest decision field.
- High- and critical-risk review is defined as targeted risk review, not automatic full line-by-line reading.

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
