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

    def authorizers(self) -> list[dict[str, object]]:
        return [{"user_id": 295708153, "login": "historical-login"}]

    def comment(
        self,
        now: datetime,
        *,
        user_id: int = 295708153,
        login: str = "current-login",
        association: str = "OWNER",
        allowed_paths: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "id": 123,
            "html_url": "https://example.invalid/comment/123",
            "author_association": association,
            "user": {"id": user_id, "login": login},
            "body": "ASI-H1-EXCEPTION-V1\n"
            + json.dumps(
                {
                    "authorization_level": "H1",
                    "authorization_scope": "control-plane-exception-only",
                    "merge_authorized": False,
                    "pr_number": 6,
                    "base_sha": "a" * 40,
                    "head_sha": "b" * 40,
                    "allowed_paths": allowed_paths
                    if allowed_paths is not None
                    else [".github/workflows/validate-skill.yml"],
                    "expires_at": (now + timedelta(hours=1)).isoformat(),
                    "reason": "exact bootstrap exception for producer workflow",
                }
            ),
        }

    def test_owner_comment_uses_stable_id_not_mutable_login(self) -> None:
        now = datetime.now(timezone.utc)
        result = verify_run_v3.h1_comment_matches(
            self.comment(now, login="renamed-owner"),
            authorizers=self.authorizers(),
            pr_number=6,
            base_sha="a" * 40,
            head_sha="b" * 40,
            protected_changes=[".github/workflows/validate-skill.yml"],
            now=now,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(295708153, result["authorized_by_user_id"])
        self.assertEqual("renamed-owner", result["authorized_by"])
        self.assertEqual("historical-login", result["configured_login"])
        self.assertFalse(result["merge_authorized"])

    def test_owner_comment_rejects_wrong_stable_id(self) -> None:
        now = datetime.now(timezone.utc)
        result = verify_run_v3.h1_comment_matches(
            self.comment(now, user_id=999),
            authorizers=self.authorizers(),
            pr_number=6,
            base_sha="a" * 40,
            head_sha="b" * 40,
            protected_changes=[".github/workflows/validate-skill.yml"],
            now=now,
        )
        self.assertIsNone(result)

    def test_owner_comment_rejects_non_owner_association(self) -> None:
        now = datetime.now(timezone.utc)
        result = verify_run_v3.h1_comment_matches(
            self.comment(now, association="MEMBER"),
            authorizers=self.authorizers(),
            pr_number=6,
            base_sha="a" * 40,
            head_sha="b" * 40,
            protected_changes=[".github/workflows/validate-skill.yml"],
            now=now,
        )
        self.assertIsNone(result)

    def test_owner_comment_rejects_wrong_paths(self) -> None:
        now = datetime.now(timezone.utc)
        result = verify_run_v3.h1_comment_matches(
            self.comment(now, allowed_paths=["guardian/other.py"]),
            authorizers=self.authorizers(),
            pr_number=6,
            base_sha="a" * 40,
            head_sha="b" * 40,
            protected_changes=[".github/workflows/validate-skill.yml"],
            now=now,
        )
        self.assertIsNone(result)

    def test_repository_owner_binding_accepts_rename_same_id(self) -> None:
        result = verify_run_v3.validate_repository_owner(
            self.authorizers(),
            {"owner": {"id": 295708153, "login": "M0-coder"}},
        )
        self.assertEqual(295708153, result["user_id"])
        self.assertEqual("historical-login", result["configured_login"])
        self.assertEqual("M0-coder", result["observed_login"])

    def test_repository_owner_binding_rejects_wrong_id(self) -> None:
        with self.assertRaises(ValueError):
            verify_run_v3.validate_repository_owner(
                self.authorizers(),
                {"owner": {"id": 999, "login": "other-owner"}},
            )

    def test_h1_authorizers_reject_legacy_string_schema(self) -> None:
        with self.assertRaises(ValueError):
            verify_run_v3.h1_authorizers({"h1_authorizers": ["owner"]})

    def test_h1_authorizers_reject_duplicate_ids(self) -> None:
        with self.assertRaises(ValueError):
            verify_run_v3.h1_authorizers(
                {
                    "h1_authorizers": [
                        {"user_id": 295708153, "login": "a"},
                        {"user_id": 295708153, "login": "b"},
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
