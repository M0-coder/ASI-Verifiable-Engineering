#!/usr/bin/env python3
"""Finalize measured technical, recovery, and package evidence claims."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

EXTERNAL_PROMOTION_GATES = {
    "branch_protection",
    "independent_audit",
    "target_environment_observation",
}


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
    item = cast(dict[str, Any], evidence[name])
    for field in (
        "result_artifact",
        "result_digest",
        "log_artifact",
        "log_digest",
    ):
        if item.get(field) != command.get(field):
            raise ValueError(f"Gate {name} field {field} is inconsistent.")
    return item


def _load_json_log(evidence_dir: Path, gate: dict[str, Any]) -> dict[str, Any]:
    relative = gate.get("log_artifact")
    if not isinstance(relative, str) or not relative:
        raise ValueError("Measured gate has no log artifact.")
    path = (evidence_dir / relative).resolve()
    try:
        path.relative_to(evidence_dir.resolve())
    except ValueError as exc:
        raise ValueError("Measured gate log path escapes the evidence directory.") from exc
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Measured gate log must contain a JSON object: {relative}")
    return cast(dict[str, Any], raw)


def _finalize_preoperational_level(manifest: dict[str, Any]) -> None:
    gates = manifest.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("Manifest gates are missing.")
    technical = {
        name: state
        for name, state in gates.items()
        if name not in EXTERNAL_PROMOTION_GATES
    }
    if technical and all(state == "passed" for state in technical.values()):
        manifest["evidence_level"] = "E6"
        manifest["assurance_level"] = "T4"
    else:
        manifest["evidence_level"] = "E5"
        manifest["assurance_level"] = "T3"


def finalize(
    manifest: dict[str, Any],
    evidence_dir: Path,
) -> dict[str, Any]:
    rollback_evidence = _measured_gate(manifest, "rollback_check")
    package_evidence = _measured_gate(manifest, "package_installability")
    rollback_report = _load_json_log(evidence_dir, rollback_evidence)
    package_report = _load_json_log(evidence_dir, package_evidence)

    if rollback_report.get("passed") is not True:
        raise ValueError("Rollback report is not passed.")
    if package_report.get("passed") is not True:
        raise ValueError("Package installability report is not passed.")
    archive_digest = package_report.get("archive_digest")
    if not isinstance(archive_digest, str) or not archive_digest.startswith("sha256:"):
        raise ValueError("Package report has no valid archive_digest.")

    rollback = manifest.get("rollback")
    if not isinstance(rollback, dict):
        raise ValueError("Manifest rollback object is missing.")
    rollback.update(
        {
            "tested": True,
            "scope": "source_tree",
            "restored_base_tree": rollback_report.get("restored_base_tree"),
            "evidence": rollback_evidence,
            "limitations": rollback_report.get("limitations", []),
        }
    )
    manifest["package_installability"] = {
        "tested": True,
        "scope": "portable_skill_archive",
        "archive_digest": archive_digest,
        "deterministic_rebuild": package_report.get("deterministic_rebuild"),
        "content_preserved_after_extract": package_report.get(
            "content_preserved_after_extract"
        ),
        "file_count": package_report.get("file_count"),
        "evidence": package_evidence,
        "limitations": package_report.get("limitations", []),
    }
    _finalize_preoperational_level(manifest)
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
        manifest = finalize(raw, path.parent)
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
