# Changelog

## 0.2.0-draft.1 — 2026-08-08

Reconstruction candidate aligned to Doctrine v3.3, Architecture v16, and Packaging/runtime v7.

- replaces the frozen Doctrine 1.2 Skill candidate with canonical namespaced domains;
- removes legacy final-decision vocabulary from the active Skill contract;
- adds stable `norm_id`/`norm_ref` assets and a Specification Snapshot;
- adds explicit Audit Coverage disclosure and an experimental Doctrine Fitness profile informed by the Morimil-app field trial;
- packages the real Skill tree instead of the BIRTH-06 marker fixture;
- keeps the Trust Anchor fail-closed and preserves stable GitHub owner identity binding;
- expands protected control-plane scope to `producer/**`, the portable Skill, `tools/**`, `mypy.ini`, and `requirements-ci.lock`;
- adds Trust Policy instance revisioning, `policy_contract.py`, and runtime `verify_run_v4.py` so protected domains cannot silently disappear;
- adds strict mypy 2.3.0 source evidence with version-locked CI dependencies;
- updates `actions/checkout` and `actions/setup-python` to Node-24-native releases pinned by immutable commit SHA;
- preserves evidence artifacts even when a measured source gate fails, then fails the source workflow after upload so a real measured `FAIL` cannot appear as a green workflow;
- keeps `independent_audit`, `target_environment_observation`, branch protection, and unavailable controls as explicit `NOT_VERIFIED`/trusted inputs rather than fabricating evidence.

Historical BIRTH implementation branches and pull requests remain Git history; they are not normative sources for this candidate.
