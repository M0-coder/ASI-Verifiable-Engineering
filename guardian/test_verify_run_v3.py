from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

import verify_run_v3


class TrustAnchorV3Tests(unittest.TestCase):
    def test_gate_ownership_partitions_branch_protection(self) -> None:
        policy = {
            "required_gates": ["integrity", "branch_protection"],
            "source_required_gates": ["integrity"],
            "trusted_required_gates": ["branch_protection"],
        }
        source, trusted = verify_run_v3.gate_ownership(policy)
        self.assertEqual(["integrity"], source)
        self.assertEqual(["branch_protection"], trusted)

    def test_gate_ownership_rejects_overlap(self) -> None:
        policy = {
            "required_gates": ["integrity", "branch_protection"],
            "source_required_gates": ["integrity", "branch_protection"],
            "trusted_required_gates": ["branch_protection"],
        }
        with self.assertRaises(ValueError):
            verify_run_v3.gate_ownership(policy)

    def test_owner_comment_h1_is_exact_and_not_merge_authorization(self) -> None:
        now = datetime.now(timezone.utc)
        comment = {
            "id": 123,
            "html_url": "https://example.invalid/comment/123",
            "author_association": "OWNER",
            "user": {"login": "owner"},
            "body": "ASI-H1-EXCEPTION-V1\n"
            + json.dumps(
                {
                    "authorization_level": "H1",
                    "authorization_scope": "control-plane-exception-only",
                    "merge_authorized": False,
                    "pr_number": 6,
                    "base_sha": "a" * 40,
                    "head_sha": "b" * 40,
                    "allowed_paths": [".github/workflows/validate-skill.yml"],
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "reason": "exact bootstrap exception for producer workflow",
                }
            ),
        }
        result = verify_run_v3.h1_comment_matches(
            comment,
            authorizers=["owner"],
            pr_number=6,
            base_sha="a" * 40,
            head_sha="b" * 40,
            protected_changes=[".github/workflows/validate-skill.yml"],
            now=now,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result["merge_authorized"])

    def test_owner_comment_rejects_wrong_paths(self) -> None:
        now = datetime.now(timezone.utc)
        comment = {
            "author_association": "OWNER",
            "user": {"login": "owner"},
            "body": "ASI-H1-EXCEPTION-V1\n"
            + json.dumps(
                {
                    "authorization_level": "H1",
                    "authorization_scope": "control-plane-exception-only",
                    "merge_authorized": False,
                    "pr_number": 6,
                    "base_sha": "a" * 40,
                    "head_sha": "b" * 40,
                    "allowed_paths": ["guardian/other.py"],
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "reason": "wrong path",
                }
            ),
        }
        result = verify_run_v3.h1_comment_matches(
            comment,
            authorizers=["owner"],
            pr_number=6,
            base_sha="a" * 40,
            head_sha="b" * 40,
            protected_changes=[".github/workflows/validate-skill.yml"],
            now=now,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
