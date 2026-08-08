from __future__ import annotations

import json
import unittest
from pathlib import Path

import verify_contract


class VerifyContractTests(unittest.TestCase):
    @classmethod
    def root(cls) -> Path:
        return Path(__file__).resolve().parents[1]

    def inputs(self) -> tuple[str, dict, str]:
        root = self.root()
        workflow = (root / ".github/workflows/asi-trust-anchor.yml").read_text(encoding="utf-8")
        policy = json.loads((root / "guardian/trust-policy.json").read_text(encoding="utf-8"))
        verifier = (root / "guardian/verify_protection_binding.py").read_text(encoding="utf-8")
        return workflow, policy, verifier

    def test_repository_contract_passes(self) -> None:
        workflow, policy, verifier = self.inputs()
        report = verify_contract.evaluate_contract(workflow, policy, verifier)
        self.assertTrue(report["passed"], report)
        self.assertEqual(6, report["contract_version"])
        self.assertEqual(4, report["policy_schema_version"])
        self.assertGreaterEqual(report["policy_revision"], 6)

    def test_runtime_v4_is_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace("guardian/verify_run_v4.py", "guardian/verify_run_v3.py")
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertFalse(report["passed"])
        self.assertIn("trusted_v4_verifier", report["missing_or_invalid_controls"])
        self.assertIn("v3_runtime_downgrade_forbidden", report["missing_or_invalid_controls"])

    def test_producer_skill_and_typecheck_inputs_are_protected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = dict(policy)
        invalid["protected_paths"] = [
            item
            for item in policy["protected_paths"]
            if item not in {
                "producer/**",
                "skills/asi-verifiable-engineering/**",
                "mypy.ini",
                "requirements-ci.lock",
            }
        ]
        report = verify_contract.evaluate_contract(workflow, invalid, verifier)
        self.assertFalse(report["passed"])
        self.assertIn("protected_path:producer/**", report["missing_or_invalid_controls"])
        self.assertIn("protected_path:skills/asi-verifiable-engineering/**", report["missing_or_invalid_controls"])
        self.assertIn("protected_path:mypy.ini", report["missing_or_invalid_controls"])
        self.assertIn("protected_path:requirements-ci.lock", report["missing_or_invalid_controls"])

    def test_stable_h1_identity_is_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = dict(policy)
        invalid["h1_authorizers"] = [{"login": "M0-coder"}]
        report = verify_contract.evaluate_contract(workflow, invalid, verifier)
        self.assertIn("h1_authorizer_stable_user_id", report["missing_or_invalid_controls"])

    def test_mobile_main_checkout_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace("          ref: ${{ github.workflow_sha }}", "          ref: main", 1)
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn("mobile_main_checkout_forbidden", report["missing_or_invalid_controls"])


if __name__ == "__main__":
    unittest.main()
