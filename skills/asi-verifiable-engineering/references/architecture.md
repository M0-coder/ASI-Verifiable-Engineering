# Architecture Projection v16

Status: `DERIVED / PLANNED` unless implementation evidence proves otherwise.

This file implements doctrine through `norm_ref`; it is not a second normative source.

## Components

- **Context Adapter** — normalizes `REPOSITORY | GREENFIELD | WORKSPACE` into a fixed Work Context.
- **Capability Resolver** — produces a runtime-bound Capability Manifest.
- **Specification/Claim Registry** — maps authorized requirements to claims, assumptions, exclusions, acceptance criteria, and risk.
- **Risk Classifier** — derives initial and post-diff risk.
- **Assurance Planner** — selects controls from claim/risk/policy/capabilities.
- **Constructor** — creates or modifies candidate state.
- **Verification Loop Engine** — executes controls, attacks claims, diagnoses and iterates within scope.
- **Evidence Graph** — binds evidence to candidate/claim/control/toolchain/environment/freshness.
- **Adversarial Evaluator** — searches for weak oracles, policy drift, false greens, stale bindings, hidden side effects, and specification mismatch.
- **Proof Bundle Builder** — assembles traceable decision inputs.
- **Trust Anchor** — validates admissibility and derives Candidate Decision.
- **Normative Evolution Loop** — routes counterevidence about doctrine into governance without runtime self-exemption.

## Authority split

The Constructor and Loop Engine may repair. They cannot emit the trusted Candidate Decision. A source producer may claim a decision, but the Trust Anchor treats it as non-authoritative input.

`branch_protection` or equivalent privileged administrative facts belong to the trusted boundary, not to unprivileged PR code.

## Canonical status projection

Architecture consumes `ASI-NORM-STATUS-001`. Local progress states, loop stop reasons, audit stages, or capability lifecycle states must have their own namespaces and cannot redefine canonical enums.

## Evidence dependency graph

A material change to candidate identity, environment, policy, oracle, toolchain, distribution, or normative identity invalidates dependent evidence. Staleness propagates through dependencies; it is not a manual prose choice.

## Assurance Preservation / Confidence Ratchet

A change that removes, weakens, bypasses, or alters an existing assurance control must provide explicit replacement/compensating evidence and governance. Baseline reduction is never the default fix for a regression.

## Verification Infrastructure Assurance

Controls that judge other controls are themselves in scope. Validate runner identity, workflow provenance, action pins, policy binding, evidence artifact integrity, protected-path authority, and whether CI semantics can hide failures.

## Normative Evolution Loop

`counterevidence → doctrinal finding → DOCTRINE_REVIEW_REQUIRED → Skill Governance Authority → change proposal → impact/assurance preservation → new doctrine/core version → self-audit + independent review when required → new Specification Snapshot/distribution → integrity/authenticity revalidation → activation`

A running distribution cannot rewrite the universal core governing its own decision. If new semantics are required, stop/escalate or start a new runtime/session under the new distribution identity.

## Known architectural threats

- self-grading and correlated evaluators;
- Goodhart/metric gaming;
- specification drift/wrong-target assurance;
- weak oracles and test fragility;
- capability fabrication or leakage;
- cross-project/context contamination;
- context authority injection;
- stale candidate/environment evidence;
- distribution truncation/version skew/authenticity spoofing;
- trust-root substitution;
- mutable specification snapshot/profile hot-swap;
- derived-source authority drift;
- doctrine ossification or runtime self-exemption;
- infinite/expensive repair loops;
- hidden external side effects.

These threats are design risks until instantiated by a concrete Work Context/finding.
