from __future__ import annotations

import unittest

import verify_protection_binding


class ProtectionBindingTests(unittest.TestCase):
    def valid_protection(self) -> dict[str, object]:
        return {
            "required_status_checks": {
                "strict": True,
                "checks": [
                    {
                        "context": "ASI Trust Anchor",
                        "app_id": 15368,
                    }
                ],
            },
            "enforce_admins": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
        }

    def test_matching_app_id_passes(self) -> None:
        check_runs = {
            "check_runs": [
                {
                    "name": "ASI Trust Anchor",
                    "app": {"id": 15368},
                }
            ]
        }
        report = verify_protection_binding.evaluate_binding(
            self.valid_protection(),
            check_runs,
        )
        self.assertTrue(report["passed"])

    def test_same_name_from_different_app_is_rejected(self) -> None:
        check_runs = {
            "check_runs": [
                {
                    "name": "ASI Trust Anchor",
                    "app": {"id": 99999},
                }
            ]
        }
        report = verify_protection_binding.evaluate_binding(
            self.valid_protection(),
            check_runs,
        )
        self.assertFalse(report["passed"])
        self.assertIn(
            "required_check_app_binding",
            report["missing_or_invalid_controls"],
        )


if __name__ == "__main__":
    unittest.main()
