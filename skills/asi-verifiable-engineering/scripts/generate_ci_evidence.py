#!/usr/bin/env python3
"""Generate a commit-bound ASI evidence manifest from measured gate results."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from verify_change_budget import evaluate_budget, load_budget

SHA256_PREFIX = "sha256:"


def sha256_bytes(data: bytes) -> str:
    return SHA256_PREFIX + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_bytes(root: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process.stdout


def required_gates(policy_text: str) -> set[str]:
    match = re.search(
        r"^required_gates:\s*$\n(?P<body>(?:^  .*(?:\n|$)|^\s*$)*)",
        policy_text,
        flags=re.MULTILINE,
    )
    if not match:
        raise ValueError("Policy does not contain required_gates.")
    return {
        name
        for name, state in re.findall(
            r"^  ([a-z][a-z0-9_]*):\s*(true|false)\s*$",
            match.group("body"),
            flags=re.MULTILINE,
        )
        if state == "true"
    }


def lockfile_digest(root: Path) -> str:
    candidates = (
        "requirements-ci.lock",
        "requirements.lock",
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
    payload = b"".join(
        path.name.encode("utf-8") + b"\0" + path.read_bytes()
        for path in sorted(found)
    )
    return sha256_bytes(payload)


def _safe_relative(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def load_gate_results(output_dir: Path) -> dict[str, dict[str, Any]]:
    gates_dir = output_dir / "gates"
    if not gates_dir.is_dir():
        raise FileNotFoundError(f"Gate result directory does not exist: {gates_dir}")

    results: dict[str, dict[str, Any]] = {}
    for result_path in sorted(gates_dir.glob("*.json")):
        data = json.loads(result_path.read_text(encoding="utf-8"))
        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Gate result has no valid name: {result_path}")
        if name in results:
            raise ValueError(f"Duplicate gate result: {name}")
        if data.get("result_version") != 1:
            raise ValueError(f"Unsupported gate result version for {name}")
        if not isinstance(data.get("exit_code"), int):
            raise ValueError(f"Gate {name} has no integer exit_code")
        if not isinstance(data.get("argv"), list) or not data["argv"]:
            raise ValueError(f"Gate {name} has no measured argv")

        log_artifact = data.get("log_artifact")
        if not isinstance(log_artifact, str) or not log_artifact:
            raise ValueError(f"Gate {name} has no log_artifact")
        log_path = output_dir / log_artifact
        if not log_path.is_file():
            raise FileNotFoundError(f"Gate log does not exist: {log_path}")
        measured_log_digest = sha256_file(log_path)
        if data.get("log_digest") != measured_log_digest:
            raise ValueError(f"Gate {name} log digest does not match its file")

        result_artifact = _safe_relative(result_path, output_dir)
        data["result_artifact"] = result_artifact
        data["result_digest"] = sha256_file(result_path)
        results[name] = data
    return results


def result_artifacts(
    results: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    artifacts: dict[str, dict[str, str]] = {}
    for result in results.values():
        result_path = str(result["result_artifact"])
        log_path = str(result["log_artifact"])
        artifacts[result_path] = {
            "path": result_path,
            "digest": str(result["result_digest"]),
            "producer": "github-actions/run_gate.py",
        }
        artifacts[log_path] = {
            "path": log_path,
            "digest": str(result["log_digest"]),
            "producer": "github-actions/run_gate.py",
        }
    return [artifacts[path] for path in sorted(artifacts)]


def generate(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve()
    policy_path = (root / args.policy).resolve()
    budget_path = (root / args.budget).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    policy_text = policy_path.read_text(encoding="utf-8")
    budget = load_budget(budget_path)
    budget_report = evaluate_budget(
        root,
        budget,
        args.base_commit,
        args.evaluated_commit,
    )
    budget_report_path = output_dir / "change-budget-report.json"
    budget_report_path.write_text(
        json.dumps(budget_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    diff_bytes = git_bytes(
        root,
        "diff",
        "--binary",
        args.base_commit,
        args.evaluated_commit,
    )
    results = load_gate_results(output_dir)
    required = required_gates(policy_text)

    gates: dict[str, str] = {}
    gate_evidence: dict[str, dict[str, Any]] = {}
    for name in sorted(required):
        if name == "independent_audit":
            gates[name] = "not_verified"
            gate_evidence[name] = {
                "justification": "Independent targeted review has not been completed."
            }
            continue
        result = results.get(name)
        if result is None:
            gates[name] = "not_verified"
            gate_evidence[name] = {
                "justification": f"No measured result exists for required gate {name}."
            }
            continue
        gates[name] = "passed" if result["exit_code"] == 0 else "failed"
        gate_evidence[name] = {
            "result_artifact": result["result_artifact"],
            "result_digest": result["result_digest"],
            "log_artifact": result["log_artifact"],
            "log_digest": result["log_digest"],
        }

    commands: list[dict[str, Any]] = []
    for name, result in sorted(results.items()):
        commands.append(
            {
                "name": name,
                "argv": result["argv"],
                "command": result["command"],
                "started_at": result["started_at"],
                "finished_at": result["finished_at"],
                "duration_seconds": result["duration_seconds"],
                "exit_code": result["exit_code"],
                "result_artifact": result["result_artifact"],
                "result_digest": result["result_digest"],
                "log_artifact": result["log_artifact"],
                "log_digest": result["log_digest"],
            }
        )

    honesty_result = results.get(args.test_honesty_gate)
    if honesty_result is None:
        test_honesty = {
            "method": "not_verified",
            "result_artifact": None,
            "result_digest": None,
            "evidence": None,
            "digest": None,
        }
    else:
        test_honesty = {
            "method": "adversarial_control_tests",
            "result_artifact": honesty_result["result_artifact"],
            "result_digest": honesty_result["result_digest"],
            "evidence": honesty_result["log_artifact"],
            "digest": honesty_result["log_digest"],
        }

    automated_required = required - {"independent_audit"}
    all_automated_passed = all(gates.get(name) == "passed" for name in automated_required)
    evidence_level = "E6" if all_automated_passed else "E5"
    assurance_level = "T4" if all_automated_passed else "T3"

    unverified = set(args.unverified)
    for name, state in gates.items():
        if state == "not_verified":
            unverified.add(f"Required gate {name} is not verified.")
    if not budget_report["within_budget"]:
        unverified.add("Change budget is not satisfied.")
    if honesty_result is None or honesty_result["exit_code"] != 0:
        unverified.add("Test-honesty control is not verified.")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires = now + timedelta(days=args.validity_days)

    summary_path = output_dir / "ci-summary.json"
    summary = {
        "repository": args.repository,
        "workflow_run": args.workflow_run,
        "base_commit": args.base_commit,
        "head_commit": args.head_commit,
        "evaluated_commit": args.evaluated_commit,
        "gates": gates,
        "changed_files": budget_report["changed_files"],
        "generated_at": now.isoformat().replace("+00:00", "Z"),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    artifacts = result_artifacts(results)
    artifacts.extend(
        [
            {
                "path": "change-budget-report.json",
                "digest": sha256_file(budget_report_path),
                "producer": "generate_ci_evidence.py",
            },
            {
                "path": "ci-summary.json",
                "digest": sha256_file(summary_path),
                "producer": "generate_ci_evidence.py",
            },
        ]
    )

    manifest: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "manifest_version": 2,
        "repository": args.repository,
        "branch": args.branch,
        "base_commit": args.base_commit,
        "head_commit": args.head_commit,
        "evaluated_commit": args.evaluated_commit,
        "integrable_commit": args.evaluated_commit,
        "policy_version": 1,
        "policy_digest": sha256_file(policy_path),
        "diff_digest": sha256_bytes(diff_bytes),
        "doctrine_version": args.doctrine_version,
        "skill_version": args.skill_version,
        "risk": args.risk,
        "evidence_level": evidence_level,
        "assurance_level": assurance_level,
        "independence": ["I2"],
        "environment": {
            "os": args.os_name,
            "architecture": args.architecture,
            "runtime": args.runtime,
            "package_manager": "stdlib",
            "lockfile_digest": lockfile_digest(root),
        },
        "changed_files": budget_report["changed_files"],
        "change_budget": {
            "reference": str(budget_path.relative_to(root)),
            **budget_report,
        },
        "commands": commands,
        "gates": gates,
        "gate_evidence": gate_evidence,
        "test_honesty": test_honesty,
        "forensic_triggers": budget_report["forensic_triggers"],
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
        "artifacts": artifacts,
        "unverified": sorted(unverified),
        "residual_risks": [
            "Independent targeted human review has not been completed.",
            "The Skill has not been installed and exercised in the target environment.",
        ],
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

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
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
    result.add_argument("--repo-root", default=".")
    result.add_argument("--builder", required=True)
    result.add_argument("--workflow-run", required=True)
    result.add_argument(
        "--risk",
        choices=("low", "medium", "high", "critical"),
        required=True,
    )
    result.add_argument("--skill-version", required=True)
    result.add_argument("--doctrine-version", required=True)
    result.add_argument("--test-honesty-gate", default="test_honesty")
    result.add_argument("--unverified", action="append", default=[])
    result.add_argument("--os-name", default="ubuntu-24.04")
    result.add_argument("--architecture", default="x86_64")
    result.add_argument("--runtime", default="python-3.12")
    result.add_argument("--validity-days", type=int, default=7)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        manifest = generate(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"Cannot generate CI evidence: {exc}") from exc
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
