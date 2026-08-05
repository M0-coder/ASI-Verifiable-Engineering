#!/usr/bin/env python3
"""Run one verification gate and emit measured, digest-bound evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

GATE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def atomic_write_json(path: Path, data: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def execute_gate(
    name: str,
    output_dir: Path,
    command: list[str],
) -> dict[str, object]:
    if not GATE_NAME.fullmatch(name):
        raise ValueError(f"Invalid gate name: {name!r}")
    if not command:
        raise ValueError("A gate command is required.")

    gates_dir = output_dir / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    log_path = gates_dir / f"{name}.log"
    result_path = gates_dir / f"{name}.json"

    started_at = utc_now()
    started = time.monotonic()
    with log_path.open("wb") as log_file:
        process = subprocess.run(
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            check=False,
        )
    duration = max(time.monotonic() - started, 0.0)
    finished_at = utc_now()

    result: dict[str, object] = {
        "result_version": 1,
        "name": name,
        "argv": command,
        "command": shlex.join(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration, 6),
        "exit_code": process.returncode,
        "log_artifact": str(log_path.relative_to(output_dir)),
        "log_digest": sha256_file(log_path),
        "environment": {
            "github_sha": os.environ.get("GITHUB_SHA"),
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "runner_os": os.environ.get("RUNNER_OS"),
            "runner_arch": os.environ.get("RUNNER_ARCH"),
        },
    }
    atomic_write_json(result_path, result)
    result["result_artifact"] = str(result_path.relative_to(output_dir))
    result["result_digest"] = sha256_file(result_path)
    return result


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--name", required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("command", nargs=argparse.REMAINDER)
    return result


def main() -> int:
    args = parser().parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    try:
        result = execute_gate(args.name, args.output_dir, command)
    except (OSError, ValueError) as exc:
        print(f"Cannot execute gate: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    exit_code = result["exit_code"]
    return int(exit_code) if isinstance(exit_code, int) else 2


if __name__ == "__main__":
    raise SystemExit(main())
