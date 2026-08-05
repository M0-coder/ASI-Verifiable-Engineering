from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    ROOT
    / "skills"
    / "asi-verifiable-engineering"
    / "scripts"
    / "validate_policy.py"
)


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy_validator = load_module("policy_contract_validator", VALIDATOR)


class IndependentAuditPolicyTests(unittest.TestCase):
    def test_independent_audit_command_is_mandatory(self) -> None:
        source = (ROOT / ".asi" / "policy.yml").read_text(encoding="utf-8")
        line = next(
            item
            for item in source.splitlines()
            if item.startswith("  independent_audit:")
        )
        invalid = source.replace(line + "\n", "", 1)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.yml"
            path.write_text(invalid, encoding="utf-8")
            errors = policy_validator.validate_policy(path)
        self.assertTrue(
            any("independent_audit" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
