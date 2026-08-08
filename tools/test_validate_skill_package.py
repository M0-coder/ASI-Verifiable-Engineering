from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools import validate_skill_package


class ValidateSkillPackageTests(unittest.TestCase):
    @classmethod
    def source_root(cls) -> Path:
        return Path(__file__).resolve().parents[1] / "skills" / "asi-verifiable-engineering"

    def test_repository_package_passes(self) -> None:
        report = validate_skill_package.validate(self.source_root())
        self.assertTrue(report["passed"], report)

    def test_digest_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-package-test-") as tmp:
            root = Path(tmp) / "skill"
            shutil.copytree(self.source_root(), root)
            path = root / "references" / "architecture.md"
            path.write_text(path.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
            report = validate_skill_package.validate(root)
            self.assertFalse(report["passed"])
            self.assertIn("digest:references/architecture.md", report["findings"])

    def test_legacy_candidate_decision_token_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-package-test-") as tmp:
            root = Path(tmp) / "skill"
            shutil.copytree(self.source_root(), root)
            path = root / "SKILL.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nAPPROVED\n", encoding="utf-8")
            report = validate_skill_package.validate(root)
            self.assertFalse(report["passed"])
            self.assertIn("legacy_decision_token:APPROVED", report["findings"])


if __name__ == "__main__":
    unittest.main()
