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
        self.assertEqual(4, report["contract_version"])

    def test_mobile_main_checkout_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            "          ref: ${{ github.workflow_sha }}",
            "          ref: main",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn(
            "mobile_main_checkout_forbidden",
            report["missing_or_invalid_controls"],
        )

    def test_v3_verifier_is_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            "          python3 guardian/verify_run_v3.py 2>&1 |",
            "          python3 guardian/verify_run_v2.py 2>&1 |",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn("trusted_v3_verifier", report["missing_or_invalid_controls"])
        self.assertIn(
            "v2_runtime_downgrade_forbidden",
            report["missing_or_invalid_controls"],
        )

    def test_branch_protection_must_be_trust_owned(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = dict(policy)
        invalid["source_required_gates"] = list(policy["source_required_gates"]) + [
            "branch_protection"
        ]
        report = verify_contract.evaluate_contract(workflow, invalid, verifier)
        self.assertIn("gate_ownership_overlap", report["missing_or_invalid_controls"])

    def test_owner_comment_mode_is_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = dict(policy)
        invalid["bootstrap_exception_mode"] = "none"
        report = verify_contract.evaluate_contract(workflow, invalid, verifier)
        self.assertIn(
            "owner_comment_exception_mode",
            report["missing_or_invalid_controls"],
        )

    def test_runner_context_in_job_env_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            "      ASI_TRUST_POLICY: guardian/trust-policy.json\n",
            "      ASI_TRUST_POLICY: guardian/trust-policy.json\n"
            "      ASI_TRUST_OUTPUT: ${{ runner.temp }}/asi-trust-anchor\n",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn(
            "runner_context_forbidden_in_job_env",
            report["missing_or_invalid_controls"],
        )


if __name__ == "__main__":
    unittest.main()
