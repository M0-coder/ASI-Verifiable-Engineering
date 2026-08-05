#!/usr/bin/env python3
"""Rehearse reversal of the evaluated source diff in an isolated Git worktree."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def git(
    root: Path,
    *args: str,
    input_bytes: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _commit(explicit: str | None, environment_name: str) -> str:
    value = explicit or os.environ.get(environment_name)
    if not value or not SHA40.fullmatch(value):
        raise ValueError(
            f"A valid 40-character commit is required through {environment_name}."
        )
    return value


def verify_rollback(
    root: Path,
    base_commit: str,
    evaluated_commit: str,
) -> dict[str, object]:
    root = root.resolve()
    head = git(root, "rev-parse", "HEAD").stdout.decode("utf-8").strip()
    if head != evaluated_commit:
        raise ValueError("Repository HEAD must equal the evaluated commit.")

    patch = git(
        root,
        "diff",
        "--binary",
        base_commit,
        evaluated_commit,
    ).stdout
    if not patch:
        raise ValueError("The evaluated diff is empty; rollback rehearsal is undefined.")

    changed_files = [
        line
        for line in git(
            root,
            "diff",
            "--name-only",
            base_commit,
            evaluated_commit,
        ).stdout.decode("utf-8").splitlines()
        if line
    ]

    with tempfile.TemporaryDirectory(prefix="asi-rollback-") as temp:
        worktree = Path(temp) / "worktree"
        added = False
        try:
            git(
                root,
                "worktree",
                "add",
                "--detach",
                "--force",
                str(worktree),
                evaluated_commit,
            )
            added = True
            apply_result = git(
                worktree,
                "apply",
                "--reverse",
                "--index",
                "--binary",
                "-",
                input_bytes=patch,
                check=False,
            )
            if apply_result.returncode != 0:
                return {
                    "verification_version": 1,
                    "scope": "source_tree",
                    "base_commit": base_commit,
                    "evaluated_commit": evaluated_commit,
                    "changed_files": sorted(changed_files),
                    "reverse_apply_exit_code": apply_result.returncode,
                    "restored_base_tree": False,
                    "passed": False,
                    "error": apply_result.stderr.decode("utf-8", errors="replace"),
                }

            comparison = git(
                worktree,
                "diff",
                "--quiet",
                base_commit,
                "--",
                check=False,
            )
            untracked = git(
                worktree,
                "ls-files",
                "--others",
                "--exclude-standard",
            ).stdout.decode("utf-8").splitlines()
            passed = comparison.returncode == 0 and not untracked
            return {
                "verification_version": 1,
                "scope": "source_tree",
                "base_commit": base_commit,
                "evaluated_commit": evaluated_commit,
                "changed_files": sorted(changed_files),
                "reverse_apply_exit_code": apply_result.returncode,
                "base_comparison_exit_code": comparison.returncode,
                "untracked_files": sorted(item for item in untracked if item),
                "restored_base_tree": passed,
                "limitations": [
                    "This verifies source-tree reversibility only.",
                    "It does not prove production, database, secret, or external-service rollback.",
                ],
                "passed": passed,
            }
        finally:
            if added:
                git(
                    root,
                    "worktree",
                    "remove",
                    "--force",
                    str(worktree),
                    check=False,
                )
                git(root, "worktree", "prune", check=False)


def main() -> int:
    root = Path.cwd()
    try:
        base = _commit(None, "ASI_BASE_SHA")
        evaluated = _commit(None, "ASI_EVALUATED_SHA")
        report = verify_rollback(root, base, evaluated)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Source rollback verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
