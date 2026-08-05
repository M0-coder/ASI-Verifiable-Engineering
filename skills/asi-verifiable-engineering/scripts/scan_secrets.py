#!/usr/bin/env python3
"""Scan tracked text files for high-confidence secret patterns."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "github_classic_token": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "github_fine_grained_token": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    "openai_style_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

MAX_FILE_BYTES = 2 * 1024 * 1024


def tracked_files(root: Path) -> list[Path]:
    process = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [root / item.decode("utf-8") for item in process.stdout.split(b"\0") if item]


def scan(root: Path) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    scanned_files = 0

    for path in tracked_files(root):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_BYTES:
            skipped.append(
                {
                    "path": str(path.relative_to(root)),
                    "reason": "file_too_large",
                    "size": size,
                }
            )
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append(
                {
                    "path": str(path.relative_to(root)),
                    "reason": "non_text_or_unreadable",
                    "size": size,
                }
            )
            continue

        scanned_files += 1
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(
                    {
                        "path": str(path.relative_to(root)),
                        "line": line,
                        "pattern": label,
                    }
                )

    return {
        "scan_version": 1,
        "scanned_files": scanned_files,
        "skipped_files": skipped,
        "findings": findings,
        "passed": not findings,
    }


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd()
    try:
        report = scan(root.resolve())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Secret scan failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
