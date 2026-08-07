from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from producer import gate_checks


class GateChecksTests(unittest.TestCase):
    def test_format_rejects_trailing_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("x = 1  \n", encoding="utf-8")
            self.assertTrue(gate_checks.check_text_format(path))

    def test_format_accepts_clean_utf8_lf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(gate_checks.check_text_format(path), [])

    def test_lint_rejects_bare_except(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(
                "try:\n    pass\nexcept:\n    pass\n",
                encoding="utf-8",
            )
            self.assertTrue(gate_checks.lint_python(path))

    def test_secret_patterns_detect_known_shapes(self) -> None:
        samples = [
            "gh" + "p_" + "A" * 35,
            "AK" + "IA" + "A" * 16,
            "-----BEGIN " + "PRIVATE KEY-----",
        ]
        patterns = gate_checks.secret_patterns()
        for sample in samples:
            self.assertTrue(any(pattern.search(sample) for pattern in patterns))

    def test_imported_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(
                "import json\nfrom pathlib import Path\n",
                encoding="utf-8",
            )
            self.assertEqual(gate_checks.imported_roots(path), {"json", "pathlib"})


if __name__ == "__main__":
    unittest.main()
