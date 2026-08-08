from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import verify_run_v4


class VerifyRunV4Tests(unittest.TestCase):
    @classmethod
    def policy(cls) -> dict:
        root = Path(__file__).resolve().parents[1]
        return json.loads((root / "guardian/trust-policy.json").read_text(encoding="utf-8"))

    def write_policy(self, root: Path, policy: dict) -> Path:
        path = root / "policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        return path

    def test_wrapper_delegates_after_policy_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-verify-v4-") as tmp:
            policy_path = self.write_policy(Path(tmp), self.policy())
            with mock.patch.dict(os.environ, {"ASI_TRUST_POLICY": str(policy_path)}), mock.patch.object(
                verify_run_v4.verify_run_v3, "run", return_value=0
            ) as delegated:
                self.assertEqual(0, verify_run_v4.run())
                delegated.assert_called_once_with()

    def test_wrapper_rejects_policy_without_skill_protection(self) -> None:
        policy = self.policy()
        policy["protected_paths"] = [
            path for path in policy["protected_paths"] if path != "skills/asi-verifiable-engineering/**"
        ]
        with tempfile.TemporaryDirectory(prefix="asi-verify-v4-") as tmp:
            policy_path = self.write_policy(Path(tmp), policy)
            with mock.patch.dict(os.environ, {"ASI_TRUST_POLICY": str(policy_path)}):
                with self.assertRaisesRegex(ValueError, "protected_path:skills/asi-verifiable-engineering/\\*\\*"):
                    verify_run_v4.run()


if __name__ == "__main__":
    unittest.main()
