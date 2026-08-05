#!/usr/bin/env python3
"""Collect commit-bound review and target-observation attestations from GitHub."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, cast

REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
DECISIVE_STATES = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
TARGET_ENVIRONMENTS = {"chatgpt", "codex", "openai-api"}
REVIEW_MARKER = "ASI-TARGETED-REVIEW-V1"
OBSERVATION_MARKER = "ASI-TARGET-OBSERVATION-V1"
OBSERVATION_URL = re.compile(
    r"^ASI-TARGET-EVIDENCE-URL:\s*(https://raw\.githubusercontent\.com/\S+)\s*$",
    re.MULTILINE,
)
OBSERVATION_DIGEST = re.compile(
    r"^ASI-TARGET-EVIDENCE-SHA256:\s*(sha256:[0-9a-f]{64})\s*$",
    re.MULTILINE,
)
MAX_OBSERVATION_BYTES = 1_000_000
ObservationLoader = Callable[[str, str], dict[str, Any]]


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


def fetch_external_observation(url: str, expected_digest: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError("Target evidence must use raw.githubusercontent.com over HTTPS.")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "asi-verifiable-engineering"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(MAX_OBSERVATION_BYTES + 1)
    if len(payload) > MAX_OBSERVATION_BYTES:
        raise ValueError("Target evidence exceeds the one-megabyte limit.")
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if digest != expected_digest:
        raise ValueError("Target evidence SHA-256 does not match the review declaration.")
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Target evidence root must be a JSON object.")
    return cast(dict[str, Any], raw)


def validate_observation(
    raw: dict[str, Any],
    repository: str,
    head_commit: str,
    reviewer: str,
    evidence_url: str,
    evidence_digest: str,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    current = now or datetime.now(timezone.utc)
    if raw.get("observation_version") != 1:
        errors.append("observation_version_must_equal_1")
    if raw.get("repository") != repository:
        errors.append("observation_repository_mismatch")
    if raw.get("head_commit") != head_commit:
        errors.append("observation_head_commit_mismatch")
    if raw.get("reviewer") != reviewer:
        errors.append("observation_reviewer_mismatch")
    target = raw.get("target_environment")
    if target not in TARGET_ENVIRONMENTS:
        errors.append("unsupported_target_environment")
    if raw.get("result") != "passed":
        errors.append("target_observation_result_is_not_passed")
    package_digest = raw.get("package_digest")
    if not isinstance(package_digest, str) or not SHA256.fullmatch(package_digest):
        errors.append("invalid_package_digest")
    checks = raw.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(not isinstance(item, str) or not item for item in checks)
    ):
        errors.append("checks_must_be_a_non_empty_string_list")
    executed_at = raw.get("executed_at")
    try:
        observed = datetime.fromisoformat(str(executed_at).replace("Z", "+00:00"))
        if observed.tzinfo is None:
            raise ValueError
        if observed > current + timedelta(minutes=5):
            errors.append("observation_time_is_in_the_future")
        if current - observed > timedelta(days=7):
            errors.append("observation_is_older_than_seven_days")
    except ValueError:
        errors.append("invalid_executed_at")

    return (
        {
            "observation_version": raw.get("observation_version"),
            "repository": raw.get("repository"),
            "head_commit": raw.get("head_commit"),
            "reviewer": raw.get("reviewer"),
            "target_environment": target,
            "package_digest": package_digest,
            "result": raw.get("result"),
            "executed_at": executed_at,
            "checks": checks,
            "limitations": raw.get("limitations", []),
            "evidence_url": evidence_url,
            "evidence_digest": evidence_digest,
        },
        errors,
    )


def evaluate_reviews(
    reviews: list[dict[str, Any]],
    builder: str,
    head_commit: str,
    repository: str,
    observation_loader: ObservationLoader = fetch_external_observation,
) -> dict[str, Any]:
    approvals: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for review in latest_decisive_reviews(reviews):
        user = review.get("user")
        if not isinstance(user, dict):
            continue
        login_value = user.get("login")
        login = login_value if isinstance(login_value, str) else ""
        reasons: list[str] = []
        if review.get("state") != "APPROVED":
            reasons.append("latest_decisive_state_is_not_approved")
        if review.get("commit_id") != head_commit:
            reasons.append("review_is_stale_for_current_head")
        if user.get("type") != "User":
            reasons.append("reviewer_is_not_a_human_user_account")
        if not login:
            reasons.append("reviewer_login_is_missing")
        if login == builder:
            reasons.append("reviewer_is_the_builder")
        if review.get("author_association") not in TRUSTED_ASSOCIATIONS:
            reasons.append("reviewer_is_not_a_trusted_repository_associate")
        body_value = review.get("body")
        body = body_value if isinstance(body_value, str) else ""
        if REVIEW_MARKER not in body:
            reasons.append("targeted_review_marker_is_missing")
        if not review.get("submitted_at"):
            reasons.append("submitted_at_is_missing")

        normalized: dict[str, Any] = {
            "review_id": review.get("id"),
            "reviewer": login,
            "state": review.get("state"),
            "commit_id": review.get("commit_id"),
            "submitted_at": review.get("submitted_at"),
            "author_association": review.get("author_association"),
            "html_url": review.get("html_url"),
            "review_marker": REVIEW_MARKER,
        }
        if reasons:
            normalized["reasons"] = reasons
            rejected.append(normalized)
            continue

        if OBSERVATION_MARKER in body:
            url_match = OBSERVATION_URL.search(body)
            digest_match = OBSERVATION_DIGEST.search(body)
            observation_errors: list[str] = []
            if url_match is None:
                observation_errors.append("target_evidence_url_is_missing")
            if digest_match is None:
                observation_errors.append("target_evidence_digest_is_missing")
            if not observation_errors:
                assert url_match is not None
                assert digest_match is not None
                evidence_url = url_match.group(1)
                evidence_digest = digest_match.group(1)
                try:
                    raw = observation_loader(evidence_url, evidence_digest)
                    observation, validation_errors = validate_observation(
                        raw,
                        repository,
                        head_commit,
                        login,
                        evidence_url,
                        evidence_digest,
                    )
                    observation_errors.extend(validation_errors)
                    if not validation_errors:
                        normalized["target_observation"] = observation
                        observations.append(observation)
                except (
                    OSError,
                    ValueError,
                    urllib.error.HTTPError,
                    urllib.error.URLError,
                    json.JSONDecodeError,
                    UnicodeDecodeError,
                ) as exc:
                    observation_errors.append(f"target_evidence_error:{exc}")
            if observation_errors:
                normalized["target_observation_errors"] = observation_errors
        approvals.append(normalized)

    return {
        "attestation_version": 2,
        "source": "github_pull_request_reviews_api",
        "builder": builder,
        "head_commit": head_commit,
        "repository": repository,
        "review_marker": REVIEW_MARKER,
        "observation_marker": OBSERVATION_MARKER,
        "approvals": approvals,
        "observations": observations,
        "rejected_latest_reviews": rejected,
        "passed": bool(approvals),
        "observation_passed": bool(observations),
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


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    group = result.add_mutually_exclusive_group(required=True)
    group.add_argument("--require-review", action="store_true")
    group.add_argument("--require-observation", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        repository, pull_request, head_commit, builder, token = (
            _required_environment()
        )
        reviews = fetch_reviews(repository, pull_request, token)
        report = evaluate_reviews(reviews, builder, head_commit, repository)
        report["pull_request"] = pull_request
    except (
        OSError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        report = {
            "attestation_version": 2,
            "source": "github_pull_request_reviews_api",
            "passed": False,
            "observation_passed": False,
            "error": str(exc),
        }

    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_observation:
        return 0 if report.get("observation_passed") is True else 1
    return 0 if report.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
