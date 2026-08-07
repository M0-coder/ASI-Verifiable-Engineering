#!/usr/bin/env python3
"""Run one unprivileged measured gate and persist its exact result."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--name", required=True)
    result.add_argument("--output-dir", required=True)
    result.add_argument("--description", required=True)
    result.add_argument("command", nargs=argparse.REMAINDER)
    return result


def main() -> int:
    args = parser().parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("measured gate command is required")
    if not args.name.replace("_", "").isalnum():
        raise SystemExit("gate name must contain only letters, numbers, and underscores")

    output = Path(args.output_dir).resolve()
    gates = output / "gates"
    gates.mkdir(parents=True, exist_ok=True)
    log_path = gates / f"{args.name}.log"
    result_path = gates / f"{args.name}.json"

    started = utc_now()
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        exit_code = completed.returncode
        log_text = completed.stdout
    except OSError as exc:
        exit_code = 127
        log_text = f"{type(exc).__name__}: {exc}\n"
    finished = utc_now()

    log_path.write_text(log_text, encoding="utf-8")
    result = {
        "result_version": 2,
        "name": args.name,
        "exit_code": exit_code,
        "argv": command,
        "command": shlex.join(command),
        "description": args.description,
        "started_at": started,
        "finished_at": finished,
        "log_artifact": f"gates/{args.name}.log",
        "log_digest": sha256_file(log_path),
    }
    result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(log_text, end="")
    print(json.dumps(result, indent=2, sort_keys=True))
    # A measured gate can fail while the evidence-producing workflow continues.
    # The trusted verifier consumes exit_code from the artifact.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
