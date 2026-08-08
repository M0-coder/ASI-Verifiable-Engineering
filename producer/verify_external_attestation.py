#!/usr/bin/env python3
"""Validate external audit/target-observation attestations bound to one PR head."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, cast

from producer.evidence_producer import PACKAGE_SOURCE, build_deterministic_package

API_VERSION = "2022-11-28"
MARKER = "ASI-EXTERNAL-ATTESTATION-V1"
URL_PATTERN = re.compile(
    r"^ASI-ATTESTATION-URL:\s*(https://raw\.githubusercontent\.com/\S+)\s*$",
    re.MULTILINE,
)
DIGEST_PATTERN = re.compile(
    r"^ASI-ATTESTATION-SHA256:\s*(sha256:[0-9a-f]{64})\s*$",
    re.MULTILINE,
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
TRUSTED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
ACCEPTED_REVIEW_STATES = {"COMMENTED", "APPROVED"}
TARGET_ENVIRONMENTS = {"chatgpt", "codex", "openai-api"}
MAX_EVIDENCE_BYTES = 1_000_000
EvidenceLoader = Callable[[str, str, str], dict[str, Any]]


def recent_timestamp(value: Any, field: str, errors: list[str], now: datetime) -> None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append(f"invalid_{field}")
        return
    if parsed > now + timedelta(minutes=5):
        errors.append(f"{field}_is_in_the_future")
    if now - parsed > timedelta(days=7):
        errors.append(f"{field}_is_older_than_seven_days")


def validate_raw_url(url: str, repository: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise ValueError("attestation URL must use raw.githubusercontent.com over HTTPS")
    parts = [item for item in parsed.path.split("/") if item]
    owner, repo = repository.split("/", 1)
    if len(parts) < 4 or parts[0] != owner or parts[1] != repo:
        raise ValueError("attestation URL must point to the same repository")
    if not SHA40.fullmatch(parts[2]):
        raise ValueError("attestation URL must be pinned to an immutable commit SHA")


def fetch_external_evidence(
    url: str,
    expected_digest: str,
    repository: str,
) -> dict[str, Any]:
    validate_raw_url(url, repository)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "asi-verifiable-engineering"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read(MAX_EVIDENCE_BYTES + 1)
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise ValueError("attestation evidence exceeds the one-megabyte limit")
    actual = "sha256:" + hashlib.sha256(payload).hexdigest()
    if actual != expected_digest:
        raise ValueError("attestation evidence SHA-256 does not match the review declaration")
    raw = json.loads(payload.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("attestation evidence root must be a JSON object")
    return cast(dict[str, Any], raw)


def validate_attestation(
    raw: dict[str, Any],
    *,
    repository: str,
    pr_number: int,
    head_sha: str,
    builder_context_id: str,
    kind: str,
    package_digest: str | None,
    now: datetime | None = None,
) -> list[str]:
    errors: list[str] = []
    current = now or datetime.now(timezone.utc)
    if raw.get("schema") != "asi.external_attestation.v1":
        errors.append("schema_mismatch")
    if raw.get("repository") != repository:
        errors.append("repository_mismatch")
    if raw.get("pull_request") != pr_number:
        errors.append("pull_request_mismatch")
    if raw.get("head_sha") != head_sha:
        errors.append("head_sha_mismatch")
    if raw.get("builder_context_id") != builder_context_id:
        errors.append("builder_context_id_mismatch")

    auditor_context = raw.get("auditor_context_id")
    if not isinstance(auditor_context, str) or not auditor_context.strip():
        errors.append("auditor_context_id_required")
    elif auditor_context == builder_context_id:
        errors.append("auditor_context_must_differ_from_builder_context")

    audit = raw.get("audit")
    if not isinstance(audit, dict):
        errors.append("audit_object_required")
    else:
        if audit.get("mode") != "read_only":
            errors.append("audit_mode_must_be_read_only")
        if audit.get("result") != "PASS":
            errors.append("audit_result_must_be_PASS")
        checks = audit.get("checks")
        if (
            not isinstance(checks, list)
            or not checks
            or any(not isinstance(item, str) or not item for item in checks)
        ):
            errors.append("audit_checks_required")
        findings = audit.get("findings")
        if not isinstance(findings, list):
            errors.append("audit_findings_must_be_list")
        elif findings:
            errors.append("audit_PASS_requires_no_findings")
        if audit.get("write_actions") != []:
            errors.append("audit_write_actions_must_be_empty")
        publication_actions = audit.get("publication_actions", [])
        if (
            not isinstance(publication_actions, list)
            or any(not isinstance(item, str) for item in publication_actions)
        ):
            errors.append("audit_publication_actions_must_be_string_list")
        recent_timestamp(audit.get("created_at"), "audit_created_at", errors, current)

    if kind == "target-environment-observation":
        observation = raw.get("target_observation")
        if not isinstance(observation, dict):
            errors.append("target_observation_object_required")
        else:
            if observation.get("target_environment") not in TARGET_ENVIRONMENTS:
                errors.append("unsupported_target_environment")
            if observation.get("result") != "PASS":
                errors.append("target_observation_result_must_be_PASS")
            if package_digest is None or observation.get("package_digest") != package_digest:
                errors.append("package_digest_mismatch")
            checks = observation.get("checks")
            if (
                not isinstance(checks, list)
                or not checks
                or any(not isinstance(item, str) or not item for item in checks)
            ):
                errors.append("target_observation_checks_required")
            limitations = observation.get("limitations", [])
            if (
                not isinstance(limitations, list)
                or any(not isinstance(item, str) for item in limitations)
            ):
                errors.append("target_observation_limitations_must_be_string_list")
            recent_timestamp(
                observation.get("executed_at"),
                "target_observation_executed_at",
                errors,
                current,
            )
    return errors


def latest_marked_reviews(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for review in sorted(reviews, key=lambda item: int(item.get("id", 0))):
        body = review.get("body")
        user = review.get("user")
        if not isinstance(body, str) or MARKER not in body or not isinstance(user, dict):
            continue
        login = user.get("login")
        if isinstance(login, str) and login:
            latest[login] = review
    return [latest[key] for key in sorted(latest)]


def evaluate_reviews(
    reviews: list[dict[str, Any]],
    *,
    repository: str,
    pr_number: int,
    head_sha: str,
    builder_context_id: str,
    kind: str,
    package_digest: str | None,
    evidence_loader: EvidenceLoader = fetch_external_evidence,
) -> tuple[str, dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    marked = latest_marked_reviews(reviews)
    for review in marked:
        reasons: list[str] = []
        user = review.get("user")
        body = review.get("body")
        if not isinstance(user, dict) or not isinstance(body, str):
            continue
        if review.get("state") not in ACCEPTED_REVIEW_STATES:
            reasons.append("review_state_not_accepted")
        if review.get("commit_id") != head_sha:
            reasons.append("review_not_bound_to_current_head")
        if user.get("type") != "User":
            reasons.append("review_actor_not_human_user_account")
        if review.get("author_association") not in TRUSTED_ASSOCIATIONS:
            reasons.append("review_actor_not_trusted_repository_associate")
        if not review.get("submitted_at"):
            reasons.append("review_submitted_at_missing")
        url_match = URL_PATTERN.search(body)
        digest_match = DIGEST_PATTERN.search(body)
        if url_match is None:
            reasons.append("attestation_url_missing")
        if digest_match is None:
            reasons.append("attestation_digest_missing")
        record: dict[str, Any] = {
            "review_id": review.get("id"),
            "actor": user.get("login"),
            "commit_id": review.get("commit_id"),
        }
        if reasons:
            record["reasons"] = reasons
            rejected.append(record)
            continue
        assert url_match is not None
        assert digest_match is not None
        try:
            url = url_match.group(1)
            digest = digest_match.group(1)
            if not SHA256.fullmatch(digest):
                raise ValueError("invalid attestation digest")
            raw = evidence_loader(url, digest, repository)
            validation = validate_attestation(
                raw,
                repository=repository,
                pr_number=pr_number,
                head_sha=head_sha,
                builder_context_id=builder_context_id,
                kind=kind,
                package_digest=package_digest,
            )
            if validation:
                record["reasons"] = validation
                rejected.append(record)
                continue
            record["attestation_url"] = url
            record["attestation_digest"] = digest
            record["auditor_context_id"] = raw.get("auditor_context_id")
            accepted.append(record)
        except (
            OSError,
            ValueError,
            urllib.error.HTTPError,
            urllib.error.URLError,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as exc:
            record["reasons"] = [f"attestation_evidence_error:{exc}"]
            rejected.append(record)

    report = {
        "schema": "asi.external_gate_report.v1",
        "kind": kind,
        "repository": repository,
        "pull_request": pr_number,
        "head_sha": head_sha,
        "builder_context_id": builder_context_id,
        "package_digest": package_digest,
        "accepted": accepted,
        "rejected": rejected,
    }
    if accepted:
        return "PASS", report
    if marked:
        return "FAIL", report
    return "NOT_VERIFIED", report


def fetch_reviews(repository: str, pr_number: int, token: str) -> list[dict[str, Any]]:
    owner, repo = repository.split("/", 1)
    reviews: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            "https://api.github.com/repos/"
            f"{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"
            f"/pulls/{pr_number}/reviews?per_page=100&page={page}"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "asi-verifiable-engineering",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
        if not isinstance(raw, list):
            raise ValueError("GitHub reviews response must be a list")
        batch = [cast(dict[str, Any], item) for item in raw if isinstance(item, dict)]
        reviews.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return reviews


def package_digest(repo_root: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="asi-attestation-package-") as tmp:
        return build_deterministic_package(
            repo_root / PACKAGE_SOURCE,
            Path(tmp) / "skill.zip",
        )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "kind",
        choices=("independent-audit", "target-environment-observation"),
    )
    result.add_argument("--repository", required=True)
    result.add_argument("--pr-number", type=int, required=True)
    result.add_argument("--head-sha", required=True)
    result.add_argument("--builder-context-id", required=True)
    result.add_argument("--repo-root", default=".")
    return result


def main() -> int:
    args = parser().parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("GITHUB_TOKEN is required")
        return 1
    if args.pr_number <= 0 or not SHA40.fullmatch(args.head_sha):
        print("invalid pull request/head identity")
        return 1
    package = (
        package_digest(Path(args.repo_root).resolve())
        if args.kind == "target-environment-observation"
        else None
    )
    try:
        reviews = fetch_reviews(args.repository, args.pr_number, token)
        state, report = evaluate_reviews(
            reviews,
            repository=args.repository,
            pr_number=args.pr_number,
            head_sha=args.head_sha,
            builder_context_id=args.builder_context_id,
            kind=args.kind,
            package_digest=package,
        )
    except (
        OSError,
        ValueError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
        UnicodeDecodeError,
    ) as exc:
        print(json.dumps({"state": "FAIL", "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    report["state"] = state
    print(json.dumps(report, indent=2, sort_keys=True))
    if state == "PASS":
        return 0
    if state == "NOT_VERIFIED":
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
