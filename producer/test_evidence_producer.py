from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from producer import evidence_producer


class EvidenceProducerTests(unittest.TestCase):
    def test_artifact_name_binds_attempt_head_and_evaluated_sha(self) -> None:
        name = evidence_producer.artifact_name(123, 4, "a" * 40, "b" * 40)
        self.assertEqual(
            "asi-evidence-123-attempt-4-" + "a" * 40 + "-" + "b" * 40,
            name,
        )

    def test_change_budget_rejects_outside_path(self) -> None:
        budget = {
            "version": 1,
            "max_files": 2,
            "allowed_prefixes": ["skills/"],
            "allowed_root_files": ["README.md"],
            "forbidden_paths": [".env"],
        }
        report = evidence_producer.verify_change_budget(["skills/a", "outside.txt"], budget)
        self.assertFalse(report["within_budget"])
        self.assertEqual(["outside.txt"], report["unexpected_paths"])

    def test_deterministic_package_has_sorted_fixed_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-producer-test-") as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            (root / "b.txt").write_text("b\n", encoding="utf-8")
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            target = Path(tmp) / "package.zip"
            first = evidence_producer.build_deterministic_package(root, target)
            payload = target.read_bytes()
            second = evidence_producer.build_deterministic_package(root, target)
            self.assertEqual(first, second)
            self.assertEqual(payload, target.read_bytes())
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                self.assertEqual(["a.txt", "b.txt"], archive.namelist())
                self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))


if __name__ == "__main__":
    unittest.main()
