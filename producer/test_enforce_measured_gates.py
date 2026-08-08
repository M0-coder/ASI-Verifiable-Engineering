from __future__ import annotations

import unittest

from producer import enforce_measured_gates


class EnforceMeasuredGatesTests(unittest.TestCase):
    def test_executed_failure_is_reported(self) -> None:
        manifest = {
            "audit_coverage": {"executed": ["lint", "typecheck"]},
            "gates": {"lint": "passed", "typecheck": "failed", "independent_audit": "not_verified"},
        }
        self.assertEqual(["typecheck"], enforce_measured_gates.failed_executed_gates(manifest))

    def test_external_not_verified_does_not_fail_transport(self) -> None:
        manifest = {
            "audit_coverage": {"executed": ["lint", "typecheck"]},
            "gates": {"lint": "passed", "typecheck": "passed", "independent_audit": "not_verified"},
        }
        self.assertEqual([], enforce_measured_gates.failed_executed_gates(manifest))


if __name__ == "__main__":
    unittest.main()
