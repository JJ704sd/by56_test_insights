from __future__ import annotations

import copy
import unittest

from qualityctl.risk import RISK_DIMENSIONS
from qualityctl.selection import evaluate_automation_candidate, select_regression_tests


def manifest() -> dict:
    dimensions = {
        name: {"status": "not_affected", "reason": "reviewed"}
        for name in RISK_DIMENSIONS
    }
    dimensions["side_effects"] = {
        "status": "affected",
        "evidence": "writes changed",
        "scenarios": ["retry stays idempotent"],
    }
    return {
        "schema_version": "1.0",
        "change_id": "C-1",
        "version_type": "daily",
        "changed_components": ["orders"],
        "agent_evaluation": {
            "required": False,
            "approved_by": "qa-owner",
            "evidence_ref": "policy://traditional-service",
        },
        "dependencies": {"upstream": [], "downstream": ["billing"]},
        "risk_signals": ["billing", "side_effect"],
        "dimensions": dimensions,
    }


def catalog() -> dict:
    return {
        "schema_version": "1.0",
        "automation_policy": {
            "version": "roi-v1",
            "source_ref": "approved://roi-v1",
            "approval_status": "APPROVED",
            "max_payback_months": 3,
            "min_monthly_net_minutes": 30,
        },
        "tests": [
            {
                "id": "SMOKE",
                "priority": "CP0",
                "components": ["unrelated"],
                "dimensions": ["business_flow"],
                "risks": [],
                "suites": ["smoke"],
                "labels": [],
                "automated": True,
            },
            {
                "id": "IDEMPOTENCY",
                "priority": "CP0",
                "components": ["billing"],
                "dimensions": ["side_effects"],
                "risks": ["billing"],
                "suites": ["core"],
                "labels": [],
                "automated": False,
                "automation_fit": {
                    "stable": True,
                    "repeatable": True,
                    "oracle": "state",
                    "runs_per_month": 10,
                    "manual_minutes": 20,
                    "residual_review_minutes_per_run": 2,
                    "maintenance_minutes_per_month": 20,
                    "flaky_investigation_minutes_per_month": 5,
                    "execution_cost_minutes_equivalent_per_month": 5,
                    "data_maintenance_minutes_per_month": 0,
                    "setup_minutes": 180,
                    "data_basis": "ESTIMATED",
                    "observation_window_days": 30,
                },
            },
            {
                "id": "UNRELATED",
                "priority": "CP2",
                "components": ["profile"],
                "dimensions": ["side_effects"],
                "risks": ["billing"],
                "suites": ["full"],
                "labels": [],
                "automated": False,
            },
        ]
    }


class SelectionTests(unittest.TestCase):
    def test_daily_selects_smoke_and_impacted_dependency(self) -> None:
        result = select_regression_tests(catalog(), manifest())
        self.assertEqual(result["status"], "READY")
        self.assertEqual(
            {row["test_id"] for row in result["selected"]}, {"SMOKE", "IDEMPOTENCY"}
        )
        self.assertEqual(result["automation_review"][0]["decision"], "CANDIDATE")

    def test_major_selects_full_catalog(self) -> None:
        change = manifest()
        change["version_type"] = "major"
        result = select_regression_tests(catalog(), change)
        self.assertEqual(len(result["selected"]), 3)

    def test_affected_dimension_without_test_requires_review(self) -> None:
        change = manifest()
        change["dimensions"]["permissions"] = {
            "status": "affected",
            "evidence": "role mapping changed",
            "scenarios": ["tenant B cannot read tenant A"],
        }
        change["risk_signals"].append("auth")
        modified_catalog = copy.deepcopy(catalog())
        modified_catalog["tests"] = [
            test for test in modified_catalog["tests"] if test["id"] != "UNRELATED"
        ]
        result = select_regression_tests(modified_catalog, change)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertTrue(any(gap["dimension"] == "permissions" for gap in result["coverage_gaps"]))

    def test_malformed_catalog_blocks_selection(self) -> None:
        broken = catalog()
        broken["tests"].append({"priority": "CP1"})
        result = select_regression_tests(broken, manifest())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["errors"])

    def test_unstable_candidate_is_not_automated_for_automation_sake(self) -> None:
        candidate = catalog()["tests"][1]
        candidate["automation_fit"]["stable"] = False
        result = evaluate_automation_candidate(
            candidate, catalog()["automation_policy"]
        )
        self.assertEqual(result["decision"], "DO_NOT_AUTOMATE_YET")
        self.assertIn("behavior is not stable", result["reasons"])

    def test_existing_automation_without_cost_data_needs_review(self) -> None:
        result = evaluate_automation_candidate(
            catalog()["tests"][0], catalog()["automation_policy"]
        )
        self.assertEqual(result["decision"], "INSUFFICIENT_DATA")

    def test_missing_setup_cost_is_insufficient_data(self) -> None:
        candidate = catalog()["tests"][1]
        del candidate["automation_fit"]["setup_minutes"]
        result = evaluate_automation_candidate(
            candidate, catalog()["automation_policy"]
        )
        self.assertEqual(result["decision"], "INSUFFICIENT_DATA")

    def test_negative_or_boolean_costs_are_rejected(self) -> None:
        candidate = catalog()["tests"][1]
        candidate["automation_fit"]["runs_per_month"] = -10
        candidate["automation_fit"]["manual_minutes"] = True
        result = evaluate_automation_candidate(
            candidate, catalog()["automation_policy"]
        )
        self.assertEqual(result["decision"], "INSUFFICIENT_DATA")

    def test_excessive_payback_is_not_a_candidate(self) -> None:
        candidate = catalog()["tests"][1]
        candidate["automation_fit"]["setup_minutes"] = 100000
        result = evaluate_automation_candidate(
            candidate, catalog()["automation_policy"]
        )
        self.assertEqual(result["decision"], "DO_NOT_AUTOMATE_YET")


if __name__ == "__main__":
    unittest.main()
