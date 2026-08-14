from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from qualityctl.validation import (
    SUPPORTED_VERSION,
    validate_agent_run,
    validate_agent_spec,
    validate_catalog,
    validate_manifest,
)
from qualityctl.mcp_server import (
    assess_automation_roi,
    decide_release_gate,
    evaluate_agent_evidence,
    select_regression_scope,
    validate_change_risks,
)
from mcp.server.mcpserver.exceptions import ToolError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = REPOSITORY_ROOT / "examples"
INVALID = REPOSITORY_ROOT / "tests" / "fixtures" / "invalid"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class ManifestValidationTests(unittest.TestCase):
    def test_supported_version_is_1_0(self) -> None:
        self.assertEqual(SUPPORTED_VERSION, "1.0")

    def test_unsupported_version_passes_structure_but_flagged_by_view_model(self) -> None:
        # Version 2.0 is structurally valid; the rule core must still produce
        # a gate answer and let the view_model mark it as not-supported.
        payload = load_json(EXAMPLES / "risk-manifest.json")
        payload["schema_version"] = "2.0"
        result = validate_manifest(payload)
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_example_manifest_passes(self) -> None:
        result = validate_manifest(load_json(EXAMPLES / "risk-manifest.json"))
        self.assertTrue(result.ok, msg=str(result.errors))
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.model)

    def test_missing_schema_version_rejected(self) -> None:
        payload = load_json(INVALID / "manifest_missing_schema_version.json")
        result = validate_manifest(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("schema_version" in err for err in result.errors))

    def test_non_string_schema_version_rejected(self) -> None:
        payload = load_json(INVALID / "manifest_unknown_version.json")
        # The payload here has schema_version=2.0 (a supported string).
        # It should now PASS structural validation; the view_model layer
        # detects unsupported major versions separately.
        result = validate_manifest(payload)
        self.assertTrue(result.ok, msg=str(result.errors))

        # But a non-string schema_version is still rejected at the boundary.
        bad = dict(payload)
        bad["schema_version"] = 2.0
        result_bad = validate_manifest(bad)
        self.assertFalse(result_bad.ok)
        self.assertTrue(any("schema_version" in err for err in result_bad.errors))

    def test_non_object_payload_rejected(self) -> None:
        result = validate_manifest("not-an-object")
        self.assertFalse(result.ok)
        self.assertTrue(any("JSON object" in err for err in result.errors))

    def test_invalid_version_type_rejected(self) -> None:
        payload = load_json(INVALID / "manifest_affected_missing_evidence.json")
        result = validate_manifest(payload)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("version_type", joined)
        self.assertIn("affected", joined)

    def test_affected_dimension_without_evidence_rejected(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        manifest["dimensions"]["business_flow"] = {"status": "affected"}
        result = validate_manifest(manifest)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("affected", joined)
        self.assertIn("evidence", joined)
        self.assertIn("scenarios", joined)

    def test_unknown_dimension_without_owner_rejected(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        manifest["dimensions"]["permissions"] = {
            "status": "unknown",
            "resolve_by": "2026-08-30",
        }
        result = validate_manifest(manifest)
        self.assertFalse(result.ok)
        self.assertTrue(any("owner" in err for err in result.errors))

    def test_extra_field_rejected(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        manifest["unknown_top_level"] = 1
        result = validate_manifest(manifest)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("unknown_top_level", joined)

    def test_blank_string_in_components_rejected(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        manifest["changed_components"] = ["", "x"]
        result = validate_manifest(manifest)
        self.assertFalse(result.ok)


class CatalogValidationTests(unittest.TestCase):
    def test_example_catalog_passes(self) -> None:
        result = validate_catalog(load_json(EXAMPLES / "test-catalog.json"))
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_empty_tests_rejected(self) -> None:
        result = validate_catalog({"schema_version": "1.0", "tests": []})
        self.assertFalse(result.ok)
        self.assertTrue(any("tests" in err for err in result.errors))

    def test_duplicate_test_id_rejected(self) -> None:
        payload = load_json(INVALID / "catalog_duplicate_id.json")
        result = validate_catalog(payload)
        self.assertFalse(result.ok)
        self.assertTrue(any("duplicate" in err for err in result.errors))

    def test_unapproved_policy_rejected(self) -> None:
        catalog = load_json(EXAMPLES / "test-catalog.json")
        catalog["automation_policy"]["approval_status"] = "MAYBE"
        result = validate_catalog(catalog)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertTrue("approval_status" in joined or "APPROVED" in joined)

    def test_negative_payback_rejected(self) -> None:
        catalog = load_json(EXAMPLES / "test-catalog.json")
        catalog["automation_policy"]["max_payback_months"] = -1
        result = validate_catalog(catalog)
        self.assertFalse(result.ok)


class AgentSpecValidationTests(unittest.TestCase):
    def test_example_spec_passes(self) -> None:
        result = validate_agent_spec(load_json(EXAMPLES / "agent-cases.json"))
        self.assertTrue(result.ok, msg=str(result.errors))

    def test_empty_cases_rejected(self) -> None:
        spec = load_json(EXAMPLES / "agent-cases.json")
        spec["cases"] = []
        result = validate_agent_spec(spec)
        self.assertFalse(result.ok)
        self.assertTrue(any("cases" in err for err in result.errors))

    def test_invalid_regex_pattern_rejected(self) -> None:
        payload = load_json(INVALID / "agent_spec_bad_regex.json")
        result = validate_agent_spec(payload)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("regex", joined)

    def test_number_assert_with_both_tolerances_rejected(self) -> None:
        spec = load_json(EXAMPLES / "agent-cases.json")
        spec["cases"][0]["assertions"].append(
            {
                "type": "number",
                "path": "x",
                "expected": 1.0,
                "absolute_tolerance": 0.1,
                "relative_tolerance": 0.1,
            }
        )
        result = validate_agent_spec(spec)
        self.assertFalse(result.ok)
        self.assertTrue(any("exactly one" in err for err in result.errors))

    def test_number_assert_with_no_tolerance_rejected(self) -> None:
        spec = load_json(EXAMPLES / "agent-cases.json")
        spec["cases"][0]["assertions"].append(
            {"type": "number", "path": "x", "expected": 1.0}
        )
        result = validate_agent_spec(spec)
        self.assertFalse(result.ok)

    def test_unapproved_threshold_rejected(self) -> None:
        spec = load_json(EXAMPLES / "agent-cases.json")
        spec["threshold_profile"]["approval_status"] = "GUESS"
        result = validate_agent_spec(spec)
        self.assertFalse(result.ok)


class AgentRunValidationTests(unittest.TestCase):
    def test_example_runs_pass(self) -> None:
        runs = load_jsonl(EXAMPLES / "agent-runs.jsonl")
        self.assertTrue(runs, "expected at least 9 rows in agent-runs.jsonl")
        for index, row in enumerate(runs):
            result = validate_agent_run(row)
            self.assertTrue(result.ok, msg=f"row {index}: {result.errors}")

    def test_missing_case_id_rejected(self) -> None:
        runs = load_jsonl(EXAMPLES / "agent-runs.jsonl")
        bad = dict(runs[0])
        bad.pop("case_id")
        result = validate_agent_run(bad)
        self.assertFalse(result.ok)
        self.assertTrue(any("case_id" in err for err in result.errors))

    def test_ok_status_without_output_rejected(self) -> None:
        runs = load_jsonl(EXAMPLES / "agent-runs.jsonl")
        bad = dict(runs[0])
        bad.pop("output")
        result = validate_agent_run(bad)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("output", joined)

    def test_runner_invalid_requires_error(self) -> None:
        runs = load_jsonl(EXAMPLES / "agent-runs.jsonl")
        bad = dict(runs[0])
        bad["technical_status"] = "runner_invalid"
        bad.pop("output", None)
        result = validate_agent_run(bad)
        self.assertFalse(result.ok)

    def test_manual_review_with_blank_field_rejected(self) -> None:
        runs = load_jsonl(EXAMPLES / "agent-runs.jsonl")
        bad = dict(runs[0])
        bad["manual_review"] = {"status": "pass"}
        result = validate_agent_run(bad)
        self.assertFalse(result.ok)


class McpBoundaryTests(unittest.TestCase):
    """Verify the production MCP tools reject invalid input via ToolError.

    The MCP SDK turns ``ToolError`` into a ``CallToolResult(is_error=True,
    content=[TextContent(...)])`` so the failure reaches the caller verbatim.
    These tests exercise the boundary without spinning up stdio.
    """

    def test_validate_change_risks_rejects_missing_schema_version(self) -> None:
        manifest = load_json(INVALID / "manifest_missing_schema_version.json")
        with self.assertRaises(ToolError) as ctx:
            validate_change_risks(manifest)
        self.assertIn("structural_validation", str(ctx.exception))
        self.assertIn("schema_version", str(ctx.exception))

    def test_validate_change_risks_passes_valid_example(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        result = validate_change_risks(manifest)
        self.assertEqual(result["status"], "READY")

    def test_select_regression_scope_rejects_bad_catalog(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        with self.assertRaises(ToolError) as ctx:
            select_regression_scope(
                load_json(INVALID / "catalog_duplicate_id.json"), manifest
            )
        self.assertIn("duplicate", str(ctx.exception))

    def test_evaluate_agent_evidence_rejects_bad_regex(self) -> None:
        spec = load_json(INVALID / "agent_spec_bad_regex.json")
        runs = [
            {
                "case_id": "C1",
                "run_id": "1",
                "evaluation_fingerprint": "f",
                "technical_status": "ok",
                "output": {},
            }
        ]
        with self.assertRaises(ToolError) as ctx:
            evaluate_agent_evidence(spec, runs)
        self.assertIn("regex", str(ctx.exception))

    def test_decide_release_gate_rejects_bad_catalog(self) -> None:
        manifest = load_json(EXAMPLES / "risk-manifest.json")
        with self.assertRaises(ToolError) as ctx:
            decide_release_gate(
                manifest, load_json(INVALID / "catalog_duplicate_id.json")
            )
        self.assertIn("duplicate", str(ctx.exception))

    def test_assess_automation_roi_requires_automation_fit(self) -> None:
        with self.assertRaises(ToolError) as ctx:
            assess_automation_roi(
                candidate={"id": "X", "automated": False},
                policy={
                    "version": "roi-v1",
                    "source_ref": "approved://roi-v1",
                    "approval_status": "APPROVED",
                    "max_payback_months": 3,
                    "min_monthly_net_minutes": 30,
                },
            )
        self.assertIn("automation_fit", str(ctx.exception))

    def test_assess_automation_roi_requires_policy_version(self) -> None:
        with self.assertRaises(ToolError) as ctx:
            assess_automation_roi(
                candidate={"id": "X", "automated": False, "automation_fit": {}},
                policy={"source_ref": "approved://roi-v1"},
            )
        self.assertIn("version", str(ctx.exception))


class ErrorPathFormatTests(unittest.TestCase):
    """Verify that error paths render as dotted/bracketed paths, not Pydantic's
    default dotted-only output. LLM callers can locate a field by reading the
    string verbatim.
    """

    def test_list_index_uses_brackets(self) -> None:
        payload = {
            "schema_version": "1.0",
            "tests": [
                {"id": "OK", "automated": True},
                {
                    "id": "BAD",
                    "automated": True,
                    "automation_fit": {
                        "stable": True,
                        "repeatable": True,
                        "oracle": "exact",
                        "runs_per_month": 0,  # invalid
                        "manual_minutes": 0,
                        "residual_review_minutes_per_run": 0,
                        "maintenance_minutes_per_month": 0,
                        "flaky_investigation_minutes_per_month": 0,
                        "execution_cost_minutes_equivalent_per_month": 0,
                        "data_maintenance_minutes_per_month": 0,
                        "setup_minutes": 0,
                        "data_basis": "ESTIMATED",
                        "observation_window_days": 30,
                    },
                },
            ],
        }
        result = validate_catalog(payload)
        joined = " ".join(result.errors)
        self.assertIn("tests[1].automation_fit.runs_per_month", joined)
        self.assertNotIn("tests.. 1..", joined)

    def test_deeply_nested_path_is_dotted(self) -> None:
        payload = {
            "schema_version": "1.0",
            "change_id": "X",
            "version_type": "daily",
            "changed_components": ["a"],
            "agent_evaluation": {
                "required": False,
                "approved_by": "q",
                "evidence_ref": "p://x",
            },
            "dependencies": {"upstream": [], "downstream": []},
            "risk_signals": [],
            "dimensions": {
                "business_flow": {"status": "affected"},
                "exception_paths": {"status": "not_affected", "reason": "ok"},
                "boundaries": {"status": "not_affected", "reason": "ok"},
                "permissions": {"status": "unknown"},
                "data_consistency": {"status": "not_affected", "reason": "ok"},
                "upstream_downstream": {"status": "not_affected", "reason": "ok"},
                "side_effects": {"status": "not_affected", "reason": "ok"},
                "recoverability": {"status": "not_affected", "reason": "ok"},
            },
        }
        result = validate_manifest(payload)
        joined = " ".join(result.errors)
        self.assertIn("dimensions.business_flow", joined)
        self.assertIn("dimensions.permissions", joined)
        self.assertNotIn("dimensions..", joined)


class ResultDictShapeTests(unittest.TestCase):
    def test_to_dict_is_stable(self) -> None:
        result = validate_manifest({"schema_version": "1.0"})
        self.assertIn("ok", result.to_dict())
        self.assertIn("errors", result.to_dict())
        self.assertIsInstance(result.to_dict()["errors"], list)


class CliErrorFormatTests(unittest.TestCase):
    """Lock the on-the-wire JSON shape of the CLI's structured validation error.

    The post-Round-1 refactor moved per-run validation into a single helper
    (``qualityctl.validation.validate_agent_runs``) shared by the CLI and the
    MCP server. To keep downstream consumers stable, the CLI emits exactly one
    stderr JSON object per invocation, with errors collapsed into a single
    ``; ``-joined entry per failing row (matching the MCP helper shape).
    """

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "qualityctl", *args],
            cwd=str(REPOSITORY_ROOT),
            capture_output=True,
            text=True,
        )

    def test_cli_invalid_manifest_writes_structured_json(self) -> None:
        result = self._run_cli(
            "risk-check", str(INVALID / "manifest_missing_schema_version.json")
        )
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["command"], "risk-check")
        self.assertEqual(payload["kind"], "structural_validation")
        self.assertEqual(payload["input"], "manifest")
        self.assertIsInstance(payload["errors"], list)
        self.assertGreater(len(payload["errors"]), 0)
        for entry in payload["errors"]:
            self.assertIsInstance(entry, str)

    def test_cli_invalid_run_collapses_errors_with_semicolon(self) -> None:
        """A single failing row yields one entry ``runs[N]: err1; err2``;
        matches the MCP helper's shape so consumers can parse both identically.
        """
        with tempfile.NamedTemporaryFile(
            "w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as handle:
            # Bad enum + missing error field => two Pydantic errors per row.
            handle.write(
                '{"case_id": "C", "run_id": "1", "technical_status": "bogus"}\n'
            )
            path = handle.name
        try:
            result = self._run_cli(
                "agent-eval",
                str(EXAMPLES / "agent-cases.json"),
                path,
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stderr)
            self.assertEqual(payload["kind"], "structural_validation")
            self.assertEqual(payload["input"], "agent_run")
            self.assertEqual(
                len(payload["errors"]),
                1,
                "expected one entry per failing row, joined with '; '",
            )
            self.assertTrue(payload["errors"][0].startswith("runs[0]:"))
            self.assertIn("; ", payload["errors"][0])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()