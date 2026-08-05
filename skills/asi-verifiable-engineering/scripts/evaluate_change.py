#!/usr/bin/env python3
"""Derive an ASI approval decision from policy and verified primary evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from validate_evidence import validate_manifest, verify_bindings

T_RANK = {f"T{i}": i for i in range(7)}
E_RANK = {f"E{i}": i for i in range(9)}
REQUIRED_E_FOR_T = {
    "T0": "E0",
    "T1": "E2",
    "T2": "E4",
    "T3": "E5",
    "T4": "E6",
    "T5": "E7",
    "T6": "E8",
}


def _section(text: str, name: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(name)}:\s*$\n(?P<body>(?:^[ \t].*(?:\n|$)|^\s*$)*)",
        flags=re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group("body") if match else ""


def _nested_block(section: str, name: str) -> str:
    pattern = re.compile(
        rf"^  {re.escape(name)}:\s*$\n(?P<body>(?:^    .*(?:\n|$)|^\s*$)*)",
        flags=re.MULTILINE,
    )
    match = pattern.search(section)
    return match.group("body") if match else ""


def _bool(section: str, key: str, default: bool = False) -> bool:
    match = re.search(
        rf"^  {re.escape(key)}:\s*(true|false)\s*$",
        section,
        re.MULTILINE,
    )
    return (match.group(1) == "true") if match else default


def _list(section: str, key: str) -> list[str]:
    match = re.search(
        rf"^  {re.escape(key)}:\s*$\n(?P<body>(?:^    - .*(?:\n|$))*)",
        section,
        re.MULTILINE,
    )
    if not match:
        return []
    return [
        item.strip().strip("\"'")
        for item in re.findall(
            r"^    - (.+?)\s*$",
            match.group("body"),
            re.MULTILINE,
        )
    ]


def parse_policy(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    gates_section = _section(text, "required_gates")
    required_gates = {
        name
        for name, state in re.findall(
            r"^  ([a-z][a-z0-9_]*):\s*(true|false)\s*$",
            gates_section,
            re.MULTILINE,
        )
        if state == "true"
    }

    acceptance = _section(text, "automated_acceptance")
    assurance_section = _section(text, "assurance")
    assurance: dict[str, dict[str, Any]] = {}
    for risk in ("low", "medium", "high", "critical"):
        block = _nested_block(assurance_section, risk)
        minimum_match = re.search(
            r"^    minimum_t:\s*(T[0-6])\s*$",
            block,
            re.MULTILINE,
        )
        independence = re.findall(
            r"^      - (I[0-3])\s*$",
            block,
            re.MULTILINE,
        )
        assurance[risk] = {
            "minimum_t": minimum_match.group(1) if minimum_match else None,
            "independence": independence,
        }

    return {
        "required_gates": required_gates,
        "assurance": assurance,
        "automated_acceptance": {
            "enabled": _bool(acceptance, "enabled"),
            "eligible_risks": _list(acceptance, "eligible_risks"),
            "line_by_line_review_default": _bool(
                acceptance,
                "line_by_line_review_default",
                default=True,
            ),
            "require_all_required_gates_passed": _bool(
                acceptance,
                "require_all_required_gates_passed",
            ),
            "require_no_unverified": _bool(
                acceptance,
                "require_no_unverified",
            ),
            "require_no_residual_risks_for_automatic": _bool(
                acceptance,
                "require_no_residual_risks_for_automatic",
            ),
            "require_test_honesty": _bool(
                acceptance,
                "require_test_honesty",
            ),
            "require_change_budget": _bool(
                acceptance,
                "require_change_budget",
            ),
            "require_distinct_builder_auditor": _bool(
                acceptance,
                "require_distinct_builder_auditor",
            ),
            "require_rollback_tested": _bool(
                acceptance,
                "require_rollback_tested",
            ),
            "require_policy_digest": _bool(
                acceptance,
                "require_policy_digest",
            ),
            "require_diff_digest": _bool(
                acceptance,
                "require_diff_digest",
            ),
        },
    }


def _binding_requires_forensics(error: str) -> bool:
    lowered = error.lower()
    markers = (
        "digest",
        "artifact",
        "does not match",
        "unsafe",
        "repository head",
        "git binding",
    )
    return any(marker in lowered for marker in markers)


def evaluate_change(
    policy: dict[str, Any],
    manifest: dict[str, Any],
    binding_errors: list[str] | None = None,
) -> dict[str, Any]:
    blockers = list(validate_manifest(manifest))
    binding_errors = list(binding_errors or [])
    blockers.extend(binding_errors)
    notes: list[str] = []
    risk = manifest.get("risk")
    gates = manifest.get("gates") if isinstance(manifest.get("gates"), dict) else {}
    required_gates = policy.get("required_gates", set())
    acceptance = policy.get("automated_acceptance", {})

    forensic_triggers = set(
        manifest.get("forensic_triggers", [])
        if isinstance(manifest.get("forensic_triggers"), list)
        else []
    )
    if any(_binding_requires_forensics(error) for error in binding_errors):
        forensic_triggers.add("evidence_integrity_conflict")

    if acceptance.get("line_by_line_review_default") is not False:
        blockers.append("Policy must explicitly set line_by_line_review_default=false.")

    if acceptance.get("require_all_required_gates_passed"):
        for gate in sorted(required_gates):
            state = gates.get(gate)
            if state != "passed":
                blockers.append(f"Required gate {gate} must be passed, got {state!r}.")

    commands = manifest.get("commands")
    if isinstance(commands, list):
        for command in commands:
            if isinstance(command, dict) and command.get("exit_code") != 0:
                blockers.append(
                    f"Command {command.get('name', '<unnamed>')} has non-zero exit code."
                )

    assurance = (
        policy.get("assurance", {}).get(risk, {})
        if isinstance(risk, str)
        else {}
    )
    minimum_t = assurance.get("minimum_t")
    actual_t = manifest.get("assurance_level")
    if minimum_t and actual_t in T_RANK and T_RANK[actual_t] < T_RANK[minimum_t]:
        blockers.append(f"{risk} risk requires at least {minimum_t}, got {actual_t}.")

    required_independence = set(assurance.get("independence", []))
    actual_independence = set(manifest.get("independence", []))
    missing_independence = sorted(required_independence - actual_independence)
    if missing_independence:
        blockers.append(
            "Missing required independence levels: " + ", ".join(missing_independence)
        )

    required_e = REQUIRED_E_FOR_T.get(str(actual_t))
    actual_e = manifest.get("evidence_level")
    if required_e and actual_e in E_RANK and E_RANK[actual_e] < E_RANK[required_e]:
        blockers.append(f"{actual_t} requires at least {required_e}, got {actual_e}.")

    if acceptance.get("require_no_unverified") and manifest.get("unverified"):
        blockers.append("Approval requires an empty unverified list.")

    residual_risks = manifest.get("residual_risks")
    if (
        acceptance.get("require_no_residual_risks_for_automatic")
        and residual_risks
        and risk in acceptance.get("eligible_risks", [])
    ):
        notes.append("Residual risks require explicit human risk acceptance.")

    budget = manifest.get("change_budget")
    if acceptance.get("require_change_budget"):
        if not isinstance(budget, dict) or budget.get("within_budget") is not True:
            blockers.append("Change budget must be present and satisfied.")
        elif budget.get("violations"):
            blockers.append("Change budget contains violations.")

    if acceptance.get("require_test_honesty"):
        honesty = manifest.get("test_honesty")
        if not isinstance(honesty, dict) or honesty.get("method") == "not_verified":
            blockers.append("Test-honesty evidence is required.")

    review = manifest.get("review")
    if acceptance.get("require_distinct_builder_auditor"):
        if not isinstance(review, dict):
            blockers.append("Independent review metadata is required.")
        else:
            if not review.get("auditor"):
                blockers.append("Independent auditor identity is required.")
            if review.get("builder") == review.get("auditor"):
                blockers.append("Builder and auditor must be distinct.")
            if review.get("same_context") is not False:
                blockers.append("Builder and auditor must use independent contexts.")

    rollback = manifest.get("rollback")
    if (
        acceptance.get("require_rollback_tested")
        and (not isinstance(rollback, dict) or rollback.get("tested") is not True)
    ):
        blockers.append("Rollback must be tested.")

    if manifest.get("integrable_commit") != manifest.get("evaluated_commit"):
        blockers.append("integrable_commit must equal evaluated_commit.")

    human_review = (
        review.get("human_review", {})
        if isinstance(review, dict)
        else {}
    )
    if risk in {"high", "critical"}:
        expected_mode = "targeted_dual" if risk == "critical" else "targeted"
        if human_review.get("completed") is not True:
            blockers.append(f"{risk} risk requires completed {expected_mode} human review.")
        if human_review.get("mode") != expected_mode:
            blockers.append(f"{risk} risk requires human review mode {expected_mode}.")

    claimed_decision = manifest.get("decision")
    if blockers:
        derived_decision = "BLOCKED"
    elif residual_risks or manifest.get("conditions"):
        derived_decision = "CONDITIONAL"
    elif claimed_decision == "REJECTED":
        derived_decision = "REJECTED"
    else:
        derived_decision = "APPROVED"

    if claimed_decision != derived_decision:
        blockers.append(
            f"Claimed decision {claimed_decision!r} does not match derived decision {derived_decision!r}."
        )
        derived_decision = "BLOCKED"

    automatic_eligible = (
        acceptance.get("enabled") is True
        and risk in acceptance.get("eligible_risks", [])
        and derived_decision == "APPROVED"
        and not blockers
        and not residual_risks
        and not forensic_triggers
    )

    line_by_line_required = bool(forensic_triggers)
    if line_by_line_required:
        human_action = "perform_forensic_review_and_rebuild_evidence"
        human_review_mode = "forensic"
    elif automatic_eligible:
        human_action = "none"
        human_review_mode = "none"
    elif risk == "critical":
        human_review_mode = "targeted_dual"
        human_action = (
            "targeted_dual_review_completed"
            if derived_decision == "APPROVED"
            else "complete_targeted_dual_review_and_resolve_blockers"
        )
    elif risk == "high":
        human_review_mode = "targeted"
        human_action = (
            "targeted_risk_review_completed"
            if derived_decision == "APPROVED"
            else "complete_targeted_review_and_resolve_blockers"
        )
    elif residual_risks or manifest.get("conditions"):
        human_action = "accept_or_reject_residual_risk"
        human_review_mode = "exception_only"
    else:
        human_action = "resolve_blockers"
        human_review_mode = "exception_only"

    return {
        "decision": derived_decision,
        "automatic_approval_eligible": automatic_eligible,
        "approval_basis": "policy_and_verified_primary_evidence",
        "line_by_line_review_required": line_by_line_required,
        "forensic_triggers": sorted(forensic_triggers),
        "human_review_mode": human_review_mode,
        "human_action": human_action,
        "risk": risk,
        "evaluated_commit": manifest.get("evaluated_commit"),
        "blockers": sorted(set(blockers)),
        "notes": notes,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("policy", type=Path)
    result.add_argument("evidence", type=Path)
    result.add_argument("--expect")
    result.add_argument("--evidence-dir", type=Path)
    result.add_argument("--repo-root", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        policy = parse_policy(args.policy)
        manifest = json.loads(args.evidence.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot load evaluation input: {exc}", file=sys.stderr)
        return 1

    binding_errors: list[str] = []
    if bool(args.evidence_dir) != bool(args.repo_root):
        print("--evidence-dir and --repo-root must be supplied together.", file=sys.stderr)
        return 2
    if args.evidence_dir and args.repo_root:
        binding_errors = verify_bindings(
            manifest,
            args.evidence_dir,
            args.policy,
            args.repo_root,
        )

    result = evaluate_change(policy, manifest, binding_errors)
    print(json.dumps(result, indent=2, sort_keys=True))

    if args.expect is not None:
        return 0 if result["decision"] == args.expect else 1
    return 0 if result["decision"] in {"APPROVED", "CONDITIONAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
