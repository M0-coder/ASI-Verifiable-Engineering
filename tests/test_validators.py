from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "asi-verifiable-engineering"
SCRIPTS_DIR = SKILL_DIR / "scripts"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(SCRIPTS_DIR))

skill_validator = load_module(
    "skill_validator",
    ROOT / "tools" / "validate_skill_package.py",
)
policy_validator = load_module(
    "policy_validator",
    SCRIPTS_DIR / "validate_policy.py",
)
evidence_validator = load_module(
    "evidence_validator",
    SCRIPTS_DIR / "validate_evidence.py",
)
decision_engine = load_module(
    "decision_engine",
    SCRIPTS_DIR / "evaluate_change.py",
)


class SkillPackageTests(unittest.TestCase):
    def test_repository_skill_package_is_valid(self) -> None:
        errors = skill_validator.validate_package(SKILL_DIR)
        self.assertEqual([], errors, "\n".join(errors))

    def test_frontmatter_requires_closing_delimiter(self) -> None:
        with self.assertRaises(ValueError):
            skill_validator.parse_frontmatter("---\nname: broken\n")

    def test_name_must_match_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "correct-name"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\n"
                "name: wrong-name\n"
                "description: Use this for validation.\n"
                "---\n"
                "Body\n",
                encoding="utf-8",
            )
            errors = skill_validator.validate_package(skill)
            self.assertTrue(
                any("must match directory" in error for error in errors)
            )


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / ".asi" / "policy.yml"
        self.source = self.path.read_text(encoding="utf-8")

    def _validate_modified(self, old: str, new: str) -> list[str]:
        invalid = self.source.replace(old, new)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.yml"
            path.write_text(invalid, encoding="utf-8")
            return policy_validator.validate_policy(path)

    def test_repository_policy_is_valid(self) -> None:
        errors = policy_validator.validate_policy(self.path)
        self.assertEqual([], errors, "\n".join(errors))

    def test_placeholder_blocks_policy(self) -> None:
        errors = self._validate_modified(
            'policy_owner: "Eidon"',
            'policy_owner: "REPLACE_WITH_OWNER"',
        )
        self.assertTrue(
            any("placeholder" in error.lower() for error in errors)
        )

    def test_self_approval_must_remain_false(self) -> None:
        errors = self._validate_modified(
            "self_approve: false",
            "self_approve: true",
        )
        self.assertTrue(any("self_approve" in error for error in errors))

    def test_required_gate_cannot_be_disabled(self) -> None:
        errors = self._validate_modified(
            "secret_scan: true",
            "secret_scan: false",
        )
        self.assertTrue(any("secret_scan" in error for error in errors))

    def test_line_by_line_review_is_not_default_gate(self) -> None:
        errors = self._validate_modified(
            "line_by_line_review_default: false",
            "line_by_line_review_default: true",
        )
        self.assertTrue(
            any("line_by_line_review_default" in error for error in errors)
        )


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        path = SKILL_DIR / "assets" / "evidence-manifest.example.json"
        self.valid_manifest = json.loads(path.read_text(encoding="utf-8"))

    def test_example_manifest_is_valid(self) -> None:
        errors = evidence_validator.validate_manifest(self.valid_manifest)
        self.assertEqual([], errors, "\n".join(errors))

    def test_approved_cannot_contain_unverified_items(self) -> None:
        data = copy.deepcopy(self.valid_manifest)
        data["unverified"] = ["integration environment"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(
            any("cannot contain unverified" in error for error in errors)
        )

    def test_approved_cannot_contain_residual_risks(self) -> None:
        data = copy.deepcopy(self.valid_manifest)
        data["residual_risks"] = ["unknown external dependency"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(
            any("cannot contain residual risks" in error for error in errors)
        )

    def test_high_risk_requires_human_independence(self) -> None:
        data = copy.deepcopy(self.valid_manifest)
        data["risk"] = "high"
        data["independence"] = ["I1", "I2"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("requires I3" in error for error in errors))

    def test_critical_approval_requires_two_approvers(self) -> None:
        data = copy.deepcopy(self.valid_manifest)
        data["risk"] = "critical"
        data["evidence_level"] = "E8"
        data["assurance_level"] = "T6"
        data["independence"] = ["I2", "I3"]
        data["review"]["human_review"] = {
            "required": True,
            "completed": True,
            "mode": "targeted_dual",
        }
        data["approved_by"] = ["one-reviewer"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("two approvers" in error for error in errors))

    def test_passed_gate_requires_digest_bound_evidence(self) -> None:
        data = copy.deepcopy(self.valid_manifest)
        del data["gate_evidence"]["unit_tests"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(
            any("gate_evidence.unit_tests" in error for error in errors)
        )

    def test_builder_and_auditor_must_be_distinct(self) -> None:
        data = copy.deepcopy(self.valid_manifest)
        data["review"]["auditor"] = data["review"]["builder"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(
            any("must be distinct" in error for error in errors)
        )


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        policy_path = ROOT / ".asi" / "policy.yml"
        evidence_path = (
            SKILL_DIR / "assets" / "evidence-manifest.example.json"
        )
        self.policy = decision_engine.parse_policy(policy_path)
        self.manifest = json.loads(
            evidence_path.read_text(encoding="utf-8")
        )

    def test_example_is_approved_without_line_by_line_review(self) -> None:
        result = decision_engine.evaluate_change(
            self.policy,
            copy.deepcopy(self.manifest),
        )
        self.assertEqual("APPROVED", result["decision"])
        self.assertTrue(result["automatic_approval_eligible"])
        self.assertFalse(result["line_by_line_review_required"])
        self.assertEqual([], result["blockers"])

    def test_claimed_approval_does_not_override_failed_gate(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["gates"]["unit_tests"] = "failed"
        result = decision_engine.evaluate_change(self.policy, data)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertFalse(result["automatic_approval_eligible"])
        self.assertTrue(
            any("unit_tests" in blocker for blocker in result["blockers"])
        )

    def test_lower_assurance_cannot_be_approved(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["assurance_level"] = "T2"
        data["evidence_level"] = "E4"
        result = decision_engine.evaluate_change(self.policy, data)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertTrue(
            any("requires at least T4" in blocker for blocker in result["blockers"])
        )

    def test_same_builder_and_auditor_blocks(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["review"]["auditor"] = data["review"]["builder"]
        result = decision_engine.evaluate_change(self.policy, data)
        self.assertEqual("BLOCKED", result["decision"])
        self.assertTrue(
            any("must be distinct" in blocker for blocker in result["blockers"])
        )

    def test_high_risk_uses_targeted_not_line_by_line_review(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["risk"] = "high"
        data["evidence_level"] = "E7"
        data["assurance_level"] = "T5"
        data["independence"] = ["I2", "I3"]
        data["review"]["human_review"] = {
            "required": True,
            "completed": True,
            "mode": "targeted",
        }
        data["approved_by"] = ["human-reviewer"]
        result = decision_engine.evaluate_change(self.policy, data)
        self.assertEqual("APPROVED", result["decision"])
        self.assertFalse(result["automatic_approval_eligible"])
        self.assertFalse(result["line_by_line_review_required"])
        self.assertEqual("targeted", result["human_review_mode"])


if __name__ == "__main__":
    unittest.main()
