# ASI Verifiable Engineering

**Status:** bootstrap draft (`0.1.0-draft.2`). The pull request remains blocked until the solo-operator evidence path is exercised, branch protection is active, and the owner explicitly authorizes merge.

ASI Verifiable Engineering is an Agent Skill and verification framework designed for one human owner who delegates implementation and auditing to separate AI chats.

## Objective

Future chats should be able to modify software safely without forcing the owner to inspect every changed line.

A change is not approved because an AI wrote it, explained it, reviewed it, or placed `APPROVED` in a file. The decision engine evaluates the exact integrable commit from measured commands, policy, diff, artifacts, rollback, audit context, and target observation.

## Solo-Operator Mode

The model separates four roles:

1. **Builder chat:** may modify code and owns a stable `builder_context_id`.
2. **Auditor chat:** a different context, read-only, with a distinct `auditor_context_id` and `write_actions: []`.
3. **CI:** executes commands, recomputes bindings, checks context separation, and derives the decision.
4. **Owner:** authorizes high-risk merge after the engine derives `APPROVED`; no line-by-line inspection is required.

The same GitHub account may publish builder and auditor evidence. Independence is established by different chat contexts, read-only behavior, exact commit binding, external evidence, and CI verification—not merely by different usernames.

## Independence and authorization

- `I0`: builder self-assessment.
- `I1`: separate read-only AI audit context.
- `I2`: deterministic tools and CI.
- `I3`: external human or institutional verifier, reserved for critical work.

- `H0`: automatic eligible approval for low/medium risk.
- `H1`: owner manually merges an approved high-risk head.
- `H2`: dual human authorization for critical risk.

## Approval path

### Low and medium

The policy may permit automatic approval after E6/T4/I1+I2, all required gates, tested rollback, valid bindings, and no incompatible residual risk.

### High

The engine may derive `APPROVED` after:

- all technical and governance gates pass;
- a separate AI context produces a valid read-only audit;
- the exact Skill package is observed in ChatGPT, Codex, or OpenAI API;
- evidence reaches E7/T5/I1+I2;
- no blockers remain.

The owner then performs H1 by manually merging the approved head.

### Critical

Critical changes require E8/T6/I1+I2+I3 and H2. They cannot be approved by a solo operator without qualified external human participation.

## Audit attestation

The auditor publishes a GitHub PR review comment containing:

```text
ASI-SOLO-AUDIT-V1
ASI-AUDIT-EVIDENCE-URL: https://raw.githubusercontent.com/...
ASI-AUDIT-EVIDENCE-SHA256: sha256:<digest>
```

The referenced JSON follows:

```text
skills/asi-verifiable-engineering/assets/target-observation.example.json
```

CI rejects the attestation when:

- builder and auditor context IDs match;
- the audit is not read-only;
- any write action is reported;
- the head is stale;
- the URL or digest is invalid;
- the target observation does not match the exact package digest;
- the evidence is too old or otherwise inconsistent.

## Repository layout

```text
.asi/
├── policy.yml
└── change-budget.json

.github/workflows/
├── validate-skill.yml
└── main-integrity.yml

skills/asi-verifiable-engineering/
├── SKILL.md
├── references/
├── assets/
└── scripts/

tests/
tools/
```

## Measured controls

The strict profile includes:

- Git identity and change budget;
- protected canonical branch;
- deterministic formatting, lint, and type checking;
- package validation and reproducible archive;
- unit, integration, and adversarial honesty tests;
- secret and supply-chain scans;
- source rollback rehearsal;
- separate-context audit;
- target-environment observation;
- cryptographic binding validation;
- evidence-derived decision.

A GitHub workflow step shown as successful because it collected evidence is not necessarily a passed gate. The generated manifest is the source of truth.

## Current authority

Until this draft is merged and tagged:

1. Notion doctrine version `1.2` remains the adopted source.
2. This repository is the candidate executable implementation.
3. A tagged release becomes canonical only after explicit owner adoption.

## Decisions

- `APPROVED`
- `CONDITIONAL`
- `BLOCKED`
- `REJECTED`

`NO VERIFICADO` is an evidence state, not a final decision.

The system does not prove that software is perfect. It makes approval claims measurable, reproducible, attributable, and difficult for a builder chat to falsify.
