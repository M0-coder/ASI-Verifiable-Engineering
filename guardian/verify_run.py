#!/usr/bin/env python3
"""Trusted verifier for evidence produced by an unprivileged pull-request workflow."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

API_VERSION = "2022-11-28"
CHECK_NAME = "ASI Trust Anchor"
MAX_ARTIFACT_BYTES = 100_000_000
PACKAGE_PATH = "package/asi-verifiable-engineering.zip"


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def api_request(
    url: str,
    token: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "asi-trust-anchor",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def download_bytes(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "asi-trust-anchor",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read(MAX_ARTIFACT_BYTES + 1)
    if len(payload) > MAX_ARTIFACT_BYTES:
        raise ValueError("Workflow artifact exceeds the configured size limit.")
    return payload


def load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return cast(dict[str, Any], raw)


def safe_extract(archive: bytes, destination: Path) -> None:
    destination = destination.resolve()
    archive_path = destination.parent / "downloaded-artifact.zip"
    archive_path.write_bytes(archive)
    with zipfile.ZipFile(archive_path) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise ValueError(
                    f"Unsafe path in workflow artifact: {member.filename}"
                ) from exc
            if member.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as output:
                while True:
                    block = source.read(1024 * 1024)
                    if not block:
                        break
                    output.write(block)


def path_matches(path: str, pattern: str) -> bool:
    normalized = pattern.replace("**", "*")
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, normalized)


def control_plane_changes(
    changed_files: list[str],
    protected_patterns: list[str],
) -> list[str]:
    return sorted(
        path
        for path in changed_files
        if any(path_matches(path, pattern) for pattern in protected_patterns)
    )


def exception_matches(
    exceptions: list[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(timezone.utc)
    for item in exceptions:
        if item.get("pr_number") != pr_number:
            continue
        if item.get("head_sha") != head_sha:
            continue
        if item.get("base_sha") != base_sha:
            continue
        expires_at = item.get("expires_at")
        if not isinstance(expires_at, str):
            continue
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if expiry.tzinfo is None or expiry < current:
            continue
        return True
    return False


def verify_bound_file(root: Path, relative: str, digest: str) -> None:
    if not digest.startswith("sha256:"):
        raise ValueError(f"Invalid digest for {relative}")
    path = (root / relative).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Evidence path escapes artifact root: {relative}") from exc
    if not path.is_file():
        raise ValueError(f"Missing evidence file: {relative}")
    actual = sha256_file(path)
    if actual != digest:
        raise ValueError(
            f"Evidence digest mismatch for {relative}: {actual} != {digest}"
        )


def verify_gate(
    root: Path,
    manifest: dict[str, Any],
    gate_name: str,
) -> None:
    gates = manifest.get("gates")
    evidence = manifest.get("gate_evidence")
    commands = manifest.get("commands")
    if not isinstance(gates, dict) or gates.get(gate_name) != "passed":
        raise ValueError(f"Required gate is not passed: {gate_name}")
    if not isinstance(evidence, dict):
        raise ValueError("Manifest gate_evidence is missing.")
    binding = evidence.get(gate_name)
    if not isinstance(binding, dict):
        raise ValueError(f"Gate evidence is missing: {gate_name}")
    if not isinstance(commands, list):
        raise ValueError("Manifest commands are missing.")
    command = next(
        (
            item
            for item in commands
            if isinstance(item, dict) and item.get("name") == gate_name
        ),
        None,
    )
    if not isinstance(command, dict) or command.get("exit_code") != 0:
        raise ValueError(f"Measured command did not pass: {gate_name}")

    for artifact_field, digest_field in (
        ("result_artifact", "result_digest"),
        ("log_artifact", "log_digest"),
    ):
        relative = binding.get(artifact_field)
        digest = binding.get(digest_field)
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise ValueError(f"Incomplete evidence binding for {gate_name}")
        if command.get(artifact_field) != relative:
            raise ValueError(f"Command artifact mismatch for {gate_name}")
        if command.get(digest_field) != digest:
            raise ValueError(f"Command digest mismatch for {gate_name}")
        verify_bound_file(root, relative, digest)

    result_path = root / cast(str, binding["result_artifact"])
    result = load_json(result_path)
    if result.get("exit_code") != 0:
        raise ValueError(f"Gate result artifact is not successful: {gate_name}")


def verify_artifact(
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
    manifest = load_json(root / "manifest.json")
    decision = load_json(root / "decision.json")

    expected_identity = {
        "repository": repository,
        "base_commit": base_sha,
        "head_commit": head_sha,
        "evaluated_commit": merge_sha,
        "integrable_commit": merge_sha,
    }
    for field, expected in expected_identity.items():
        if manifest.get(field) != expected:
            raise ValueError(
                f"Manifest identity mismatch for {field}: "
                f"{manifest.get(field)!r} != {expected!r}"
            )

    change_budget = manifest.get("change_budget")
    if not isinstance(change_budget, dict):
        raise ValueError("Manifest change_budget is missing.")
    if change_budget.get("within_budget") is not True:
        raise ValueError("Manifest reports an exceeded change budget.")
    manifest_files = change_budget.get("changed_files")
    if not isinstance(manifest_files, list):
        raise ValueError("Manifest changed_files is invalid.")
    if sorted(manifest_files) != sorted(changed_files):
        raise ValueError("Manifest changed_files does not match the live PR.")

    required_gates = policy.get("required_gates")
    if not isinstance(required_gates, list) or not required_gates:
        raise ValueError("Trust policy required_gates must be a non-empty list.")
    for gate in required_gates:
        if not isinstance(gate, str):
            raise ValueError("Trust policy gate names must be strings.")
        verify_gate(root, manifest, gate)

    package = root / PACKAGE_PATH
    if not package.is_file():
        raise ValueError(
            "Exact portable package bytes are missing from the workflow artifact."
        )
    package_digest = sha256_file(package)
    installability = manifest.get("package_installability")
    if not isinstance(installability, dict):
        raise ValueError("Manifest package_installability is missing.")
    if installability.get("archive_digest") != package_digest:
        raise ValueError("Portable package digest does not match the manifest.")

    if decision.get("decision") != "APPROVED":
        raise ValueError("Source decision is not APPROVED.")

    protected_patterns = policy.get("protected_paths")
    if not isinstance(protected_patterns, list):
        raise ValueError("Trust policy protected_paths must be a list.")
    protected = control_plane_changes(
        changed_files,
        [str(item) for item in protected_patterns],
    )
    exceptions = policy.get("bootstrap_exceptions", [])
    if protected and not exception_matches(
        [item for item in exceptions if isinstance(item, dict)],
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
    ):
        raise ValueError(
            "Control-plane paths changed without an exact, unexpired "
            "trust-anchor exception: "
            + ", ".join(protected)
        )

    return {
        "verification_version": 1,
        "repository": repository,
        "pull_request": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_sha": merge_sha,
        "changed_files": sorted(changed_files),
        "protected_changes": protected,
        "required_gates": required_gates,
        "package_path": PACKAGE_PATH,
        "package_digest": package_digest,
        "source_decision": decision.get("decision"),
        "passed": True,
    }


def list_pr_files(api_base: str, repository: str, pr_number: int, token: str) -> list[str]:
    files: list[str] = []
    page = 1
    while True:
        raw = api_request(
            f"{api_base}/repos/{repository}/pulls/{pr_number}/files"
            f"?per_page=100&page={page}",
            token,
        )
        if not isinstance(raw, list):
            raise ValueError("GitHub pull-request files response must be a list.")
        batch = [
            item["filename"]
            for item in raw
            if isinstance(item, dict) and isinstance(item.get("filename"), str)
        ]
        files.extend(batch)
        if len(raw) < 100:
            break
        page += 1
    return sorted(files)


def create_check(
    api_base: str,
    repository: str,
    head_sha: str,
    token: str,
) -> int:
    raw = api_request(
        f"{api_base}/repos/{repository}/check-runs",
        token,
        method="POST",
        payload={
            "name": CHECK_NAME,
            "head_sha": head_sha,
            "status": "in_progress",
            "output": {
                "title": "ASI trust-anchor verification",
                "summary": "Trusted verification is running from the default branch.",
            },
        },
    )
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), int):
        raise ValueError("Cannot create the ASI Trust Anchor check run.")
    return cast(int, raw["id"])


def complete_check(
    api_base: str,
    repository: str,
    check_id: int,
    token: str,
    *,
    conclusion: str,
    title: str,
    summary: str,
) -> None:
    api_request(
        f"{api_base}/repos/{repository}/check-runs/{check_id}",
        token,
        method="PATCH",
        payload={
            "status": "completed",
            "conclusion": conclusion,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "output": {
                "title": title[:255],
                "summary": summary[:65535],
            },
        },
    )


def run() -> int:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    admin_token = os.environ.get("ASI_GITHUB_ADMIN_TOKEN", "")
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    api_base = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    policy_path = Path(
        os.environ.get("ASI_TRUST_POLICY", "guardian/trust-policy.json")
    )
    if repository.count("/") != 1:
        raise ValueError("GITHUB_REPOSITORY must use owner/repository format.")
    if not token:
        raise ValueError("GITHUB_TOKEN is required.")
    if not event_path.is_file():
        raise ValueError("GITHUB_EVENT_PATH is unavailable.")
    if not policy_path.is_file():
        raise ValueError("Trust policy is unavailable.")

    event = load_json(event_path)
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
    if not isinstance(head_sha, str) or not isinstance(run_id, int):
        raise ValueError("Source workflow identity is incomplete.")

    check_id = create_check(api_base, repository, head_sha, token)
    report: dict[str, Any]
    try:
        policy = load_json(policy_path)
        trusted_workflow = policy.get("trusted_workflow")
        if source.get("name") != trusted_workflow:
            raise ValueError("Unexpected source workflow.")
        if source.get("event") != "pull_request":
            raise ValueError("Source workflow must be triggered by pull_request.")

        pr = api_request(
            f"{api_base}/repos/{repository}/pulls/{pr_number}",
            token,
        )
        if not isinstance(pr, dict):
            raise ValueError("Cannot fetch pull request metadata.")
        head = pr.get("head")
        base = pr.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            raise ValueError("Pull request refs are incomplete.")
        if head.get("sha") != head_sha:
            raise ValueError("Source workflow head does not match the live PR head.")
        base_sha = base.get("sha")
        merge_sha = pr.get("merge_commit_sha")
        if not isinstance(base_sha, str) or not isinstance(merge_sha, str):
            raise ValueError("Pull request base or merge commit is missing.")

        changed_files = list_pr_files(api_base, repository, pr_number, token)

        artifacts = api_request(
            f"{api_base}/repos/{repository}/actions/runs/{run_id}/artifacts"
            "?per_page=100",
            token,
        )
        if not isinstance(artifacts, dict):
            raise ValueError("Cannot list source workflow artifacts.")
        expected_name = f"{policy.get('artifact_prefix')}{run_id}"
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
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, int):
            raise ValueError("Artifact id is missing.")
        archive = download_bytes(
            f"{api_base}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
            token,
        )
        api_digest = artifact.get("digest")
        archive_digest = sha256_bytes(archive)
        if isinstance(api_digest, str) and api_digest != archive_digest:
            raise ValueError("Downloaded artifact digest does not match GitHub metadata.")

        with tempfile.TemporaryDirectory(prefix="asi-trust-anchor-") as temp:
            evidence_root = Path(temp) / "evidence"
            evidence_root.mkdir()
            safe_extract(archive, evidence_root)
            report = verify_artifact(
                evidence_root,
                policy,
                repository=repository,
                pr_number=pr_number,
                base_sha=base_sha,
                head_sha=head_sha,
                merge_sha=merge_sha,
                changed_files=changed_files,
            )
            report["source_run_id"] = run_id
            report["source_artifact_id"] = artifact_id
            report["source_artifact_digest"] = archive_digest

        if not admin_token:
            raise ValueError("ASI_GITHUB_ADMIN_TOKEN is required.")
        raw_protection = api_request(
            f"{api_base}/repos/{repository}/branches/"
            f"{urllib.parse.quote(str(base.get('ref')), safe='')}/protection",
            admin_token,
        )
        if not isinstance(raw_protection, dict):
            raise ValueError("Branch-protection response is invalid.")
        report["branch_protection_raw_digest"] = sha256_bytes(
            json.dumps(
                raw_protection,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )

        report["passed"] = True
        summary = json.dumps(report, indent=2, sort_keys=True)
        complete_check(
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
            "verification_version": 1,
            "repository": repository,
            "source_run_id": run_id,
            "head_sha": head_sha,
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        summary = json.dumps(report, indent=2, sort_keys=True)
        complete_check(
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
        urllib.error.HTTPError,
        urllib.error.URLError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"Trust-anchor bootstrap failure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
