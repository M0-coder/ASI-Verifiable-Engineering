#!/usr/bin/env python3
"""Validate an ASI machine-readable evidence manifest."""

from __future__ import annotations

import json
import re
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


def _parse_iso8601(
    value: Any,
    field: str,
    errors: list[str],
) -> datetime | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty ISO-8601 string.")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not valid ISO-8601: {value!r}")
        return None


def _require_sha256(
    value: Any,
    field: str,
    errors: list[str],
) -> None:
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        errors.append(
            f"{field} must be sha256 followed by 64 lowercase hex characters."
        )


def validate_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Manifest root must be a JSON object."]

    missing = sorted(REQUIRED_FIELDS - data.keys())
    if missing:
        errors.append("Missing fields: " + ", ".join(missing))

    if data.get("manifest_version") != 1:
        errors.append("manifest_version must equal 1.")

    for field in ("base_commit", "evaluated_commit", "integrable_commit"):
        value = data.get(field)
        if not isinstance(value, str) or not SHA40.fullmatch(value):
            errors.append(
                f"{field} must be a 40-character lowercase Git SHA."
            )

    if (
        isinstance(data.get("integrable_commit"), str)
        and isinstance(data.get("evaluated_commit"), str)
        and data.get("integrable_commit") != data.get("evaluated_commit")
    ):
        errors.append("integrable_commit must equal evaluated_commit.")
    if data.get("base_commit") == data.get("evaluated_commit"):
        errors.append("base_commit and evaluated_commit must differ.")

    _require_sha256(data.get("policy_digest"), "policy_digest", errors)
    _require_sha256(data.get("diff_digest"), "diff_digest", errors)

    if data.get("risk") not in ALLOWED_RISKS:
        errors.append("risk must be low, medium, high, or critical.")
    if not isinstance(data.get("evidence_level"), str) or not E_LEVEL.fullmatch(
        data.get("evidence_level", "")
    ):
        errors.append("evidence_level must be E0 through E8.")
    if not isinstance(data.get("assurance_level"), str) or not T_LEVEL.fullmatch(
        data.get("assurance_level", "")
    ):
        errors.append("assurance_level must be T0 through T6.")

    independence = data.get("independence")
    if not isinstance(independence, list) or not independence:
        errors.append("independence must be a non-empty list.")
    else:
        for value in independence:
            if not isinstance(value, str) or not I_LEVEL.fullmatch(value):
                errors.append(f"Invalid independence level: {value!r}")

    environment = data.get("environment")
    if not isinstance(environment, dict):
        errors.append("environment must be an object.")
    else:
        for field in (
            "os",
            "architecture",
            "runtime",
            "package_manager",
            "lockfile_digest",
        ):
            if not environment.get(field):
                errors.append(f"environment.{field} is required.")
        if environment.get("lockfile_digest"):
            _require_sha256(
                environment.get("lockfile_digest"),
                "environment.lockfile_digest",
                errors,
            )

    changed_files = data.get("changed_files")
    if not isinstance(changed_files, list) or not changed_files:
        errors.append("changed_files must be a non-empty list.")
    elif any(
        not isinstance(path, str) or not path
        for path in changed_files
    ):
        errors.append("changed_files entries must be non-empty strings.")

    budget = data.get("change_budget")
    if not isinstance(budget, dict):
        errors.append("change_budget must be an object.")
    else:
        for field in ("expected_files", "unexpected_files", "within_budget"):
            if field not in budget:
                errors.append(f"change_budget.{field} is required.")
        if not isinstance(budget.get("expected_files"), list):
            errors.append("change_budget.expected_files must be a list.")
        if not isinstance(budget.get("unexpected_files"), list):
            errors.append("change_budget.unexpected_files must be a list.")
        if not isinstance(budget.get("within_budget"), bool):
            errors.append("change_budget.within_budget must be boolean.")
        if data.get("decision") in {"APPROVED", "CONDITIONAL"}:
            if budget.get("within_budget") is not True:
                errors.append(
                    "Approval requires change_budget.within_budget=true."
                )
            if budget.get("unexpected_files"):
                errors.append("Approval cannot contain unexpected files.")

    commands = data.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("commands must be a non-empty list.")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                errors.append(f"commands[{index}] must be an object.")
                continue
            for field in (
                "name",
                "command",
                "started_at",
                "duration_seconds",
                "exit_code",
                "artifact",
                "artifact_digest",
            ):
                if field not in command:
                    errors.append(f"commands[{index}].{field} is required.")
            if "exit_code" in command and not isinstance(
                command["exit_code"],
                int,
            ):
                errors.append(
                    f"commands[{index}].exit_code must be an integer."
                )
            if (
                data.get("decision") in {"APPROVED", "CONDITIONAL"}
                and command.get("exit_code") != 0
            ):
                errors.append(
                    f"commands[{index}] must have exit_code 0 for approval."
                )
            if "duration_seconds" in command and not isinstance(
                command["duration_seconds"],
                (int, float),
            ):
                errors.append(
                    f"commands[{index}].duration_seconds must be numeric."
                )
            if command.get("artifact_digest"):
                _require_sha256(
                    command["artifact_digest"],
                    f"commands[{index}].artifact_digest",
                    errors,
                )
            if command.get("started_at"):
                _parse_iso8601(
                    command.get("started_at"),
                    f"commands[{index}].started_at",
                    errors,
                )

    gates = data.get("gates")
    if not isinstance(gates, dict) or not gates:
        errors.append("gates must be a non-empty object.")
    else:
        for name, state in gates.items():
            if state not in ALLOWED_GATE_STATES:
                errors.append(
                    f"gates.{name} has invalid state: {state!r}"
                )
            if (
                data.get("decision") in {"APPROVED", "CONDITIONAL"}
                and state in {"failed", "not_verified"}
            ):
                errors.append(
                    f"Approval cannot include gate {name}={state}."
                )

    gate_evidence = data.get("gate_evidence")
    if not isinstance(gate_evidence, dict):
        errors.append("gate_evidence must be an object.")
    elif isinstance(gates, dict):
        for name, state in gates.items():
            if state == "passed":
                item = gate_evidence.get(name)
                if not isinstance(item, dict):
                    errors.append(
                        f"gate_evidence.{name} is required for passed gates."
                    )
                    continue
                if not item.get("artifact"):
                    errors.append(
                        f"gate_evidence.{name}.artifact is required."
                    )
                _require_sha256(
                    item.get("digest"),
                    f"gate_evidence.{name}.digest",
                    errors,
                )
            elif state == "not_applicable":
                item = gate_evidence.get(name)
                if (
                    not isinstance(item, dict)
                    or not item.get("justification")
                ):
                    errors.append(
                        f"gate_evidence.{name}.justification is required "
                        "when not_applicable."
                    )

    honesty = data.get("test_honesty")
    if not isinstance(honesty, dict):
        errors.append("test_honesty must be an object.")
    else:
        if honesty.get("method") not in ALLOWED_HONESTY_METHODS:
            errors.append("test_honesty.method is invalid.")
        if not honesty.get("evidence"):
            errors.append("test_honesty.evidence is required.")
        if honesty.get("digest"):
            _require_sha256(
                honesty.get("digest"),
                "test_honesty.digest",
                errors,
            )
        else:
            errors.append("test_honesty.digest is required.")

    review = data.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object.")
    else:
        for field in ("builder", "auditor", "same_context", "human_review"):
            if field not in review:
                errors.append(f"review.{field} is required.")
        if review.get("builder") == review.get("auditor"):
            errors.append(
                "review.builder and review.auditor must be distinct."
            )
        if review.get("same_context") is not False:
            errors.append("review.same_context must be false.")
        human = review.get("human_review")
        if not isinstance(human, dict):
            errors.append("review.human_review must be an object.")
        else:
            for field in ("required", "completed", "mode"):
                if field not in human:
                    errors.append(
                        f"review.human_review.{field} is required."
                    )

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty list.")
    else:
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                errors.append(f"artifacts[{index}] must be an object.")
                continue
            for field in ("path", "digest", "producer"):
                if not artifact.get(field):
                    errors.append(
                        f"artifacts[{index}].{field} is required."
                    )
            if artifact.get("digest"):
                _require_sha256(
                    artifact.get("digest"),
                    f"artifacts[{index}].digest",
                    errors,
                )

    for field in ("unverified", "residual_risks", "approved_by"):
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be a list.")

    decision = data.get("decision")
    if decision not in ALLOWED_DECISIONS:
        errors.append(
            "decision must be APPROVED, CONDITIONAL, BLOCKED, or REJECTED."
        )
    if decision == "CONDITIONAL" and not data.get("conditions"):
        errors.append("CONDITIONAL requires a non-empty conditions list.")
    if decision == "APPROVED":
        if data.get("unverified"):
            errors.append("APPROVED cannot contain unverified items.")
        if data.get("residual_risks"):
            errors.append("APPROVED cannot contain residual risks.")
        if data.get("conditions"):
            errors.append("APPROVED cannot contain conditions.")

    rollback = data.get("rollback")
    if (
        not isinstance(rollback, dict)
        or "reference" not in rollback
        or "tested" not in rollback
    ):
        errors.append("rollback must contain reference and tested.")
    elif not isinstance(rollback.get("tested"), bool):
        errors.append("rollback.tested must be boolean.")
    elif (
        decision in {"APPROVED", "CONDITIONAL"}
        and rollback.get("tested") is not True
    ):
        errors.append("Approval requires rollback.tested=true.")

    created = _parse_iso8601(
        data.get("created_at"),
        "created_at",
        errors,
    )
    expires = _parse_iso8601(
        data.get("expires_at"),
        "expires_at",
        errors,
    )
    if created and expires and expires <= created:
        errors.append("expires_at must be later than created_at.")

    risk = data.get("risk")
    levels = (
        set(independence or [])
        if isinstance(independence, list)
        else set()
    )
    human = (
        review.get("human_review", {})
        if isinstance(review, dict)
        else {}
    )
    if risk == "high":
        if "I3" not in levels:
            errors.append("High-risk evidence requires I3.")
        if (
            human.get("completed") is not True
            or human.get("mode") != "targeted"
        ):
            errors.append(
                "High-risk approval requires completed targeted human review."
            )
    if risk == "critical":
        if "I3" not in levels:
            errors.append("Critical evidence requires I3.")
        if (
            human.get("completed") is not True
            or human.get("mode") != "targeted_dual"
        ):
            errors.append(
                "Critical approval requires completed targeted_dual human review."
            )
        if (
            decision in {"APPROVED", "CONDITIONAL"}
            and len(data.get("approved_by", [])) < 2
        ):
            errors.append(
                "Critical approval requires at least two approvers."
            )

    return errors


def load_manifest(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_evidence.py PATH", file=sys.stderr)
        return 2

    path = Path(argv[1])
    try:
        data = load_manifest(path)
    except FileNotFoundError:
        print(f"Evidence manifest not found: {path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {path}: {exc}", file=sys.stderr)
        return 1

    errors = validate_manifest(data)
    if errors:
        print(f"ASI evidence validation failed for {path}:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"ASI evidence manifest is valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
