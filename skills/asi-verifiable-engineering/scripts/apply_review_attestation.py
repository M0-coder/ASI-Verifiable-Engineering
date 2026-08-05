#!/usr/bin/env python3
"""Apply verified solo-operator audit and target-observation attestations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

PENDING_AUDIT_ITEMS = {
    "Independent separate-context AI audit is pending.",
    "Independent targeted human review is pending.",
    "Required gate independent_audit is not verified.",
}
PENDING_OBSERVATION_ITEMS = {
    "Installation in the target agent environment is pending.",
    "Required gate target_environment_observation is not verified.",
}
PENDING_AUDIT_RISKS = {
    "Independent separate-context AI audit has not been completed.",
    "Independent targeted human review has not been completed.",
}
PENDING_OBSERVATION_RISKS = {
    "The Skill has not been observed in the target environment.",
}


def _command(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    commands = manifest.get("commands")
    if not isinstance(commands, list):
        raise ValueError("Manifest commands are missing.")
    result = next(
        (
            item
            for item in commands
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )
    if not isinstance(result, dict):
        raise ValueError(f"Measured command is missing: {name}")
    return cast(dict[str, Any], result)


def _gate_evidence(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    command = _command(manifest, name)
    if command.get("exit_code") != 0:
        raise ValueError(f"Measured gate did not pass: {name}")
    evidence = {
        "result_artifact": command.get("result_artifact"),
        "result_digest": command.get("result_digest"),
        "log_artifact": command.get("log_artifact"),
        "log_digest": command.get("log_digest"),
    }
    if any(not evidence.get(field) for field in evidence):
        raise ValueError(f"Measured gate has incomplete evidence: {name}")
    return evidence


def _remove_strings(value: Any, removed: set[str]) -> list[str]:
    return (
        sorted(
            item
            for item in value
            if isinstance(item, str) and item not in removed
        )
        if isinstance(value, list)
        else []
    )


def apply_attestations(
    manifest: dict[str, Any],
    audit_report: dict[str, Any],
    observation_report: dict[str, Any],
) -> dict[str, Any]:
    if audit_report.get("passed") is not True:
        return manifest
    audits = audit_report.get("audits")
    if not isinstance(audits, list) or not audits:
        raise ValueError("Passed audit report contains no audit attestations.")
    if audit_report.get("head_commit") != manifest.get("head_commit"):
        raise ValueError("Audit report is not bound to the manifest head commit.")

    review = manifest.get("review")
    if not isinstance(review, dict):
        raise ValueError("Manifest review object is missing.")
    builder_context_id = review.get("builder")
    if audit_report.get("builder_context_id") != builder_context_id:
        raise ValueError("Audit report builder context does not match the manifest.")

    accepted_audit: dict[str, Any] | None = None
    for item in audits:
        if not isinstance(item, dict):
            continue
        auditor_context_id = item.get("auditor_context_id")
        if not isinstance(auditor_context_id, str) or not auditor_context_id:
            continue
        if auditor_context_id == builder_context_id:
            continue
        if item.get("head_commit") != manifest.get("head_commit"):
            continue
        audit = item.get("audit")
        if not isinstance(audit, dict):
            continue
        if audit.get("mode") != "read_only" or audit.get("result") != "passed":
            continue
        if audit.get("write_actions") != []:
            continue
        accepted_audit = cast(dict[str, Any], item)
        break
    if accepted_audit is None:
        raise ValueError(
            "No audit attestation proves a distinct read-only AI context."
        )

    gates = manifest.get("gates")
    gate_evidence = manifest.get("gate_evidence")
    if not isinstance(gates, dict) or not isinstance(gate_evidence, dict):
        raise ValueError("Manifest gates are missing.")
    if gates.get("independent_audit") != "passed":
        raise ValueError("independent_audit gate is not passed in the manifest.")
    gate_evidence["independent_audit"] = _gate_evidence(
        manifest,
        "independent_audit",
    )

    auditor_context_id = cast(str, accepted_audit["auditor_context_id"])
    review["auditor"] = auditor_context_id
    review["auditor_actor"] = accepted_audit.get("actor")
    review["same_context"] = False
    review["audit_review"] = {
        "required": True,
        "completed": True,
        "mode": "separate_ai_read_only",
        "source": "github_review_comment_and_external_evidence",
    }
    review["human_review"] = {
        "required": True,
        "completed": False,
        "mode": "owner_merge",
    }
    review["attestation"] = accepted_audit

    independence = manifest.get("independence")
    if not isinstance(independence, list):
        raise ValueError("Manifest independence list is missing.")
    manifest["independence"] = sorted(set([*independence, "I1"]))
    manifest["unverified"] = _remove_strings(
        manifest.get("unverified"),
        PENDING_AUDIT_ITEMS,
    )
    manifest["residual_risks"] = _remove_strings(
        manifest.get("residual_risks"),
        PENDING_AUDIT_RISKS,
    )

    if observation_report.get("observation_passed") is not True:
        return manifest
    if observation_report.get("head_commit") != manifest.get("head_commit"):
        raise ValueError("Observation report is not bound to the manifest head commit.")
    observations = observation_report.get("observations")
    if not isinstance(observations, list) or not observations:
        raise ValueError("Passed observation report contains no observations.")
    package = manifest.get("package_installability")
    if not isinstance(package, dict):
        raise ValueError("Measured package installability is missing.")
    archive_digest = package.get("archive_digest")

    accepted_observation: dict[str, Any] | None = None
    for item in observations:
        if not isinstance(item, dict):
            continue
        if item.get("auditor_context_id") != auditor_context_id:
            continue
        if item.get("head_commit") != manifest.get("head_commit"):
            continue
        if item.get("package_digest") != archive_digest:
            continue
        if item.get("result") != "passed":
            continue
        accepted_observation = cast(dict[str, Any], item)
        break
    if accepted_observation is None:
        raise ValueError(
            "No target observation matches the audit context, head, and package digest."
        )
    if gates.get("target_environment_observation") != "passed":
        raise ValueError("target_environment_observation gate is not passed.")
    gate_evidence["target_environment_observation"] = _gate_evidence(
        manifest,
        "target_environment_observation",
    )

    review["operational_observation"] = accepted_observation
    manifest["operational_observation"] = accepted_observation
    manifest["evidence_level"] = "E7"
    manifest["assurance_level"] = "T5"
    manifest["unverified"] = _remove_strings(
        manifest.get("unverified"),
        PENDING_OBSERVATION_ITEMS,
    )
    manifest["residual_risks"] = _remove_strings(
        manifest.get("residual_risks"),
        PENDING_OBSERVATION_RISKS,
    )
    return manifest


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Usage: apply_review_attestation.py MANIFEST AUDIT_REPORT OBSERVATION_REPORT",
            file=sys.stderr,
        )
        return 2
    manifest_path = Path(sys.argv[1])
    audit_path = Path(sys.argv[2])
    observation_path = Path(sys.argv[3])
    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        audit_raw = json.loads(audit_path.read_text(encoding="utf-8"))
        observation_raw = json.loads(observation_path.read_text(encoding="utf-8"))
        if not all(
            isinstance(item, dict)
            for item in (manifest_raw, audit_raw, observation_raw)
        ):
            raise ValueError("Manifest and attestation roots must be objects.")
        manifest = apply_attestations(
            cast(dict[str, Any], manifest_raw),
            cast(dict[str, Any], audit_raw),
            cast(dict[str, Any], observation_raw),
        )
        temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot apply attestations: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
