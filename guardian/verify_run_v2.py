#!/usr/bin/env python3
"""Hardened trusted verifier for unprivileged workflow evidence."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, cast

import verify_run as legacy

VERIFICATION_VERSION = 2
SHA40 = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return value


def archive_limits(policy: dict[str, Any]) -> dict[str, int | float]:
    raw = policy.get("archive_limits")
    if not isinstance(raw, dict):
        raise ValueError("Trust policy archive_limits must be an object.")
    ratio = raw.get("max_compression_ratio")
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or ratio <= 1:
        raise ValueError("max_compression_ratio must be greater than one.")
    return {
        "max_compressed_bytes": _positive_int(
            raw.get("max_compressed_bytes"), "max_compressed_bytes"
        ),
        "max_files": _positive_int(raw.get("max_files"), "max_files"),
        "max_member_bytes": _positive_int(
            raw.get("max_member_bytes"), "max_member_bytes"
        ),
        "max_total_uncompressed_bytes": _positive_int(
            raw.get("max_total_uncompressed_bytes"),
            "max_total_uncompressed_bytes",
        ),
        "max_compression_ratio": float(ratio),
    }


def canonical_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or normalized.startswith("/"):
        raise ValueError(f"Unsafe absolute or empty archive path: {name!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe archive path component: {name!r}")
    return path.as_posix()


def validate_members(
    members: list[zipfile.ZipInfo],
    limits: dict[str, int | float],
) -> list[tuple[zipfile.ZipInfo, str]]:
    max_files = cast(int, limits["max_files"])
    max_member = cast(int, limits["max_member_bytes"])
    max_total = cast(int, limits["max_total_uncompressed_bytes"])
    max_ratio = cast(float, limits["max_compression_ratio"])
    if len(members) > max_files:
        raise ValueError("Workflow artifact contains too many ZIP entries.")

    seen: set[str] = set()
    total = 0
    validated: list[tuple[zipfile.ZipInfo, str]] = []
    for member in members:
        canonical = canonical_member_name(member.filename)
        if canonical in seen:
            raise ValueError(f"Duplicate ZIP entry: {canonical}")
        seen.add(canonical)
        if member.flag_bits & 0x1:
            raise ValueError(f"Encrypted ZIP entry is forbidden: {canonical}")
        mode = member.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError(f"Symbolic-link ZIP entry is forbidden: {canonical}")
        if member.compress_type not in ALLOWED_COMPRESSION:
            raise ValueError(f"Unsupported ZIP compression method: {canonical}")
        if member.file_size < 0 or member.compress_size < 0:
            raise ValueError(f"Invalid ZIP size metadata: {canonical}")
        if member.file_size > max_member:
            raise ValueError(f"ZIP member exceeds size limit: {canonical}")
        total += member.file_size
        if total > max_total:
            raise ValueError("Workflow artifact exceeds total uncompressed size limit.")
        if member.file_size:
            if member.compress_size == 0:
                raise ValueError(f"Invalid zero compressed size: {canonical}")
            ratio = member.file_size / member.compress_size
            if ratio > max_ratio:
                raise ValueError(f"ZIP compression ratio exceeds limit: {canonical}")
        validated.append((member, canonical))
    return validated


def _copy_member(
    source: BinaryIO,
    target: Path,
    *,
    declared_size: int,
    max_member: int,
) -> int:
    written = 0
    with target.open("xb") as output:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            written += len(block)
            if written > max_member or written > declared_size:
                raise ValueError(f"ZIP member expanded beyond declared limits: {target.name}")
            output.write(block)
    if written != declared_size:
        raise ValueError(f"ZIP member size mismatch: {target.name}")
    return written


def safe_extract(
    archive: bytes,
    destination: Path,
    limits: dict[str, int | float],
) -> None:
    destination = destination.resolve()
    archive_path = destination.parent / "downloaded-artifact.zip"
    archive_path.write_bytes(archive)
    max_member = cast(int, limits["max_member_bytes"])
    max_total = cast(int, limits["max_total_uncompressed_bytes"])
    actual_total = 0
    with zipfile.ZipFile(archive_path) as bundle:
        validated = validate_members(bundle.infolist(), limits)
        for member, canonical in validated:
            target = (destination / canonical).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise ValueError(f"Unsafe path in workflow artifact: {canonical}") from exc
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source:
                actual_total += _copy_member(
                    source,
                    target,
                    declared_size=member.file_size,
                    max_member=max_member,
                )
            if actual_total > max_total:
                raise ValueError(
                    "Workflow artifact exceeded total uncompressed size while extracting."
                )


def download_bytes(url: str, token: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": legacy.API_VERSION,
            "User-Agent": "asi-trust-anchor-v2",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("Workflow artifact exceeds the compressed size limit.")
    return payload


def artifact_name(
    prefix: str,
    *,
    run_id: int,
    run_attempt: int,
    head_sha: str,
    evaluated_sha: str,
) -> str:
    if not prefix or not SHA40.fullmatch(head_sha) or not SHA40.fullmatch(evaluated_sha):
        raise ValueError("Artifact identity is incomplete.")
    if run_id <= 0 or run_attempt <= 0:
        raise ValueError("Artifact run identity must be positive.")
    return (
        f"{prefix}{run_id}-attempt-{run_attempt}-"
        f"{head_sha}-{evaluated_sha}"
    )


def exception_matches_exact(
    exceptions: list[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    protected_changes: list[str],
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    expected_paths = sorted(protected_changes)
    for item in exceptions:
        if item.get("pr_number") != pr_number:
            continue
        if item.get("head_sha") != head_sha or item.get("base_sha") != base_sha:
            continue
        if item.get("authorization_level") != "H1":
            continue
        if not isinstance(item.get("authorized_by"), str) or not item["authorized_by"]:
            continue
        if not isinstance(item.get("reason"), str) or not item["reason"]:
            continue
        allowed = item.get("allowed_paths")
        if not isinstance(allowed, list) or not all(isinstance(p, str) for p in allowed):
            continue
        if sorted(cast(list[str], allowed)) != expected_paths:
            continue
        expires_at = item.get("expires_at")
        if not isinstance(expires_at, str):
            continue
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if expiry.tzinfo is None or expiry <= current:
            continue
        return True
    return False


def verify_artifact_v2(
    root: Path,
    policy: dict[str, Any],
    *,
    repository: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    merge_sha: str,
    changed_files: list[str],
) -> dict[str, Any]:
    report = legacy.verify_artifact(
        root,
        policy,
        repository=repository,
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_sha=merge_sha,
        changed_files=changed_files,
    )
    protected = cast(list[str], report.get("protected_changes", []))
    if protected:
        raw_exceptions = policy.get("bootstrap_exceptions", [])
        exceptions = [item for item in raw_exceptions if isinstance(item, dict)]
        if not exception_matches_exact(
            exceptions,
            pr_number=pr_number,
            head_sha=head_sha,
            base_sha=base_sha,
            protected_changes=protected,
        ):
            raise ValueError(
                "Control-plane exception is not bound to exact paths and H1 authority."
            )
    report["verification_version"] = VERIFICATION_VERSION
    return report


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def trust_anchor_provenance(policy_path: Path) -> dict[str, str]:
    trust_sha = os.environ.get("ASI_TRUST_ANCHOR_SHA", "")
    workflow_path = Path(
        os.environ.get("ASI_TRUST_WORKFLOW", ".github/workflows/asi-trust-anchor.yml")
    )
    verifier_path = Path(
        os.environ.get("ASI_TRUST_VERIFIER", "guardian/verify_run_v2.py")
    )
    if not SHA40.fullmatch(trust_sha):
        raise ValueError("ASI_TRUST_ANCHOR_SHA must be an immutable 40-character SHA.")
    checked_out = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if checked_out != trust_sha:
        raise ValueError("Checked-out trust anchor does not match workflow SHA.")
    for path in (workflow_path, policy_path, verifier_path):
        if not path.is_file():
            raise ValueError(f"Trust-anchor provenance file is missing: {path}")
    return {
        "trust_anchor_commit": trust_sha,
        "workflow_digest": legacy.sha256_file(workflow_path),
        "policy_digest": legacy.sha256_file(policy_path),
        "verifier_digest": legacy.sha256_file(verifier_path),
    }


def run() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    admin_token = os.environ.get("ASI_GITHUB_ADMIN_TOKEN", "")
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    api_base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    policy_path = Path(
        os.environ.get("ASI_TRUST_POLICY", "guardian/trust-policy.json")
    )
    output_root = Path(os.environ.get("ASI_TRUST_OUTPUT", ""))
    if repository.count("/") != 1:
        raise ValueError("GITHUB_REPOSITORY must use owner/repository format.")
    if not token:
        raise ValueError("GITHUB_TOKEN is required.")
    if not event_path.is_file() or not policy_path.is_file():
        raise ValueError("Event payload or trust policy is unavailable.")
    if not output_root.is_dir():
        raise ValueError("ASI_TRUST_OUTPUT must be an existing directory.")

    event = legacy.load_json(event_path)
    source = event.get("workflow_run")
    if not isinstance(source, dict):
        raise ValueError("workflow_run event payload is missing.")
    pull_requests = source.get("pull_requests")
    if not isinstance(pull_requests, list) or len(pull_requests) != 1:
        raise ValueError("Exactly one pull request must be associated with the run.")
    pr_ref = pull_requests[0]
    if not isinstance(pr_ref, dict) or not isinstance(pr_ref.get("number"), int):
        raise ValueError("Pull request number is missing from workflow_run.")
    pr_number = cast(int, pr_ref["number"])
    head_sha = source.get("head_sha")
    run_id = source.get("id")
    run_attempt = source.get("run_attempt")
    if (
        not isinstance(head_sha, str)
        or not SHA40.fullmatch(head_sha)
        or not isinstance(run_id, int)
        or not isinstance(run_attempt, int)
    ):
        raise ValueError("Source workflow identity is incomplete.")

    check_id = legacy.create_check(api_base, repository, head_sha, token)
    report: dict[str, Any]
    try:
        policy = legacy.load_json(policy_path)
        if policy.get("version") != 2 or policy.get("artifact_name_version") != 2:
            raise ValueError("Trust policy v2 is required.")
        limits = archive_limits(policy)
        if source.get("name") != policy.get("trusted_workflow"):
            raise ValueError("Unexpected source workflow.")
        if source.get("event") != "pull_request" or source.get("conclusion") != "success":
            raise ValueError("Source workflow must be a successful pull_request run.")

        pr = legacy.api_request(
            f"{api_base}/repos/{repository}/pulls/{pr_number}", token
        )
        if not isinstance(pr, dict):
            raise ValueError("Cannot fetch pull request metadata.")
        write_json(output_root / "pull-request.json", pr)
        head = pr.get("head")
        base = pr.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise ValueError("Pull request refs are incomplete.")
        if head.get("sha") != head_sha:
            raise ValueError("Source workflow head does not match the live PR head.")
        base_sha = base.get("sha")
        merge_sha = pr.get("merge_commit_sha")
        if (
            not isinstance(base_sha, str)
            or not SHA40.fullmatch(base_sha)
            or not isinstance(merge_sha, str)
            or not SHA40.fullmatch(merge_sha)
        ):
            raise ValueError("Pull request base or merge commit is missing.")

        changed_files = legacy.list_pr_files(api_base, repository, pr_number, token)
        artifacts = legacy.api_request(
            f"{api_base}/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100",
            token,
        )
        if not isinstance(artifacts, dict):
            raise ValueError("Cannot list source workflow artifacts.")
        write_json(output_root / "source-artifacts.json", artifacts)
        prefix = policy.get("artifact_prefix")
        if not isinstance(prefix, str):
            raise ValueError("Trust policy artifact_prefix is invalid.")
        expected_name = artifact_name(
            prefix,
            run_id=run_id,
            run_attempt=run_attempt,
            head_sha=head_sha,
            evaluated_sha=merge_sha,
        )
        matches = [
            item
            for item in artifacts.get("artifacts", [])
            if isinstance(item, dict)
            and item.get("name") == expected_name
            and item.get("expired") is False
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one non-expired artifact named {expected_name}."
            )
        artifact = matches[0]
        write_json(output_root / "selected-artifact.json", artifact)
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, int):
            raise ValueError("Artifact id is missing.")
        archive = download_bytes(
            f"{api_base}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
            token,
            cast(int, limits["max_compressed_bytes"]),
        )
        archive_digest = legacy.sha256_bytes(archive)
        api_digest = artifact.get("digest")
        if isinstance(api_digest, str) and api_digest != archive_digest:
            raise ValueError("Downloaded artifact digest does not match GitHub metadata.")

        with tempfile.TemporaryDirectory(prefix="asi-trust-anchor-v2-") as temp:
            evidence_root = Path(temp) / "evidence"
            evidence_root.mkdir()
            safe_extract(archive, evidence_root, limits)
            report = verify_artifact_v2(
                evidence_root,
                policy,
                repository=repository,
                pr_number=pr_number,
                base_sha=base_sha,
                head_sha=head_sha,
                merge_sha=merge_sha,
                changed_files=changed_files,
            )
        report.update(
            {
                "source_run_id": run_id,
                "source_run_attempt": run_attempt,
                "source_artifact_id": artifact_id,
                "source_artifact_name": expected_name,
                "source_artifact_digest": archive_digest,
                "trust_anchor": trust_anchor_provenance(policy_path),
            }
        )

        if not admin_token:
            raise ValueError("ASI_GITHUB_ADMIN_TOKEN is required.")
        raw_protection = legacy.api_request(
            f"{api_base}/repos/{repository}/branches/"
            f"{urllib.parse.quote(str(base.get('ref')), safe='')}/protection",
            admin_token,
        )
        if not isinstance(raw_protection, dict):
            raise ValueError("Branch-protection response is invalid.")
        write_json(output_root / "branch-protection.json", raw_protection)
        report["branch_protection_raw_digest"] = legacy.sha256_bytes(
            json.dumps(raw_protection, sort_keys=True, separators=(",", ":")).encode()
        )
        report["passed"] = True
        write_json(output_root / "verification-report.json", report)
        summary = json.dumps(report, indent=2, sort_keys=True)
        legacy.complete_check(
            api_base,
            repository,
            check_id,
            token,
            conclusion="success",
            title="ASI Trust Anchor passed",
            summary=summary,
        )
        print(summary)
        return 0
    except Exception as exc:
        report = {
            "verification_version": VERIFICATION_VERSION,
            "repository": repository,
            "source_run_id": run_id,
            "source_run_attempt": run_attempt,
            "head_sha": head_sha,
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        write_json(output_root / "verification-report.json", report)
        summary = json.dumps(report, indent=2, sort_keys=True)
        legacy.complete_check(
            api_base,
            repository,
            check_id,
            token,
            conclusion="failure",
            title="ASI Trust Anchor blocked",
            summary=summary,
        )
        print(summary)
        return 1


def main() -> int:
    try:
        return run()
    except (
        OSError,
        ValueError,
        subprocess.CalledProcessError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"Trust-anchor v2 bootstrap failure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
