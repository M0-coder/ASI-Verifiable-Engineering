from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
FINALIZER = (
    ROOT
    / "skills"
    / "asi-verifiable-engineering"
    / "scripts"
    / "finalize_measured_evidence.py"
)


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


finalizer = load_module("preoperational_finalizer", FINALIZER)


class PreoperationalLevelTests(unittest.TestCase):
    def test_external_governance_failures_do_not_downgrade_technical_t4(self) -> None:
        manifest = {
            "evidence_level": "E5",
            "assurance_level": "T3",
            "gates": {
                "integrity": "passed",
                "build": "passed",
                "unit_tests": "passed",
                "branch_protection": "failed",
                "independent_audit": "failed",
                "target_environment_observation": "failed",
            },
        }
        finalizer._finalize_preoperational_level(manifest)
        self.assertEqual("E6", manifest["evidence_level"])
        self.assertEqual("T4", manifest["assurance_level"])

    def test_technical_failure_downgrades_preoperational_level(self) -> None:
        manifest = {
            "evidence_level": "E6",
            "assurance_level": "T4",
            "gates": {
                "integrity": "passed",
                "build": "failed",
                "branch_protection": "failed",
                "independent_audit": "failed",
                "target_environment_observation": "failed",
            },
        }
        finalizer._finalize_preoperational_level(manifest)
        self.assertEqual("E5", manifest["evidence_level"])
        self.assertEqual("T3", manifest["assurance_level"])


if __name__ == "__main__":
    unittest.main()
