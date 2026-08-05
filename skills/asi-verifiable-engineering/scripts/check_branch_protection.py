#!/usr/bin/env python3
"""Verify solo-operator GitHub branch protection for the canonical branch."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

EXPECTED_CHECK = "Verify measured gates and derive decision"


def _enabled(value: Any) -> bool:
    return isinstance(value, dict) and value.get("enabled") is True


def evaluate_protection(data: dict[str, Any], expected_check: str) -> dict[str, Any]:
    missing: list[str] = []

    status = data.get("required_status_checks")
    contexts: set[str] = set()
    if not isinstance(status, dict):
        missing.append("required_status_checks")
    else:
        if status.get("strict") is not True:
            missing.append("strict_status_checks")
        raw_contexts = status.get("contexts")
        if isinstance(raw_contexts, list):
            contexts.update(item for item in raw_contexts if isinstance(item, str))
        raw_checks = status.get("checks")
        if isinstance(raw_checks, list):
            for item in raw_checks:
                if isinstance(item, dict) and isinstance(item.get("context"), str):
                    contexts.add(cast(str, item["context"]))
        if expected_check not in contexts:
            missing.append("required_asi_status_check")

    if not _enabled(data.get("enforce_admins")):
        missing.append("enforce_admins")
    if not _enabled(data.get("required_conversation_resolution")):
        missing.append("required_conversation_resolution")
    if _enabled(data.get("allow_force_pushes")):
        missing.append("force_pushes_must_be_disabled")
    if _enabled(data.get("allow_deletions")):
        missing.append("branch_deletions_must_be_disabled")

    return {
        "verification_version": 2,
        "operator_mode": "solo",
        "expected_status_check": expected_check,
        "observed_status_checks": sorted(contexts),
        "human_pr_approval_required": False,
        "missing_or_invalid_controls": sorted(missing),
        "passed": not missing,
    }


def fetch_protection(repository: str, branch: str, token: str) -> dict[str, Any]:
    owner, repo = repository.split("/", 1)
    url = (
        "https://api.github.com/repos/"
        f"{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(repo, safe='')}/branches/"
        f"{urllib.parse.quote(branch, safe='')}/protection"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "asi-verifiable-engineering",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = json.loads(response.read().decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Branch-protection response must be an object.")
    return cast(dict[str, Any], raw)


def main() -> int:
    repository = os.environ.get("ASI_REPOSITORY", "")
    branch = os.environ.get("ASI_PROTECTED_BRANCH", "main")
    token = os.environ.get("ASI_GITHUB_ADMIN_TOKEN", "")
    try:
        if repository.count("/") != 1:
            raise ValueError("ASI_REPOSITORY must use owner/repository format.")
        if not branch:
            raise ValueError("ASI_PROTECTED_BRANCH is required.")
        if not token:
            raise ValueError(
                "ASI_GITHUB_ADMIN_TOKEN is required with Administration: read permission."
            )
        protection = fetch_protection(repository, branch, token)
        report = evaluate_protection(protection, EXPECTED_CHECK)
        report["repository"] = repository
        report["branch"] = branch
    except (
        OSError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        report = {
            "verification_version": 2,
            "operator_mode": "solo",
            "repository": repository,
            "branch": branch,
            "passed": False,
            "error": str(exc),
        }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
