from __future__ import annotations

import copy
import unittest

from qualityctl.agent_eval import evaluate_agent_runs, wilson_interval


def spec() -> dict:
    return {
        "schema_version": "1.0",
        "agent_version": "a1",
        "dataset_version": "d1",
        "evaluation_fingerprint": "sha256:test-fixture-v1",
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
                "min_pass_rate": 1.0,
                "assertions": [
                    {
                        "type": "number",
                        "path": "price",
                        "expected": 10.0,
                        "absolute_tolerance": 0.01,
                    }
                ],
            }
        ],
    }


def passing_runs() -> list[dict]:
    return [
        {
            "case_id": "HIGH",
            "run_id": str(index),
            "evaluation_fingerprint": "sha256:test-fixture-v1",
            "technical_status": "ok",
            "output": {"price": 10.0},
        }
        for index in range(1, 4)
    ]


class AgentEvaluationTests(unittest.TestCase):
    def test_all_repeated_runs_pass(self) -> None:
        result = evaluate_agent_runs(spec(), passing_runs())
        self.assertEqual(result["gate"], "PASS")
        self.assertEqual(result["run_counts"]["passed"], 3)
        self.assertIsNotNone(result["case_results"][0]["wilson_95"])

    def test_regex_matching_rejects_oversized_output_strings(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"][0]["assertions"] = [
            {"type": "matches", "path": "value", "pattern": ".+"}
        ]
        runs = passing_runs()
        for run in runs:
            run["output"] = {"value": "a" * 4097}

        result = evaluate_agent_runs(evaluation_spec, runs)

        self.assertEqual(result["gate"], "FAIL")
        self.assertEqual(result["run_counts"]["deterministic_failures"], 3)
        detail = result["case_results"][0]["runs"][0]["assertions"][0]["detail"]
        self.assertIn("4096", detail)
        self.assertNotIn("a" * 4097, detail)

    def test_regex_matching_success_reports_a_match(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"][0]["assertions"] = [
            {"type": "matches", "path": "value", "pattern": ".+"}
        ]
        runs = passing_runs()
        for run in runs:
            run["output"] = {"value": "ok"}

        result = evaluate_agent_runs(evaluation_spec, runs)

        self.assertEqual(result["gate"], "PASS")
        detail = result["case_results"][0]["runs"][0]["assertions"][0]["detail"]
        self.assertIn("matches", detail)
        self.assertNotIn("does not match", detail)

    def test_one_high_risk_failure_is_not_averaged_away(self) -> None:
        runs = passing_runs()
        runs[1]["output"]["price"] = 11.0
        result = evaluate_agent_runs(spec(), runs)
        self.assertEqual(result["gate"], "FAIL")
        self.assertEqual(result["run_counts"]["deterministic_failures"], 1)

    def test_high_risk_cannot_disable_hard_fail(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"][0]["hard_fail_on_any"] = False
        evaluation_spec["cases"][0]["min_pass_rate"] = 0.5
        runs = passing_runs()
        runs[0]["output"]["price"] = 11.0
        result = evaluate_agent_runs(evaluation_spec, runs)
        self.assertEqual(result["gate"], "FAIL")
        self.assertTrue(result["case_results"][0]["hard_fail_on_any"])

    def test_runner_invalid_is_separate_and_blocks_evidence(self) -> None:
        runs = passing_runs()
        runs[2] = {
            "case_id": "HIGH",
            "run_id": "3",
            "evaluation_fingerprint": "sha256:test-fixture-v1",
            "technical_status": "runner_invalid",
            "error": "collector crashed",
        }
        result = evaluate_agent_runs(spec(), runs)
        self.assertEqual(result["gate"], "BLOCKED")
        self.assertEqual(result["run_counts"]["runner_invalid"], 1)
        self.assertEqual(result["run_counts"]["technical_failures"], 0)

    def test_missing_medium_semantic_review_requires_review(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"] = [
            {
                "id": "SEM",
                "risk": "medium",
                "planned_runs": 3,
                "min_pass_rate": 1.0,
                "hard_fail_on_any": False,
                "semantic_review_required": True,
                "assertions": [{"type": "equals", "path": "format", "expected": "ok"}],
            }
        ]
        runs = [
            {
                "case_id": "SEM",
                "run_id": str(index),
                "evaluation_fingerprint": "sha256:test-fixture-v1",
                "technical_status": "ok",
                "output": {"format": "ok"},
            }
            for index in range(1, 4)
        ]
        result = evaluate_agent_runs(evaluation_spec, runs)
        self.assertEqual(result["gate"], "REVIEW_REQUIRED")

    def test_unapproved_high_risk_threshold_blocks_pass(self) -> None:
        evaluation_spec = copy.deepcopy(spec())
        evaluation_spec["threshold_profile"]["approval_status"] = "UNAPPROVED"
        result = evaluate_agent_runs(evaluation_spec, passing_runs())
        self.assertEqual(result["gate"], "BLOCKED")

    def test_extra_runs_outside_frozen_plan_block(self) -> None:
        runs = passing_runs()
        runs.append(
            {
                "case_id": "HIGH",
                "run_id": "4",
                "evaluation_fingerprint": "sha256:test-fixture-v1",
                "technical_status": "ok",
                "output": {"price": 10.0},
            }
        )
        result = evaluate_agent_runs(spec(), runs)
        self.assertEqual(result["gate"], "BLOCKED")
        self.assertTrue(result["case_results"][0]["errors"])

    def test_wilson_reports_uncertainty_for_three_of_three(self) -> None:
        interval = wilson_interval(3, 3)
        self.assertIsNotNone(interval)
        assert interval is not None
        self.assertLess(interval[0], 0.5)
        self.assertEqual(interval[1], 1.0)

    def test_missing_frozen_identity_blocks(self) -> None:
        evaluation_spec = spec()
        del evaluation_spec["execution_profile"]
        result = evaluate_agent_runs(evaluation_spec, passing_runs())
        self.assertEqual(result["gate"], "BLOCKED")

    def test_mixed_fingerprint_blocks(self) -> None:
        runs = passing_runs()
        runs[0]["evaluation_fingerprint"] = "sha256:other"
        result = evaluate_agent_runs(spec(), runs)
        self.assertEqual(result["gate"], "BLOCKED")
        self.assertTrue(any("fingerprint mismatch" in error for error in result["errors"]))

    def test_empty_required_assertion_blocks(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"][0]["assertions"] = [{"type": "required"}]
        result = evaluate_agent_runs(evaluation_spec, passing_runs())
        self.assertEqual(result["gate"], "BLOCKED")

    def test_unattributed_manual_pass_does_not_count(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"] = [
            {
                "id": "SEM",
                "risk": "medium",
                "planned_runs": 3,
                "min_pass_rate": 1.0,
                "semantic_review_required": True,
                "assertions": [{"type": "equals", "path": "format", "expected": "ok"}],
            }
        ]
        runs = [
            {
                "case_id": "SEM",
                "run_id": str(index),
                "evaluation_fingerprint": "sha256:test-fixture-v1",
                "technical_status": "ok",
                "manual_review": "pass",
                "output": {"format": "ok"},
            }
            for index in range(1, 4)
        ]
        result = evaluate_agent_runs(evaluation_spec, runs)
        # Bare-string manual_review is malformed (Pydantic schema rejects the
        # row); the evaluation is therefore BLOCKED rather than quietly
        # promoted to a missing-review REVIEW_REQUIRED.
        self.assertEqual(result["gate"], "BLOCKED")
        self.assertTrue(
            any("manual_review" in err for err in result["errors"]),
            result["errors"],
        )

    def test_medium_risk_single_sample_is_blocked(self) -> None:
        evaluation_spec = spec()
        evaluation_spec["cases"][0]["risk"] = "medium"
        evaluation_spec["cases"][0]["planned_runs"] = 1
        result = evaluate_agent_runs(evaluation_spec, passing_runs()[:1])
        self.assertEqual(result["gate"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
