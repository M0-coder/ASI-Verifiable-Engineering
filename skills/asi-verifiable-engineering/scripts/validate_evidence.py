#!/usr/bin/env python3
"""Validate ASI evidence structure and, optionally, its cryptographic bindings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
E_LEVEL = re.compile(r"^E[0-8]$")
T_LEVEL = re.compile(r"^T[0-6]$")
I_LEVEL = re.compile(r"^I[0-3]$")
ALLOWED_RISKS = {"low", "medium", "high", "critical"}
ALLOWED_DECISIONS = {"APPROVED", "CONDITIONAL", "BLOCKED", "REJECTED"}
ALLOWED_GATE_STATES = {"passed", "failed", "not_applicable", "not_verified"}
ALLOWED_HONESTY_METHODS = {
    "not_verified",
    "adversarial_control_tests",
    "fails_on_base_passes_on_head",
    "revert_fix_makes_test_fail",
    "mutation_testing",
    "independent_negative_test",
}

REQUIRED_FIELDS = {
    "manifest_version",
    "repository",
    "branch",
    "base_commit",
    "head_commit",
    "evaluated_commit",
    "integrable_commit",
    "policy_version",
    "policy_digest",
    "diff_digest",
    "doctrine_version",
    "skill_version",
    "risk",
    "evidence_level",
    "assurance_level",
    "independence",
    "environment",
    "changed_files",
    "change_budget",
    "commands",
    "gates",
    "gate_evidence",
    "test_honesty",
    "forensic_triggers",
    "review",
    "artifacts",
    "unverified",
    "residual_risks",
    "decision",
    "rollback",
    "approved_by",
    "created_at",
    "expires_at",
}


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_iso8601(value: Any, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty ISO-8601 string.")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not valid ISO-8601: {value!r}")
        return None


def _require_sha256(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        errors.append(f"{field} must be sha256 followed by 64 lowercase hex characters.")


def _string_list(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field} must be a list.")
        return []
    if any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{field} entries must be non-empty strings.")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{field} must not contain duplicates.")
    return list(value)


def _artifact_map(data: dict[str, Any], errors: list[str]) -> dict[str, str]:
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list.")
        return {}
    result: dict[str, str] = {}
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"artifacts[{index}] must be an object.")
            continue
        path = artifact.get("path")
        digest = artifact.get("digest")
        producer = artifact.get("producer")
        if not isinstance(path, str) or not path:
            errors.append(f"artifacts[{index}].path is required.")
            continue
        if path in result:
            errors.append(f"Duplicate artifact path: {path}")
        _require_sha256(digest, f"artifacts[{index}].digest", errors)
        if not isinstance(producer, str) or not producer:
            errors.append(f"artifacts[{index}].producer is required.")
        if isinstance(digest, str):
            result[path] = digest
    return result


def validate_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Manifest root must be a JSON object."]

    missing = sorted(REQUIRED_FIELDS - data.keys())
    if missing:
        errors.append("Missing fields: " + ", ".join(missing))

    if data.get("manifest_version") != 2:
        errors.append("manifest_version must equal 2.")

    for field in ("base_commit", "head_commit", "evaluated_commit", "integrable_commit"):
        value = data.get(field)
        if not isinstance(value, str) or not SHA40.fullmatch(value):
            errors.append(f"{field} must be a 40-character lowercase Git SHA.")
    if data.get("integrable_commit") != data.get("evaluated_commit"):
        errors.append("integrable_commit must equal evaluated_commit.")
    if data.get("base_commit") == data.get("evaluated_commit"):
        errors.append("base_commit and evaluated_commit must differ.")

    _require_sha256(data.get("policy_digest"), "policy_digest", errors)
    _require_sha256(data.get("diff_digest"), "diff_digest", errors)

    risk = data.get("risk")
    if risk not in ALLOWED_RISKS:
        errors.append("risk must be low, medium, high, or critical.")
    if not isinstance(data.get("evidence_level"), str) or not E_LEVEL.fullmatch(
        data.get("evidence_level", "")
    ):
        errors.append("evidence_level must be E0 through E8.")
    if not isinstance(data.get("assurance_level"), str) or not T_LEVEL.fullmatch(
        data.get("assurance_level", "")
    ):
        errors.append("assurance_level must be T0 through T6.")

    independence = _string_list(data.get("independence"), "independence", errors)
    for value in independence:
        if not I_LEVEL.fullmatch(value):
            errors.append(f"Invalid independence level: {value!r}")

    environment = data.get("environment")
    if not isinstance(environment, dict):
        errors.append("environment must be an object.")
    else:
        for field in ("os", "architecture", "runtime", "package_manager", "lockfile_digest"):
            if not environment.get(field):
                errors.append(f"environment.{field} is required.")
        if environment.get("lockfile_digest"):
            _require_sha256(environment.get("lockfile_digest"), "environment.lockfile_digest", errors)

    changed_files = _string_list(data.get("changed_files"), "changed_files", errors)
    if not changed_files:
        errors.append("changed_files must be non-empty.")

    budget = data.get("change_budget")
    if not isinstance(budget, dict):
        errors.append("change_budget must be an object.")
    else:
        for field in (
            "expected_files",
            "unexpected_files",
            "forbidden_files",
            "binary_files",
            "violations",
            "within_budget",
        ):
            if field not in budget:
                errors.append(f"change_budget.{field} is required.")
        for field in ("expected_files", "unexpected_files", "forbidden_files", "binary_files", "violations"):
            if field in budget:
                _string_list(budget.get(field), f"change_budget.{field}", errors)
        if not isinstance(budget.get("within_budget"), bool):
            errors.append("change_budget.within_budget must be boolean.")

    decision = data.get("decision")
    if decision not in ALLOWED_DECISIONS:
        errors.append("decision must be APPROVED, CONDITIONAL, BLOCKED, or REJECTED.")

    artifacts = _artifact_map(data, errors)

    commands = data.get("commands")
    command_map: dict[str, dict[str, Any]] = {}
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list.")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                errors.append(f"commands[{index}] must be an object.")
                continue
            name = command.get("name")
            if not isinstance(name, str) or not name:
                errors.append(f"commands[{index}].name is required.")
                continue
            if name in command_map:
                errors.append(f"Duplicate command name: {name}")
            command_map[name] = command
            for field in (
                "argv",
                "command",
                "started_at",
                "finished_at",
                "duration_seconds",
                "exit_code",
                "result_artifact",
                "result_digest",
                "log_artifact",
                "log_digest",
            ):
                if field not in command:
                    errors.append(f"commands[{index}].{field} is required.")
            if not isinstance(command.get("argv"), list) or not command.get("argv"):
                errors.append(f"commands[{index}].argv must be a non-empty list.")
            if not isinstance(command.get("exit_code"), int):
                errors.append(f"commands[{index}].exit_code must be an integer.")
            duration = command.get("duration_seconds")
            if not isinstance(duration, (int, float)) or duration < 0:
                errors.append(f"commands[{index}].duration_seconds must be non-negative numeric.")
            started = _parse_iso8601(command.get("started_at"), f"commands[{index}].started_at", errors)
            finished = _parse_iso8601(command.get("finished_at"), f"commands[{index}].finished_at", errors)
            if started and finished and finished < started:
                errors.append(f"commands[{index}].finished_at precedes started_at.")
            for suffix in ("result_digest", "log_digest"):
                _require_sha256(command.get(suffix), f"commands[{index}].{suffix}", errors)
            for artifact_field, digest_field in (
                ("result_artifact", "result_digest"),
                ("log_artifact", "log_digest"),
            ):
                path = command.get(artifact_field)
                digest = command.get(digest_field)
                if isinstance(path, str) and artifacts.get(path) != digest:
                    errors.append(
                        f"commands[{index}].{artifact_field} is not declared with the same digest in artifacts."
                    )

    gates = data.get("gates")
    if not isinstance(gates, dict) or not gates:
        errors.append("gates must be a non-empty object.")
        gates = {}
    else:
        for name, state in gates.items():
            if state not in ALLOWED_GATE_STATES:
                errors.append(f"gates.{name} has invalid state: {state!r}")

    gate_evidence = data.get("gate_evidence")
    if not isinstance(gate_evidence, dict):
        errors.append("gate_evidence must be an object.")
        gate_evidence = {}
    for name, state in gates.items():
        item = gate_evidence.get(name)
        if not isinstance(item, dict):
            errors.append(f"gate_evidence.{name} is required.")
            continue
        if state in {"passed", "failed"}:
            for field in ("result_artifact", "result_digest", "log_artifact", "log_digest"):
                if not item.get(field):
                    errors.append(f"gate_evidence.{name}.{field} is required.")
            _require_sha256(item.get("result_digest"), f"gate_evidence.{name}.result_digest", errors)
            _require_sha256(item.get("log_digest"), f"gate_evidence.{name}.log_digest", errors)
            if artifacts.get(str(item.get("result_artifact"))) != item.get("result_digest"):
                errors.append(f"gate_evidence.{name}.result_artifact is not bound in artifacts.")
            if artifacts.get(str(item.get("log_artifact"))) != item.get("log_digest"):
                errors.append(f"gate_evidence.{name}.log_artifact is not bound in artifacts.")
            command = command_map.get(name)
            if command is None:
                errors.append(f"Measured command for gate {name} is missing.")
            elif (command.get("exit_code") == 0) != (state == "passed"):
                errors.append(f"Gate {name} state contradicts its measured exit_code.")
        elif not item.get("justification"):
            errors.append(f"gate_evidence.{name}.justification is required for {state}.")

    honesty = data.get("test_honesty")
    if not isinstance(honesty, dict):
        errors.append("test_honesty must be an object.")
    else:
        method = honesty.get("method")
        if method not in ALLOWED_HONESTY_METHODS:
            errors.append("test_honesty.method is invalid.")
        if method == "not_verified":
            if decision in {"APPROVED", "CONDITIONAL"}:
                errors.append("Approval requires verified test honesty.")
        else:
            for field in ("result_artifact", "result_digest", "evidence", "digest"):
                if not honesty.get(field):
                    errors.append(f"test_honesty.{field} is required.")
            _require_sha256(honesty.get("result_digest"), "test_honesty.result_digest", errors)
            _require_sha256(honesty.get("digest"), "test_honesty.digest", errors)
            if artifacts.get(str(honesty.get("result_artifact"))) != honesty.get("result_digest"):
                errors.append("test_honesty.result_artifact is not bound in artifacts.")
            if artifacts.get(str(honesty.get("evidence"))) != honesty.get("digest"):
                errors.append("test_honesty.evidence is not bound in artifacts.")

    _string_list(data.get("forensic_triggers"), "forensic_triggers", errors)
    unverified = _string_list(data.get("unverified"), "unverified", errors)
    residual_risks = _string_list(data.get("residual_risks"), "residual_risks", errors)
    approved_by = _string_list(data.get("approved_by"), "approved_by", errors)

    review = data.get("review")
    human: dict[str, Any] = {}
    if not isinstance(review, dict):
        errors.append("review must be an object.")
    else:
        if not isinstance(review.get("builder"), str) or not review.get("builder"):
            errors.append("review.builder is required.")
        if "auditor" not in review:
            errors.append("review.auditor is required, and may be null while blocked.")
        if review.get("same_context") not in {True, False}:
            errors.append("review.same_context must be boolean.")
        human_value = review.get("human_review")
        if not isinstance(human_value, dict):
            errors.append("review.human_review must be an object.")
        else:
            human = human_value
            for field in ("required", "completed", "mode"):
                if field not in human:
                    errors.append(f"review.human_review.{field} is required.")

    rollback = data.get("rollback")
    if not isinstance(rollback, dict) or not rollback.get("reference"):
        errors.append("rollback.reference is required.")
    elif not isinstance(rollback.get("tested"), bool):
        errors.append("rollback.tested must be boolean.")

    created = _parse_iso8601(data.get("created_at"), "created_at", errors)
    expires = _parse_iso8601(data.get("expires_at"), "expires_at", errors)
    if created and expires and expires <= created:
        errors.append("expires_at must be later than created_at.")

    if decision == "CONDITIONAL" and not data.get("conditions"):
        errors.append("CONDITIONAL requires a non-empty conditions list.")
    if decision == "APPROVED" and data.get("conditions"):
        errors.append("APPROVED cannot contain conditions.")

    approval_requested = decision in {"APPROVED", "CONDITIONAL"}
    if approval_requested:
        if unverified:
            errors.append("Approval cannot contain unverified items.")
        if decision == "APPROVED" and residual_risks:
            errors.append("APPROVED cannot contain residual risks.")
        if isinstance(budget, dict):
            if budget.get("within_budget") is not True or budget.get("violations"):
                errors.append("Approval requires a satisfied change budget.")
        if isinstance(rollback, dict) and rollback.get("tested") is not True:
            errors.append("Approval requires rollback.tested=true.")
        if isinstance(review, dict):
            auditor = review.get("auditor")
            if not isinstance(auditor, str) or not auditor:
                errors.append("Approval requires an identified independent auditor.")
            if review.get("builder") == auditor:
                errors.append("Approval requires builder and auditor to be distinct.")
            if review.get("same_context") is not False:
                errors.append("Approval requires independent review context.")
        levels = set(independence)
        if risk == "high":
            if "I3" not in levels:
                errors.append("High-risk approval requires I3.")
            if human.get("completed") is not True or human.get("mode") != "targeted":
                errors.append("High-risk approval requires completed targeted human review.")
        if risk == "critical":
            if "I3" not in levels:
                errors.append("Critical approval requires I3.")
            if human.get("completed") is not True or human.get("mode") != "targeted_dual":
                errors.append("Critical approval requires completed targeted_dual review.")
            if len(approved_by) < 2:
                errors.append("Critical approval requires at least two approvers.")

    return errors


def _safe_artifact_path(evidence_dir: Path, relative: str) -> Path | None:
    path = (evidence_dir / relative).resolve()
    try:
        path.relative_to(evidence_dir.resolve())
    except ValueError:
        return None
    return path


def _git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def verify_bindings(
    data: dict[str, Any],
    evidence_dir: Path,
    policy_path: Path,
    repo_root: Path,
) -> list[str]:
    errors: list[str] = []
    evidence_dir = evidence_dir.resolve()
    repo_root = repo_root.resolve()
    policy_path = policy_path.resolve()

    if sha256_file(policy_path) != data.get("policy_digest"):
        errors.append("policy_digest does not match the policy file.")

    try:
        diff = _git_bytes(
            repo_root,
            "diff",
            "--binary",
            str(data.get("base_commit")),
            str(data.get("evaluated_commit")),
        )
        actual_diff_digest = "sha256:" + hashlib.sha256(diff).hexdigest()
        if actual_diff_digest != data.get("diff_digest"):
            errors.append("diff_digest does not match the evaluated Git diff.")
        changed = sorted(
            line
            for line in _git_bytes(
                repo_root,
                "diff",
                "--name-only",
                str(data.get("base_commit")),
                str(data.get("evaluated_commit")),
            ).decode("utf-8").splitlines()
            if line
        )
        if changed != data.get("changed_files"):
            errors.append("changed_files does not match the evaluated Git diff.")
        head = _git_bytes(repo_root, "rev-parse", "HEAD").decode("utf-8").strip()
        if head != data.get("evaluated_commit"):
            errors.append("Repository HEAD does not equal evaluated_commit.")
    except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        errors.append(f"Cannot recompute Git bindings: {exc}")

    artifacts = data.get("artifacts") if isinstance(data.get("artifacts"), list) else []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        relative = artifact.get("path")
        if not isinstance(relative, str):
            continue
        path = _safe_artifact_path(evidence_dir, relative)
        if path is None:
            errors.append(f"Unsafe artifact path: {relative}")
            continue
        if not path.is_file():
            errors.append(f"Artifact does not exist: {relative}")
            continue
        digest = sha256_file(path)
        if digest != artifact.get("digest"):
            errors.append(f"Artifact digest mismatch: {relative}")

    commands = {
        item.get("name"): item
        for item in data.get("commands", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    gate_evidence = data.get("gate_evidence") if isinstance(data.get("gate_evidence"), dict) else {}
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    for name, state in gates.items():
        if state not in {"passed", "failed"}:
            continue
        item = gate_evidence.get(name)
        if not isinstance(item, dict):
            continue
        result_relative = item.get("result_artifact")
        if not isinstance(result_relative, str):
            continue
        result_path = _safe_artifact_path(evidence_dir, result_relative)
        if result_path is None or not result_path.is_file():
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot read gate result {name}: {exc}")
            continue
        if result.get("name") != name:
            errors.append(f"Gate result name mismatch for {name}.")
        if (result.get("exit_code") == 0) != (state == "passed"):
            errors.append(f"Gate state does not match measured result for {name}.")
        if result.get("log_artifact") != item.get("log_artifact"):
            errors.append(f"Gate log path mismatch for {name}.")
        if result.get("log_digest") != item.get("log_digest"):
            errors.append(f"Gate log digest mismatch for {name}.")
        command = commands.get(name)
        if command is not None:
            for field in (
                "argv",
                "command",
                "started_at",
                "finished_at",
                "duration_seconds",
                "exit_code",
                "log_artifact",
                "log_digest",
            ):
                if command.get(field) != result.get(field):
                    errors.append(f"Command field {field} does not match gate result {name}.")

    honesty = data.get("test_honesty")
    if isinstance(honesty, dict) and honesty.get("method") != "not_verified":
        result_relative = honesty.get("result_artifact")
        if isinstance(result_relative, str):
            result_path = _safe_artifact_path(evidence_dir, result_relative)
            if result_path and result_path.is_file():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    if result.get("exit_code") != 0:
                        errors.append("Test-honesty control did not exit successfully.")
                    if result.get("log_artifact") != honesty.get("evidence"):
                        errors.append("Test-honesty log path does not match its measured result.")
                    if result.get("log_digest") != honesty.get("digest"):
                        errors.append("Test-honesty log digest does not match its measured result.")
                except (OSError, json.JSONDecodeError) as exc:
                    errors.append(f"Cannot read test-honesty result: {exc}")

    return errors


def load_manifest(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("manifest", type=Path)
    result.add_argument("--evidence-dir", type=Path)
    result.add_argument("--policy", type=Path)
    result.add_argument("--repo-root", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        data = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot load evidence manifest: {exc}", file=sys.stderr)
        return 1

    errors = validate_manifest(data)
    binding_options = (args.evidence_dir, args.policy, args.repo_root)
    if any(binding_options) and not all(binding_options):
        errors.append("--evidence-dir, --policy, and --repo-root must be supplied together.")
    elif all(binding_options) and isinstance(data, dict):
        errors.extend(
            verify_bindings(
                data,
                args.evidence_dir,
                args.policy,
                args.repo_root,
            )
        )

    if errors:
        print(f"ASI evidence validation failed for {args.manifest}:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"ASI evidence manifest is valid: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
