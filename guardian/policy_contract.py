#!/usr/bin/env python3
"""Shared contract for the repository Trust Policy schema and current instance."""

from __future__ import annotations

from typing import Any

POLICY_ID = "asi-trust-policy"
POLICY_SCHEMA_VERSION = 4
MIN_POLICY_REVISION = 5
REQUIRED_PROTECTED_PATHS = {
    ".asi/**",
    ".github/workflows/**",
    "guardian/**",
    "producer/**",
    "skills/asi-verifiable-engineering/**",
    "tools/**",
}


def validate(policy: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if policy.get("version") != POLICY_SCHEMA_VERSION:
        findings.append("trust_policy_schema_v4")
    if policy.get("policy_id") != POLICY_ID:
        findings.append("trust_policy_id")
    revision = policy.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < MIN_POLICY_REVISION:
        findings.append("trust_policy_revision")
    protected = policy.get("protected_paths")
    if not isinstance(protected, list) or not all(isinstance(item, str) for item in protected):
        findings.append("protected_paths")
    else:
        missing = REQUIRED_PROTECTED_PATHS - set(protected)
        findings.extend(f"protected_path:{path}" for path in sorted(missing))
    return findings


def require(policy: dict[str, Any]) -> None:
    findings = validate(policy)
    if findings:
        raise ValueError("Trust policy contract failed: " + ", ".join(findings))
