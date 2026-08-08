from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any

from producer import verify_external_attestation as external


class ExternalAttestationTests(unittest.TestCase):
    repository = "M0-coder/ASI-Verifiable-Engineering"
    head = "a" * 40
    builder_context = "asi-constructor-reconcile-20260808-01"
    package_digest = "sha256:" + "b" * 64

    def attestation(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "schema": "asi.external_attestation.v1",
            "repository": self.repository,
            "pull_request": 8,
            "head_sha": self.head,
            "builder_context_id": self.builder_context,
            "auditor_context_id": "asi-auditor-separate-context-01",
            "audit": {
                "mode": "read_only",
                "result": "PASS",
                "checks": ["candidate diff", "tests and evidence"],
                "findings": [],
                "write_actions": [],
                "publication_actions": ["publish immutable attestation"],
                "created_at": now,
            },
            "target_observation": {
                "target_environment": "chatgpt",
                "result": "PASS",
                "package_digest": self.package_digest,
                "checks": ["package opened", "instructions usable"],
                "limitations": [],
                "executed_at": now,
            },
        }

    def review(self) -> dict[str, Any]:
        body = "\n".join(
            [
                external.MARKER,
                "ASI-ATTESTATION-URL: https://raw.githubusercontent.com/"
                + self.repository
                + "/"
                + "c" * 40
                + "/evidence/pr8.json",
                "ASI-ATTESTATION-SHA256: sha256:" + "d" * 64,
            ]
        )
        return {
            "id": 1,
            "body": body,
            "state": "COMMENTED",
            "commit_id": self.head,
            "submitted_at": "2026-08-08T16:00:00Z",
            "author_association": "OWNER",
            "user": {"login": "M0-coder", "type": "User"},
        }

    def loader(self, url: str, digest: str, repository: str) -> dict[str, Any]:
        self.assertIn("raw.githubusercontent.com", url)
        self.assertTrue(digest.startswith("sha256:"))
        self.assertEqual(self.repository, repository)
        return self.attestation()

    def test_no_marked_review_is_not_verified(self) -> None:
        state, _ = external.evaluate_reviews(
            [],
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
            evidence_loader=self.loader,
        )
        self.assertEqual("NOT_VERIFIED", state)

    def test_valid_external_audit_passes(self) -> None:
        state, report = external.evaluate_reviews(
            [self.review()],
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
            evidence_loader=self.loader,
        )
        self.assertEqual("PASS", state)
        self.assertEqual(1, len(report["accepted"]))

    def test_pass_with_findings_is_rejected_end_to_end(self) -> None:
        raw = self.attestation()
        audit = raw["audit"]
        assert isinstance(audit, dict)
        audit["findings"] = [
            {
                "id": "F-01",
                "severity": "HIGH",
                "material": True,
                "blocking": True,
            }
        ]
        errors = external.validate_attestation(
            raw,
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
        )
        self.assertIn("audit_PASS_requires_no_findings", errors)

        def loader_with_findings(
            url: str, digest: str, repository: str
        ) -> dict[str, Any]:
            self.assertIn("raw.githubusercontent.com", url)
            self.assertTrue(digest.startswith("sha256:"))
            self.assertEqual(self.repository, repository)
            return raw

        state, report = external.evaluate_reviews(
            [self.review()],
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
            evidence_loader=loader_with_findings,
        )
        self.assertEqual("FAIL", state)
        self.assertEqual(0, len(report["accepted"]))
        self.assertEqual(1, len(report["rejected"]))
        self.assertIn(
            "audit_PASS_requires_no_findings",
            report["rejected"][0]["reasons"],
        )

    def test_same_context_is_rejected(self) -> None:
        raw = self.attestation()
        raw["auditor_context_id"] = self.builder_context
        errors = external.validate_attestation(
            raw,
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
        )
        self.assertIn("auditor_context_must_differ_from_builder_context", errors)

    def test_audit_write_action_is_rejected_but_publication_is_allowed(self) -> None:
        raw = self.attestation()
        audit = raw["audit"]
        assert isinstance(audit, dict)
        audit["write_actions"] = ["modified candidate"]
        errors = external.validate_attestation(
            raw,
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
        )
        self.assertIn("audit_write_actions_must_be_empty", errors)
        audit["write_actions"] = []
        errors = external.validate_attestation(
            raw,
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
        )
        self.assertNotIn("audit_publication_actions_must_be_string_list", errors)

    def test_invalid_marked_review_is_fail_not_not_verified(self) -> None:
        review = self.review()
        review["commit_id"] = "e" * 40
        state, report = external.evaluate_reviews(
            [review],
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="independent-audit",
            package_digest=None,
            evidence_loader=self.loader,
        )
        self.assertEqual("FAIL", state)
        self.assertEqual(1, len(report["rejected"]))

    def test_target_observation_requires_exact_package_digest(self) -> None:
        raw = self.attestation()
        observation = raw["target_observation"]
        assert isinstance(observation, dict)
        observation["package_digest"] = "sha256:" + "f" * 64
        errors = external.validate_attestation(
            raw,
            repository=self.repository,
            pr_number=8,
            head_sha=self.head,
            builder_context_id=self.builder_context,
            kind="target-environment-observation",
            package_digest=self.package_digest,
        )
        self.assertIn("package_digest_mismatch", errors)

    def test_raw_url_requires_same_repo_and_immutable_commit(self) -> None:
        with self.assertRaises(ValueError):
            external.validate_raw_url(
                "https://raw.githubusercontent.com/M0-coder/ASI-Verifiable-Engineering/main/evidence/a.json",
                self.repository,
            )
        with self.assertRaises(ValueError):
            external.validate_raw_url(
                "https://raw.githubusercontent.com/other/repo/"
                + "c" * 40
                + "/evidence/a.json",
                self.repository,
            )


if __name__ == "__main__":
    unittest.main()
