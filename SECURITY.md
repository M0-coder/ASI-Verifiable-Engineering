# Security Policy

ASI-Verifiable-Engineering is a pre-release verification framework. No published Skill version is currently declared production-certified.

## Reporting

Do not publish secrets, tokens, private keys, signing material, private repository evidence, or exploit details in a public issue. If a private channel with the repository owner is available, use it. Otherwise open a minimal public issue requesting private coordination without sensitive details.

A useful report identifies the exact commit SHA, affected component, observed impact, reproduction conditions, and whether the issue affects the unprivileged producer, portable Skill, Trust Anchor, or repository policy.

## Trust boundaries

- `producer/**` and `Validate ASI Skill` are unprivileged evidence producers.
- `guardian/**` and `ASI Trust Anchor` form the privileged verification boundary.
- Pull-request code must never be executed with privileged repository credentials by the Trust Anchor.
- Protected-path exceptions must bind exact PR/base/head/path scope and do not authorize merge.
- Missing evidence is `NOT_VERIFIED`, never a clean security result.

## Supply chain

GitHub Actions used by trusted workflows are pinned by commit SHA. The Gradle/npm-style dependency model is not used by the current stdlib-only control plane. Any future third-party runtime dependency must be version-locked, provenance-reviewed, and added through a versioned assurance change.
