from __future__ import annotations

import json
import unittest
from pathlib import Path

import verify_contract

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "asi-trust-anchor.yml"
POLICY = ROOT / "guardian" / "trust-policy.json"
VERIFIER = ROOT / "guardian" / "verify_protection_binding.py"


class TrustAnchorContractTests(unittest.TestCase):
    def inputs(self) -> tuple[str, dict[str, object], str]:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        verifier = VERIFIER.read_text(encoding="utf-8")
        self.assertIsInstance(policy, dict)
        return workflow, policy, verifier

    def test_repository_contract_passes(self) -> None:
        workflow, policy, verifier = self.inputs()
        report = verify_contract.evaluate_contract(workflow, policy, verifier)
        self.assertTrue(report["passed"], report)
        self.assertEqual(
            {
                "workflow": "ASI Trust Anchor",
                "job": "ASI Trust Anchor",
                "policy": "ASI Trust Anchor",
                "verifier": "ASI Trust Anchor",
            },
            report["observed_names"],
        )

    def test_job_name_drift_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            "jobs:\n  verify:\n    name: ASI Trust Anchor",
            "jobs:\n  verify:\n    name: Guardian execution",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertFalse(report["passed"])
        self.assertIn(
            "check_name_contract_mismatch",
            report["missing_or_invalid_controls"],
        )

    def test_registration_without_main_ref_guard_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            '          test "$GITHUB_REF" = "refs/heads/main"\n',
            "",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertFalse(report["passed"])
        self.assertIn(
            "registration_ref_guard",
            report["missing_or_invalid_controls"],
        )

    def test_registration_without_exact_main_sha_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            '          test "$GITHUB_SHA" = "$(git rev-parse HEAD)"\n',
            "",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertFalse(report["passed"])
        self.assertIn(
            "registration_sha_guard",
            report["missing_or_invalid_controls"],
        )


if __name__ == "__main__":
    unittest.main()
