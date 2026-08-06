#!/usr/bin/env python3
"""Verify branch protection binds ASI Trust Anchor to its producer GitHub App."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, cast

API_VERSION = "2022-11-28"
EXPECTED_CHECK = "ASI Trust Anchor"


def api_request(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "asi-trust-anchor",
        },
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def enabled(value: Any) -> bool:
    return isinstance(value, dict) and value.get("enabled") is True


def evaluate_binding(
    protection: dict[str, Any],
    check_runs: dict[str, Any],
    expected_check: str = EXPECTED_CHECK,
) -> dict[str, Any]:
    missing: list[str] = []

    raw_runs = check_runs.get("check_runs")
    if not isinstance(raw_runs, list):
        raise ValueError("Check-runs response must contain a list.")
    producer_app_ids = sorted(
        {
            app["id"]
            for item in raw_runs
            if isinstance(item, dict)
            and item.get("name") == expected_check
            and isinstance(item.get("app"), dict)
            and isinstance((app := cast(dict[str, Any], item["app"])).get("id"), int)
        }
    )
    if len(producer_app_ids) != 1:
        missing.append("single_trusted_check_producer")

    status = protection.get("required_status_checks")
    observed_checks: list[dict[str, Any]] = []
    if not isinstance(status, dict):
        missing.append("required_status_checks")
    else:
        if status.get("strict") is not True:
            missing.append("strict_status_checks")
        raw_checks = status.get("checks")
        if not isinstance(raw_checks, list):
            missing.append("app_bound_status_checks")
        else:
            observed_checks = [
                cast(dict[str, Any], item)
                for item in raw_checks
                if isinstance(item, dict)
            ]
            matched = [
                item
                for item in observed_checks
                if item.get("context") == expected_check
                and item.get("app_id") in producer_app_ids
            ]
            if not matched:
                missing.append("required_check_app_binding")

    if not enabled(protection.get("enforce_admins")):
        missing.append("enforce_admins")
    if not enabled(protection.get("required_conversation_resolution")):
        missing.append("required_conversation_resolution")
    if enabled(protection.get("allow_force_pushes")):
        missing.append("force_pushes_must_be_disabled")
    if enabled(protection.get("allow_deletions")):
        missing.append("branch_deletions_must_be_disabled")

    return {
        "verification_version": 1,
        "expected_check": expected_check,
        "producer_app_ids": producer_app_ids,
        "observed_required_checks": observed_checks,
        "missing_or_invalid_controls": sorted(missing),
        "passed": not missing,
    }


def main() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    head_sha = os.environ.get("ASI_HEAD_SHA", "")
    branch = os.environ.get("ASI_PROTECTED_BRANCH", "main")
    token = os.environ.get("GITHUB_TOKEN", "")
    admin_token = os.environ.get("ASI_GITHUB_ADMIN_TOKEN", "")
    api_base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    output_dir = Path(
        os.environ.get(
            "ASI_TRUST_OUTPUT",
            str(Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "asi-trust-anchor"),
        )
    )
    try:
        if repository.count("/") != 1:
            raise ValueError("GITHUB_REPOSITORY must use owner/repository format.")
        if len(head_sha) != 40:
            raise ValueError("ASI_HEAD_SHA must be a full commit SHA.")
        if not token:
            raise ValueError("GITHUB_TOKEN is required.")
        if not admin_token:
            raise ValueError("ASI_GITHUB_ADMIN_TOKEN is required.")

        encoded_branch = urllib.parse.quote(branch, safe="")
        check_runs = api_request(
            f"{api_base}/repos/{repository}/commits/{head_sha}/check-runs"
            f"?check_name={urllib.parse.quote(EXPECTED_CHECK, safe='')}"
            "&filter=latest&per_page=100",
            token,
        )
        protection = api_request(
            f"{api_base}/repos/{repository}/branches/"
            f"{encoded_branch}/protection",
            admin_token,
        )
        if not isinstance(check_runs, dict) or not isinstance(protection, dict):
            raise ValueError("GitHub returned an invalid protection response.")

        write_json(output_dir / "check-runs-raw.json", check_runs)
        write_json(output_dir / "branch-protection-raw.json", protection)
        report = evaluate_binding(protection, check_runs)
        report.update(
            {
                "repository": repository,
                "head_sha": head_sha,
                "branch": branch,
            }
        )
        write_json(output_dir / "branch-protection-verification.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    except (
        OSError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        report = {
            "verification_version": 1,
            "repository": repository,
            "head_sha": head_sha,
            "branch": branch,
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_json(output_dir / "branch-protection-verification.json", report)
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
