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
        self.assertEqual(3, report["contract_version"])
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
        self.assertIn(
            "check_name_contract_mismatch",
            report["missing_or_invalid_controls"],
        )

    def test_mobile_main_checkout_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            "          ref: ${{ github.workflow_sha }}",
            "          ref: main",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertFalse(report["passed"])
        self.assertIn(
            "mobile_main_checkout_forbidden",
            report["missing_or_invalid_controls"],
        )
        self.assertIn(
            "immutable_workflow_checkout",
            report["missing_or_invalid_controls"],
        )

    def test_v2_verifier_is_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            "          python3 guardian/verify_run_v2.py 2>&1 |",
            "          python3 guardian/verify_run.py 2>&1 |",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn("trusted_v2_verifier", report["missing_or_invalid_controls"])

    def test_registration_without_main_ref_guard_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            '          test "$GITHUB_REF" = "refs/heads/main"\n', "", 1
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn("registration_ref_guard", report["missing_or_invalid_controls"])

    def test_registration_without_exact_main_sha_is_rejected(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            '          test "$GITHUB_SHA" = "$(git rev-parse HEAD)"\n', "", 1
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn("registration_sha_guard", report["missing_or_invalid_controls"])

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

    def test_runtime_output_export_is_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = workflow.replace(
            '          echo "ASI_TRUST_OUTPUT=$RUNNER_TEMP/asi-trust-anchor" '
            '>> "$GITHUB_ENV"\n',
            "",
            1,
        )
        report = verify_contract.evaluate_contract(invalid, policy, verifier)
        self.assertIn("runtime_output_env", report["missing_or_invalid_controls"])

    def test_policy_v2_and_archive_limits_are_required(self) -> None:
        workflow, policy, verifier = self.inputs()
        invalid = dict(policy)
        invalid["version"] = 1
        invalid.pop("archive_limits")
        report = verify_contract.evaluate_contract(workflow, invalid, verifier)
        self.assertIn("trust_policy_v2", report["missing_or_invalid_controls"])
        self.assertIn("archive_limits", report["missing_or_invalid_controls"])


if __name__ == "__main__":
    unittest.main()
