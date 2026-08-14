from __future__ import annotations

import copy
import unittest

from qualityctl.gate import decide_quality_gate
from qualityctl.risk import RISK_DIMENSIONS


def manifest() -> dict:
    return {
        "schema_version": "1.0",
        "change_id": "C-GATE-1",
        "version_type": "daily",
        "changed_components": ["orders"],
        "agent_evaluation": {
            "required": False,
            "approved_by": "qa-owner",
            "evidence_ref": "policy://traditional-service",
        },
        "dependencies": {"upstream": [], "downstream": []},
        "risk_signals": [],
        "dimensions": {
            name: {"status": "not_affected", "reason": "reviewed source evidence"}
            for name in RISK_DIMENSIONS
        },
    }


def catalog() -> dict:
    return {
        "schema_version": "1.0",
        "tests": [
            {
                "id": "SMOKE",
                "priority": "CP0",
                "components": ["orders"],
                "dimensions": ["business_flow"],
                "risks": [],
                "suites": ["smoke"],
                "labels": [],
                "automated": True,
            }
        ]
    }


class QualityGateTests(unittest.TestCase):
    def test_recomputed_ready_evidence_allows_release(self) -> None:
        result = decide_quality_gate(
            manifest(),
            catalog(),
        )
        self.assertEqual(result["gate"], "PASS")
        self.assertTrue(result["release_allowed"])

    def test_malformed_raw_evidence_cannot_be_replaced_by_claimed_pass(self) -> None:
        broken = manifest()
        del broken["dimensions"]["permissions"]
        result = decide_quality_gate(
            broken,
            catalog(),
        )
        self.assertEqual(result["gate"], "BLOCKED")
        self.assertFalse(result["release_allowed"])

    def test_unknown_risk_requires_review(self) -> None:
        change = manifest()
        change["dimensions"]["permissions"] = {
            "status": "unknown",
            "owner": "security",
            "resolve_by": "2026-08-13",
        }
        result = decide_quality_gate(
            change,
            catalog(),
        )
        self.assertEqual(result["gate"], "REVIEW_REQUIRED")

    def test_agent_applicability_needs_auditable_policy(self) -> None:
        change = manifest()
        del change["agent_evaluation"]["evidence_ref"]
        result = decide_quality_gate(change, catalog())
        self.assertEqual(result["gate"], "BLOCKED")

    def test_agent_failure_cannot_be_voted_away(self) -> None:
        spec = {
            "schema_version": "1.0",
            "agent_version": "a1",
            "dataset_version": "d1",
            "evaluation_fingerprint": "sha256:gate-fixture-v1",
            "execution_profile": {
                "prompt_version": "prompt-v1",
                "model_id": "test-model",
                "model_parameters": {"temperature": 0},
                "toolset_version": "tools-v1",
                "knowledge_snapshot": "kb-v1",
                "runner_version": "runner-v1",
            },
            "threshold_profile": {
                "version": "t1",
                "source_ref": "approved://t1",
                "approval_status": "APPROVED",
            },
            "cases": [
                {
                    "id": "HIGH",
                    "risk": "high",
                    "planned_runs": 3,
                    "min_pass_rate": 0.5,
                    "hard_fail_on_any": False,
                    "assertions": [
                        {"type": "equals", "path": "status", "expected": "ok"}
                    ],
                }
            ],
        }
        runs = [
            {
                "case_id": "HIGH",
                "run_id": str(index),
                "evaluation_fingerprint": "sha256:gate-fixture-v1",
                "technical_status": "ok",
                "output": {"status": "bad" if index == 1 else "ok"},
            }
            for index in range(1, 4)
        ]
        change = manifest()
        change["agent_evaluation"] = {
            "required": True,
            "approved_by": "agent-qa-owner",
            "evidence_ref": "policy://agent-project",
        }
        result = decide_quality_gate(
            change,
            catalog(),
            agent_spec=spec,
            agent_runs=runs,
        )
        self.assertEqual(result["gate"], "FAIL")
        self.assertFalse(result["release_allowed"])

    def test_regression_gap_prevents_pass(self) -> None:
        change = copy.deepcopy(manifest())
        change["dimensions"]["permissions"] = {
            "status": "affected",
            "evidence": "role mapping changed",
            "scenarios": ["cross-tenant read is denied"],
        }
        change["risk_signals"] = ["auth"]
        result = decide_quality_gate(
            change,
            catalog(),
        )
        self.assertEqual(result["gate"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
