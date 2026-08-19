from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from jsonschema import Draft7Validator

from qualityctl.evidence import canonical_digest, compare_scopes, verify_change_bundle
from qualityctl.iteration import (
    APPROVED_CORE_COMMIT,
    APPROVED_CORE_VERSION,
    ITERATION_INDEX_CONTRACT,
    ITERATION_SUMMARY_CONTRACT,
    AdjudicationV1,
    EvidenceLedgerV1,
    IterationIndexV1,
    IterationSummaryV1,
    validate_change_evidence_report,
    validate_evidence_ledger,
    validate_iteration_index,
    validate_iteration_summary,
    summarize_iteration,
)
from qualityctl.schemas import evidence_schema_path
from qualityctl.io import read_json


ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "ff11ddb7615ede298d26e2d5b7e3bc5d75664bc6"


def _fixture_bundle() -> dict:
    # Keep the P1b fixture independent of real business evidence while reusing
    # the already-sanitized input shape exercised by the P1 evidence tests.
    from tests.test_evidence import _fixture_bundle as existing_fixture_bundle

    bundle = existing_fixture_bundle()
    draft = compare_scopes(
        bundle["manual_scope"],
        bundle["raw"]["tool_scope"],
        identity=bundle["identity"],
    )
    bundle["adjudication"]["difference_draft_digest"] = draft["decision_digest"]
    return bundle


def _bytes_digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _write_artifact(root: Path, name: str, payload: object) -> dict[str, object]:
    path = root / name
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(data)
    return {
        "path": name,
        "media_type": "application/json",
        "size": len(data),
        "digest": _bytes_digest(data),
    }


def _policy() -> dict[str, object]:
    return {
        "version": "fixture-roi-policy@1.0",
        "ref": "fixture://policy/roi-001",
        "digest": "sha256:fixture-roi-policy",
        "approved_by": "fixture-policy-owner",
        "approved_at": "2026-08-18T08:00:00+08:00",
        "valid_until": "2026-12-31T23:59:59+08:00",
        "formula_version": "roi-formula@1.0",
        "costs": {
            "build_minutes": 120,
            "gross_savings_minutes": 420,
            "maintenance_minutes": 20,
            "false_positive_minutes": 10,
            "flaky_minutes": 10,
            "runner_minutes": 10,
            "llm_minutes": 0,
            "run_minutes": 10,
            "data_minutes": 10,
        },
    }


def _versions() -> dict[str, object]:
    return {
        "schema_versions": {
            "pilot_evidence": "1.0",
            "manifest": "1.0",
            "catalog": "1.0",
            "agent_spec": "1.0",
            "agent_run": "1.0",
            "difference_draft": "1.0",
            "adjudication": "1.0",
            "change_report": "1.0",
            "ledger": "1.0",
            "iteration_index": "1.0",
            "iteration_summary": "1.0",
        },
        "qualityctl_version": "0.1.0",
        "core_version": APPROVED_CORE_VERSION,
        "core_commit": APPROVED_CORE_COMMIT,
        "python_version": "3.11",
        "catalog_version": "fixture-catalog@1.0",
        "mapping_version": "fixture-mapping@1.0",
        "threshold_version": "fixture-threshold@1.0",
        "roi_policy_version": "fixture-roi-policy@1.0",
        "canonicalization_version": "canonical-json@1.0",
        "writer_reader_matrix": "fixture-writer-reader@1.0",
        "matrix_approved_by": "fixture-release-owner",
        "matrix_approved_at": "2026-08-18T08:00:00+08:00",
        "matrix_valid_until": "2026-12-31T23:59:59+08:00",
    }


def _attestations() -> dict[str, object]:
    return {
        "secret_scan": {
            "status": "PASS",
            "version": "fixture-scanner@1.0",
            "ref": "fixture://scanner/001",
            "digest": "sha256:fixture-scanner",
        },
        "controlled_storage": {
            "status": "PASS",
            "version": "fixture-storage@1.0",
            "ref": "fixture://storage/001",
            "digest": "sha256:fixture-storage",
        },
        "formal_result": {
            "status": "RECORDED",
            "version": "fixture-authority@1.0",
            "ref": "fixture://authority/001",
            "digest": "sha256:fixture-authority",
            "release_effect": "NONE",
        },
        "least_privilege": {
            "status": "PASS",
            "version": "fixture-permissions@1.0",
            "ref": "fixture://permissions/001",
            "digest": "sha256:fixture-permissions",
        },
    }


def _build_iteration(root: Path) -> dict[str, object]:
    bundle = _fixture_bundle()
    draft = compare_scopes(
        bundle["manual_scope"],
        bundle["raw"]["tool_scope"],
        identity=bundle["identity"],
    )
    bundle["adjudication"]["difference_draft_digest"] = draft["decision_digest"]
    report = verify_change_bundle(bundle)
    ledger_entry = {
        "pilot_id": "fixture-pilot",
        "iteration_id": "fixture-iteration-001",
        "change_id": "FIXTURE-CHANGE-001",
        "run_id": "fixture-run-001",
        "status": report["status"],
        "evidence_digest": report["decision_digest"],
        "attempt_ids": ["fixture-attempt-001"],
        "out_of_plan": False,
        "report_ref": "fixture://report/001",
    }
    ledger = {
        "contract": "evidence-ledger@1.0",
        "schema_version": "1.0",
        "status": "FROZEN",
        "pilot_id": "fixture-pilot",
        "iteration_id": "fixture-iteration-001",
        "entries": [ledger_entry],
        "attempts": [
            {
                "pilot_id": "fixture-pilot",
                "iteration_id": "fixture-iteration-001",
                "change_id": "FIXTURE-CHANGE-001",
                "run_id": "fixture-run-001",
                "attempt_id": "fixture-attempt-001",
                "kind": "initial",
                "out_of_plan": False,
                "digest": "sha256:fixture-attempt-001",
                "started_at": "2026-08-18T08:05:00+08:00",
                "ended_at": "2026-08-18T08:05:01+08:00",
                "status": "PASS",
                "ref": "fixture://attempt/001",
            }
        ],
        "conflicts": [],
        "formal_release_effect": "NONE",
        "decision_digest": "sha256:fixture-ledger-decision",
    }
    refs = {
        "bundle": _write_artifact(root, "bundle.json", bundle),
        "draft": _write_artifact(root, "draft.json", draft),
        "adjudication": _write_artifact(root, "adjudication.json", bundle["adjudication"]),
        "report": _write_artifact(root, "report.json", report),
        "ledger": _write_artifact(root, "ledger.json", ledger),
    }
    return {
        "contract": ITERATION_INDEX_CONTRACT,
        "schema_version": "1.0",
        "identity": {
            "pilot_id": "fixture-pilot",
            "iteration_id": "fixture-iteration-001",
            "evidence_class": "FIXTURE",
        },
        "freeze": {
            "frozen_at": "2026-08-18T08:10:00+08:00",
            "frozen_by": "fixture-test-owner",
            "freeze_ref": "fixture://freeze/iteration-001",
            "freeze_digest": "sha256:fixture-freeze",
        },
        "activation": {
            "r2_g0_status": "BLOCKED_BY_R2_G0",
            "approval_ref": "fixture://g0/approval",
            "approval_digest": "sha256:fixture-g0-approval",
            "day0": None,
        },
        "versions": _versions(),
        "ledger": refs["ledger"],
        "changes": [
            {
                "identity": {
                    "pilot_id": "fixture-pilot",
                    "iteration_id": "fixture-iteration-001",
                    "change_id": "FIXTURE-CHANGE-001",
                    "run_id": "fixture-run-001",
                },
                "status": report["status"],
                "evidence_digest": report["decision_digest"],
                "report": refs["report"],
                "bundle": refs["bundle"],
                "draft": refs["draft"],
                "adjudication": refs["adjudication"],
                "attempt_ids": ["fixture-attempt-001"],
                "out_of_plan": False,
            }
        ],
        "formal_evidence": {
            "planned_runs": 1,
            "observed_runs": 1,
            "failures": 0,
            "attributed_failures": 0,
            "runner_invalid": 0,
            "retry_groups": 0,
            "retry_groups_complete": 0,
            "tool_added_items": 0,
            "tool_false_positive": 0,
            "high_risk_false_negative": 0,
            "error_pass": 0,
            "refs": [],
        },
        "policy": _policy(),
        "attestations": _attestations(),
        "formal_release_effect": "NONE",
    }


class P1B001To004IntegrityTests(unittest.TestCase):
    def test_adjudication_identity_must_match_bundle(self) -> None:
        bundle = _fixture_bundle()
        bundle["adjudication"]["identity"]["run_id"] = "other-run"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "ADJUDICATION_IDENTITY_MISMATCH")

    def test_stale_draft_digest_is_blocked(self) -> None:
        bundle = _fixture_bundle()
        bundle["adjudication"]["difference_draft_digest"] = "sha256:stale-draft"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "ADJUDICATION_DIGEST_MISMATCH")

    def test_attestation_pending_is_not_success(self) -> None:
        bundle = _fixture_bundle()
        for attestation in bundle["attestations"].values():
            attestation["status"] = "PENDING"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "ATTESTATION_NOT_APPROVED")

    def test_unknown_core_is_not_compatible(self) -> None:
        bundle = _fixture_bundle()
        bundle["versions"]["core_version"] = "0.1.x"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "UNSUPPORTED_CORE")


class P1B002And005SchemaParityTests(unittest.TestCase):
    def test_strict_models_reject_unknown_fields_at_each_contract_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = _build_iteration(Path(directory))
        for payload, validator in (
            (index, validate_iteration_index),
            ({**index, "unexpected": True}, validate_iteration_index),
        ):
            result = validator(payload)
            if payload is index:
                self.assertTrue(result.ok, result.errors)
            else:
                self.assertFalse(result.ok)

        ledger = {
            "contract": "evidence-ledger@1.0",
            "schema_version": "1.0",
            "status": "FROZEN",
            "pilot_id": "fixture-pilot",
            "iteration_id": "fixture-iteration-001",
            "entries": [],
            "attempts": [],
            "conflicts": [],
            "formal_release_effect": "NONE",
            "decision_digest": "sha256:ledger",
        }
        self.assertTrue(validate_evidence_ledger(ledger).ok)
        self.assertFalse(validate_evidence_ledger({**ledger, "extra": 1}).ok)
        self.assertFalse(validate_evidence_ledger({**ledger, "entries": [{"extra": 1}]}).ok)

    def test_json_schema_and_pydantic_agree_on_positive_and_negative_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = _build_iteration(Path(directory))
        summary = summarize_iteration(index, base_dir=directory)
        for kind, payload, validator in (
            ("iteration_index", index, validate_iteration_index),
            ("iteration_summary", summary, validate_iteration_summary),
        ):
            schema = json.loads(evidence_schema_path(kind).read_text(encoding="utf-8"))
            self.assertEqual(Draft7Validator(schema).is_valid(payload), validator(payload).ok)
            negative = dict(payload)
            negative["unknown_field"] = True
            self.assertFalse(Draft7Validator(schema).is_valid(negative))
            self.assertFalse(validator(negative).ok)

    def test_report_schema_is_strict_and_matches_pydantic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            report = read_json(root / "report.json")
        schema = json.loads(evidence_schema_path("change_evidence_report").read_text(encoding="utf-8"))
        self.assertEqual(Draft7Validator(schema).is_valid(report), validate_change_evidence_report(report).ok)
        self.assertFalse(validate_change_evidence_report({**report, "spoofed": True}).ok)


class P1B006And007AggregationTests(unittest.TestCase):
    def test_fixture_summary_is_valid_but_never_business_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = summarize_iteration(_build_iteration(Path(directory)), base_dir=directory)
        self.assertEqual(summary["contract"], ITERATION_SUMMARY_CONTRACT)
        self.assertEqual(summary["status"], "VALID")
        self.assertFalse(summary["business_evidence"])
        self.assertEqual(summary["formal_release_effect"], "NONE")
        self.assertFalse(summary["formal_release_allowed"])

    def test_business_evidence_cannot_be_forged_in_a_fixture_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = summarize_iteration(_build_iteration(Path(directory)), base_dir=directory)
        forged = copy.deepcopy(summary)
        forged["business_evidence"] = True
        result = validate_iteration_summary(forged)
        schema = json.loads(evidence_schema_path("iteration_summary").read_text(encoding="utf-8"))
        self.assertFalse(result.ok)
        self.assertFalse(Draft7Validator(schema).is_valid(forged))

    def test_zero_denominator_is_blocked_and_does_not_become_zero_percent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = _build_iteration(Path(directory))
            index["changes"][0]["status"] = "EXCLUDED"
            index["changes"][0]["evidence_digest"] = "sha256:excluded"
            summary = summarize_iteration(index, base_dir=directory)
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertIsNone(summary["metrics"]["evidence_completeness_rate"]["value"])

    def test_no_failure_and_no_retry_are_not_observed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = summarize_iteration(_build_iteration(Path(directory)), base_dir=directory)
        self.assertEqual(summary["metrics"]["failure_attribution_rate"]["state"], "NOT_OBSERVED")
        self.assertEqual(summary["metrics"]["retry_retention_rate"]["state"], "NOT_OBSERVED")

    def test_missing_cost_is_blocked_and_non_positive_savings_is_not_computable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = _build_iteration(Path(directory))
            index["policy"]["costs"].pop("data_minutes")
            blocked = summarize_iteration(index, base_dir=directory)
            index = _build_iteration(Path(directory))
            index["policy"]["costs"]["gross_savings_minutes"] = 0
            non_positive = summarize_iteration(index, base_dir=directory)
        self.assertEqual(blocked["roi"]["net_savings"]["state"], "BLOCKED")
        self.assertEqual(non_positive["roi"]["payback_months"]["state"], "NOT_COMPUTABLE")

    def test_stop_trigger_has_priority_over_positive_roi(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = _build_iteration(Path(directory))
            index["formal_evidence"]["high_risk_false_negative"] = 1
            summary = summarize_iteration(index, base_dir=directory)
        self.assertEqual(summary["status"], "STOP_TRIGGERED")
        self.assertIn("HIGH_RISK_FALSE_NEGATIVE", summary["stop_triggers"])

    def test_only_generated_at_changes_the_decision_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index = _build_iteration(Path(directory))
            first = summarize_iteration(index, base_dir=directory)
            second = copy.deepcopy(first)
            second["generated_at"] = "2099-01-01T00:00:00+00:00"
        self.assertEqual(first["decision_digest"], second["decision_digest"])

    def test_approval_windows_use_the_frozen_cutoff_not_runtime_clock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            index["versions"]["matrix_valid_until"] = "2026-08-18T09:00:00+08:00"
            index["policy"]["valid_until"] = "2026-08-18T09:00:00+08:00"
            early = summarize_iteration(
                index,
                base_dir=root,
                now=datetime.fromisoformat("2026-08-18T08:30:00+08:00"),
            )
            late = summarize_iteration(
                index,
                base_dir=root,
                now=datetime.fromisoformat("2027-01-01T00:00:00+00:00"),
            )
        self.assertEqual(early["status"], "VALID")
        self.assertEqual(late["status"], "VALID")
        self.assertNotEqual(early["generated_at"], late["generated_at"])
        self.assertEqual(early["decision_digest"], late["decision_digest"])


class P1B006And008SafetyAndCliTests(unittest.TestCase):
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "qualityctl", "evidence", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_path_escape_and_digest_mismatch_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            index["changes"][0]["report"]["path"] = "../outside/report.json"
            escaped = summarize_iteration(index, base_dir=root)
            index = _build_iteration(root)
            index["changes"][0]["report"]["digest"] = "sha256:wrong"
            mismatched = summarize_iteration(index, base_dir=root)
        self.assertEqual(escaped["code"], "UNSAFE_EVIDENCE_PATH")
        self.assertEqual(mismatched["code"], "ARTIFACT_DIGEST_MISMATCH")

    def test_non_json_artifact_media_type_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            index["ledger"]["media_type"] = "text/plain"
            summary = summarize_iteration(index, base_dir=root)
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertEqual(summary["code"], "UNSUPPORTED_MEDIA_TYPE")

    def test_mixed_identity_and_duplicate_identity_do_not_enter_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            duplicate = copy.deepcopy(index["changes"][0])
            index["changes"].append(duplicate)
            summary = summarize_iteration(index, base_dir=root)
        self.assertEqual(summary["code"], "DUPLICATE_CHANGE_IDENTITY")
        self.assertEqual(summary["denominator"]["eligible_count"], 0)

    def test_real_fixture_is_blocked_by_g0_without_starting_a_clock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            index["identity"]["evidence_class"] = "REAL"
            summary = summarize_iteration(index, base_dir=root)
        self.assertEqual(summary["code"], "BLOCKED_BY_R2_G0")
        self.assertFalse(summary["business_evidence"])

    def test_cli_writes_summary_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = _build_iteration(root)
            input_path = root / "iteration-index.json"
            output_path = root / "iteration-summary.json"
            input_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
            first = self._run_cli("summarize-iteration", str(input_path), "--output", str(output_path))
            original = output_path.read_bytes()
            second = self._run_cli("summarize-iteration", str(input_path), "--output", str(output_path))
            output_status = read_json(output_path)["status"]
            output_bytes = output_path.read_bytes()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(output_status, "VALID")
        self.assertEqual(second.returncode, 2)
        self.assertEqual(output_bytes, original)
        self.assertEqual(json.loads(second.stderr)["code"], "OUTPUT_EXISTS")

    def test_cli_input_errors_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = self._run_cli("summarize-iteration", str(root / "missing.json"), "--output", str(root / "out.json"))
            bad_input = root / "bad.json"
            bad_input.write_text("{not json", encoding="utf-8")
            broken = self._run_cli("summarize-iteration", str(bad_input), "--output", str(root / "broken-out.json"))
        for result in (missing, broken):
            self.assertEqual(result.returncode, 2)
            error = json.loads(result.stderr)
            self.assertFalse(error["ok"])
            for key in ("kind", "code", "message", "paths", "errors"):
                self.assertIn(key, error)


class P1B009CompatibilityObservationTests(unittest.TestCase):
    def test_initial_mixed_final_and_rollback_fixtures_remain_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = _build_iteration(root)
            initial_summary = summarize_iteration(initial, base_dir=root)

            mixed = copy.deepcopy(initial)
            mixed["versions"]["core_commit"] = "feature-branch"
            mixed_summary = summarize_iteration(mixed, base_dir=root)

            final = copy.deepcopy(initial)
            final["formal_evidence"].update(
                {
                    "failures": 1,
                    "attributed_failures": 1,
                    "retry_groups": 1,
                    "retry_groups_complete": 1,
                }
            )
            final_summary = summarize_iteration(final, base_dir=root)

            rollback = copy.deepcopy(initial)
            rollback["schema_version"] = "2.0"
            rollback_summary = summarize_iteration(rollback, base_dir=root)

        self.assertEqual(initial_summary["status"], "VALID")
        self.assertEqual(mixed_summary["code"], "UNSUPPORTED_CORE")
        self.assertEqual(final_summary["status"], "VALID")
        self.assertEqual(final_summary["metrics"]["failure_attribution_rate"]["value"], 1.0)
        self.assertEqual(final_summary["metrics"]["retry_retention_rate"]["value"], 1.0)
        self.assertEqual(rollback_summary["code"], "UNSUPPORTED_SCHEMA")


if __name__ == "__main__":
    unittest.main()
