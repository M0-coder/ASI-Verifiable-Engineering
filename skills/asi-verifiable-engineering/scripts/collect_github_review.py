#!/usr/bin/env python3
"""Collect a commit-bound independent targeted review from the GitHub API."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, cast

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
DECISIVE_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
DEFAULT_MARKER = "ASI-TARGETED-REVIEW-V1"


def latest_decisive_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for review in sorted(reviews, key=lambda item: int(item.get("id", 0))):
        user = review.get("user")
        state = review.get("state")
        if not isinstance(user, dict) or state not in DECISIVE_STATES:
            continue
        login = user.get("login")
        if isinstance(login, str) and login:
            latest[login] = review
    return [latest[login] for login in sorted(latest)]


def evaluate_reviews(
    reviews: list[dict[str, Any]],
    builder: str,
    head_commit: str,
    marker: str = DEFAULT_MARKER,
) -> dict[str, Any]:
    approvals: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for review in latest_decisive_reviews(reviews):
        user = review.get("user")
        if not isinstance(user, dict):
            continue
        login = user.get("login")
        reasons: list[str] = []
        if review.get("state") != "APPROVED":
            reasons.append("latest_decisive_state_is_not_approved")
        if review.get("commit_id") != head_commit:
            reasons.append("review_is_stale_for_current_head")
        if user.get("type") != "User":
            reasons.append("reviewer_is_not_a_human_user_account")
        if login == builder:
            reasons.append("reviewer_is_the_builder")
        if review.get("author_association") not in TRUSTED_ASSOCIATIONS:
            reasons.append("reviewer_is_not_a_trusted_repository_associate")
        body = review.get("body")
        if not isinstance(body, str) or marker not in body:
            reasons.append("targeted_review_marker_is_missing")
        if not review.get("submitted_at"):
            reasons.append("submitted_at_is_missing")

        normalized = {
            "review_id": review.get("id"),
            "reviewer": login,
            "state": review.get("state"),
            "commit_id": review.get("commit_id"),
            "submitted_at": review.get("submitted_at"),
            "author_association": review.get("author_association"),
            "html_url": review.get("html_url"),
            "marker": marker,
        }
        if reasons:
            normalized["reasons"] = reasons
            rejected.append(normalized)
        else:
            approvals.append(normalized)

    return {
        "attestation_version": 1,
        "source": "github_pull_request_reviews_api",
        "builder": builder,
        "head_commit": head_commit,
        "required_marker": marker,
        "approvals": approvals,
        "rejected_latest_reviews": rejected,
        "passed": bool(approvals),
    }


def fetch_reviews(repository: str, pull_request: int, token: str) -> list[dict[str, Any]]:
    encoded_repository = "/".join(
        urllib.parse.quote(part, safe="") for part in repository.split("/", 1)
    )
    reviews: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            "https://api.github.com/repos/"
            f"{encoded_repository}/pulls/{pull_request}/reviews"
            f"?per_page=100&page={page}"
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
            raise ValueError("GitHub reviews response must be a list.")
        batch = [cast(dict[str, Any], item) for item in raw if isinstance(item, dict)]
        reviews.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return reviews


def _required_environment() -> tuple[str, int, str, str, str]:
    repository = os.environ.get("ASI_REPOSITORY", "")
    pull_request_raw = os.environ.get("ASI_PR_NUMBER", "")
    head_commit = os.environ.get("ASI_HEAD_SHA", "")
    builder = os.environ.get("ASI_BUILDER", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not REPOSITORY.fullmatch(repository):
        raise ValueError("ASI_REPOSITORY must use owner/repository format.")
    try:
        pull_request = int(pull_request_raw)
    except ValueError as exc:
        raise ValueError("ASI_PR_NUMBER must be an integer.") from exc
    if pull_request <= 0:
        raise ValueError("ASI_PR_NUMBER must be positive.")
    if not SHA40.fullmatch(head_commit):
        raise ValueError("ASI_HEAD_SHA must be a 40-character lowercase SHA.")
    if not builder:
        raise ValueError("ASI_BUILDER is required.")
    if not token:
        raise ValueError("GITHUB_TOKEN is required.")
    return repository, pull_request, head_commit, builder, token


def main() -> int:
    try:
        repository, pull_request, head_commit, builder, token = (
            _required_environment()
        )
        reviews = fetch_reviews(repository, pull_request, token)
        report = evaluate_reviews(reviews, builder, head_commit)
        report["repository"] = repository
        report["pull_request"] = pull_request
    except (
        OSError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        report = {
            "attestation_version": 1,
            "source": "github_pull_request_reviews_api",
            "passed": False,
            "error": str(exc),
        }

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
