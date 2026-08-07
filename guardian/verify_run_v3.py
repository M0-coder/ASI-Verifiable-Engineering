#!/usr/bin/env python3
"""Trust-anchor v3: split unprivileged source gates from trusted control-plane gates."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import verify_protection_binding as protection
import verify_run as legacy
import verify_run_v2 as v2

VERIFICATION_VERSION = 3
H1_PREFIX = "ASI-H1-EXCEPTION-V1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def gate_ownership(policy: dict[str, Any]) -> tuple[list[str], list[str]]:
    required = policy.get("required_gates")
    source = policy.get("source_required_gates")
    trusted = policy.get("trusted_required_gates")
    if not isinstance(required, list) or not required or not all(isinstance(x, str) for x in required):
        raise ValueError("required_gates must be a non-empty string list.")
    if not isinstance(source, list) or not source or not all(isinstance(x, str) for x in source):
        raise ValueError("source_required_gates must be a non-empty string list.")
    if not isinstance(trusted, list) or not trusted or not all(isinstance(x, str) for x in trusted):
        raise ValueError("trusted_required_gates must be a non-empty string list.")
    if len(set(required)) != len(required) or len(set(source)) != len(source) or len(set(trusted)) != len(trusted):
        raise ValueError("Gate ownership lists must not contain duplicates.")
    if set(source) & set(trusted):
        raise ValueError("Source and trusted gate ownership must be disjoint.")
    if set(source) | set(trusted) != set(required):
        raise ValueError("Source and trusted gates must partition required_gates exactly.")
    if trusted != ["branch_protection"]:
        raise ValueError("branch_protection must be the sole trusted gate in policy v3.")
    return cast(list[str], source), cast(list[str], trusted)


def verify_source_artifact(
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
    manifest = legacy.load_json(root / "manifest.json")
    decision = legacy.load_json(root / "decision.json")
    source_gates, trusted_gates = gate_ownership(policy)

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

    budget = manifest.get("change_budget")
    if not isinstance(budget, dict) or budget.get("within_budget") is not True:
        raise ValueError("Manifest change_budget is missing or exceeded.")
    manifest_files = budget.get("changed_files")
    if not isinstance(manifest_files, list) or sorted(manifest_files) != sorted(changed_files):
        raise ValueError("Manifest changed_files does not match the live PR.")

    gates = manifest.get("gates")
    gate_evidence = manifest.get("gate_evidence")
    if not isinstance(gates, dict):
        raise ValueError("Manifest gates are missing.")
    if not isinstance(gate_evidence, dict):
        raise ValueError("Manifest gate_evidence is missing.")

    for gate in trusted_gates:
        if gates.get(gate) == "passed":
            raise ValueError(f"Unprivileged source may not assert trusted gate as passed: {gate}")
        if gate in gate_evidence:
            raise ValueError(f"Unprivileged source may not provide trusted gate evidence: {gate}")

    for gate in source_gates:
        legacy.verify_gate(root, manifest, gate)

    package = root / legacy.PACKAGE_PATH
    if not package.is_file():
        raise ValueError("Exact portable package bytes are missing from the workflow artifact.")
    package_digest = legacy.sha256_file(package)
    installability = manifest.get("package_installability")
    if not isinstance(installability, dict):
        raise ValueError("Manifest package_installability is missing.")
    if installability.get("archive_digest") != package_digest:
        raise ValueError("Portable package digest does not match the manifest.")

    protected_patterns = policy.get("protected_paths")
    if not isinstance(protected_patterns, list):
        raise ValueError("Trust policy protected_paths must be a list.")
    protected_changes = legacy.control_plane_changes(
        changed_files, [str(item) for item in protected_patterns]
    )

    return {
        "verification_version": VERIFICATION_VERSION,
        "repository": repository,
        "pull_request": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_sha": merge_sha,
        "changed_files": sorted(changed_files),
        "protected_changes": protected_changes,
        "source_required_gates": source_gates,
        "trusted_required_gates": trusted_gates,
        "package_path": legacy.PACKAGE_PATH,
        "package_digest": package_digest,
        "source_decision_claim": decision.get("decision"),
        "source_decision_authoritative": False,
    }


def parse_h1_body(body: str) -> dict[str, Any] | None:
    if not body.startswith(H1_PREFIX + "\n"):
        return None
    payload = body[len(H1_PREFIX) + 1 :].strip()
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def h1_comment_matches(
    comment: dict[str, Any],
    *,
    authorizers: list[str],
    pr_number: int,
    base_sha: str,
    head_sha: str,
    protected_changes: list[str],
    now: datetime | None = None,
) -> dict[str, Any] | None:
    user = comment.get("user")
    if not isinstance(user, dict) or user.get("login") not in authorizers:
        return None
    if comment.get("author_association") != "OWNER":
        return None
    body = comment.get("body")
    if not isinstance(body, str):
        return None
    data = parse_h1_body(body)
    if data is None:
        return None
    if data.get("authorization_level") != "H1":
        return None
    if data.get("authorization_scope") != "control-plane-exception-only":
        return None
    if data.get("merge_authorized") is not False:
        return None
    if data.get("pr_number") != pr_number:
        return None
    if data.get("base_sha") != base_sha or data.get("head_sha") != head_sha:
        return None
    allowed = data.get("allowed_paths")
    if not isinstance(allowed, list) or not all(isinstance(x, str) for x in allowed):
        return None
    if sorted(cast(list[str], allowed)) != sorted(protected_changes):
        return None
    if not isinstance(data.get("reason"), str) or not data["reason"].strip():
        return None
    expires = data.get("expires_at")
    if not isinstance(expires, str):
        return None
    try:
        expiry = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    except ValueError:
        return None
    current = now or datetime.now(timezone.utc)
    if expiry.tzinfo is None or expiry <= current:
        return None
    return {
        "mode": "owner_comment_v1",
        "comment_id": comment.get("id"),
        "comment_url": comment.get("html_url"),
        "authorized_by": user.get("login"),
        "expires_at": expires,
        "reason": data["reason"],
        "merge_authorized": False,
    }


def list_issue_comments(api_base: str, repository: str, pr_number: int, token: str) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    page = 1
    while True:
        raw = legacy.api_request(
            f"{api_base}/repos/{repository}/issues/{pr_number}/comments?per_page=100&page={page}",
            token,
        )
        if not isinstance(raw, list):
            raise ValueError("GitHub issue comments response must be a list.")
        comments.extend(item for item in raw if isinstance(item, dict))
        if len(raw) < 100:
            break
        page += 1
    return comments


def resolve_control_plane_exception(
    policy: dict[str, Any],
    *,
    api_base: str,
    repository: str,
    token: str,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    protected_changes: list[str],
) -> dict[str, Any] | None:
    if not protected_changes:
        return None

    raw_static = policy.get("bootstrap_exceptions", [])
    static = [item for item in raw_static if isinstance(item, dict)]
    if v2.exception_matches_exact(
        static,
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
        protected_changes=protected_changes,
    ):
        return {"mode": "static_policy_v2"}

    if policy.get("bootstrap_exception_mode") != "owner_comment_v1":
        return None
    authorizers = policy.get("h1_authorizers")
    if not isinstance(authorizers, list) or not authorizers or not all(isinstance(x, str) for x in authorizers):
        raise ValueError("h1_authorizers must be a non-empty string list.")
    for comment in reversed(list_issue_comments(api_base, repository, pr_number, token)):
        match = h1_comment_matches(
            comment,
            authorizers=cast(list[str], authorizers),
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            protected_changes=protected_changes,
        )
        if match is not None:
            return match
    return None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def trust_anchor_provenance(policy_path: Path) -> dict[str, str]:
    trust_sha = os.environ.get("ASI_TRUST_ANCHOR_SHA", "")
    workflow_path = Path(os.environ.get("ASI_TRUST_WORKFLOW", ".github/workflows/asi-trust-anchor.yml"))
    verifier_path = Path(os.environ.get("ASI_TRUST_VERIFIER", "guardian/verify_run_v3.py"))
    if not SHA40.fullmatch(trust_sha):
        raise ValueError("ASI_TRUST_ANCHOR_SHA must be an immutable 40-character SHA.")
    checked_out = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
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
    policy_path = Path(os.environ.get("ASI_TRUST_POLICY", "guardian/trust-policy.json"))
    output_root = Path(os.environ.get("ASI_TRUST_OUTPUT", ""))
    if repository.count("/") != 1:
        raise ValueError("GITHUB_REPOSITORY must use owner/repository format.")
    if not token:
        raise ValueError("GITHUB_TOKEN is required.")
    if not admin_token:
        raise ValueError("ASI_GITHUB_ADMIN_TOKEN is required.")
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
    try:
        policy = legacy.load_json(policy_path)
        if policy.get("version") != 3 or policy.get("artifact_name_version") != 2:
            raise ValueError("Trust policy v3 with artifact identity v2 is required.")
        gate_ownership(policy)
        limits = v2.archive_limits(policy)
        if source.get("name") != policy.get("trusted_workflow"):
            raise ValueError("Unexpected source workflow.")
        if source.get("event") != "pull_request" or source.get("conclusion") != "success":
            raise ValueError("Source workflow must be a successful pull_request run.")

        pr = legacy.api_request(f"{api_base}/repos/{repository}/pulls/{pr_number}", token)
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
            not isinstance(base_sha, str) or not SHA40.fullmatch(base_sha)
            or not isinstance(merge_sha, str) or not SHA40.fullmatch(merge_sha)
        ):
            raise ValueError("Pull request base or merge commit is missing.")

        changed_files = legacy.list_pr_files(api_base, repository, pr_number, token)
        artifacts = legacy.api_request(
            f"{api_base}/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100", token
        )
        if not isinstance(artifacts, dict):
            raise ValueError("Cannot list source workflow artifacts.")
        write_json(output_root / "source-artifacts.json", artifacts)
        prefix = policy.get("artifact_prefix")
        if not isinstance(prefix, str):
            raise ValueError("Trust policy artifact_prefix is invalid.")
        expected_name = v2.artifact_name(
            prefix,
            run_id=run_id,
            run_attempt=run_attempt,
            head_sha=head_sha,
            evaluated_sha=merge_sha,
        )
        matches = [
            item for item in artifacts.get("artifacts", [])
            if isinstance(item, dict)
            and item.get("name") == expected_name
            and item.get("expired") is False
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one non-expired artifact named {expected_name}.")
        artifact = matches[0]
        write_json(output_root / "selected-artifact.json", artifact)
        artifact_id = artifact.get("id")
        if not isinstance(artifact_id, int):
            raise ValueError("Artifact id is missing.")
        archive = v2.download_bytes(
            f"{api_base}/repos/{repository}/actions/artifacts/{artifact_id}/zip",
            token,
            cast(int, limits["max_compressed_bytes"]),
        )
        archive_digest = legacy.sha256_bytes(archive)
        api_digest = artifact.get("digest")
        if isinstance(api_digest, str) and api_digest != archive_digest:
            raise ValueError("Downloaded artifact digest does not match GitHub metadata.")

        with tempfile.TemporaryDirectory(prefix="asi-trust-anchor-v3-") as temp:
            evidence_root = Path(temp) / "evidence"
            evidence_root.mkdir()
            v2.safe_extract(archive, evidence_root, limits)
            report = verify_source_artifact(
                evidence_root,
                policy,
                repository=repository,
                pr_number=pr_number,
                base_sha=base_sha,
                head_sha=head_sha,
                merge_sha=merge_sha,
                changed_files=changed_files,
            )

        protected_changes = cast(list[str], report["protected_changes"])
        exception = resolve_control_plane_exception(
            policy,
            api_base=api_base,
            repository=repository,
            token=token,
            pr_number=pr_number,
            base_sha=base_sha,
            head_sha=head_sha,
            protected_changes=protected_changes,
        )
        if protected_changes and exception is None:
            raise ValueError(
                "Control-plane paths changed without an exact H1 exception: "
                + ", ".join(protected_changes)
            )
        report["control_plane_exception"] = exception

        encoded_branch = urllib.parse.quote(str(base.get("ref")), safe="")
        check_runs = legacy.api_request(
            f"{api_base}/repos/{repository}/commits/{head_sha}/check-runs"
            f"?check_name={urllib.parse.quote(protection.EXPECTED_CHECK, safe='')}"
            "&filter=latest&per_page=100",
            token,
        )
        raw_protection = legacy.api_request(
            f"{api_base}/repos/{repository}/branches/{encoded_branch}/protection",
            admin_token,
        )
        if not isinstance(check_runs, dict) or not isinstance(raw_protection, dict):
            raise ValueError("Branch-protection responses are invalid.")
        write_json(output_root / "check-runs-raw.json", check_runs)
        write_json(output_root / "branch-protection-raw.json", raw_protection)
        protection_report = protection.evaluate_binding(raw_protection, check_runs)
        write_json(output_root / "branch-protection-verification.json", protection_report)
        if not protection_report.get("passed"):
            raise ValueError(
                "Trusted branch_protection gate failed: "
                + ", ".join(protection_report.get("missing_or_invalid_controls", []))
            )

        report.update(
            {
                "source_run_id": run_id,
                "source_run_attempt": run_attempt,
                "source_artifact_id": artifact_id,
                "source_artifact_name": expected_name,
                "source_artifact_digest": archive_digest,
                "trusted_gates": {"branch_protection": "passed"},
                "branch_protection": protection_report,
                "trust_anchor": trust_anchor_provenance(policy_path),
                "passed": True,
            }
        )
        write_json(output_root / "verification-report.json", report)
        summary = json.dumps(report, indent=2, sort_keys=True)
        legacy.complete_check(
            api_base, repository, check_id, token,
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
            api_base, repository, check_id, token,
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
        print(f"Trust-anchor v3 bootstrap failure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
