#!/usr/bin/env python3
"""Produce unprivileged ASI evidence bound to one pull-request merge commit.

BIRTH-06 deliberately proves only the evidence transport/identity contract. It
must not manufacture privileged branch-protection evidence, independent audit
identity, target-environment observation, or any other gate that was not
actually measured by this producer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SHA40 = set("0123456789abcdef")
ARTIFACT_PREFIX = "asi-evidence-"
REQUIRED_GATES = (
    "integrity",
    "branch_protection",
    "format_check",
    "lint",
    "typecheck",
    "build",
    "package_installability",
    "unit_tests",
    "integration_tests",
    "secret_scan",
    "dependency_scan",
    "rollback_check",
    "independent_audit",
    "target_environment_observation",
)
EXPECTED_PATHS = {
    ".github/workflows/validate-skill.yml",
    "producer/README.md",
    "producer/evidence_producer.py",
    "producer/test_evidence_producer.py",
    "producer/package-source/BIRTH-06-PRODUCER.txt",
}


def sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_sha40(value: str, label: str) -> str:
    if len(value) != 40 or any(char not in SHA40 for char in value):
        raise ValueError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def artifact_name(run_id: int, run_attempt: int, head_sha: str, evaluated_sha: str) -> str:
    require_sha40(head_sha, "head_sha")
    require_sha40(evaluated_sha, "evaluated_sha")
    if run_id <= 0 or run_attempt <= 0:
        raise ValueError("run_id and run_attempt must be positive")
    return (
        f"{ARTIFACT_PREFIX}{run_id}-attempt-{run_attempt}-"
        f"{head_sha}-{evaluated_sha}"
    )


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def changed_files(root: Path, base_sha: str, evaluated_sha: str) -> list[str]:
    output = git(root, "diff", "--name-only", "--diff-filter=ACDMRTUXB", base_sha, evaluated_sha)
    return sorted(line for line in output.splitlines() if line)


def verify_change_budget(files: list[str]) -> dict[str, Any]:
    unexpected = sorted(set(files) - EXPECTED_PATHS)
    missing = sorted(EXPECTED_PATHS - set(files))
    within_budget = not unexpected and not missing and len(files) <= len(EXPECTED_PATHS)
    return {
        "within_budget": within_budget,
        "changed_files": sorted(files),
        "expected_paths": sorted(EXPECTED_PATHS),
        "unexpected_paths": unexpected,
        "missing_expected_paths": missing,
        "max_files": len(EXPECTED_PATHS),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_deterministic_package(source: Path, target: Path) -> str:
    if not source.is_dir():
        raise ValueError(f"package source directory is missing: {source}")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if not files:
        raise ValueError("package source directory is empty")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(target) as archive:
        names = sorted(archive.namelist())
    expected = sorted(path.relative_to(source).as_posix() for path in files)
    if names != expected:
        raise ValueError("portable package contents are not deterministic")
    return sha256_file(target)


def integrity_gate(
    root: Path,
    output: Path,
    *,
    base_sha: str,
    head_sha: str,
    evaluated_sha: str,
    files: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    require_sha40(base_sha, "base_sha")
    require_sha40(head_sha, "head_sha")
    require_sha40(evaluated_sha, "evaluated_sha")
    checked_out = git(root, "rev-parse", "HEAD")
    if checked_out != evaluated_sha:
        raise ValueError("checked-out commit does not equal evaluated_sha")
    subprocess.run(["git", "merge-base", "--is-ancestor", base_sha, evaluated_sha], cwd=root, check=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", head_sha, evaluated_sha], cwd=root, check=True)
    budget = verify_change_budget(files)
    if not budget["within_budget"]:
        raise ValueError("BIRTH-06 change budget does not match the live diff")

    log_rel = "gates/integrity.log"
    result_rel = "gates/integrity.json"
    log_path = output / log_rel
    result_path = output / result_rel
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                f"base_sha={base_sha}",
                f"head_sha={head_sha}",
                f"evaluated_sha={evaluated_sha}",
                f"checked_out={checked_out}",
                "changed_files:",
                *files,
                "change_budget=within_budget",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result = {
        "result_version": 2,
        "name": "integrity",
        "exit_code": 0,
        "argv": ["producer/evidence_producer.py", "integrity"],
        "command": "BIRTH-06 producer identity and exact-diff budget check",
        "log_artifact": log_rel,
        "log_digest": sha256_file(log_path),
    }
    write_json(result_path, result)
    command = {
        "name": "integrity",
        "argv": result["argv"],
        "command": result["command"],
        "exit_code": 0,
        "result_artifact": result_rel,
        "result_digest": sha256_file(result_path),
        "log_artifact": log_rel,
        "log_digest": result["log_digest"],
    }
    binding = {
        "result_artifact": result_rel,
        "result_digest": command["result_digest"],
        "log_artifact": log_rel,
        "log_digest": command["log_digest"],
    }
    return command, binding


def produce(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    base_sha = require_sha40(args.base_sha, "base_sha")
    head_sha = require_sha40(args.head_sha, "head_sha")
    evaluated_sha = require_sha40(args.evaluated_sha, "evaluated_sha")
    expected_artifact = artifact_name(args.run_id, args.run_attempt, head_sha, evaluated_sha)
    if args.expected_artifact_name != expected_artifact:
        raise ValueError("workflow artifact name does not match artifact identity v2")

    files = changed_files(root, base_sha, evaluated_sha)
    command, binding = integrity_gate(
        root,
        output,
        base_sha=base_sha,
        head_sha=head_sha,
        evaluated_sha=evaluated_sha,
        files=files,
    )

    package_path = output / "package" / "asi-verifiable-engineering.zip"
    package_digest = build_deterministic_package(
        root / "producer" / "package-source",
        package_path,
    )

    gates = {gate: "not_verified" for gate in REQUIRED_GATES}
    gates["integrity"] = "passed"
    blockers = [
        f"Required gate {gate} is not verified by BIRTH-06."
        for gate in REQUIRED_GATES
        if gate != "integrity"
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    budget = verify_change_budget(files)

    manifest = {
        "manifest_version": 3,
        "artifact_identity_version": 2,
        "repository": args.repository,
        "branch": args.branch,
        "base_commit": base_sha,
        "head_commit": head_sha,
        "evaluated_commit": evaluated_sha,
        "integrable_commit": evaluated_sha,
        "workflow_run": args.run_url,
        "workflow_run_id": args.run_id,
        "workflow_run_attempt": args.run_attempt,
        "artifact_name": expected_artifact,
        "changed_files": files,
        "change_budget": budget,
        "commands": [command],
        "gates": gates,
        "gate_evidence": {"integrity": binding},
        "package_installability": {
            "archive": "package/asi-verifiable-engineering.zip",
            "archive_digest": package_digest,
            "status": "not_verified",
            "note": "Exact package bytes are preserved for contract testing; this is not a release or target-observation attestation.",
        },
        "independence": ["I2"],
        "unverified": blockers,
        "residual_risks": [
            "Privileged branch-protection evidence is intentionally absent from the unprivileged producer.",
            "Independent I1 execution identity is not established by BIRTH-06.",
            "Target-environment observation of the exact package is not established by BIRTH-06.",
        ],
        "decision": "BLOCKED",
        "created_at": now,
    }
    decision = {
        "decision": "BLOCKED",
        "blockers": blockers,
        "authority": "producer-claim-only",
        "note": "ASI Trust Anchor remains the trusted arbiter.",
    }
    identity = {
        "version": 2,
        "run_id": args.run_id,
        "run_attempt": args.run_attempt,
        "head_sha": head_sha,
        "evaluated_sha": evaluated_sha,
        "artifact_name": expected_artifact,
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "decision.json", decision)
    write_json(output / "artifact-identity.json", identity)
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repository", required=True)
    result.add_argument("--branch", required=True)
    result.add_argument("--base-sha", required=True)
    result.add_argument("--head-sha", required=True)
    result.add_argument("--evaluated-sha", required=True)
    result.add_argument("--run-id", required=True, type=int)
    result.add_argument("--run-attempt", required=True, type=int)
    result.add_argument("--run-url", required=True)
    result.add_argument("--expected-artifact-name", required=True)
    result.add_argument("--output-dir", required=True)
    result.add_argument("--repo-root", default=".")
    return result


def main() -> int:
    try:
        manifest = produce(parser().parse_args())
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        print(f"BIRTH-06 evidence production failed: {exc}")
        return 2
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
