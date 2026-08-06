from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import verify_run


class TrustAnchorTests(unittest.TestCase):
    def test_control_plane_patterns_are_detected(self) -> None:
        changed = [
            "src/app.py",
            ".github/workflows/validate-skill.yml",
            "guardian/trust-policy.json",
        ]
        protected = verify_run.control_plane_changes(
            changed,
            [".github/workflows/**", "guardian/**"],
        )
        self.assertEqual(
            [
                ".github/workflows/validate-skill.yml",
                "guardian/trust-policy.json",
            ],
            protected,
        )

    def test_exception_requires_exact_identity_and_expiry(self) -> None:
        now = datetime.now(timezone.utc)
        exception = {
            "pr_number": 1,
            "head_sha": "a" * 40,
            "base_sha": "b" * 40,
            "expires_at": (now + timedelta(days=1)).isoformat(),
        }
        self.assertTrue(
            verify_run.exception_matches(
                [exception],
                pr_number=1,
                head_sha="a" * 40,
                base_sha="b" * 40,
                now=now,
            )
        )
        self.assertFalse(
            verify_run.exception_matches(
                [exception],
                pr_number=1,
                head_sha="c" * 40,
                base_sha="b" * 40,
                now=now,
            )
        )

    def test_bound_file_digest_is_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "result.json"
            path.write_text(json.dumps({"exit_code": 0}) + "\n", encoding="utf-8")
            digest = verify_run.sha256_file(path)
            verify_run.verify_bound_file(root, "result.json", digest)
            path.write_text(json.dumps({"exit_code": 1}) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_run.verify_bound_file(root, "result.json", digest)


if __name__ == "__main__":
    unittest.main()
