#!/usr/bin/env python3
"""Collect context-separated AI audit and target-observation attestations."""

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
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
ACCEPTED_REVIEW_STATES = {"COMMENTED", "APPROVED"}
TARGET_ENVIRONMENTS = {"chatgpt", "codex", "openai-api"}
AUDIT_MARKER = "ASI-SOLO-AUDIT-V1"
EVIDENCE_URL = re.compile(
    r"^ASI-AUDIT-EVIDENCE-URL:\s*(https://raw\.githubusercontent\.com/\S+)\s*$",
    re.MULTILINE,
)
EVIDENCE_DIGEST = re.compile(
    r"^ASI-AUDIT-EVIDENCE-SHA256:\s*(sha256:[0-9a-f]{64})\s*$",
    re.MULTILINE,
)
MAX_EVIDENCE_BYTES = 1_000_000
EvidenceLoader = Callable[[str, str], dict[str, Any]]


def _recent_timestamp(
    value: Any,
    field: str,
    errors: list[str],
    now: datetime,
) -> str | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append(f"invalid_{field}")
        return None
    if parsed > now + timedelta(minutes=5):
        errors.append(f"{field}_is_in_the_future")
    if now - parsed > timedelta(days=7):
        errors.append(f"{field}_is_older_than_seven_days")
    return str(value)


def fetch_external_evidence(url: str, expected_digest: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError("Audit evidence must use raw.githubusercontent.com over HTTPS.")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "asi-verifiable-engineering"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(MAX_EVIDENCE_BYTES + 1)
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise ValueError("Audit evidence exceeds the one-megabyte limit.")
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if digest != expected_digest:
        raise ValueError("Audit evidence SHA-256 does not match the review declaration.")
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Audit evidence root must be a JSON object.")
    return cast(dict[str, Any], raw)


def validate_attestation(
    raw: dict[str, Any],
    repository: str,
    head_commit: str,
    builder_context_id: str,
    evidence_url: str,
    evidence_digest: str,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    current = now or datetime.now(timezone.utc)

    if raw.get("attestation_version") != 1:
        errors.append("attestation_version_must_equal_1")
    if raw.get("operator_mode") != "solo":
        errors.append("operator_mode_must_be_solo")
    if raw.get("repository") != repository:
        errors.append("attestation_repository_mismatch")
    if raw.get("head_commit") != head_commit:
        errors.append("attestation_head_commit_mismatch")
    if raw.get("builder_context_id") != builder_context_id:
        errors.append("builder_context_id_mismatch")

    auditor_context = raw.get("auditor_context_id")
    if not isinstance(auditor_context, str) or not auditor_context.strip():
        errors.append("auditor_context_id_is_required")
    elif auditor_context == builder_context_id:
        errors.append("auditor_context_must_differ_from_builder_context")

    audit_raw = raw.get("audit")
    audit: dict[str, Any] = {}
    if not isinstance(audit_raw, dict):
        errors.append("audit_object_is_required")
    else:
        if audit_raw.get("mode") != "read_only":
            errors.append("audit_mode_must_be_read_only")
        if audit_raw.get("result") != "passed":
            errors.append("audit_result_is_not_passed")
        checks = audit_raw.get("checks")
        if (
            not isinstance(checks, list)
            or not checks
            or any(not isinstance(item, str) or not item for item in checks)
        ):
            errors.append("audit_checks_must_be_a_non_empty_string_list")
        findings = audit_raw.get("findings")
        if not isinstance(findings, list):
            errors.append("audit_findings_must_be_a_list")
        write_actions = audit_raw.get("write_actions")
        if write_actions != []:
            errors.append("audit_write_actions_must_be_empty")
        created_at = _recent_timestamp(
            audit_raw.get("created_at"),
            "audit_created_at",
            errors,
            current,
        )
        audit = {
            "mode": audit_raw.get("mode"),
            "result": audit_raw.get("result"),
            "created_at": created_at,
            "checks": checks,
            "findings": findings,
            "write_actions": write_actions,
        }

    normalized = {
        "attestation_version": raw.get("attestation_version"),
        "operator_mode": raw.get("operator_mode"),
        "repository": raw.get("repository"),
        "head_commit": raw.get("head_commit"),
        "builder_context_id": raw.get("builder_context_id"),
        "auditor_context_id": auditor_context,
        "audit": audit,
        "evidence_url": evidence_url,
        "evidence_digest": evidence_digest,
    }

    observation_normalized: dict[str, Any] | None = None
    observation_raw = raw.get("target_observation")
    if observation_raw is not None:
        observation_errors: list[str] = []
        if not isinstance(observation_raw, dict):
            observation_errors.append("target_observation_must_be_an_object")
        else:
            environment = observation_raw.get("target_environment")
            if environment not in TARGET_ENVIRONMENTS:
                observation_errors.append("unsupported_target_environment")
            if observation_raw.get("result") != "passed":
                observation_errors.append("target_observation_result_is_not_passed")
            package_digest = observation_raw.get("package_digest")
            if not isinstance(package_digest, str) or not SHA256.fullmatch(package_digest):
                observation_errors.append("invalid_package_digest")
            checks = observation_raw.get("checks")
            if (
                not isinstance(checks, list)
                or not checks
                or any(not isinstance(item, str) or not item for item in checks)
            ):
                observation_errors.append(
                    "target_checks_must_be_a_non_empty_string_list"
                )
            executed_at = _recent_timestamp(
                observation_raw.get("executed_at"),
                "observation_executed_at",
                observation_errors,
                current,
            )
            observation_normalized = {
                "repository": repository,
                "head_commit": head_commit,
                "auditor_context_id": auditor_context,
                "target_environment": environment,
                "package_digest": package_digest,
                "result": observation_raw.get("result"),
                "executed_at": executed_at,
                "checks": checks,
                "limitations": observation_raw.get("limitations", []),
                "evidence_url": evidence_url,
                "evidence_digest": evidence_digest,
            }
        if observation_errors:
            normalized["target_observation_errors"] = observation_errors
            observation_normalized = None

    return normalized, observation_normalized, errors


def latest_audit_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for review in sorted(reviews, key=lambda item: int(item.get("id", 0))):
        body = review.get("body")
        user = review.get("user")
        if not isinstance(body, str) or AUDIT_MARKER not in body:
            continue
        if not isinstance(user, dict):
            continue
        login = user.get("login")
        if isinstance(login, str) and login:
            latest[login] = review
    return [latest[login] for login in sorted(latest)]


def evaluate_reviews(
    reviews: list[dict[str, Any]],
    builder_context_id: str,
    head_commit: str,
    repository: str,
    evidence_loader: EvidenceLoader = fetch_external_evidence,
) -> dict[str, Any]:
    audits: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for review in latest_audit_reviews(reviews):
        user = review.get("user")
        if not isinstance(user, dict):
            continue
        actor_value = user.get("login")
        actor = actor_value if isinstance(actor_value, str) else ""
        reasons: list[str] = []
        state = review.get("state")
        if state not in ACCEPTED_REVIEW_STATES:
            reasons.append("review_state_is_not_comment_or_approval")
        if review.get("commit_id") != head_commit:
            reasons.append("audit_is_stale_for_current_head")
        if user.get("type") != "User":
            reasons.append("audit_actor_is_not_a_human_user_account")
        if not actor:
            reasons.append("audit_actor_login_is_missing")
        if review.get("author_association") not in TRUSTED_ASSOCIATIONS:
            reasons.append("audit_actor_is_not_a_trusted_repository_associate")
        if not review.get("submitted_at"):
            reasons.append("submitted_at_is_missing")

        body_value = review.get("body")
        body = body_value if isinstance(body_value, str) else ""
        url_match = EVIDENCE_URL.search(body)
        digest_match = EVIDENCE_DIGEST.search(body)
        if url_match is None:
            reasons.append("audit_evidence_url_is_missing")
        if digest_match is None:
            reasons.append("audit_evidence_digest_is_missing")

        normalized: dict[str, Any] = {
            "review_id": review.get("id"),
            "actor": actor,
            "state": state,
            "commit_id": review.get("commit_id"),
            "submitted_at": review.get("submitted_at"),
            "author_association": review.get("author_association"),
            "html_url": review.get("html_url"),
            "audit_marker": AUDIT_MARKER,
        }
        if reasons:
            normalized["reasons"] = reasons
            rejected.append(normalized)
            continue

        assert url_match is not None
        assert digest_match is not None
        evidence_url = url_match.group(1)
        evidence_digest = digest_match.group(1)
        try:
            raw = evidence_loader(evidence_url, evidence_digest)
            audit, observation, validation_errors = validate_attestation(
                raw,
                repository,
                head_commit,
                builder_context_id,
                evidence_url,
                evidence_digest,
            )
            if validation_errors:
                normalized["reasons"] = validation_errors
                normalized["attestation"] = audit
                rejected.append(normalized)
                continue
            audit["actor"] = actor
            audit["review_id"] = review.get("id")
            audit["html_url"] = review.get("html_url")
            audits.append(audit)
            if observation is not None:
                observation["actor"] = actor
                observation["review_id"] = review.get("id")
                observations.append(observation)
        except (
            OSError,
            ValueError,
            urllib.error.HTTPError,
            urllib.error.URLError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            normalized["reasons"] = [f"audit_evidence_error:{exc}"]
            rejected.append(normalized)

    return {
        "attestation_version": 3,
        "operator_mode": "solo",
        "source": "github_pull_request_review_comment_and_external_evidence",
        "builder_context_id": builder_context_id,
        "head_commit": head_commit,
        "repository": repository,
        "audit_marker": AUDIT_MARKER,
        "audits": audits,
        "observations": observations,
        "rejected_audits": rejected,
        "passed": bool(audits),
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
    builder_context_id = os.environ.get("ASI_BUILDER_CONTEXT_ID", "")
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
    if not builder_context_id:
        raise ValueError("ASI_BUILDER_CONTEXT_ID is required.")
    if not token:
        raise ValueError("GITHUB_TOKEN is required.")
    return repository, pull_request, head_commit, builder_context_id, token


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    group = result.add_mutually_exclusive_group(required=True)
    group.add_argument("--require-audit", action="store_true")
    group.add_argument("--require-observation", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        repository, pull_request, head_commit, builder_context_id, token = (
            _required_environment()
        )
        reviews = fetch_reviews(repository, pull_request, token)
        report = evaluate_reviews(
            reviews,
            builder_context_id,
            head_commit,
            repository,
        )
        report["pull_request"] = pull_request
    except (
        OSError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        report = {
            "attestation_version": 3,
            "operator_mode": "solo",
            "source": "github_pull_request_review_comment_and_external_evidence",
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
