#!/usr/bin/env python3
"""Scan dependency metadata and GitHub Actions references for unsafe supply-chain state."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*uses:\s*([^\s#]+)", re.MULTILINE)

DEPENDENCY_MANIFESTS = {
    "pyproject.toml": {"uv.lock", "poetry.lock", "Pipfile.lock"},
    "requirements.txt": {"requirements.lock", "requirements-ci.lock"},
    "package.json": {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"},
    "Cargo.toml": {"Cargo.lock"},
    "go.mod": {"go.sum"},
    "build.gradle": {"gradle.lockfile"},
    "build.gradle.kts": {"gradle.lockfile"},
}


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

    violations: list[str] = []
    if unpinned_actions:
        violations.append("unpinned_actions")
    if missing_lockfiles:
        violations.append("dependency_manifest_without_lockfile")

    return {
        "scan_version": 1,
        "workflow_files": [str(path.relative_to(root)) for path in workflow_files],
        "action_references": action_references,
        "unpinned_actions": unpinned_actions,
        "dependency_manifests": sorted(manifests),
        "missing_lockfiles": missing_lockfiles,
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
