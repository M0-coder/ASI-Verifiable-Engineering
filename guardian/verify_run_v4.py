#!/usr/bin/env python3
"""Trust-anchor runtime v4: enforce policy instance contract, then execute v3 verifier."""

from __future__ import annotations

import json
import os
from pathlib import Path

import policy_contract
import verify_run_v3

VERIFICATION_VERSION = 4


def run() -> int:
    policy_path = Path(os.environ.get("ASI_TRUST_POLICY", "guardian/trust-policy.json"))
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Trust policy root must be an object.")
    policy_contract.require(raw)
    return verify_run_v3.run()


if __name__ == "__main__":
    raise SystemExit(run())
