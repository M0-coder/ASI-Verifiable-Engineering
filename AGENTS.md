# Instructions for agents working on this repository

This repository defines a governance Skill. Treat modifications as high risk because weakening a control may affect every repository that adopts it.

## Mandatory startup

1. Begin in read-only mode.
2. Identify base, head, integrable commit, branch, and tree state.
3. Read `skills/asi-verifiable-engineering/SKILL.md`.
4. Read `skills/asi-verifiable-engineering/references/solo-operator-mode.md`.
5. Read `.asi/policy.yml` and `.asi/change-budget.json`.
6. Declare intended paths, tests, risk, stop conditions, rollback, and role before editing.

## Role declaration

Every agent must operate as exactly one role.

### Builder

A builder may modify files. It must use the `builder_context_id` declared by the change budget. It cannot issue the independent audit attestation, claim owner authorization, or approve its own work.

### Auditor

An auditor must use a different conversation or agent context and a different `auditor_context_id`.

It must:

- remain read-only;
- target the exact head;
- verify evidence and risk controls;
- record checks and findings;
- record `write_actions: []`;
- block instead of fixing;
- publish a JSON attestation linked by SHA-256.

The same GitHub owner account may post the audit comment. Context identity and behavior—not username alone—establish I1.

## Approval principle

Code is not approved because an AI or human read it. Approval is derived from measured evidence bound to the exact commit and package.

Line-by-line review is not the default. It activates only for forensic triggers such as integrity conflicts, forbidden paths, unexpected binaries, unbounded changes, obfuscation, or contradictory evidence.

## Independence and authorization

- `I1`: separate read-only AI audit context.
- `I2`: deterministic tools and CI.
- `I3`: external human or institutional verification for critical work.

- `H0`: eligible automatic approval for low or medium risk.
- `H1`: owner manually merges an approved high-risk head.
- `H2`: dual human authorization for critical risk.

Agents cannot claim H1 or H2.

## Prohibited actions

- Do not push directly to `main`.
- Do not merge or enable auto-merge.
- Do not fabricate builder or auditor context IDs.
- Do not use the same context for construction and audit.
- Do not modify files during an independent audit.
- Do not claim execution without measured results.
- Do not synthesize exit codes, durations, logs, digests, observations, or approvals.
- Do not weaken policy, CI, tests, CODEOWNERS, validators, or thresholds in a change that benefits from the weakening.
- Do not convert a required failure into a warning.
- Do not treat `continue-on-error` as evidence of a passed gate.
- Do not use example manifests as evidence for a real commit.
- Do not access production secrets or perform irreversible actions without explicit owner authorization.

## Measured execution

Resolve commands from `.asi/policy.yml` and execute them through:

```bash
python skills/asi-verifiable-engineering/scripts/run_gate.py \
  --name <gate> \
  --output-dir <evidence-directory> \
  --policy .asi/policy.yml \
  --policy-key <gate>
```

Preserve exact argv, timestamps, duration, exit code, log, result, digests, policy key, and policy digest.

## Required chain

The strict profile includes:

- identity and change budget;
- branch protection;
- format, lint, and strict types;
- package and reproducibility checks;
- unit, integration, and adversarial tests;
- secrets and supply-chain scans;
- rollback rehearsal;
- separate-context audit;
- target-environment observation;
- cryptographic binding validation;
- evidence-derived decision.

## Audit comment contract

A valid auditor comment contains:

```text
ASI-SOLO-AUDIT-V1
ASI-AUDIT-EVIDENCE-URL: https://raw.githubusercontent.com/...
ASI-AUDIT-EVIDENCE-SHA256: sha256:<digest>
```

The JSON must match the repository, head, builder context, auditor context, audit mode, timestamps, and exact package digest when observation is claimed.

## Decision language

Every evaluation ends with exactly one decision:

- `APPROVED`
- `CONDITIONAL`
- `BLOCKED`
- `REJECTED`

Missing evidence is `NO VERIFICADO`. A builder claim never overrides the derived decision.

For high risk, `APPROVED` means the evidence path is ready for H1. Only the owner may perform the merge.
