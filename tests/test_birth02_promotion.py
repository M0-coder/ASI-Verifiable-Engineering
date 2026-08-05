from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "asi-verifiable-engineering"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


decision_engine = load_module("birth02_decision", SCRIPTS / "evaluate_change.py")
protection = load_module(
    "birth02_protection",
    SCRIPTS / "check_branch_protection.py",
)


class BranchProtectionTests(unittest.TestCase):
    def protected_branch(self) -> dict[str, object]:
        return {
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": True,
            },
            "required_status_checks": {
                "strict": True,
                "checks": [
                    {
                        "context": "Verify measured gates and derive decision",
                        "app_id": 1,
                    }
                ],
            },
            "enforce_admins": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
        }

    def test_strict_main_protection_passes(self) -> None:
        report = protection.evaluate_protection(
            self.protected_branch(),
            protection.EXPECTED_CHECK,
        )
        self.assertTrue(report["passed"])
        self.assertEqual([], report["missing_or_invalid_controls"])

    def test_missing_required_check_blocks(self) -> None:
        data = self.protected_branch()
        data["required_status_checks"] = {
            "strict": True,
            "checks": [],
        }
        report = protection.evaluate_protection(data, protection.EXPECTED_CHECK)
        self.assertFalse(report["passed"])
        self.assertIn(
            "required_asi_status_check",
            report["missing_or_invalid_controls"],
        )


class ReachableApprovalTests(unittest.TestCase):
    def complete_manifest(self) -> dict[str, object]:
        source = json.loads(
            (SKILL / "assets" / "evidence-manifest.example.json").read_text(
                encoding="utf-8"
            )
        )
        manifest = copy.deepcopy(source)
        policy = decision_engine.parse_policy(ROOT / ".asi" / "policy.yml")
        required = sorted(policy["required_gates"])
        measured_controls = sorted(set(required) | {"test_honesty"})

        artifacts: list[dict[str, str]] = []
        commands: list[dict[str, object]] = []
        measured_evidence: dict[str, dict[str, str]] = {}
        for index, name in enumerate(measured_controls, start=1):
            result_digest = "sha256:" + f"{index:064x}"[-64:]
            log_digest = "sha256:" + f"{index + 100:064x}"[-64:]
            result_path = f"gates/{name}.json"
            log_path = f"gates/{name}.log"
            artifacts.extend(
                [
                    {
                        "path": result_path,
                        "digest": result_digest,
                        "producer": "test",
                    },
                    {
                        "path": log_path,
                        "digest": log_digest,
                        "producer": "test",
                    },
                ]
            )
            commands.append(
                {
                    "name": name,
                    "argv": ["python", name],
                    "command": f"python {name}",
                    "started_at": "2026-08-05T15:00:00Z",
                    "finished_at": "2026-08-05T15:00:01Z",
                    "duration_seconds": 1.0,
                    "exit_code": 0,
                    "result_artifact": result_path,
                    "result_digest": result_digest,
                    "log_artifact": log_path,
                    "log_digest": log_digest,
                }
            )
            measured_evidence[name] = {
                "result_artifact": result_path,
                "result_digest": result_digest,
                "log_artifact": log_path,
                "log_digest": log_digest,
            }

        manifest.update(
            {
                "risk": "high",
                "evidence_level": "E7",
                "assurance_level": "T5",
                "independence": ["I2", "I3"],
                "commands": commands,
                "gates": {name: "passed" for name in required},
                "gate_evidence": {
                    name: measured_evidence[name] for name in required
                },
                "artifacts": artifacts,
                "unverified": [],
                "residual_risks": [],
                "conditions": [],
                "decision": "BLOCKED",
                "approved_by": ["independent-reviewer"],
                "rollback": {
                    "reference": "git revert",
                    "tested": True,
                },
                "review": {
                    "builder": "builder-user",
                    "auditor": "independent-reviewer",
                    "same_context": False,
                    "human_review": {
                        "required": True,
                        "completed": True,
                        "mode": "targeted",
                    },
                },
            }
        )
        honesty = measured_evidence["test_honesty"]
        manifest["test_honesty"] = {
            "method": "adversarial_control_tests",
            "result_artifact": honesty["result_artifact"],
            "result_digest": honesty["result_digest"],
            "evidence": honesty["log_artifact"],
            "digest": honesty["log_digest"],
        }
        return manifest

    def test_complete_high_risk_evidence_is_derivably_approved(self) -> None:
        policy = decision_engine.parse_policy(ROOT / ".asi" / "policy.yml")
        result = decision_engine.evaluate_change(policy, self.complete_manifest())
        self.assertEqual("APPROVED", result["decision"])
        self.assertEqual("BLOCKED", result["claimed_decision"])
        self.assertEqual([], result["blockers"])
        self.assertEqual("targeted_risk_review_completed", result["human_action"])
        self.assertFalse(result["line_by_line_review_required"])


if __name__ == "__main__":
    unittest.main()
