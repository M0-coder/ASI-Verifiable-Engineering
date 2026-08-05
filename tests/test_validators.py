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
sys.path.insert(0, str(SCRIPTS_DIR))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
            skill = Path(temp) / "correct-name"
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
        self.assertTrue(any("must match directory" in error for error in errors))


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

    def test_required_gate_cannot_be_disabled(self) -> None:
        errors = self._validate_modified(
            "dependency_scan: true",
            "dependency_scan: false",
        )
        self.assertTrue(any("dependency_scan" in error for error in errors))

    def test_obsolete_generic_security_command_is_rejected(self) -> None:
        errors = self._validate_modified(
            "  test_honesty:",
            "  security_scan: \"python fake.py\"\n  test_honesty:",
        )
        self.assertTrue(any("obsolete" in error for error in errors))

    def test_line_by_line_review_is_not_default(self) -> None:
        errors = self._validate_modified(
            "line_by_line_review_default: false",
            "line_by_line_review_default: true",
        )
        self.assertTrue(
            any("line_by_line_review_default" in error for error in errors)
        )


class EvidenceStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        path = SKILL_DIR / "assets" / "evidence-manifest.example.json"
        self.manifest = json.loads(path.read_text(encoding="utf-8"))

    def test_blocked_example_is_structurally_valid(self) -> None:
        errors = evidence_validator.validate_manifest(self.manifest)
        self.assertEqual([], errors, "\n".join(errors))

    def test_blocked_high_risk_manifest_does_not_require_i3_yet(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["risk"] = "high"
        data["review"]["human_review"] = {
            "required": True,
            "completed": False,
            "mode": "targeted",
        }
        errors = evidence_validator.validate_manifest(data)
        self.assertFalse(any("requires I3" in error for error in errors))

    def test_gate_state_must_match_measured_exit_code(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["commands"][0]["exit_code"] = 1
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("contradicts" in error for error in errors))

    def test_artifact_digest_must_match_every_reference(self) -> None:
        data = copy.deepcopy(self.manifest)
        data["commands"][0]["log_digest"] = "sha256:" + "9" * 64
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("same digest" in error for error in errors))


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = decision_engine.parse_policy(ROOT / ".asi" / "policy.yml")
        path = SKILL_DIR / "assets" / "evidence-manifest.example.json"
        self.manifest = json.loads(path.read_text(encoding="utf-8"))

    def test_incomplete_example_is_blocked_without_line_review(self) -> None:
        result = decision_engine.evaluate_change(
            self.policy,
            copy.deepcopy(self.manifest),
        )
        self.assertEqual("BLOCKED", result["decision"])
        self.assertFalse(result["line_by_line_review_required"])

    def test_binding_conflict_activates_forensic_review(self) -> None:
        result = decision_engine.evaluate_change(
            self.policy,
            copy.deepcopy(self.manifest),
            ["Artifact digest mismatch: gates/unit_tests.log"],
        )
        self.assertEqual("BLOCKED", result["decision"])
        self.assertTrue(result["line_by_line_review_required"])
        self.assertEqual("forensic", result["human_review_mode"])


if __name__ == "__main__":
    unittest.main()
