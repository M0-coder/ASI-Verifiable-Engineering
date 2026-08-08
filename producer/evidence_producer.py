#!/usr/bin/env python3
"""Produce unprivileged ASI evidence for one exact pull-request merge candidate."""

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
PACKAGE_SOURCE = Path("skills/asi-verifiable-engineering")
PACKAGE_ARCHIVE = "package/asi-verifiable-engineering.zip"


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
    return f"{ARTIFACT_PREFIX}{run_id}-attempt-{run_attempt}-{head_sha}-{evaluated_sha}"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def changed_files(root: Path, base_sha: str, evaluated_sha: str) -> list[str]:
    output = git(
        root,
        "diff",
        "--name-only",
        "--diff-filter=ACDMRTUXB",
        base_sha,
        evaluated_sha,
    )
    return sorted(line for line in output.splitlines() if line)


def load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return raw


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_change_budget(files: list[str], budget: dict[str, Any]) -> dict[str, Any]:
    max_files = budget.get("max_files")
    prefixes = budget.get("allowed_prefixes")
    roots = budget.get("allowed_root_files")
    forbidden = budget.get("forbidden_paths")
    if not isinstance(max_files, int) or max_files <= 0:
        raise ValueError("change budget max_files must be a positive integer")
    if not isinstance(prefixes, list) or not all(isinstance(x, str) for x in prefixes):
        raise ValueError("change budget allowed_prefixes must be a string list")
    if not isinstance(roots, list) or not all(isinstance(x, str) for x in roots):
        raise ValueError("change budget allowed_root_files must be a string list")
    if not isinstance(forbidden, list) or not all(isinstance(x, str) for x in forbidden):
        raise ValueError("change budget forbidden_paths must be a string list")

    def allowed(path: str) -> bool:
        return path in roots or any(path.startswith(prefix) for prefix in prefixes)

    unexpected = sorted(path for path in files if not allowed(path))
    forbidden_hits = sorted(path for path in files if path in forbidden)
    within_budget = len(files) <= max_files and not unexpected and not forbidden_hits
    return {
        "policy_version": budget.get("version"),
        "within_budget": within_budget,
        "changed_files": files,
        "max_files": max_files,
        "unexpected_paths": unexpected,
        "forbidden_paths": forbidden_hits,
    }


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
    budget: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require_sha40(base_sha, "base_sha")
    require_sha40(head_sha, "head_sha")
    require_sha40(evaluated_sha, "evaluated_sha")
    checked_out = git(root, "rev-parse", "HEAD")
    if checked_out != evaluated_sha:
        raise ValueError("checked-out commit does not equal evaluated_sha")
    subprocess.run(["git", "merge-base", "--is-ancestor", base_sha, evaluated_sha], cwd=root, check=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", head_sha, evaluated_sha], cwd=root, check=True)
    budget_report = verify_change_budget(files, budget)
    if not budget_report["within_budget"]:
        raise ValueError("live diff exceeds repository change budget")

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
        "command": "candidate identity + repository change-budget verification",
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
    return command, binding, budget_report


def load_measured_gate(output: Path, name: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    result_rel = f"gates/{name}.json"
    result_path = output / result_rel
    if not result_path.is_file():
        raise FileNotFoundError(result_path)
    data = load_json(result_path)
    if data.get("result_version") != 2 or data.get("name") != name:
        raise ValueError(f"measured gate identity is invalid: {name}")
    exit_code = data.get("exit_code")
    argv = data.get("argv")
    command_text = data.get("command")
    log_rel = data.get("log_artifact")
    log_digest = data.get("log_digest")
    if (
        not isinstance(exit_code, int)
        or not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
        or not isinstance(command_text, str)
        or not command_text
        or not isinstance(log_rel, str)
        or not isinstance(log_digest, str)
    ):
        raise ValueError(f"measured gate result is incomplete: {name}")
    log_path = output / log_rel
    if not log_path.is_file() or sha256_file(log_path) != log_digest:
        raise ValueError(f"measured gate log binding is invalid: {name}")
    result_digest = sha256_file(result_path)
    command = {
        "name": name,
        "argv": argv,
        "command": command_text,
        "exit_code": exit_code,
        "result_artifact": result_rel,
        "result_digest": result_digest,
        "log_artifact": log_rel,
        "log_digest": log_digest,
    }
    binding = {
        "result_artifact": result_rel,
        "result_digest": result_digest,
        "log_artifact": log_rel,
        "log_digest": log_digest,
    }
    return ("passed" if exit_code == 0 else "failed"), command, binding


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

    trust_policy = load_json(root / "guardian/trust-policy.json")
    source_required = trust_policy.get("source_required_gates")
    trusted_required = trust_policy.get("trusted_required_gates")
    if not isinstance(source_required, list) or not all(isinstance(x, str) for x in source_required):
        raise ValueError("source_required_gates are invalid")
    if not isinstance(trusted_required, list) or not all(isinstance(x, str) for x in trusted_required):
        raise ValueError("trusted_required_gates are invalid")

    files = changed_files(root, base_sha, evaluated_sha)
    integrity_command, integrity_binding, budget_report = integrity_gate(
        root,
        output,
        base_sha=base_sha,
        head_sha=head_sha,
        evaluated_sha=evaluated_sha,
        files=files,
        budget=load_json(root / ".asi/change-budget.json"),
    )

    gates = {name: "not_verified" for name in source_required + trusted_required}
    gates["integrity"] = "passed"
    commands = [integrity_command]
    gate_evidence: dict[str, dict[str, Any]] = {"integrity": integrity_binding}

    for name in source_required:
        if name == "integrity":
            continue
        try:
            state, command, binding = load_measured_gate(output, name)
        except FileNotFoundError:
            continue
        gates[name] = state
        commands.append(command)
        gate_evidence[name] = binding

    for name in trusted_required:
        gates[name] = "not_verified"
        gate_evidence.pop(name, None)

    package_path = output / PACKAGE_ARCHIVE
    package_digest = build_deterministic_package(root / PACKAGE_SOURCE, package_path)
    package_state = gates.get("package_installability", "not_verified")

    blockers: list[str] = []
    reason_codes: list[str] = []
    for gate in source_required:
        state = gates.get(gate, "not_verified")
        if state == "failed":
            blockers.append(f"Required source gate {gate} failed.")
            reason_codes.append(f"required_control_failed:{gate}")
        elif state != "passed":
            blockers.append(f"Required source gate {gate} is not verified.")
            reason_codes.append(f"required_control_not_verified:{gate}")
    for gate in trusted_required:
        blockers.append(f"Trusted gate {gate} must be established by ASI Trust Anchor.")
        reason_codes.append(f"trusted_control_pending:{gate}")

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snapshot = load_json(root / PACKAGE_SOURCE / "assets/specification-snapshot.json")
    manifest = {
        "manifest_version": 4,
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
        "change_budget": budget_report,
        "commands": commands,
        "gates": gates,
        "gate_evidence": gate_evidence,
        "package_installability": {
            "archive": PACKAGE_ARCHIVE,
            "archive_digest": package_digest,
            "status": package_state,
        },
        "specification_snapshot": {
            "skill_version": snapshot.get("skill_version"),
            "doctrine_version": snapshot.get("doctrine_version"),
            "architecture_version": snapshot.get("architecture_version"),
            "packaging_contract_version": snapshot.get("packaging_contract_version"),
            "full_conformance": snapshot.get("full_conformance"),
        },
        "audit_coverage": {
            "executed": sorted(gate_evidence),
            "inherited_evidence": [],
            "unavailable_or_not_verified": sorted(name for name in source_required if gates.get(name) == "not_verified"),
            "trusted_boundary_pending": sorted(trusted_required),
        },
        "unverified": [item for item in blockers if "not verified" in item.lower() or "Trust Anchor" in item],
        "residual_risks": [
            "Unprivileged producer cannot establish privileged branch-protection state.",
            "Independent audit and target-environment observation remain explicit gates and are not fabricated.",
            "The Notion source export digest remains NOT_VERIFIED in the current Specification Snapshot."
        ],
        "candidate_decision": "BLOCKED",
        "candidate_decision_reason_codes": sorted(set(reason_codes)),
        "decision": "BLOCKED",
        "created_at": now,
    }
    decision = {
        "decision": "BLOCKED",
        "candidate_decision": "BLOCKED",
        "candidate_decision_reason_codes": sorted(set(reason_codes)),
        "blockers": blockers,
        "authority": "producer-claim-only",
        "note": "ASI Trust Anchor remains the trusted decision authority."
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
    args = parser().parse_args()
    manifest = produce(args)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
