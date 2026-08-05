#!/usr/bin/env python3
"""Validate the minimum ASI policy contract without third-party dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = {
    "doctrine",
    "repository",
    "commands",
    "required_gates",
    "risk_escalation",
    "assurance",
    "automated_acceptance",
    "evidence",
    "deployment",
    "agent_permissions",
    "exceptions",
}

REQUIRED_COMMANDS = {
    "install",
    "format_check",
    "lint",
    "typecheck",
    "build",
    "unit_tests",
    "integration_tests",
    "security_scan",
}

REQUIRED_GATES = {
    "format_check",
    "lint",
    "typecheck",
    "build",
    "unit_tests",
    "integration_tests",
    "secret_scan",
    "dependency_scan",
    "independent_audit",
}

FALSE_AGENT_PERMISSIONS = {
    "direct_push_protected_branch",
    "self_approve",
    "modify_policy_in_same_change",
    "disable_required_gate",
    "access_production_secrets",
    "irreversible_action_without_human",
}

TRUE_AUTOMATED_ACCEPTANCE_RULES = {
    "enabled",
    "require_all_required_gates_passed",
    "require_no_unverified",
    "require_no_residual_risks_for_automatic",
    "require_test_honesty",
    "require_change_budget",
    "require_distinct_builder_auditor",
    "require_rollback_tested",
    "require_policy_digest",
    "require_diff_digest",
}

PLACEHOLDERS = (
    "REPLACE_WITH_",
    "<comando",
    "<command",
    "<owner",
    "<sha",
    "TODO_POLICY",
)


def _top_level_sections(text: str) -> set[str]:
    return set(
        re.findall(
            r"^([a-z][a-z0-9_]*):\s*$",
            text,
            flags=re.MULTILINE,
        )
    )


def _section(text: str, name: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(name)}:\s*$\n"
        rf"(?P<body>(?:^[ \t].*(?:\n|$)|^\s*$)*)",
        flags=re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group("body") if match else ""


def _mapping_keys(section: str) -> set[str]:
    return set(
        re.findall(
            r"^  ([a-z][a-z0-9_]*):",
            section,
            flags=re.MULTILINE,
        )
    )


def validate_policy(path: Path) -> list[str]:
    errors: list[str] = []

    if not path.is_file():
        return [f"Policy file does not exist: {path}"]

    text = path.read_text(encoding="utf-8")

    if not re.search(r"^version:\s*1\s*$", text, flags=re.MULTILINE):
        errors.append("`version: 1` is required.")

    for marker in PLACEHOLDERS:
        if marker.lower() in text.lower():
            errors.append(f"Unresolved placeholder detected: {marker}")

    missing_sections = sorted(
        REQUIRED_SECTIONS - _top_level_sections(text)
    )
    if missing_sections:
        errors.append(
            "Missing top-level sections: " + ", ".join(missing_sections)
        )

    repository = _section(text, "repository")
    risk_match = re.search(
        r"^  default_risk:\s*(low|medium|high|critical)\s*$",
        repository,
        flags=re.MULTILINE,
    )
    if not risk_match:
        errors.append(
            "repository.default_risk must be low, medium, high, or critical."
        )
    if not re.search(
        r"^  policy_owner:\s*[^\s].+$",
        repository,
        flags=re.MULTILINE,
    ):
        errors.append("repository.policy_owner is required.")
    if "- main" not in repository:
        errors.append(
            "main must be listed under repository.protected_branches."
        )

    commands = _section(text, "commands")
    missing_commands = sorted(REQUIRED_COMMANDS - _mapping_keys(commands))
    if missing_commands:
        errors.append("Missing commands: " + ", ".join(missing_commands))
    for key in REQUIRED_COMMANDS:
        match = re.search(
            rf"^  {key}:\s*[\"']?(.+?)[\"']?\s*$",
            commands,
            re.MULTILINE,
        )
        if match and not match.group(1).strip():
            errors.append(f"commands.{key} cannot be empty.")

    gates = _section(text, "required_gates")
    missing_gates = sorted(REQUIRED_GATES - _mapping_keys(gates))
    if missing_gates:
        errors.append(
            "Missing required gates: " + ", ".join(missing_gates)
        )
    for gate in REQUIRED_GATES:
        if not re.search(
            rf"^  {gate}:\s*true\s*$",
            gates,
            re.MULTILINE,
        ):
            errors.append(
                f"required_gates.{gate} must be true in the strict profile."
            )

    agent_permissions = _section(text, "agent_permissions")
    for permission in sorted(FALSE_AGENT_PERMISSIONS):
        if not re.search(
            rf"^  {permission}:\s*false\s*$",
            agent_permissions,
            re.MULTILINE,
        ):
            errors.append(
                f"agent_permissions.{permission} must be false."
            )

    exceptions = _section(text, "exceptions")
    if not re.search(
        r"^  allow_permanent:\s*false\s*$",
        exceptions,
        re.MULTILINE,
    ):
        errors.append("exceptions.allow_permanent must be false.")
    for key in (
        "require_owner",
        "require_expiry",
        "require_compensating_controls",
    ):
        if not re.search(
            rf"^  {key}:\s*true\s*$",
            exceptions,
            re.MULTILINE,
        ):
            errors.append(f"exceptions.{key} must be true.")

    assurance = _section(text, "assurance")
    expected_t = {
        "low": "T4",
        "medium": "T4",
        "high": "T5",
        "critical": "T6",
    }
    expected_i = {
        "low": {"I1", "I2"},
        "medium": {"I1", "I2"},
        "high": {"I2", "I3"},
        "critical": {"I2", "I3"},
    }
    for level, expected in expected_t.items():
        block_match = re.search(
            rf"^  {level}:\s*$\n(?P<body>(?:^    .*\n?)*)",
            assurance,
            flags=re.MULTILINE,
        )
        if not block_match:
            errors.append(f"assurance.{level} is required.")
            continue
        body = block_match.group("body")
        if not re.search(
            rf"^    minimum_t:\s*{expected}\s*$",
            body,
            flags=re.MULTILINE,
        ):
            errors.append(
                f"assurance.{level}.minimum_t must be {expected}."
            )
        actual_i = set(
            re.findall(
                r"^      - (I[0-3])\s*$",
                body,
                flags=re.MULTILINE,
            )
        )
        missing_i = sorted(expected_i[level] - actual_i)
        if missing_i:
            errors.append(
                f"assurance.{level}.independence is missing: "
                + ", ".join(missing_i)
            )

    automated = _section(text, "automated_acceptance")
    for key in sorted(TRUE_AUTOMATED_ACCEPTANCE_RULES):
        if not re.search(
            rf"^  {key}:\s*true\s*$",
            automated,
            re.MULTILINE,
        ):
            errors.append(f"automated_acceptance.{key} must be true.")
    if not re.search(
        r"^  line_by_line_review_default:\s*false\s*$",
        automated,
        re.MULTILINE,
    ):
        errors.append(
            "automated_acceptance.line_by_line_review_default must be false."
        )
    eligible_match = re.search(
        r"^  eligible_risks:\s*$\n"
        r"(?P<body>(?:^    - (?:low|medium|high|critical)\s*$\n?)*)",
        automated,
        flags=re.MULTILINE,
    )
    if not eligible_match:
        errors.append("automated_acceptance.eligible_risks is required.")
    else:
        eligible = set(
            re.findall(
                r"^    - (low|medium|high|critical)\s*$",
                eligible_match.group("body"),
                flags=re.MULTILINE,
            )
        )
        if eligible != {"low", "medium"}:
            errors.append(
                "automated_acceptance.eligible_risks must be exactly low and medium."
            )

    evidence = _section(text, "evidence")
    for key in (
        "require_commit_sha",
        "require_exit_codes",
        "require_artifact_digests",
    ):
        if not re.search(
            rf"^  {key}:\s*true\s*$",
            evidence,
            re.MULTILINE,
        ):
            errors.append(f"evidence.{key} must be true.")

    deployment = _section(text, "deployment")
    if not re.search(
        r"^  build_once_promote_same_artifact:\s*true\s*$",
        deployment,
        re.MULTILINE,
    ):
        errors.append(
            "deployment.build_once_promote_same_artifact must be true."
        )
    if not re.search(
        r"^  require_rollback:\s*true\s*$",
        deployment,
        re.MULTILINE,
    ):
        errors.append("deployment.require_rollback must be true.")
    if not re.search(
        r"^  autonomous_production_changes:\s*false\s*$",
        deployment,
        re.MULTILINE,
    ):
        errors.append(
            "deployment.autonomous_production_changes must be false."
        )

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: validate_policy.py PATH", file=sys.stderr)
        return 2

    path = Path(argv[1])
    errors = validate_policy(path)
    if errors:
        print(f"ASI policy validation failed for {path}:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"ASI policy is valid: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
