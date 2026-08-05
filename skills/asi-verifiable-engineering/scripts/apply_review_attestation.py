#!/usr/bin/env python3
"""Apply a verified GitHub review attestation to an ASI evidence manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

PENDING_REVIEW_ITEMS = {
    "Independent targeted human review is pending.",
    "Required gate independent_audit is not verified.",
}
PENDING_REVIEW_RISKS = {
    "Independent targeted human review has not been completed.",
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


def apply_attestation(
    manifest: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    if report.get("passed") is not True:
        return manifest
    approvals = report.get("approvals")
    if not isinstance(approvals, list) or not approvals:
        raise ValueError("Passed review report contains no approvals.")
    if report.get("head_commit") != manifest.get("head_commit"):
        raise ValueError("Review report is not bound to the manifest head commit.")

    review = manifest.get("review")
    if not isinstance(review, dict):
        raise ValueError("Manifest review object is missing.")
    if report.get("builder") != review.get("builder"):
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

    command = _command(manifest, "independent_audit")
    if command.get("exit_code") != 0:
        raise ValueError("Independent audit command did not pass.")
    evidence = {
        "result_artifact": command.get("result_artifact"),
        "result_digest": command.get("result_digest"),
        "log_artifact": command.get("log_artifact"),
        "log_digest": command.get("log_digest"),
    }
    if any(not evidence.get(field) for field in evidence):
        raise ValueError("Independent audit command has incomplete evidence.")

    gates = manifest.get("gates")
    gate_evidence = manifest.get("gate_evidence")
    if not isinstance(gates, dict) or not isinstance(gate_evidence, dict):
        raise ValueError("Manifest gates are missing.")
    gates["independent_audit"] = "passed"
    gate_evidence["independent_audit"] = evidence

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
    review["attestation"] = report

    independence = manifest.get("independence")
    if not isinstance(independence, list):
        raise ValueError("Manifest independence list is missing.")
    manifest["independence"] = sorted(set([*independence, "I3"]))
    manifest["approved_by"] = sorted(set(reviewers))
    manifest["unverified"] = sorted(
        item
        for item in manifest.get("unverified", [])
        if isinstance(item, str) and item not in PENDING_REVIEW_ITEMS
    )
    manifest["residual_risks"] = sorted(
        item
        for item in manifest.get("residual_risks", [])
        if isinstance(item, str) and item not in PENDING_REVIEW_RISKS
    )
    return manifest


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: apply_review_attestation.py MANIFEST REVIEW_REPORT",
            file=sys.stderr,
        )
        return 2
    manifest_path = Path(sys.argv[1])
    report_path = Path(sys.argv[2])
    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        report_raw = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(manifest_raw, dict) or not isinstance(report_raw, dict):
            raise ValueError("Manifest and review report roots must be objects.")
        manifest = apply_attestation(manifest_raw, report_raw)
        temporary = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot apply review attestation: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
