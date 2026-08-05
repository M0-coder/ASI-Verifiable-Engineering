from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
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
MARKER = "ASI-TARGETED-REVIEW-V1"


def review(
    review_id: int,
    reviewer: str,
    state: str = "APPROVED",
    commit_id: str = HEAD,
    body: str = MARKER,
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
        "body": body,
        "submitted_at": "2026-08-05T17:00:00Z",
        "author_association": association,
        "html_url": f"https://example.invalid/review/{review_id}",
    }


class ReviewCollectorTests(unittest.TestCase):
    def test_valid_independent_targeted_approval_passes(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, "independent-reviewer")],
            BUILDER,
            HEAD,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(
            "independent-reviewer",
            result["approvals"][0]["reviewer"],
        )

    def test_builder_cannot_approve_own_change(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, BUILDER)],
            BUILDER,
            HEAD,
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "reviewer_is_the_builder",
            result["rejected_latest_reviews"][0]["reasons"],
        )

    def test_stale_approval_is_rejected(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, "reviewer", commit_id="b" * 40)],
            BUILDER,
            HEAD,
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
        )
        self.assertFalse(result["passed"])
        reasons = result["rejected_latest_reviews"][0]["reasons"]
        self.assertIn("reviewer_is_not_a_human_user_account", reasons)
        self.assertIn("targeted_review_marker_is_missing", reasons)

    def test_later_changes_requested_invalidates_prior_approval(self) -> None:
        result = collector.evaluate_reviews(
            [
                review(1, "reviewer", state="APPROVED"),
                review(2, "reviewer", state="CHANGES_REQUESTED"),
            ],
            BUILDER,
            HEAD,
        )
        self.assertFalse(result["passed"])
        self.assertEqual(
            "CHANGES_REQUESTED",
            result["rejected_latest_reviews"][0]["state"],
        )


class ReviewApplicationTests(unittest.TestCase):
    def manifest(self) -> dict[str, object]:
        return {
            "head_commit": HEAD,
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
            "commands": [
                {
                    "name": "independent_audit",
                    "exit_code": 0,
                    "result_artifact": "gates/independent_audit.json",
                    "result_digest": "sha256:" + "1" * 64,
                    "log_artifact": "gates/independent_audit.log",
                    "log_digest": "sha256:" + "2" * 64,
                }
            ],
            "gates": {"independent_audit": "not_verified"},
            "gate_evidence": {
                "independent_audit": {
                    "justification": "pending",
                }
            },
            "independence": ["I2"],
            "approved_by": [],
            "unverified": [
                "Independent targeted human review is pending.",
                "Required gate independent_audit is not verified.",
                "Target installation is pending.",
            ],
            "residual_risks": [
                "Independent targeted human review has not been completed.",
                "Target installation is pending.",
            ],
        }

    def report(self) -> dict[str, object]:
        return {
            "passed": True,
            "builder": BUILDER,
            "head_commit": HEAD,
            "approvals": [
                {
                    "reviewer": "independent-reviewer",
                    "commit_id": HEAD,
                    "review_id": 1,
                }
            ],
        }

    def test_valid_report_promotes_independence_without_setting_t5(self) -> None:
        manifest = self.manifest()
        updated = applier.apply_attestation(manifest, self.report())
        self.assertEqual("passed", updated["gates"]["independent_audit"])
        self.assertIn("I3", updated["independence"])
        self.assertEqual(
            "independent-reviewer",
            updated["review"]["auditor"],
        )
        self.assertNotIn("assurance_level", updated)
        self.assertEqual(
            ["Target installation is pending."],
            updated["unverified"],
        )

    def test_failed_report_does_not_change_manifest(self) -> None:
        manifest = self.manifest()
        original = copy.deepcopy(manifest)
        updated = applier.apply_attestation(manifest, {"passed": False})
        self.assertEqual(original, updated)


if __name__ == "__main__":
    unittest.main()
