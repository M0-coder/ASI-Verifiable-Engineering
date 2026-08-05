#!/usr/bin/env python3
"""Verify that a main-branch commit came from an attested merged pull request."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

from collect_github_review import evaluate_reviews, fetch_reviews


def fetch_associated_pull_requests(
    repository: str,
    commit: str,
    token: str,
) -> list[dict[str, Any]]:
    owner, repo = repository.split("/", 1)
    url = (
        "https://api.github.com/repos/"
        f"{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(repo, safe='')}/commits/"
        f"{urllib.parse.quote(commit, safe='')}/pulls"
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
    if not isinstance(raw, list):
        raise ValueError("Associated pull-request response must be a list.")
    return [cast(dict[str, Any], item) for item in raw if isinstance(item, dict)]


def evaluate_merged_commit(
    repository: str,
    commit: str,
    token: str,
) -> dict[str, Any]:
    candidates = fetch_associated_pull_requests(repository, commit, token)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for pull_request in candidates:
        base_value = pull_request.get("base")
        head_value = pull_request.get("head")
        user_value = pull_request.get("user")
        number_value = pull_request.get("number")
        reasons: list[str] = []
        if not pull_request.get("merged_at"):
            reasons.append("pull_request_is_not_merged")
        if not isinstance(base_value, dict) or base_value.get("ref") != "main":
            reasons.append("pull_request_did_not_target_main")
        if (
            not isinstance(head_value, dict)
            or not isinstance(head_value.get("sha"), str)
        ):
            reasons.append("pull_request_head_is_missing")
        if (
            not isinstance(user_value, dict)
            or not isinstance(user_value.get("login"), str)
        ):
            reasons.append("pull_request_builder_is_missing")
        if not isinstance(number_value, int) or number_value <= 0:
            reasons.append("pull_request_number_is_invalid")
        if reasons:
            rejected.append({"number": number_value, "reasons": reasons})
            continue

        assert isinstance(head_value, dict)
        assert isinstance(user_value, dict)
        assert isinstance(number_value, int)
        head_sha_value = head_value.get("sha")
        builder_value = user_value.get("login")
        assert isinstance(head_sha_value, str)
        assert isinstance(builder_value, str)
        head_sha = head_sha_value
        builder = builder_value
        number = number_value

        reviews = fetch_reviews(repository, number, token)
        attestation = evaluate_reviews(
            reviews,
            builder,
            head_sha,
            repository,
        )
        if attestation.get("passed") is not True:
            reasons.append("independent_review_attestation_missing")
        if attestation.get("observation_passed") is not True:
            reasons.append("target_observation_attestation_missing")
        if reasons:
            rejected.append(
                {
                    "number": number,
                    "head_commit": head_sha,
                    "reasons": reasons,
                    "attestation": attestation,
                }
            )
            continue
        accepted.append(
            {
                "number": number,
                "head_commit": head_sha,
                "merge_commit_sha": pull_request.get("merge_commit_sha"),
                "attestation": attestation,
            }
        )

    return {
        "verification_version": 1,
        "repository": repository,
        "main_commit": commit,
        "accepted_pull_requests": accepted,
        "rejected_pull_requests": rejected,
        "passed": bool(accepted),
    }


def main() -> int:
    repository = os.environ.get("ASI_REPOSITORY", "")
    commit = os.environ.get("ASI_MERGED_COMMIT", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    try:
        if repository.count("/") != 1:
            raise ValueError("ASI_REPOSITORY must use owner/repository format.")
        if len(commit) != 40:
            raise ValueError("ASI_MERGED_COMMIT must be a full commit SHA.")
        if not token:
            raise ValueError("GITHUB_TOKEN is required.")
        report = evaluate_merged_commit(repository, commit, token)
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
            "main_commit": commit,
            "passed": False,
            "error": str(exc),
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
