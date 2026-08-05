from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "asi-verifiable-engineering"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


skill_validator = load_module("skill_validator", ROOT / "tools" / "validate_skill_package.py")
policy_validator = load_module(
    "policy_validator", SKILL_DIR / "scripts" / "validate_policy.py"
)
evidence_validator = load_module(
    "evidence_validator", SKILL_DIR / "scripts" / "validate_evidence.py"
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
                "---\nname: wrong-name\ndescription: Use this for validation.\n---\nBody\n",
                encoding="utf-8",
            )
            errors = skill_validator.validate_package(skill)
            self.assertTrue(any("must match directory" in error for error in errors))


class PolicyTests(unittest.TestCase):
    def test_repository_policy_is_valid(self) -> None:
        errors = policy_validator.validate_policy(ROOT / ".asi" / "policy.yml")
        self.assertEqual([], errors, "\n".join(errors))

    def test_placeholder_blocks_policy(self) -> None:
        source = (ROOT / ".asi" / "policy.yml").read_text(encoding="utf-8")
        invalid = source.replace('policy_owner: "Eidon"', 'policy_owner: "REPLACE_WITH_OWNER"')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.yml"
            path.write_text(invalid, encoding="utf-8")
            errors = policy_validator.validate_policy(path)
        self.assertTrue(any("placeholder" in error.lower() for error in errors))

    def test_self_approval_must_remain_false(self) -> None:
        source = (ROOT / ".asi" / "policy.yml").read_text(encoding="utf-8")
        invalid = source.replace("self_approve: false", "self_approve: true")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.yml"
            path.write_text(invalid, encoding="utf-8")
            errors = policy_validator.validate_policy(path)
        self.assertTrue(any("self_approve" in error for error in errors))


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        path = SKILL_DIR / "assets" / "evidence-manifest.example.json"
        self.valid_manifest = json.loads(path.read_text(encoding="utf-8"))

    def test_example_manifest_is_valid(self) -> None:
        errors = evidence_validator.validate_manifest(self.valid_manifest)
        self.assertEqual([], errors, "\n".join(errors))

    def test_approved_cannot_contain_unverified_items(self) -> None:
        data = dict(self.valid_manifest)
        data["decision"] = "APPROVED"
        data["unverified"] = ["integration environment"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("cannot contain unverified" in error for error in errors))

    def test_high_risk_requires_human_independence(self) -> None:
        data = dict(self.valid_manifest)
        data["risk"] = "high"
        data["independence"] = ["I1", "I2"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("requires I3" in error for error in errors))

    def test_critical_approval_requires_two_approvers(self) -> None:
        data = dict(self.valid_manifest)
        data["risk"] = "critical"
        data["independence"] = ["I2", "I3"]
        data["decision"] = "APPROVED"
        data["conditions"] = []
        data["unverified"] = []
        data["approved_by"] = ["one-reviewer"]
        errors = evidence_validator.validate_manifest(data)
        self.assertTrue(any("two approvers" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
