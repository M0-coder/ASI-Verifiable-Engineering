from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from producer import gate_checks


class GateChecksTests(unittest.TestCase):
    def test_text_format_rejects_trailing_whitespace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-gate-test-") as tmp:
            path = Path(tmp) / "bad.md"
            path.write_bytes(b"hello  \n")
            self.assertIn("line 1 has trailing whitespace", gate_checks.check_text_format(path))

    def test_lint_rejects_eval(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-gate-test-") as tmp:
            path = Path(tmp) / "bad.py"
            path.write_text("eval('1+1')\n", encoding="utf-8")
            errors = gate_checks.lint_python(path)
            self.assertTrue(any("dynamic eval is forbidden" in error for error in errors))

    def test_repository_local_modules_are_discovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="asi-gate-test-") as tmp:
            root = Path(tmp)
            (root / "guardian").mkdir()
            (root / "guardian" / "verify.py").write_text("x = 1\n", encoding="utf-8")
            modules = gate_checks.repository_local_modules(root)
            self.assertIn("guardian", modules)
            self.assertIn("verify", modules)


if __name__ == "__main__":
    unittest.main()
