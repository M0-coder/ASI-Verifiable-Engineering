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
E_LEVEL = re.compile(r"^E[0-8]$")
T_LEVEL = re.compile(r"^T[0-6]$")
I_LEVEL = re.compile(r"^I[0-3]$")
ALLOWED_RISKS = {"low", "medium", "high", "critical"}
ALLOWED_DECISIONS = {"APPROVED", "CONDITIONAL", "BLOCKED", "REJECTED"}
ALLOWED_GATE_STATES = {"passed", "failed", "not_applicable", "not_verified"}

REQUIRED_FIELDS = {
    "manifest_version",
    "repository",
    "base_commit",
    "evaluated_commit",
    "policy_version",
    "doctrine_version",
    "skill_version",
    "risk",
    "evidence_level",
    "assurance_level",
    "independence",
    "commands",
    "gates",
    "artifacts",
    "unverified",
    "residual_risks",
    "decision",
    "rollback",
    "created_at",
    "expires_at",
}


def _parse_iso8601(value: Any, field: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{field} must be a non-empty ISO-8601 string.")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field} is not valid ISO-8601: {value!r}")
        return None


def validate_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Manifest root must be a JSON object."]

    missing = sorted(REQUIRED_FIELDS - data.keys())
    if missing:
        errors.append("Missing fields: " + ", ".join(missing))

    if data.get("manifest_version") != 1:
        errors.append("manifest_version must equal 1.")

    for field in ("base_commit", "evaluated_commit"):
        value = data.get(field)
        if not isinstance(value, str) or not SHA40.fullmatch(value):
            errors.append(f"{field} must be a 40-character lowercase Git SHA.")

    if data.get("risk") not in ALLOWED_RISKS:
        errors.append("risk must be low, medium, high, or critical.")
    if not isinstance(data.get("evidence_level"), str) or not E_LEVEL.fullmatch(data["evidence_level"]):
        errors.append("evidence_level must be E0 through E8.")
    if not isinstance(data.get("assurance_level"), str) or not T_LEVEL.fullmatch(data["assurance_level"]):
        errors.append("assurance_level must be T0 through T6.")

    independence = data.get("independence")
    if not isinstance(independence, list) or not independence:
        errors.append("independence must be a non-empty list.")
    else:
        for value in independence:
            if not isinstance(value, str) or not I_LEVEL.fullmatch(value):
                errors.append(f"Invalid independence level: {value!r}")

    commands = data.get("commands")
    if not isinstance(commands, list):
        errors.append("commands must be a list.")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                errors.append(f"commands[{index}] must be an object.")
                continue
            for field in ("name", "command", "exit_code"):
                if field not in command:
                    errors.append(f"commands[{index}].{field} is required.")
            if "exit_code" in command and not isinstance(command["exit_code"], int):
                errors.append(f"commands[{index}].exit_code must be an integer.")
            if "artifact_digest" in command:
                digest = command["artifact_digest"]
                if not isinstance(digest, str) or not digest.startswith("sha256:"):
                    errors.append(f"commands[{index}].artifact_digest must start with sha256:.")

    gates = data.get("gates")
    if not isinstance(gates, dict) or not gates:
        errors.append("gates must be a non-empty object.")
    else:
        for name, state in gates.items():
            if state not in ALLOWED_GATE_STATES:
                errors.append(f"gates.{name} has invalid state: {state!r}")

    for field in ("artifacts", "unverified", "residual_risks"):
        if field in data and not isinstance(data[field], list):
            errors.append(f"{field} must be a list.")

    decision = data.get("decision")
    if decision not in ALLOWED_DECISIONS:
        errors.append("decision must be APPROVED, CONDITIONAL, BLOCKED, or REJECTED.")

    if decision == "CONDITIONAL" and not data.get("conditions"):
        errors.append("CONDITIONAL requires a non-empty conditions list.")
    if decision == "APPROVED" and data.get("unverified"):
        errors.append("APPROVED cannot contain unverified items.")

    rollback = data.get("rollback")
    if not isinstance(rollback, dict) or "reference" not in rollback or "tested" not in rollback:
        errors.append("rollback must contain reference and tested.")
    elif not isinstance(rollback.get("tested"), bool):
        errors.append("rollback.tested must be boolean.")

    created = _parse_iso8601(data.get("created_at"), "created_at", errors)
    expires = _parse_iso8601(data.get("expires_at"), "expires_at", errors)
    if created and expires and expires <= created:
        errors.append("expires_at must be later than created_at.")

    risk = data.get("risk")
    levels = set(independence or []) if isinstance(independence, list) else set()
    if risk == "high" and "I3" not in levels:
        errors.append("High-risk evidence requires I3.")
    if risk == "critical":
        if "I3" not in levels:
            errors.append("Critical evidence requires I3.")
        if decision in {"APPROVED", "CONDITIONAL"} and len(data.get("approved_by", [])) < 2:
            errors.append("Critical approval requires at least two approvers.")

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
