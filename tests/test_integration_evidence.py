from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "asi-verifiable-engineering" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_gate = load_module("run_gate_integration", SCRIPTS / "run_gate.py")
generator = load_module(
    "generator_integration",
    SCRIPTS / "generate_ci_evidence.py",
)
validator = load_module(
    "validator_integration",
    SCRIPTS / "validate_evidence.py",
)


class EvidenceIntegrationTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> str:
        return subprocess.check_output(
            ["git", *args],
            cwd=root,
            text=True,
        ).strip()

    def test_manifest_is_bound_and_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            repo = workspace / "repo"
            evidence = workspace / "evidence"
            repo.mkdir()
            self._git(repo, "init", "-q")
            self._git(repo, "config", "user.name", "ASI Test")
            self._git(repo, "config", "user.email", "asi@example.invalid")

            policy = repo / "policy.yml"
            policy.write_text(
                "commands:\n"
                "  unit_tests: \"python --version\"\n"
                "  test_honesty: \"python --version\"\n"
                "required_gates:\n"
                "  unit_tests: true\n"
                "  independent_audit: true\n",
                encoding="utf-8",
            )
            budget = repo / "budget.json"
            budget.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "expected_paths": ["src.txt"],
                        "forbidden_paths": ["keys/**"],
                        "max_files": 2,
                        "max_changed_lines": 20,
                        "allow_binary_files": False,
                        "rollback": "git revert",
                    }
                ),
                encoding="utf-8",
            )
            (repo / "requirements-ci.lock").write_text(
                "ruff==0.15.22\n",
                encoding="utf-8",
            )
            source = repo / "src.txt"
            source.write_text("before\n", encoding="utf-8")
            self._git(repo, "add", ".")
            self._git(repo, "commit", "-qm", "base")
            base = self._git(repo, "rev-parse", "HEAD")

            source.write_text("after\n", encoding="utf-8")
            self._git(repo, "add", "src.txt")
            self._git(repo, "commit", "-qm", "change")
            head = self._git(repo, "rev-parse", "HEAD")

            evidence.mkdir()
            for name in ("unit_tests", "test_honesty"):
                command = run_gate.resolve_policy_command(policy, name)
                result = run_gate.execute_gate(
                    name,
                    evidence,
                    command,
                    policy,
                    name,
                )
                self.assertEqual(0, result["exit_code"])

            args = SimpleNamespace(
                repository="example/repository",
                branch="feature/test",
                base_commit=base,
                head_commit=head,
                evaluated_commit=head,
                policy="policy.yml",
                budget="budget.json",
                output_dir=str(evidence),
                repo_root=str(repo),
                builder="builder-agent",
                workflow_run="https://example.invalid/run/1",
                risk="medium",
                skill_version="0.1.0-test",
                doctrine_version="1.2",
                test_honesty_gate="test_honesty",
                unverified=["Independent review pending."],
                os_name="test-os",
                architecture="test-arch",
                runtime="python-test",
                validity_days=7,
            )
            previous = Path.cwd()
            try:
                os.chdir(repo)
                manifest = generator.generate(args)
            finally:
                os.chdir(previous)

            structure_errors = validator.validate_manifest(manifest)
            self.assertEqual([], structure_errors, "\n".join(structure_errors))
            binding_errors = validator.verify_bindings(
                manifest,
                evidence,
                policy,
                repo,
            )
            self.assertEqual([], binding_errors, "\n".join(binding_errors))

            log_path = evidence / "gates" / "unit_tests.log"
            log_path.write_text("tampered\n", encoding="utf-8")
            tamper_errors = validator.verify_bindings(
                manifest,
                evidence,
                policy,
                repo,
            )
            self.assertTrue(any("digest mismatch" in item for item in tamper_errors))


if __name__ == "__main__":
    unittest.main()
