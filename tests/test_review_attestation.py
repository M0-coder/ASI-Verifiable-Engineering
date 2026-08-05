from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "asi-verifiable-engineering" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collector = load_module(
    "collector_review_test",
    SCRIPTS / "collect_github_review.py",
)
applier = load_module(
    "applier_review_test",
    SCRIPTS / "apply_review_attestation.py",
)

HEAD = "a" * 40
BUILDER = "builder-user"
REVIEWER = "independent-reviewer"
REPOSITORY = "owner/repository"
PACKAGE_DIGEST = "sha256:" + "3" * 64
EVIDENCE_DIGEST = "sha256:" + "4" * 64
EVIDENCE_URL = "https://raw.githubusercontent.com/reviewer/evidence/main/report.json"
REVIEW_MARKER = "ASI-TARGETED-REVIEW-V1"
OBSERVATION_MARKER = "ASI-TARGET-OBSERVATION-V1"


def review_body(include_observation: bool = False) -> str:
    lines = [REVIEW_MARKER]
    if include_observation:
        lines.extend(
            [
                OBSERVATION_MARKER,
                f"ASI-TARGET-EVIDENCE-URL: {EVIDENCE_URL}",
                f"ASI-TARGET-EVIDENCE-SHA256: {EVIDENCE_DIGEST}",
            ]
        )
    return "\n".join(lines)


def review(
    review_id: int,
    reviewer: str,
    state: str = "APPROVED",
    commit_id: str = HEAD,
    body: str | None = None,
    account_type: str = "User",
    association: str = "COLLABORATOR",
) -> dict[str, object]:
    return {
        "id": review_id,
        "user": {
            "login": reviewer,
            "type": account_type,
        },
        "state": state,
        "commit_id": commit_id,
        "body": body if body is not None else review_body(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "author_association": association,
        "html_url": f"https://example.invalid/review/{review_id}",
    }


def observation() -> dict[str, object]:
    return {
        "observation_version": 1,
        "repository": REPOSITORY,
        "head_commit": HEAD,
        "reviewer": REVIEWER,
        "target_environment": "codex",
        "package_digest": PACKAGE_DIGEST,
        "result": "passed",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "checks": [
            "Skill loaded from the verified package.",
            "Read-only startup protocol executed.",
            "Decision output matched the expected contract.",
        ],
        "limitations": [],
    }


class ReviewCollectorTests(unittest.TestCase):
    def test_valid_independent_targeted_approval_passes(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, REVIEWER)],
            BUILDER,
            HEAD,
            REPOSITORY,
        )
        self.assertTrue(result["passed"])
        self.assertFalse(result["observation_passed"])
        self.assertEqual(REVIEWER, result["approvals"][0]["reviewer"])

    def test_valid_external_observation_is_verified(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, REVIEWER, body=review_body(include_observation=True))],
            BUILDER,
            HEAD,
            REPOSITORY,
            observation_loader=lambda _url, _digest: observation(),
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["observation_passed"])
        self.assertEqual("codex", result["observations"][0]["target_environment"])

    def test_builder_cannot_approve_own_change(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, BUILDER)],
            BUILDER,
            HEAD,
            REPOSITORY,
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "reviewer_is_the_builder",
            result["rejected_latest_reviews"][0]["reasons"],
        )

    def test_stale_approval_is_rejected(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, REVIEWER, commit_id="b" * 40)],
            BUILDER,
            HEAD,
            REPOSITORY,
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "review_is_stale_for_current_head",
            result["rejected_latest_reviews"][0]["reasons"],
        )

    def test_bot_and_missing_marker_are_rejected(self) -> None:
        result = collector.evaluate_reviews(
            [
                review(
                    1,
                    "review-bot",
                    body="looks good",
                    account_type="Bot",
                )
            ],
            BUILDER,
            HEAD,
            REPOSITORY,
        )
        self.assertFalse(result["passed"])
        reasons = result["rejected_latest_reviews"][0]["reasons"]
        self.assertIn("reviewer_is_not_a_human_user_account", reasons)
        self.assertIn("targeted_review_marker_is_missing", reasons)

    def test_later_changes_requested_invalidates_prior_approval(self) -> None:
        result = collector.evaluate_reviews(
            [
                review(1, REVIEWER, state="APPROVED"),
                review(2, REVIEWER, state="CHANGES_REQUESTED"),
            ],
            BUILDER,
            HEAD,
            REPOSITORY,
        )
        self.assertFalse(result["passed"])
        self.assertEqual(
            "CHANGES_REQUESTED",
            result["rejected_latest_reviews"][0]["state"],
        )


class ReviewApplicationTests(unittest.TestCase):
    def manifest(self) -> dict[str, object]:
        commands = []
        gate_evidence: dict[str, object] = {}
        for index, name in enumerate(
            ("independent_audit", "target_environment_observation"),
            start=1,
        ):
            commands.append(
                {
                    "name": name,
                    "exit_code": 0,
                    "result_artifact": f"gates/{name}.json",
                    "result_digest": "sha256:" + str(index) * 64,
                    "log_artifact": f"gates/{name}.log",
                    "log_digest": "sha256:" + str(index + 2) * 64,
                }
            )
            gate_evidence[name] = {
                "result_artifact": f"gates/{name}.json",
                "result_digest": "sha256:" + str(index) * 64,
                "log_artifact": f"gates/{name}.log",
                "log_digest": "sha256:" + str(index + 2) * 64,
            }
        return {
            "head_commit": HEAD,
            "evidence_level": "E6",
            "assurance_level": "T4",
            "package_installability": {
                "archive_digest": PACKAGE_DIGEST,
            },
            "review": {
                "builder": BUILDER,
                "auditor": None,
                "same_context": False,
                "human_review": {
                    "required": True,
                    "completed": False,
                    "mode": "targeted",
                },
            },
            "commands": commands,
            "gates": {
                "independent_audit": "passed",
                "target_environment_observation": "passed",
            },
            "gate_evidence": gate_evidence,
            "independence": ["I2"],
            "approved_by": [],
            "unverified": [
                "Independent targeted human review is pending.",
                "Installation in the target agent environment is pending.",
            ],
            "residual_risks": [
                "Independent targeted human review has not been completed.",
                "The Skill has not been installed in the target environment.",
            ],
        }

    def review_report(self) -> dict[str, object]:
        return {
            "passed": True,
            "builder": BUILDER,
            "head_commit": HEAD,
            "approvals": [
                {
                    "reviewer": REVIEWER,
                    "commit_id": HEAD,
                    "review_id": 1,
                }
            ],
        }

    def observation_report(self, package_digest: str = PACKAGE_DIGEST) -> dict[str, object]:
        item = observation()
        item["package_digest"] = package_digest
        return {
            "observation_passed": True,
            "head_commit": HEAD,
            "observations": [item],
        }

    def test_review_without_observation_promotes_only_independence(self) -> None:
        manifest = self.manifest()
        updated = applier.apply_attestations(
            manifest,
            self.review_report(),
            {"observation_passed": False},
        )
        self.assertIn("I3", updated["independence"])
        self.assertEqual("T4", updated["assurance_level"])
        self.assertEqual("E6", updated["evidence_level"])

    def test_matching_observation_promotes_to_t5_e7(self) -> None:
        manifest = self.manifest()
        updated = applier.apply_attestations(
            manifest,
            self.review_report(),
            self.observation_report(),
        )
        self.assertEqual("T5", updated["assurance_level"])
        self.assertEqual("E7", updated["evidence_level"])
        self.assertEqual("codex", updated["operational_observation"]["target_environment"])
        self.assertEqual([], updated["unverified"])
        self.assertEqual([], updated["residual_risks"])

    def test_observation_for_different_package_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            applier.apply_attestations(
                self.manifest(),
                self.review_report(),
                self.observation_report("sha256:" + "9" * 64),
            )

    def test_failed_review_report_does_not_change_manifest(self) -> None:
        manifest = self.manifest()
        original = copy.deepcopy(manifest)
        updated = applier.apply_attestations(
            manifest,
            {"passed": False},
            {"observation_passed": False},
        )
        self.assertEqual(original, updated)


if __name__ == "__main__":
    unittest.main()
