#!/usr/bin/env python3
"""Fail CI after evidence upload when an actually executed source gate failed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evidence manifest root must be an object")
    return raw


def failed_executed_gates(manifest: dict[str, Any]) -> list[str]:
    coverage = manifest.get("audit_coverage")
    gates = manifest.get("gates")
    if not isinstance(coverage, dict) or not isinstance(gates, dict):
        raise ValueError("evidence manifest is missing audit_coverage/gates")
    executed = coverage.get("executed")
    if not isinstance(executed, list) or not all(isinstance(item, str) for item in executed):
        raise ValueError("audit_coverage.executed must be a string list")
    return sorted(name for name in executed if gates.get(name) == "failed")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("manifest", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    manifest = load_manifest(args.manifest)
    failed = failed_executed_gates(manifest)
    if failed:
        print("Measured source gates failed: " + ", ".join(failed))
        return 1
    print("Measured source gates: no FAIL results. External NOT_VERIFIED gates remain Trust Anchor inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
