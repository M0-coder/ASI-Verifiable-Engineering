# Field Validation Profile — EXPERIMENTAL

This profile is **not a new universal norm in doctrine v3.3**. It is an experimental operational projection derived from existing evidence-admissibility, self-audit, output, and doctrine-revisability contracts. Promoting it to REQUIRED universal behavior would require a future doctrine version.

## Why it exists

The first real read-only field trial against `M0-coder/Morimil-app` showed that ASI can distinguish:

- implemented and evidenced capability;
- implemented but scope-limited capability;
- planned/not-yet-implemented capability;
- confirmed defect;
- stale documentation/issue state;
- CI evidence bound to a different SHA;
- a large green test count from system-wide completion.

The trial also exposed a meta-risk: an “end-to-end audit” label can sound stronger than the actual inspected/executed surface. This profile makes that coverage explicit.

## Audit Coverage disclosure

Use `assets/audit-coverage.example.json` and record:

- `inspected`: source/config/docs/issues/workflows actually read;
- `executed`: controls/commands actually executed for this candidate;
- `inherited_evidence`: prior CI/artifacts reused with identity/freshness binding;
- `unavailable`: capabilities or evidence sources not accessible;
- `not_inspected`: known surfaces outside this audit;
- `write_actions`: mutations performed by the auditor;
- `coverage_limitations`: what the audit cannot prove.

A read-only audit with `write_actions != []` is internally inconsistent.

## Doctrine Fitness record

Use `assets/doctrine-fitness.example.json` after field trials to record:

- rules/`norm_ref` actually exercised;
- rules that found material issues;
- rules that produced useful negative evidence;
- rules not exercised;
- false positives/noise;
- missing concepts discovered;
- candidate improvements;
- whether a finding requires `DOCTRINE_REVIEW_REQUIRED`.

The purpose is anti-dogma: controls should earn continued value through evidence, not survive forever because they exist.

## Promotion rule

Do not promote this profile from EXPERIMENTAL solely because one repository benefited from it. Test it across materially different Work Contexts and preserve failures/noise. Any universal promotion requires Skill Governance Authority and a versioned doctrine change.
