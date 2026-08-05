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
BUILDER_CONTEXT = "builder-context-01"
AUDITOR_CONTEXT = "auditor-context-02"
REPOSITORY = "owner/repository"
PACKAGE_DIGEST = "sha256:" + "3" * 64
EVIDENCE_DIGEST = "sha256:" + "4" * 64
EVIDENCE_URL = "https://raw.githubusercontent.com/owner/evidence/main/audit.json"
MARKER = "ASI-SOLO-AUDIT-V1"


def review_body() -> str:
    return "\n".join(
        [
            MARKER,
            f"ASI-AUDIT-EVIDENCE-URL: {EVIDENCE_URL}",
            f"ASI-AUDIT-EVIDENCE-SHA256: {EVIDENCE_DIGEST}",
        ]
    )


def review(
    review_id: int,
    state: str = "COMMENTED",
    commit_id: str = HEAD,
    body: str | None = None,
    account_type: str = "User",
    association: str = "OWNER",
) -> dict[str, object]:
    return {
        "id": review_id,
        "user": {"login": "owner", "type": account_type},
        "state": state,
        "commit_id": commit_id,
        "body": body if body is not None else review_body(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "author_association": association,
        "html_url": f"https://example.invalid/review/{review_id}",
    }


def attestation(
    auditor_context: str = AUDITOR_CONTEXT,
    include_observation: bool = True,
) -> dict[str, object]:
    result: dict[str, object] = {
        "attestation_version": 1,
        "operator_mode": "solo",
        "repository": REPOSITORY,
        "head_commit": HEAD,
        "builder_context_id": BUILDER_CONTEXT,
        "auditor_context_id": auditor_context,
        "audit": {
            "mode": "read_only",
            "result": "passed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "checks": [
                "Commit identity verified.",
                "Policy gates inspected.",
                "Evidence bindings reproduced.",
            ],
            "findings": [],
            "write_actions": [],
        },
    }
    if include_observation:
        result["target_observation"] = {
            "target_environment": "codex",
            "package_digest": PACKAGE_DIGEST,
            "result": "passed",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "checks": ["Skill loaded.", "Read-only protocol executed."],
            "limitations": [],
        }
    return result


class SoloAuditCollectorTests(unittest.TestCase):
    def test_same_github_owner_can_submit_distinct_context_audit(self) -> None:
        result = collector.evaluate_reviews(
            [review(1)],
            BUILDER_CONTEXT,
            HEAD,
            REPOSITORY,
            evidence_loader=lambda _url, _digest: attestation(),
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["observation_passed"])
        self.assertEqual(AUDITOR_CONTEXT, result["audits"][0]["auditor_context_id"])

    def test_same_context_is_rejected(self) -> None:
        result = collector.evaluate_reviews(
            [review(1)],
            BUILDER_CONTEXT,
            HEAD,
            REPOSITORY,
            evidence_loader=lambda _url, _digest: attestation(BUILDER_CONTEXT),
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "auditor_context_must_differ_from_builder_context",
            result["rejected_audits"][0]["reasons"],
        )

    def test_write_action_is_rejected(self) -> None:
        evidence = attestation()
        evidence["audit"]["write_actions"] = ["modified source.py"]
        result = collector.evaluate_reviews(
            [review(1)],
            BUILDER_CONTEXT,
            HEAD,
            REPOSITORY,
            evidence_loader=lambda _url, _digest: evidence,
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "audit_write_actions_must_be_empty",
            result["rejected_audits"][0]["reasons"],
        )

    def test_stale_comment_is_rejected(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, commit_id="b" * 40)],
            BUILDER_CONTEXT,
            HEAD,
            REPOSITORY,
            evidence_loader=lambda _url, _digest: attestation(),
        )
        self.assertFalse(result["passed"])
        self.assertIn(
            "audit_is_stale_for_current_head",
            result["rejected_audits"][0]["reasons"],
        )

    def test_missing_marker_is_ignored(self) -> None:
        result = collector.evaluate_reviews(
            [review(1, body="ordinary review")],
            BUILDER_CONTEXT,
            HEAD,
            REPOSITORY,
        )
        self.assertFalse(result["passed"])
        self.assertEqual([], result["rejected_audits"])


class SoloAuditApplicationTests(unittest.TestCase):
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
            "package_installability": {"archive_digest": PACKAGE_DIGEST},
            "review": {
                "builder": BUILDER_CONTEXT,
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
                "The Skill has not been observed in the target environment.",
            ],
        }

    def audit_report(self) -> dict[str, object]:
        evidence = attestation(include_observation=False)
        evidence.update({"actor": "owner", "review_id": 1})
        return {
            "passed": True,
            "builder_context_id": BUILDER_CONTEXT,
            "head_commit": HEAD,
            "audits": [evidence],
        }

    def observation_report(self, package_digest: str = PACKAGE_DIGEST) -> dict[str, object]:
        item = {
            "repository": REPOSITORY,
            "head_commit": HEAD,
            "auditor_context_id": AUDITOR_CONTEXT,
            "target_environment": "codex",
            "package_digest": package_digest,
            "result": "passed",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "checks": ["Skill loaded."],
        }
        return {
            "observation_passed": True,
            "head_commit": HEAD,
            "observations": [item],
        }

    def test_audit_adds_i1_not_i3(self) -> None:
        updated = applier.apply_attestations(
            self.manifest(),
            self.audit_report(),
            {"observation_passed": False},
        )
        self.assertIn("I1", updated["independence"])
        self.assertNotIn("I3", updated["independence"])
        self.assertEqual(AUDITOR_CONTEXT, updated["review"]["auditor"])
        self.assertEqual("owner_merge", updated["review"]["human_review"]["mode"])

    def test_observation_promotes_to_t5_e7(self) -> None:
        updated = applier.apply_attestations(
            self.manifest(),
            self.audit_report(),
            self.observation_report(),
        )
        self.assertEqual("T5", updated["assurance_level"])
        self.assertEqual("E7", updated["evidence_level"])
        self.assertEqual([], updated["unverified"])
        self.assertEqual([], updated["residual_risks"])

    def test_wrong_package_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            applier.apply_attestations(
                self.manifest(),
                self.audit_report(),
                self.observation_report("sha256:" + "9" * 64),
            )

    def test_failed_audit_does_not_change_manifest(self) -> None:
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
