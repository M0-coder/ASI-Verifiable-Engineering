#!/usr/bin/env python3
"""Check deterministic text-format invariants for all tracked repository files."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MAX_CODE_LINE = 160
CODE_SUFFIXES = {
    ".py",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    return [root / item.decode("utf-8") for item in output.split(b"\0") if item]


def check_file(root: Path, path: Path) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    relative = str(path.relative_to(root))
    raw = path.read_bytes()
    if b"\x00" in raw:
        return findings
    if b"\r\n" in raw or b"\r" in raw:
        findings.append({"path": relative, "reason": "non_lf_line_endings"})
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        findings.append({"path": relative, "reason": "non_utf8_text"})
        return findings
    if text and not text.endswith("\n"):
        findings.append({"path": relative, "reason": "missing_final_newline"})

    for line_number, line in enumerate(text.splitlines(), start=1):
        trailing_spaces = len(line) - len(line.rstrip(" "))
        intentional_markdown_break = (
            path.suffix.lower() == ".md" and trailing_spaces == 2
        )
        if (line.endswith("\t") or trailing_spaces > 0) and not intentional_markdown_break:
            findings.append(
                {
                    "path": relative,
                    "line": line_number,
                    "reason": "trailing_whitespace",
                }
            )
        if "\t" in line:
            findings.append(
                {
                    "path": relative,
                    "line": line_number,
                    "reason": "tab_character",
                }
            )
        if path.suffix.lower() in CODE_SUFFIXES and len(line) > MAX_CODE_LINE:
            findings.append(
                {
                    "path": relative,
                    "line": line_number,
                    "reason": "line_too_long",
                    "length": len(line),
                    "maximum": MAX_CODE_LINE,
                }
            )
    return findings


def scan(root: Path) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    checked = 0
    for path in tracked_files(root):
        if not path.is_file():
            continue
        try:
            findings.extend(check_file(root, path))
            checked += 1
        except OSError as exc:
            findings.append(
                {
                    "path": str(path.relative_to(root)),
                    "reason": "unreadable_file",
                    "error": str(exc),
                }
            )
    return {
        "check_version": 1,
        "checked_files": checked,
        "maximum_code_line": MAX_CODE_LINE,
        "findings": findings,
        "passed": not findings,
    }


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path.cwd()
    try:
        report = scan(root.resolve())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Format check failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
