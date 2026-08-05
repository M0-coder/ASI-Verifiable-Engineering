#!/usr/bin/env python3
"""Apply verified review and target-observation attestations to a manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

PENDING_REVIEW_ITEMS = {
    "Independent targeted human review is pending.",
    "Required gate independent_audit is not verified.",
}
PENDING_OBSERVATION_ITEMS = {
    "Installation in the target agent environment is pending.",
    "Required gate target_environment_observation is not verified.",
}
PENDING_REVIEW_RISKS = {
    "Independent targeted human review has not been completed.",
}
PENDING_OBSERVATION_RISKS = {
    "The Skill has not been installed in the target environment.",
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
    return sorted(
        item
        for item in value if isinstance(item, str) and item not in removed
    ) if isinstance(value, list) else []


def apply_attestations(
    manifest: dict[str, Any],
    review_report: dict[str, Any],
    observation_report: dict[str, Any],
) -> dict[str, Any]:
    if review_report.get("passed") is not True:
        return manifest
    approvals = review_report.get("approvals")
    if not isinstance(approvals, list) or not approvals:
        raise ValueError("Passed review report contains no approvals.")
    if review_report.get("head_commit") != manifest.get("head_commit"):
        raise ValueError("Review report is not bound to the manifest head commit.")

    review = manifest.get("review")
    if not isinstance(review, dict):
        raise ValueError("Manifest review object is missing.")
    if review_report.get("builder") != review.get("builder"):
        raise ValueError("Review report builder does not match the manifest builder.")

    reviewers: list[str] = []
    for approval in approvals:
        if not isinstance(approval, dict):
            raise ValueError("Approval entry must be an object.")
        reviewer = approval.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer:
            raise ValueError("Approval reviewer is missing.")
        if reviewer == review.get("builder"):
            raise ValueError("Builder cannot be the independent reviewer.")
        if approval.get("commit_id") != manifest.get("head_commit"):
            raise ValueError("Approval is stale for the manifest head commit.")
        reviewers.append(reviewer)

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

    primary = reviewers[0]
    review["auditor"] = primary
    review["reviewers"] = sorted(set(reviewers))
    review["same_context"] = False
    review["human_review"] = {
        "required": True,
        "completed": True,
        "mode": "targeted",
        "source": "github_pull_request_reviews_api",
    }
    review["attestation"] = review_report

    independence = manifest.get("independence")
    if not isinstance(independence, list):
        raise ValueError("Manifest independence list is missing.")
    manifest["independence"] = sorted(set([*independence, "I3"]))
    manifest["approved_by"] = sorted(set(reviewers))
    manifest["unverified"] = _remove_strings(
        manifest.get("unverified"),
        PENDING_REVIEW_ITEMS,
    )
    manifest["residual_risks"] = _remove_strings(
        manifest.get("residual_risks"),
        PENDING_REVIEW_RISKS,
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
        if item.get("reviewer") not in reviewers:
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
            "No target observation matches the approved reviewer, head, and package digest."
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
            "Usage: apply_review_attestation.py MANIFEST REVIEW_REPORT OBSERVATION_REPORT",
            file=sys.stderr,
        )
        return 2
    manifest_path = Path(sys.argv[1])
    review_path = Path(sys.argv[2])
    observation_path = Path(sys.argv[3])
    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        review_raw = json.loads(review_path.read_text(encoding="utf-8"))
        observation_raw = json.loads(observation_path.read_text(encoding="utf-8"))
        if not all(
            isinstance(item, dict)
            for item in (manifest_raw, review_raw, observation_raw)
        ):
            raise ValueError("Manifest and attestation roots must be objects.")
        manifest = apply_attestations(
            cast(dict[str, Any], manifest_raw),
            cast(dict[str, Any], review_raw),
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
