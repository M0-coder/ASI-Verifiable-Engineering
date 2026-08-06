from __future__ import annotations

import io
import tempfile
import unittest
import warnings
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import verify_run_v2


LIMITS: dict[str, int | float] = {
    "max_compressed_bytes": 1_000_000,
    "max_files": 8,
    "max_member_bytes": 1_000_000,
    "max_total_uncompressed_bytes": 2_000_000,
    "max_compression_ratio": 100.0,
}


def make_zip(entries: list[tuple[str, bytes]]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in entries:
            bundle.writestr(name, content)
    return payload.getvalue()


class HardenedTrustAnchorTests(unittest.TestCase):
    def test_safe_extract_accepts_small_archive(self) -> None:
        archive = make_zip([("manifest.json", b"{}"), ("logs/gate.log", b"ok")])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            root.mkdir()
            verify_run_v2.safe_extract(archive, root, LIMITS)
            self.assertEqual("ok", (root / "logs/gate.log").read_text())

    def test_path_traversal_is_rejected(self) -> None:
        archive = make_zip([("../escape.txt", b"blocked")])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            root.mkdir()
            with self.assertRaises(ValueError):
                verify_run_v2.safe_extract(archive, root, LIMITS)

    def test_duplicate_names_are_rejected(self) -> None:
        payload = io.BytesIO()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(payload, "w") as bundle:
                bundle.writestr("same.txt", b"one")
                bundle.writestr("same.txt", b"two")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "Duplicate ZIP entry"):
                verify_run_v2.safe_extract(payload.getvalue(), root, LIMITS)

    def test_encrypted_member_metadata_is_rejected(self) -> None:
        member = zipfile.ZipInfo("secret.txt")
        member.flag_bits |= 0x1
        member.file_size = 10
        member.compress_size = 10
        with self.assertRaisesRegex(ValueError, "Encrypted ZIP entry"):
            verify_run_v2.validate_members([member], LIMITS)

    def test_compression_ratio_is_bounded(self) -> None:
        member = zipfile.ZipInfo("bomb.txt")
        member.file_size = 100_000
        member.compress_size = 1
        with self.assertRaisesRegex(ValueError, "compression ratio"):
            verify_run_v2.validate_members([member], LIMITS)

    def test_artifact_name_binds_attempt_head_and_evaluated_sha(self) -> None:
        name = verify_run_v2.artifact_name(
            "asi-evidence-",
            run_id=123,
            run_attempt=4,
            head_sha="a" * 40,
            evaluated_sha="b" * 40,
        )
        self.assertEqual(
            "asi-evidence-123-attempt-4-" + "a" * 40 + "-" + "b" * 40,
            name,
        )

    def test_exception_requires_exact_paths_and_h1(self) -> None:
        now = datetime.now(timezone.utc)
        exception = {
            "pr_number": 5,
            "base_sha": "a" * 40,
            "head_sha": "b" * 40,
            "allowed_paths": ["guardian/verify_run_v2.py"],
            "authorization_level": "H1",
            "authorized_by": "repository-owner",
            "reason": "time-limited trust-root repair",
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }
        self.assertTrue(
            verify_run_v2.exception_matches_exact(
                [exception],
                pr_number=5,
                base_sha="a" * 40,
                head_sha="b" * 40,
                protected_changes=["guardian/verify_run_v2.py"],
                now=now,
            )
        )
        self.assertFalse(
            verify_run_v2.exception_matches_exact(
                [exception],
                pr_number=5,
                base_sha="a" * 40,
                head_sha="b" * 40,
                protected_changes=[
                    "guardian/verify_run_v2.py",
                    ".github/workflows/asi-trust-anchor.yml",
                ],
                now=now,
            )
        )


if __name__ == "__main__":
    unittest.main()
