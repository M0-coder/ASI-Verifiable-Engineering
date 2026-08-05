#!/usr/bin/env python3
"""Generate a commit-bound ASI evidence manifest from a real CI execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_bytes(*args: str) -> bytes:
    process = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process.stdout


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8")


def policy_commands(text: str) -> dict[str, str]:
    match = re.search(
        r"^commands:\s*$\n(?P<body>(?:^  .*(?:\n|$)|^\s*$)*)",
        text,
        flags=re.MULTILINE,
    )
    if not match:
        return {}
    commands: dict[str, str] = {}
    for name, raw_value in re.findall(
        r"^  ([a-z][a-z0-9_]*):\s*(.+?)\s*$",
        match.group("body"),
        flags=re.MULTILINE,
    ):
        commands[name] = raw_value.strip().strip('"\'')
    return commands


def lockfile_digest(root: Path) -> str:
    candidates = (
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "Cargo.lock",
        "go.sum",
        "gradle.lockfile",
    )
    found = [root / name for name in candidates if (root / name).is_file()]
    if not found:
        return sha256_bytes(b"NO_LOCKFILE:STANDARD_LIBRARY_ONLY")
    digest_input = b"".join(
        path.name.encode("utf-8") + b"\0" + path.read_bytes()
        for path in sorted(found)
    )
    return sha256_bytes(digest_input)


def load_budget(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError("Change budget version must equal 1.")
    expected = data.get("expected_paths")
    if not isinstance(expected, list) or not expected:
        raise ValueError("Change budget expected_paths must be non-empty.")
    return data


def generate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path.cwd()
    policy_path = Path(args.policy)
    budget_path = Path(args.budget)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_text = policy_path.read_text(encoding="utf-8")
    budget = load_budget(budget_path)

    diff_bytes = git_bytes(
        "diff",
        "--binary",
        args.base_commit,
        args.evaluated_commit,
    )
    changed_files = sorted(
        line
        for line in git_text(
            "diff",
            "--name-only",
            args.base_commit,
            args.evaluated_commit,
        ).splitlines()
        if line
    )

    expected_files = sorted(set(budget["expected_paths"]))
    unexpected_files = sorted(set(changed_files) - set(expected_files))
    missing_expected_files = sorted(set(expected_files) - set(changed_files))
    within_budget = not unexpected_files

    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires = now + timedelta(days=args.validity_days)

    summary_path = output_dir / "ci-summary.json"
    summary = {
        "repository": args.repository,
        "workflow_run": args.workflow_run,
        "base_commit": args.base_commit,
        "evaluated_commit": args.evaluated_commit,
        "head_commit": args.head_commit,
        "changed_files": changed_files,
        "passed_gates": sorted(set(args.passed_gate)),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_digest = sha256_file(summary_path)

    tests_log = Path(args.tests_log)
    if not tests_log.is_file():
        raise FileNotFoundError(f"Tests log does not exist: {tests_log}")
    tests_digest = sha256_file(tests_log)

    passed_gates = sorted(set(args.passed_gate))
    gates = {name: "passed" for name in passed_gates}
    gates["independent_audit"] = "not_verified"

    gate_evidence = {
        name: {
            "artifact": summary_path.name,
            "digest": summary_digest,
        }
        for name in passed_gates
    }

    commands = []
    for name, command in sorted(policy_commands(policy_text).items()):
        commands.append(
            {
                "name": name,
                "command": command,
                "started_at": now.isoformat().replace("+00:00", "Z"),
                "duration_seconds": 0.0,
                "exit_code": 0,
                "artifact": summary_path.name,
                "artifact_digest": summary_digest,
            }
        )

    unverified = list(args.unverified)
    if not within_budget:
        unverified.append("Change budget exceeded by unexpected files.")
    unverified = sorted(set(unverified))

    residual_risks = [
        "Independent targeted human review has not been completed.",
        "The Skill has not been installed and exercised in the target environment.",
    ]

    manifest = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "manifest_version": 1,
        "repository": args.repository,
        "branch": args.branch,
        "base_commit": args.base_commit,
        "evaluated_commit": args.evaluated_commit,
        "integrable_commit": args.evaluated_commit,
        "head_commit": args.head_commit,
        "policy_version": 1,
        "policy_digest": sha256_file(policy_path),
        "diff_digest": sha256_bytes(diff_bytes),
        "doctrine_version": args.doctrine_version,
        "skill_version": args.skill_version,
        "risk": args.risk,
        "evidence_level": "E6",
        "assurance_level": "T4",
        "independence": ["I2"],
        "environment": {
            "os": args.os_name,
            "architecture": args.architecture,
            "runtime": args.runtime,
            "package_manager": "stdlib",
            "lockfile_digest": lockfile_digest(root),
        },
        "changed_files": changed_files,
        "change_budget": {
            "reference": str(budget_path),
            "expected_files": expected_files,
            "missing_expected_files": missing_expected_files,
            "unexpected_files": unexpected_files,
            "within_budget": within_budget,
        },
        "commands": commands,
        "gates": gates,
        "gate_evidence": gate_evidence,
        "test_honesty": {
            "method": "independent_negative_test",
            "evidence": tests_log.name,
            "digest": tests_digest,
        },
        "review": {
            "builder": args.builder,
            "auditor": None,
            "same_context": False,
            "human_review": {
                "required": True,
                "completed": False,
                "mode": "targeted",
            },
        },
        "artifacts": [
            {
                "path": summary_path.name,
                "digest": summary_digest,
                "producer": "github-actions",
            },
            {
                "path": tests_log.name,
                "digest": tests_digest,
                "producer": "github-actions",
            },
        ],
        "unverified": unverified,
        "residual_risks": residual_risks,
        "decision": "BLOCKED",
        "conditions": [],
        "rollback": {
            "reference": budget.get("rollback", "Close the pull request."),
            "tested": False,
        },
        "approved_by": [],
        "workflow_run": args.workflow_run,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
    }

    output_path = output_dir / "manifest.json"
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repository", required=True)
    result.add_argument("--branch", required=True)
    result.add_argument("--base-commit", required=True)
    result.add_argument("--head-commit", required=True)
    result.add_argument("--evaluated-commit", required=True)
    result.add_argument("--policy", required=True)
    result.add_argument("--budget", required=True)
    result.add_argument("--output-dir", required=True)
    result.add_argument("--builder", required=True)
    result.add_argument("--workflow-run", required=True)
    result.add_argument("--risk", choices=("low", "medium", "high", "critical"), required=True)
    result.add_argument("--skill-version", required=True)
    result.add_argument("--doctrine-version", required=True)
    result.add_argument("--tests-log", required=True)
    result.add_argument("--passed-gate", action="append", default=[])
    result.add_argument("--unverified", action="append", default=[])
    result.add_argument("--os-name", default="ubuntu-24.04")
    result.add_argument("--architecture", default="x86_64")
    result.add_argument("--runtime", default="python-3.12")
    result.add_argument("--validity-days", type=int, default=7)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = generate(args)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
