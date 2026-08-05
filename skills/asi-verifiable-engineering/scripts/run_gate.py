#!/usr/bin/env python3
"""Run one policy-authorized verification gate and emit measured evidence."""

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


def policy_commands(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"^commands:\s*$\n(?P<body>(?:^  .*(?:\n|$)|^\s*$)*)",
        text,
        flags=re.MULTILINE,
    )
    if not match:
        raise ValueError("Policy does not contain a commands section.")

    commands: dict[str, str] = {}
    for name, raw_value in re.findall(
        r"^  ([a-z][a-z0-9_]*):\s*(.+?)\s*$",
        match.group("body"),
        flags=re.MULTILINE,
    ):
        commands[name] = raw_value.strip().strip('"\'')
    return commands


def resolve_policy_command(policy: Path, key: str) -> list[str]:
    commands = policy_commands(policy)
    command = commands.get(key)
    if not command:
        raise ValueError(f"Policy command is missing or empty: {key}")
    return shlex.split(command)


def execute_gate(
    name: str,
    output_dir: Path,
    command: list[str],
    policy_path: Path | None = None,
    policy_key: str | None = None,
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

    policy_reference: dict[str, object] | None = None
    if policy_path is not None:
        policy_reference = {
            "path": str(policy_path),
            "digest": sha256_file(policy_path),
            "command_key": policy_key,
        }

    result: dict[str, object] = {
        "result_version": 2,
        "name": name,
        "argv": command,
        "command": shlex.join(command),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration, 6),
        "exit_code": process.returncode,
        "log_artifact": str(log_path.relative_to(output_dir)),
        "log_digest": sha256_file(log_path),
        "policy": policy_reference,
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
    result.add_argument("--policy", type=Path)
    result.add_argument("--policy-key")
    result.add_argument("command", nargs=argparse.REMAINDER)
    return result


def main() -> int:
    args = parser().parse_args()
    explicit_command = list(args.command)
    if explicit_command and explicit_command[0] == "--":
        explicit_command = explicit_command[1:]

    if bool(args.policy) != bool(args.policy_key):
        print("--policy and --policy-key must be supplied together.", file=sys.stderr)
        return 2
    if args.policy and explicit_command:
        print("Use either a policy command or an explicit command, not both.", file=sys.stderr)
        return 2

    try:
        command = (
            resolve_policy_command(args.policy, args.policy_key)
            if args.policy and args.policy_key
            else explicit_command
        )
        result = execute_gate(
            args.name,
            args.output_dir,
            command,
            args.policy,
            args.policy_key,
        )
    except (OSError, ValueError) as exc:
        print(f"Cannot execute gate: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    exit_code = result["exit_code"]
    return int(exit_code) if isinstance(exit_code, int) else 2


if __name__ == "__main__":
    raise SystemExit(main())
