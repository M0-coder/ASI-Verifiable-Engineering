from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guardian"))

from producer import evidence_producer as producer  # noqa: E402
import verify_run_v2 as guardian_v2  # noqa: E402


class ProducerGuardianIntegrationTests(unittest.TestCase):
    def test_artifact_identity_matches_guardian_v2(self) -> None:
        head = "a" * 40
        evaluated = "b" * 40
        expected = producer.artifact_name(77, 3, head, evaluated)
        observed = guardian_v2.artifact_name(
            "asi-evidence-",
            run_id=77,
            run_attempt=3,
            head_sha=head,
            evaluated_sha=evaluated,
        )
        self.assertEqual(expected, observed)

    def test_deterministic_package_is_accepted_by_guardian_zip_policy(self) -> None:
        policy = json.loads(
            (ROOT / "guardian" / "trust-policy.json").read_text(encoding="utf-8")
        )
        limits = guardian_v2.archive_limits(policy)
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            source = temp / "source"
            source.mkdir()
            (source / "marker.txt").write_text("birth-06.1\n", encoding="utf-8")
            package = temp / "package.zip"
            producer.build_deterministic_package(source, package)
            destination = temp / "extracted"
            destination.mkdir()
            guardian_v2.safe_extract(package.read_bytes(), destination, limits)
            self.assertEqual(
                (destination / "marker.txt").read_text(encoding="utf-8"),
                "birth-06.1\n",
            )


if __name__ == "__main__":
    unittest.main()
