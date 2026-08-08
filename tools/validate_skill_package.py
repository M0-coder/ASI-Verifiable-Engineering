#!/usr/bin/env python3
"""Validate the portable ASI Skill source without external dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

EXPECTED_DOMAINS = {
    "assurance_level": ["T0", "T1", "T2", "T3", "T4", "T5", "T6"],
    "candidate_decision": ["PASS", "BLOCKED", "ESCALATE"],
    "capability_availability": ["AVAILABLE", "UNAVAILABLE", "UNKNOWN"],
    "control_maturity": [
        "EXPERIMENTAL", "SHADOW", "OBSERVED", "VALIDATED", "REQUIRED", "DEPRECATED", "RETIRED"
    ],
    "control_result": ["PASS", "FAIL", "NOT_VERIFIED", "INFRA_FAILURE"],
    "evaluator_aggregate": [
        "CONSENSUS_PASS", "CONSENSUS_FAIL", "DISAGREEMENT", "INSUFFICIENT_EVIDENCE"
    ],
    "evidence_freshness": ["FRESH", "STALE_IDENTITY", "STALE_ENVIRONMENT", "SUPERSEDED"],
    "evidence_maturity": ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"],
}

REQUIRED_NORMS = {
    "ASI-NORM-LANGUAGE-001",
    "ASI-NORM-PRECEDENCE-001",
    "ASI-NORM-STATUS-001",
    "ASI-NORM-EVIDENCE-001",
    "ASI-NORM-VERSIONING-001",
    "ASI-NORM-PROJECTION-001",
    "ASI-NORM-STRUCTURE-001",
    "ASI-NORM-CORE-001",
    "ASI-NORM-CONTROL-LIFECYCLE-001",
    "ASI-NORM-AUTHORITY-001",
    "ASI-NORM-FRESHNESS-001",
    "ASI-NORM-CLAIM-SCOPE-001",
    "ASI-NORM-EXCEPTION-001",
    "ASI-NORM-SPEC-INTEGRITY-001",
    "ASI-NORM-WORK-CONTEXT-001",
    "ASI-NORM-EVIDENCE-MATURITY-001",
    "ASI-NORM-AUDIT-001",
    "ASI-NORM-ARCH-QUALITY-001",
    "ASI-NORM-TESTING-001",
    "ASI-NORM-CHANGE-001",
    "ASI-NORM-SUPPLY-CHAIN-001",
    "ASI-NORM-REPRO-001",
    "ASI-NORM-CI-001",
    "ASI-NORM-STOP-001",
    "ASI-NORM-FINDING-001",
    "ASI-NORM-METRICS-001",
    "ASI-NORM-AGENT-001",
    "ASI-NORM-PROOF-001",
    "ASI-NORM-DECISION-001",
    "ASI-NORM-VERIFIED-DONE-001",
    "ASI-NORM-OUTPUT-001",
    "ASI-NORM-AI-PROFILE-001",
    "ASI-NORM-AI-ACCEPTANCE-001",
    "ASI-NORM-ASSURANCE-LEVELS-001",
    "ASI-NORM-RISK-001",
    "ASI-NORM-POLICY-001",
    "ASI-NORM-BOOTSTRAP-001",
}

FORBIDDEN_ACTIVE_DECISION_TOKENS = {
    "APPROVED",
    "CONDITIONAL",
    "REJECTED",
    "APROBADO CONDICIONALMENTE",
}


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return raw


def frontmatter(text: str) -> str:
    match = re.match(r"\A---\n(?P<body>.*?)\n---\n", text, re.DOTALL)
    if match is None:
        raise ValueError("SKILL.md is missing YAML-style frontmatter")
    return match.group("body")


def validate(root: Path) -> dict[str, Any]:
    findings: list[str] = []
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return {"passed": False, "findings": ["manifest_missing"]}
    manifest = load_json(manifest_path)
    if manifest.get("schema") != "asi.portable_manifest.v1":
        findings.append("manifest_schema")
    expected_versions = {
        "skill_version": "0.2.0-draft.1",
        "doctrine_version": "3.3",
        "architecture_version": "16",
        "packaging_contract_version": "7",
    }
    for field, expected in expected_versions.items():
        if manifest.get(field) != expected:
            findings.append(f"manifest_{field}")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        findings.append("manifest_files")
        files = {}
    for relative, expected_digest in sorted(files.items()):
        if not isinstance(relative, str) or not isinstance(expected_digest, str):
            findings.append("manifest_file_entry")
            continue
        path = root / relative
        if not path.is_file():
            findings.append(f"missing:{relative}")
            continue
        actual = git_blob_sha1(path.read_bytes())
        if actual != expected_digest:
            findings.append(f"digest:{relative}")

    allowed = set(files) | {"manifest.json"}
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(observed - allowed)
    if unexpected:
        findings.extend(f"unexpected:{path}" for path in unexpected)

    skill_path = root / "SKILL.md"
    if skill_path.is_file():
        skill_text = skill_path.read_text(encoding="utf-8")
        try:
            meta = frontmatter(skill_text)
        except ValueError:
            findings.append("skill_frontmatter")
        else:
            for snippet in (
                'version: "0.2.0-draft.1"',
                'doctrine-version: "3.3"',
                'architecture-version: "16"',
                'packaging-contract-version: "7"',
            ):
                if snippet not in meta:
                    findings.append(f"skill_metadata:{snippet}")
        active_text = skill_text + "\n" + (root / "references/core-doctrine.md").read_text(encoding="utf-8")
        for token in FORBIDDEN_ACTIVE_DECISION_TOKENS:
            if re.search(rf"\b{re.escape(token)}\b", active_text):
                findings.append(f"legacy_decision_token:{token}")
    else:
        findings.append("skill_missing")

    domains_path = root / "assets/canonical-domains.json"
    if domains_path.is_file():
        domains = load_json(domains_path)
        for name, expected in EXPECTED_DOMAINS.items():
            if domains.get(name) != expected:
                findings.append(f"canonical_domain:{name}")
    else:
        findings.append("canonical_domains_missing")

    registry_path = root / "assets/norm-registry.json"
    if registry_path.is_file():
        registry = load_json(registry_path)
        raw_norms = registry.get("norms")
        if not isinstance(raw_norms, list):
            findings.append("norm_registry_entries")
        else:
            ids = [item.get("norm_id") for item in raw_norms if isinstance(item, dict)]
            if len(ids) != len(set(ids)):
                findings.append("norm_registry_duplicate_id")
            if set(ids) != REQUIRED_NORMS:
                findings.append("norm_registry_required_set")
    else:
        findings.append("norm_registry_missing")

    snapshot_path = root / "assets/specification-snapshot.json"
    if snapshot_path.is_file():
        snapshot = load_json(snapshot_path)
        if snapshot.get("doctrine_version") != "3.3":
            findings.append("snapshot_doctrine_version")
        if snapshot.get("architecture_version") != "16":
            findings.append("snapshot_architecture_version")
        if snapshot.get("packaging_contract_version") != "7":
            findings.append("snapshot_packaging_version")
        norm = snapshot.get("norm_registry")
        if not isinstance(norm, dict) or norm.get("git_blob_sha1") != files.get("assets/norm-registry.json"):
            findings.append("snapshot_norm_registry_binding")
        master = snapshot.get("master_source")
        if not isinstance(master, dict) or master.get("source_export_digest_status") != "NOT_VERIFIED":
            findings.append("snapshot_source_digest_honesty")
    else:
        findings.append("snapshot_missing")

    field_path = root / "references/field-validation.md"
    if not field_path.is_file() or "EXPERIMENTAL" not in field_path.read_text(encoding="utf-8"):
        findings.append("field_validation_maturity")

    return {
        "schema": "asi.package_validation.v1",
        "passed": not findings,
        "findings": sorted(set(findings)),
        "observed_files": sorted(observed),
        "manifest_git_blob_sha1": git_blob_sha1(manifest_path.read_bytes()),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("root", nargs="?", default="skills/asi-verifiable-engineering")
    return result


def main() -> int:
    args = parser().parse_args()
    report = validate(Path(args.root).resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
