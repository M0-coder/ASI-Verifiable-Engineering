# Security policy

## Scope

Security reports may concern:

- instructions that could cause an agent to exceed authorization;
- ways to bypass risk classification or approval;
- false-green behavior in validators or CI;
- secret exposure;
- dependency or workflow supply-chain risk;
- evidence tampering;
- semantic prompt injection or unsafe Skill activation;
- paths that permit self-approval or direct protected-branch changes.

## Reporting

Do not open a public issue containing an exploitable weakness, secret, private repository data, or instructions that would weaken active controls.

Use GitHub private vulnerability reporting or a private security advisory for this repository. Include:

- affected version and commit;
- reproduction with safe test data;
- expected and observed behavior;
- impact and likely risk class;
- proposed mitigation when known.

## Response principles

- Preserve evidence and the affected commit.
- Do not weaken a control to demonstrate a fix.
- Treat governance, CI, policy, validators, release automation, and Skill activation as high risk by default.
- Prepare rollback before publishing a corrective release.
- Publish a new version and changelog entry after remediation.

## Supported versions

Until the first stable release, only the latest draft branch and latest tagged prerelease are evaluated for fixes.
