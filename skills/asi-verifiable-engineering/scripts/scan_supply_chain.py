#!/usr/bin/env python3
"""Scan dependency metadata and Actions references for unsafe supply-chain state."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[^\s;]+(?:\s*;\s*.+)?$"
)

DEPENDENCY_MANIFESTS = {
    "pyproject.toml": {"uv.lock", "poetry.lock", "Pipfile.lock"},
    "requirements.txt": {"requirements.lock", "requirements-ci.lock"},
    "package.json": {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"},
    "Cargo.toml": {"Cargo.lock"},
    "go.mod": {"go.sum"},
    "build.gradle": {"gradle.lockfile"},
    "build.gradle.kts": {"gradle.lockfile"},
}


def _scan_requirements_lock(path: Path) -> list[dict[str, object]]:
    violations: list[dict[str, object]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-", "http://", "https://", "git+")):
            violations.append(
                {
                    "path": path.name,
                    "line": line_number,
                    "reason": "non_registry_or_option_requirement",
                }
            )
        elif not EXACT_REQUIREMENT.fullmatch(line):
            violations.append(
                {
                    "path": path.name,
                    "line": line_number,
                    "reason": "requirement_not_exactly_pinned",
                }
            )
    return violations


def scan(root: Path) -> dict[str, object]:
    workflow_files = sorted(
        path
        for path in (root / ".github" / "workflows").glob("*.y*ml")
        if path.is_file()
    )
    action_references: list[dict[str, object]] = []
    unpinned_actions: list[dict[str, str]] = []

    for path in workflow_files:
        text = path.read_text(encoding="utf-8")
        for reference in USES.findall(text):
            local = reference.startswith("./")
            docker_digest = reference.startswith("docker://") and "@sha256:" in reference
            pinned = local or docker_digest
            if not pinned and "@" in reference:
                _, ref = reference.rsplit("@", 1)
                pinned = bool(ACTION_SHA.fullmatch(ref))
            item = {
                "workflow": str(path.relative_to(root)),
                "reference": reference,
                "pinned": pinned,
            }
            action_references.append(item)
            if not pinned:
                unpinned_actions.append(
                    {
                        "workflow": str(path.relative_to(root)),
                        "reference": reference,
                    }
                )

    manifests: list[str] = []
    missing_lockfiles: list[dict[str, object]] = []
    for manifest_name, accepted_locks in DEPENDENCY_MANIFESTS.items():
        manifest = root / manifest_name
        if not manifest.is_file():
            continue
        manifests.append(manifest_name)
        present = sorted(name for name in accepted_locks if (root / name).is_file())
        if not present:
            missing_lockfiles.append(
                {
                    "manifest": manifest_name,
                    "accepted_lockfiles": sorted(accepted_locks),
                }
            )

    lock_file = root / "requirements-ci.lock"
    lock_violations = (
        _scan_requirements_lock(lock_file)
        if lock_file.is_file()
        else [
            {
                "path": "requirements-ci.lock",
                "line": 0,
                "reason": "required_ci_lock_missing",
            }
        ]
    )

    violations: list[str] = []
    if unpinned_actions:
        violations.append("unpinned_actions")
    if missing_lockfiles:
        violations.append("dependency_manifest_without_lockfile")
    if lock_violations:
        violations.append("invalid_ci_dependency_lock")

    return {
        "scan_version": 2,
        "workflow_files": [str(path.relative_to(root)) for path in workflow_files],
        "action_references": action_references,
        "unpinned_actions": unpinned_actions,
        "dependency_manifests": sorted(manifests),
        "missing_lockfiles": missing_lockfiles,
        "ci_lock": str(lock_file.relative_to(root)) if lock_file.is_file() else None,
        "ci_lock_violations": lock_violations,
        "violations": violations,
        "passed": not violations,
    }


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd()
    try:
        report = scan(root.resolve())
    except OSError as exc:
        print(f"Supply-chain scan failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
