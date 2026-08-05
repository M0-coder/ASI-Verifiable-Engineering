from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "asi-verifiable-engineering"
SCRIPTS = SKILL_DIR / "scripts"


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_gate = load_module("run_gate_test", SCRIPTS / "run_gate.py")
budget_control = load_module(
    "budget_control_test",
    SCRIPTS / "verify_change_budget.py",
)
supply_chain = load_module(
    "supply_chain_test",
    SCRIPTS / "scan_supply_chain.py",
)
secret_scan = load_module("secret_scan_test", SCRIPTS / "scan_secrets.py")
rollback_control = load_module(
    "rollback_control_test",
    SCRIPTS / "verify_source_rollback.py",
)
installability = load_module(
    "installability_test",
    SCRIPTS / "verify_installability.py",
)


class AdversarialControlTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        return subprocess.check_output(
            ["git", *args],
            cwd=root,
            text=True,
        ).strip()

    def _init_repo(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "config", "user.name", "ASI Test")
        self._git(root, "config", "user.email", "asi@example.invalid")

    def test_gate_runner_records_real_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            result = run_gate.execute_gate(
                "negative_control",
                output,
                [sys.executable, "-c", "raise SystemExit(7)"],
            )
            result_file = output / "gates" / "negative_control.json"
            persisted = json.loads(result_file.read_text(encoding="utf-8"))

        self.assertEqual(7, result["exit_code"])
        self.assertEqual(7, persisted["exit_code"])
        self.assertGreaterEqual(result["duration_seconds"], 0.0)
        self.assertTrue(str(result["log_digest"]).startswith("sha256:"))

    def test_forbidden_path_blocks_even_when_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._init_repo(root)
            (root / "safe.txt").write_text("base\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "base")
            base = self._git(root, "rev-parse", "HEAD")

            forbidden = root / "keys" / "secret.txt"
            forbidden.parent.mkdir()
            forbidden.write_text("not-a-secret\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "forbidden")
            head = self._git(root, "rev-parse", "HEAD")

            budget = {
                "version": 1,
                "builder_context_id": "builder-context-test",
                "expected_paths": ["keys/secret.txt"],
                "forbidden_paths": ["keys/**"],
                "max_files": 2,
                "max_changed_lines": 20,
                "allow_binary_files": False,
            }
            report = budget_control.evaluate_budget(root, budget, base, head)

        self.assertFalse(report["within_budget"])
        self.assertEqual(["keys/secret.txt"], report["forbidden_files"])
        self.assertIn("forbidden_path_change", report["forensic_triggers"])

    def test_floating_action_reference_fails_supply_chain_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workflow = root / ".github" / "workflows" / "ci.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "steps:\n  - uses: actions/checkout@v4\n",
                encoding="utf-8",
            )
            (root / "requirements-ci.lock").write_text(
                "ruff==0.15.22\n",
                encoding="utf-8",
            )
            report = supply_chain.scan(root)

        self.assertFalse(report["passed"])
        self.assertIn("unpinned_actions", report["violations"])

    def test_secret_scanner_detects_constructed_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._init_repo(root)
            token = "ghp_" + ("A" * 30)
            (root / "sample.txt").write_text(token + "\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "secret")
            report = secret_scan.scan(root)

        self.assertFalse(report["passed"])
        self.assertEqual("github_classic_token", report["findings"][0]["pattern"])

    def test_source_rollback_restores_exact_base_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._init_repo(root)
            source = root / "source.txt"
            source.write_text("base\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "base")
            base = self._git(root, "rev-parse", "HEAD")

            source.write_text("changed\n", encoding="utf-8")
            (root / "new.txt").write_text("new\n", encoding="utf-8")
            self._git(root, "add", ".")
            self._git(root, "commit", "-qm", "change")
            evaluated = self._git(root, "rev-parse", "HEAD")
            report = rollback_control.verify_rollback(root, base, evaluated)

        self.assertTrue(report["passed"])
        self.assertTrue(report["restored_base_tree"])
        self.assertEqual("source_tree", report["scope"])

    def test_portable_skill_package_is_deterministic(self) -> None:
        report = installability.verify_installability(SKILL_DIR)
        self.assertTrue(report["passed"])
        self.assertTrue(report["deterministic_rebuild"])
        self.assertTrue(report["content_preserved_after_extract"])
        self.assertGreater(report["file_count"], 10)


if __name__ == "__main__":
    unittest.main()
