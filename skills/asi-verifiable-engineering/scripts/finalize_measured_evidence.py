#!/usr/bin/env python3
"""Finalize recovery and package claims from measured gate evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _measured_gate(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    gates = manifest.get("gates")
    evidence = manifest.get("gate_evidence")
    commands = manifest.get("commands")
    if not isinstance(gates, dict) or gates.get(name) != "passed":
        raise ValueError(f"Gate {name} is not passed.")
    if not isinstance(evidence, dict) or not isinstance(evidence.get(name), dict):
        raise ValueError(f"Gate {name} has no evidence binding.")
    if not isinstance(commands, list):
        raise ValueError("Manifest commands are missing.")
    command = next(
        (
            item
            for item in commands
            if isinstance(item, dict) and item.get("name") == name
        ),
        None,
    )
    if not isinstance(command, dict) or command.get("exit_code") != 0:
        raise ValueError(f"Gate {name} has no successful measured command.")
    item = evidence[name]
    for field in (
        "result_artifact",
        "result_digest",
        "log_artifact",
        "log_digest",
    ):
        if item.get(field) != command.get(field):
            raise ValueError(f"Gate {name} field {field} is inconsistent.")
    return item


def finalize(manifest: dict[str, Any]) -> dict[str, Any]:
    rollback_evidence = _measured_gate(manifest, "rollback_check")
    package_evidence = _measured_gate(manifest, "package_installability")

    rollback = manifest.get("rollback")
    if not isinstance(rollback, dict):
        raise ValueError("Manifest rollback object is missing.")
    rollback.update(
        {
            "tested": True,
            "scope": "source_tree",
            "evidence": rollback_evidence,
            "limitations": [
                "Source-tree reversal was rehearsed in an isolated worktree.",
                "Production, database, secret, and external-service rollback remain separate controls.",
            ],
        }
    )
    manifest["package_installability"] = {
        "tested": True,
        "scope": "portable_skill_archive",
        "evidence": package_evidence,
        "limitations": [
            "Portable package creation and extraction were verified.",
            "Installation in a specific ChatGPT, Codex, or API account remains unverified.",
        ],
    }
    return manifest


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: finalize_measured_evidence.py MANIFEST", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Manifest root must be an object.")
        manifest = finalize(raw)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Cannot finalize measured evidence: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
