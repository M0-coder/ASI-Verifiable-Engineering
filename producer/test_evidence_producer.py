from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from producer import evidence_producer as producer


class EvidenceProducerTests(unittest.TestCase):
    def test_artifact_name_binds_attempt_head_and_evaluated_sha(self) -> None:
        head = "a" * 40
        evaluated = "b" * 40
        self.assertEqual(
            producer.artifact_name(123, 4, head, evaluated),
            f"asi-evidence-123-attempt-4-{head}-{evaluated}",
        )

    def test_artifact_name_rejects_short_sha(self) -> None:
        with self.assertRaises(ValueError):
            producer.artifact_name(123, 1, "abc", "b" * 40)

    def test_change_budget_is_exact(self) -> None:
        self.assertTrue(
            producer.verify_change_budget(
                sorted(producer.EXPECTED_PATHS)
            )["within_budget"]
        )
        bad = sorted(producer.EXPECTED_PATHS | {"unexpected.txt"})
        self.assertFalse(producer.verify_change_budget(bad)["within_budget"])

    def test_measured_gate_set_excludes_unproved_controls(self) -> None:
        self.assertNotIn("branch_protection", producer.MEASURED_GATES)
        self.assertNotIn("typecheck", producer.MEASURED_GATES)
        self.assertNotIn("package_installability", producer.MEASURED_GATES)
        self.assertNotIn("independent_audit", producer.MEASURED_GATES)
        self.assertNotIn("target_environment_observation", producer.MEASURED_GATES)

    def test_package_bytes_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "marker.txt").write_text("birth-06.1\n", encoding="utf-8")
            first = root / "first.zip"
            second = root / "second.zip"
            self.assertEqual(
                producer.build_deterministic_package(source, first),
                producer.build_deterministic_package(source, second),
            )
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
