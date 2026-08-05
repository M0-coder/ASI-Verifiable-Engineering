#!/usr/bin/env python3
"""Verify a change budget against the exact Git diff."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def git_text(root: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process.stdout


def load_budget(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Change budget version must equal 1.")
    expected = data.get("expected_paths")
    if not isinstance(expected, list) or not expected:
        raise ValueError("expected_paths must be a non-empty list.")
    forbidden = data.get("forbidden_paths", [])
    if not isinstance(forbidden, list):
        raise ValueError("forbidden_paths must be a list.")
    return data


def _matches(path: str, pattern: str) -> bool:
    normalized = pattern.replace("**", "*")
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, normalized)


def evaluate_budget(
    root: Path,
    budget: dict[str, Any],
    base_commit: str,
    evaluated_commit: str,
) -> dict[str, Any]:
    changed_files = sorted(
        line
        for line in git_text(
            root,
            "diff",
            "--name-only",
            base_commit,
            evaluated_commit,
        ).splitlines()
        if line
    )
    expected_files = sorted(set(str(path) for path in budget["expected_paths"]))
    forbidden_patterns = [str(value) for value in budget.get("forbidden_paths", [])]

    unexpected_files = sorted(set(changed_files) - set(expected_files))
    missing_expected_files = sorted(set(expected_files) - set(changed_files))
    forbidden_files = sorted(
        path
        for path in changed_files
        if any(_matches(path, pattern) for pattern in forbidden_patterns)
    )

    additions = 0
    deletions = 0
    binary_files: list[str] = []
    for line in git_text(
        root,
        "diff",
        "--numstat",
        base_commit,
        evaluated_commit,
    ).splitlines():
        if not line:
            continue
        added, removed, path = line.split("\t", 2)
        if added == "-" or removed == "-":
            binary_files.append(path)
            continue
        additions += int(added)
        deletions += int(removed)

    max_files = int(budget.get("max_files", len(expected_files)))
    max_changed_lines = int(
        budget.get("max_changed_lines", max(additions + deletions, 1))
    )
    allow_binary_files = bool(budget.get("allow_binary_files", False))

    violations: list[str] = []
    if unexpected_files:
        violations.append("unexpected_files")
    if forbidden_files:
        violations.append("forbidden_paths")
    if len(changed_files) > max_files:
        violations.append("max_files_exceeded")
    if additions + deletions > max_changed_lines:
        violations.append("max_changed_lines_exceeded")
    if binary_files and not allow_binary_files:
        violations.append("binary_files_forbidden")

    forensic_triggers: list[str] = []
    if forbidden_files:
        forensic_triggers.append("forbidden_path_change")
    if binary_files:
        forensic_triggers.append("binary_or_generated_change")
    if "max_changed_lines_exceeded" in violations:
        forensic_triggers.append("unbounded_change")

    return {
        "budget_version": 1,
        "base_commit": base_commit,
        "evaluated_commit": evaluated_commit,
        "changed_files": changed_files,
        "expected_files": expected_files,
        "missing_expected_files": missing_expected_files,
        "unexpected_files": unexpected_files,
        "forbidden_files": forbidden_files,
        "binary_files": sorted(binary_files),
        "additions": additions,
        "deletions": deletions,
        "changed_lines": additions + deletions,
        "max_files": max_files,
        "max_changed_lines": max_changed_lines,
        "allow_binary_files": allow_binary_files,
        "violations": violations,
        "forensic_triggers": forensic_triggers,
        "within_budget": not violations,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--budget", type=Path, required=True)
    result.add_argument("--base-commit", required=True)
    result.add_argument("--evaluated-commit", required=True)
    result.add_argument("--repo-root", type=Path, default=Path.cwd())
    result.add_argument("--report", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        budget = load_budget(args.budget)
        report = evaluate_budget(
            args.repo_root,
            budget,
            args.base_commit,
            args.evaluated_commit,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Cannot verify change budget: {exc}", file=sys.stderr)
        return 2

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if report["within_budget"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
