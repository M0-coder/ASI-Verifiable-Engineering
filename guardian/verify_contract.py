#!/usr/bin/env python3
"""Verify that the trust-anchor workflow, policy, and verifier agree exactly."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

WORKFLOW_NAME = re.compile(r"^name:\s*(?P<name>[^\n]+?)\s*$", re.MULTILINE)
JOB_NAME = re.compile(
    r"^jobs:\s*$\n"
    r"(?:^[ \t].*\n)*?"
    r"^  verify:\s*$\n"
    r"(?:^    .*\n)*?"
    r"^    name:\s*(?P<name>[^\n]+?)\s*$",
    re.MULTILINE,
)
EXPECTED_CHECK = re.compile(
    r'^EXPECTED_CHECK\s*=\s*["\'](?P<name>[^"\']+)["\']\s*$',
    re.MULTILINE,
)

REQUIRED_WORKFLOW_SNIPPETS = {
    "workflow_dispatch_trigger": "  workflow_dispatch:",
    "workflow_run_trigger": "  workflow_run:",
    "immutable_workflow_checkout": "          ref: ${{ github.workflow_sha }}",
    "trust_anchor_sha_env": "      ASI_TRUST_ANCHOR_SHA: ${{ github.workflow_sha }}",
    "trusted_v2_verifier": "          python3 guardian/verify_run_v2.py 2>&1 |",
    "immutable_checkout_guard": (
        '          test "$(git rev-parse HEAD)" = "$ASI_TRUST_ANCHOR_SHA"'
    ),
    "runtime_output_env": (
        '          echo "ASI_TRUST_OUTPUT=$RUNNER_TEMP/asi-trust-anchor" '
        '>> "$GITHUB_ENV"'
    ),
    "runtime_output_directory": (
        '          mkdir -p "$RUNNER_TEMP/asi-trust-anchor"'
    ),
    "registration_event_guard": "        if: github.event_name == 'workflow_dispatch'",
    "registration_ref_guard": '          test "$GITHUB_REF" = "refs/heads/main"',
    "registration_sha_guard": '          test "$GITHUB_SHA" = "$(git rev-parse HEAD)"',
    "evidence_event_guard": "        if: github.event_name == 'workflow_run'",
}

REQUIRED_ARCHIVE_LIMITS = {
    "max_compressed_bytes",
    "max_files",
    "max_member_bytes",
    "max_total_uncompressed_bytes",
    "max_compression_ratio",
}


def _match_name(pattern: re.Pattern[str], text: str, label: str) -> str:
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"Cannot resolve {label}.")
    return match.group("name").strip()


def _verify_job_env_lines(workflow_text: str) -> list[str]:
    lines = workflow_text.splitlines()
    in_verify = False
    in_env = False
    result: list[str] = []

    for line in lines:
        if line == "  verify:":
            in_verify = True
            continue
        if (
            in_verify
            and line.startswith("  ")
            and not line.startswith("    ")
            and line.strip()
        ):
            break
        if in_verify and line == "    env:":
            in_env = True
            continue
        if in_env:
            if line.startswith("      "):
                result.append(line.strip())
                continue
            if line.strip():
                break

    return result


def evaluate_contract(
    workflow_text: str,
    policy: dict[str, Any],
    verifier_text: str,
) -> dict[str, Any]:
    missing: list[str] = []
    workflow_name = _match_name(WORKFLOW_NAME, workflow_text, "workflow name")
    job_name = _match_name(JOB_NAME, workflow_text, "verify job name")
    verifier_name = _match_name(
        EXPECTED_CHECK,
        verifier_text,
        "verifier expected check",
    )
    policy_name = policy.get("required_check")
    if not isinstance(policy_name, str) or not policy_name:
        raise ValueError("Policy required_check must be a non-empty string.")

    observed_names = {
        "workflow": workflow_name,
        "job": job_name,
        "policy": policy_name,
        "verifier": verifier_name,
    }
    if len(set(observed_names.values())) != 1:
        missing.append("check_name_contract_mismatch")

    for label, snippet in REQUIRED_WORKFLOW_SNIPPETS.items():
        if snippet not in workflow_text:
            missing.append(label)

    if "          ref: main" in workflow_text:
        missing.append("mobile_main_checkout_forbidden")

    job_env_lines = _verify_job_env_lines(workflow_text)
    if any("${{ runner." in line for line in job_env_lines):
        missing.append("runner_context_forbidden_in_job_env")

    if policy.get("version") != 2:
        missing.append("trust_policy_v2")
    if policy.get("artifact_name_version") != 2:
        missing.append("artifact_name_contract_v2")
    archive_limits = policy.get("archive_limits")
    if not isinstance(archive_limits, dict):
        missing.append("archive_limits")
    else:
        missing.extend(
            f"archive_limit_{name}"
            for name in sorted(REQUIRED_ARCHIVE_LIMITS)
            if name not in archive_limits
        )

    return {
        "contract_version": 3,
        "observed_names": observed_names,
        "missing_or_invalid_controls": sorted(set(missing)),
        "passed": not missing,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--workflow", type=Path, required=True)
    result.add_argument("--policy", type=Path, required=True)
    result.add_argument("--verifier", type=Path, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        workflow_text = args.workflow.read_text(encoding="utf-8")
        policy_raw = json.loads(args.policy.read_text(encoding="utf-8"))
        verifier_text = args.verifier.read_text(encoding="utf-8")
        if not isinstance(policy_raw, dict):
            raise ValueError("Trust policy root must be an object.")
        report = evaluate_contract(workflow_text, policy_raw, verifier_text)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Trust-anchor contract verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
