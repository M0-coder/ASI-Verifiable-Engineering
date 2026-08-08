from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDIAN = ROOT / "guardian"
if str(GUARDIAN) not in sys.path:
    sys.path.insert(0, str(GUARDIAN))

import verify_run_v3  # noqa: E402
from tools import validate_skill_package  # noqa: E402


class IntegrationContractTests(unittest.TestCase):
    def test_gate_ownership_matches_trust_policy(self) -> None:
        policy = json.loads((GUARDIAN / "trust-policy.json").read_text(encoding="utf-8"))
        source, trusted = verify_run_v3.gate_ownership(policy)
        self.assertEqual(["branch_protection"], trusted)
        self.assertNotIn("branch_protection", source)
        self.assertIn("package_installability", source)
        self.assertIn("independent_audit", source)
        self.assertIn("target_environment_observation", source)

    def test_portable_skill_source_is_structurally_valid(self) -> None:
        report = validate_skill_package.validate(ROOT / "skills" / "asi-verifiable-engineering")
        self.assertTrue(report["passed"], report)

    def test_source_decision_is_non_authoritative_by_contract(self) -> None:
        source = (GUARDIAN / "verify_run_v3.py").read_text(encoding="utf-8")
        self.assertIn('"source_decision_authoritative": False', source)


if __name__ == "__main__":
    unittest.main()
