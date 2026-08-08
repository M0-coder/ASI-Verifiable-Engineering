from __future__ import annotations

import json
import unittest
from pathlib import Path

import policy_contract


class PolicyContractTests(unittest.TestCase):
    @classmethod
    def policy(cls) -> dict:
        root = Path(__file__).resolve().parents[1]
        return json.loads((root / "guardian/trust-policy.json").read_text(encoding="utf-8"))

    def test_current_policy_passes(self) -> None:
        self.assertEqual([], policy_contract.validate(self.policy()))

    def test_missing_protected_path_fails(self) -> None:
        policy = self.policy()
        policy["protected_paths"] = [
            path for path in policy["protected_paths"] if path != "producer/**"
        ]
        self.assertIn("protected_path:producer/**", policy_contract.validate(policy))

    def test_revision_must_be_current(self) -> None:
        policy = self.policy()
        policy["revision"] = 4
        self.assertIn("trust_policy_revision", policy_contract.validate(policy))


if __name__ == "__main__":
    unittest.main()
