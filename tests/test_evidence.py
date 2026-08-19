from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator

from qualityctl.evidence import (
    FORMAL_RELEASE_EFFECT,
    RISK_DIMENSIONS,
    canonical_digest,
    compare_scopes,
    freeze_ledger,
    validate_adjudication_record,
    validate_catalog_readiness,
    validate_difference_draft,
    validate_pilot_evidence_bundle,
    verify_change_bundle,
    write_json_exclusive,
)
from qualityctl.io import read_json
from qualityctl.schemas import evidence_schema_path
from qualityctl.selection import select_regression_tests


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _load_json(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _load_runs() -> list[dict]:
    return [
        json.loads(line)
        for line in (EXAMPLES / "agent-runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def _write_raw_reference(root: Path, name: str, value: object) -> dict:
    path = root / name
    if name.endswith(".jsonl"):
        assert isinstance(value, list)
        data = (
            "\n".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for item in value
            )
            + "\n"
        ).encode("utf-8")
        media_type = "application/x-ndjson"
    else:
        data = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        media_type = "application/json"
    path.write_bytes(data)
    return {
        "path": name,
        "media_type": media_type,
        "size": len(data),
        "digest": f"sha256:{hashlib.sha256(data).hexdigest()}",
    }


def _externalize_raw_inputs(bundle: dict, root: Path) -> dict[str, dict]:
    references = {
        "manifest": _write_raw_reference(root, "manifest.json", bundle["raw"]["manifest"]),
        "catalog": _write_raw_reference(root, "catalog.json", bundle["raw"]["catalog"]),
        "agent_spec": _write_raw_reference(root, "agent-spec.json", bundle["raw"]["agent_spec"]),
        "agent_runs": _write_raw_reference(root, "agent-runs.jsonl", bundle["raw"]["agent_runs"]),
    }
    bundle["raw"].update(copy.deepcopy(references))
    return references


def _fixture_catalog() -> tuple[dict, dict]:
    catalog = _load_json("test-catalog.json")
    templates = catalog["tests"]
    tests: list[dict] = []
    for index in range(30):
        test = copy.deepcopy(templates[index % len(templates)])
        test["id"] = f"FIXTURE-TEST-{index + 1:03d}"
        test["components"] = ["fixture-component"]
        test["dimensions"] = [RISK_DIMENSIONS[index % len(RISK_DIMENSIONS)]]
        test["labels"] = ["historical_escape"] if index == 2 else []
        tests.append(test)
    catalog["tests"] = tests
    readiness = {
        "catalog_version": "fixture-catalog@1.0",
        "source_ref": "fixture://catalog/source",
        "reviewer_ids": ["fixture-test-owner", "fixture-dev-owner"],
        "oracle_refs": {
            test["id"]: f"fixture://oracle/{test['id']}" for test in tests
        },
        "dimension_coverage": list(RISK_DIMENSIONS),
        "historical_escape_refs": ["fixture://history/escape-001"],
    }
    return catalog, readiness


def _fixture_bundle() -> dict:
    manifest = _load_json("risk-manifest.json")
    manifest["change_id"] = "FIXTURE-CHANGE-001"
    catalog, readiness = _fixture_catalog()
    spec = _load_json("agent-cases.json")
    runs = _load_runs()
    tool_result = select_regression_tests(catalog, manifest)
    selected = [item["test_id"] for item in tool_result["selected"]]
    manual_scope = {"selected_test_ids": selected}
    return {
        "contract": "pilot-evidence-bundle@1.0",
        "schema_version": "1.0",
        "mode": "FIXTURE_DRY_RUN",
        "g0_status": "BLOCKED_BY_R2_G0",
        "identity": {
            "pilot_id": "fixture-pilot",
            "iteration_id": "fixture-iteration-001",
            "change_id": "FIXTURE-CHANGE-001",
            "run_id": "fixture-run-001",
            "change_ref": "fixture://change/001",
            "version_type": "daily",
        },
        "versions": {
            "core_version": "0.1.0",
            "core_commit": "ff11ddb7615ede298d26e2d5b7e3bc5d75664bc6",
            "python_version": "3.11",
            "input_schema_versions": {
                "manifest": "1.0",
                "catalog": "1.0",
                "agent_spec": "1.0",
                "agent_run": "1.0",
            },
            "catalog_version": "fixture-catalog@1.0",
            "mapping_version": "fixture-mapping@1.0",
            "policy_version": "fixture-policy@1.0",
        },
        "freeze": {
            "scope_ref": "fixture://freeze/manual-scope",
            "scope_digest": canonical_digest(manual_scope),
            "owner": "fixture-test-owner",
            "manual_frozen_at": "2026-08-18T08:00:00+08:00",
        },
        "manual_scope": manual_scope,
        "tool_runs": [
            {
                "tool": "decide_release_gate",
                "request_ref": "fixture://raw/request/gate",
                "response_ref": "fixture://raw/response/gate",
                "exit_code": 0,
                "started_at": "2026-08-18T08:05:00+08:00",
                "ended_at": "2026-08-18T08:05:01+08:00",
                "ref": "fixture://raw/gate",
                "digest": "sha256:fixture-gate-output",
            }
        ],
        "ordering": {
            "tool_started_at": "2026-08-18T08:05:00+08:00",
            "tool_result_visible_at": "2026-08-18T08:06:00+08:00",
            "unblinded_at": "2026-08-18T08:07:00+08:00",
            "adjudicated_at": "2026-08-18T08:08:00+08:00",
        },
        "attempts": [
            {
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
        "attestations": {
            "secret_scan": {
                "status": "PASS",
                "version": "fixture-scanner@1",
                "ref": "fixture://scan/001",
                "digest": "sha256:fixture-scan",
            },
            "controlled_storage": {
                "status": "PASS",
                "version": "fixture-storage@1",
                "ref": "fixture://storage/001",
                "digest": "sha256:fixture-storage",
            },
            "formal_result": {
                "status": "RECORDED",
                "version": "fixture-release@1",
                "ref": "fixture://formal-result/001",
                "digest": "sha256:fixture-formal",
                "release_effect": "NONE",
            },
            "least_privilege": {
                "status": "PASS",
                "version": "fixture-permissions@1",
                "ref": "fixture://permissions/001",
                "digest": "sha256:fixture-permissions",
            },
        },
        "catalog_readiness": readiness,
        "adjudication": {
            "contract": "adjudication@1.0",
            "identity": {
                "pilot_id": "fixture-pilot",
                "change_id": "FIXTURE-CHANGE-001",
                "run_id": "fixture-run-001",
            },
            "difference_draft_digest": compare_scopes(
                manual_scope,
                {"selected_test_ids": selected},
                identity={
                    "pilot_id": "fixture-pilot",
                    "iteration_id": "fixture-iteration-001",
                    "change_id": "FIXTURE-CHANGE-001",
                    "run_id": "fixture-run-001",
                    "change_ref": "fixture://change/001",
                    "version_type": "daily",
                },
            )["decision_digest"],
            "items": [],
            "reviewer_id": "fixture-adjudicator",
            "reviewer_role": "test-owner",
            "adjudicated_at": "2026-08-18T08:08:00+08:00",
            "status": "CLOSED",
            "formal_release_effect": "NONE",
        },
        "raw": {
            "manifest": manifest,
            "catalog": catalog,
            "agent_spec": spec,
            "agent_runs": runs,
            "tool_scope": {"selected_test_ids": selected},
        },
        "formal_release_effect": "NONE",
    }


class PilotEvidenceContractTests(unittest.TestCase):
    def test_test_extra_declares_jsonschema_for_reproducible_parity_checks(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("[project.optional-dependencies]", pyproject)
        self.assertRegex(pyproject, r'(?m)^\s*"jsonschema[^"\n]*"')

    def test_test_extra_pins_jsonschema_for_reproducible_parity_checks(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertRegex(pyproject, r'(?m)^\s*"jsonschema==4\.26\.0",?\s*$')

    def test_canonicalization_lives_in_core_not_embedded_ui(self) -> None:
        source = (
            ROOT / "plugins" / "quality-gatekeeper" / "embedded_ui" / "view_model.py"
        ).read_text(encoding="utf-8")
        self.assertIn("from qualityctl.evidence import", source)
        self.assertNotIn("import hashlib", source)

    def test_fixture_validates_against_pilot_pydantic_contract(self) -> None:
        result = validate_pilot_evidence_bundle(_fixture_bundle())
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.model.contract, "pilot-evidence-bundle@1.0")

    def test_pilot_json_schema_resource_is_pinned_with_the_pydantic_contract(self) -> None:
        path = evidence_schema_path("pilot_evidence_bundle")
        self.assertTrue(path.is_file())
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "https://qualityctl.dev/schemas/v1/pilot-evidence-bundle.schema.json")
        self.assertIn("identity", schema["required"])
        self.assertIn("core_version", schema["$defs"]["versions"]["required"])
        self.assertIn("core_commit", schema["$defs"]["versions"]["required"])
        self.assertFalse(schema["additionalProperties"])

    def test_missing_exact_core_identity_is_blocked_before_compatibility_pass(self) -> None:
        bundle = _fixture_bundle()
        bundle["versions"].pop("core_commit")
        structural = validate_pilot_evidence_bundle(bundle)
        report = verify_change_bundle(bundle)
        self.assertFalse(structural.ok)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "INVALID_BUNDLE")

    def test_external_raw_refs_have_pydantic_json_schema_parity(self) -> None:
        schema = json.loads(
            evidence_schema_path("pilot_evidence_bundle").read_text(encoding="utf-8")
        )
        validator = Draft7Validator(schema)
        with tempfile.TemporaryDirectory() as directory:
            bundle = _fixture_bundle()
            _externalize_raw_inputs(bundle, Path(directory))
            self.assertTrue(validate_pilot_evidence_bundle(bundle).ok)
            self.assertEqual(list(validator.iter_errors(bundle)), [])

            incomplete = copy.deepcopy(bundle)
            incomplete["raw"]["agent_runs"].pop("digest")
            self.assertFalse(validate_pilot_evidence_bundle(incomplete).ok)
            self.assertTrue(list(validator.iter_errors(incomplete)))

    def test_unknown_major_is_a_compatibility_block_not_a_release_pass(self) -> None:
        bundle = _fixture_bundle()
        bundle["versions"]["input_schema_versions"]["manifest"] = "2.0"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "UNSUPPORTED_SCHEMA")
        self.assertEqual(report["formal_release_effect"], FORMAL_RELEASE_EFFECT)

    def test_unapproved_minor_is_not_treated_as_compatible(self) -> None:
        bundle = _fixture_bundle()
        bundle["versions"]["input_schema_versions"]["catalog"] = "1.1"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "UNSUPPORTED_SCHEMA")

    def test_verifier_does_not_mutate_raw_inputs(self) -> None:
        bundle = _fixture_bundle()
        before = copy.deepcopy(bundle["raw"])
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "ELIGIBLE")
        self.assertEqual(bundle["raw"], before)

    def test_same_bundle_has_stable_report_decision_digest(self) -> None:
        first = verify_change_bundle(_fixture_bundle())
        second = verify_change_bundle(_fixture_bundle())
        self.assertEqual(first["decision_digest"], second["decision_digest"])

    def test_decision_digest_ignores_generated_at_but_not_evidence(self) -> None:
        first = {"generated_at": "2026-08-18T00:00:00Z", "status": "ELIGIBLE"}
        second = {"generated_at": "2026-08-19T00:00:00Z", "status": "ELIGIBLE"}
        self.assertEqual(canonical_digest(first, purpose="decision"), canonical_digest(second, purpose="decision"))
        second["status"] = "BLOCKED"
        self.assertNotEqual(canonical_digest(first, purpose="decision"), canonical_digest(second, purpose="decision"))

    def test_exclusive_writer_does_not_change_existing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_bytes(b"original\x00bytes")
            with self.assertRaises(FileExistsError):
                write_json_exclusive({"status": "BLOCKED"}, path)
            self.assertEqual(path.read_bytes(), b"original\x00bytes")

    def test_catalog_readiness_requires_count_and_approved_metadata(self) -> None:
        catalog, readiness = _fixture_catalog()
        self.assertTrue(validate_catalog_readiness(catalog, readiness).ok)
        too_small = copy.deepcopy(catalog)
        too_small["tests"] = too_small["tests"][:29]
        self.assertFalse(validate_catalog_readiness(too_small, readiness).ok)
        missing_review = copy.deepcopy(readiness)
        missing_review["reviewer_ids"] = []
        self.assertFalse(validate_catalog_readiness(catalog, missing_review).ok)
        missing_dimension = copy.deepcopy(readiness)
        missing_dimension["dimension_coverage"] = ["business_flow"]
        self.assertFalse(validate_catalog_readiness(catalog, missing_dimension).ok)

    def test_stale_output_on_agent_failure_is_blocked_and_not_reported(self) -> None:
        bundle = _fixture_bundle()
        bad = bundle["raw"]["agent_runs"][0]
        bad["technical_status"] = "technical_failure"
        bad["error"] = "fixture failure"
        bad["output"] = {"stale": "must not escape"}
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "INVALID_AGENT_FAILURE_EVIDENCE")
        self.assertNotIn("stale", json.dumps(report, ensure_ascii=False))

    def test_agent_frozen_digest_mismatch_blocks_even_when_claimed_fingerprint_matches(self) -> None:
        bundle = _fixture_bundle()
        bundle["versions"]["agent_spec_digest"] = "sha256:not-the-frozen-content"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "AGENT_DIGEST_MISMATCH")

    def test_not_applicable_agent_domain_does_not_require_run_rows(self) -> None:
        bundle = _fixture_bundle()
        bundle["raw"]["manifest"]["agent_evaluation"]["required"] = False
        bundle["raw"]["agent_spec"] = None
        bundle["raw"]["agent_runs"] = None
        bundle["versions"]["input_schema_versions"].pop("agent_spec", None)
        bundle["versions"]["input_schema_versions"].pop("agent_run", None)
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "ELIGIBLE")
        self.assertEqual(report["raw_gate"], "PASS")

    def test_all_raw_artifact_kinds_use_the_same_safe_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = _fixture_bundle()
            references = _externalize_raw_inputs(bundle, root)
            report = verify_change_bundle(bundle, base_dir=root)
            self.assertEqual(report["status"], "ELIGIBLE", report.get("errors"))

            for key in references:
                with self.subTest(key=key, violation="size"):
                    invalid = copy.deepcopy(bundle)
                    invalid["raw"][key]["size"] += 1
                    blocked = verify_change_bundle(invalid, base_dir=root)
                    self.assertEqual(blocked["status"], "BLOCKED")
                    self.assertTrue(
                        any(f"{key} size mismatch" in error for error in blocked["errors"]),
                        blocked["errors"],
                    )
                with self.subTest(key=key, violation="digest"):
                    invalid = copy.deepcopy(bundle)
                    invalid["raw"][key]["digest"] = "sha256:not-the-file-bytes"
                    blocked = verify_change_bundle(invalid, base_dir=root)
                    self.assertEqual(blocked["status"], "BLOCKED")
                    self.assertTrue(
                        any(f"{key} digest mismatch" in error for error in blocked["errors"]),
                        blocked["errors"],
                    )
                with self.subTest(key=key, violation="parent-traversal"):
                    invalid = copy.deepcopy(bundle)
                    invalid["raw"][key]["path"] = f"../outside-{key}.json"
                    blocked = verify_change_bundle(invalid, base_dir=root)
                    self.assertEqual(blocked["status"], "BLOCKED")
                    self.assertTrue(
                        any(f"{key} path" in error for error in blocked["errors"]),
                        blocked["errors"],
                    )
                with self.subTest(key=key, violation="absolute-path"):
                    invalid = copy.deepcopy(bundle)
                    invalid["raw"][key]["path"] = str(
                        (root / references[key]["path"]).resolve()
                    )
                    blocked = verify_change_bundle(invalid, base_dir=root)
                    self.assertEqual(blocked["status"], "BLOCKED")
                    self.assertTrue(
                        any(f"{key} path" in error for error in blocked["errors"]),
                        blocked["errors"],
                    )

    def test_agent_runs_symlink_escape_is_blocked_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            container = Path(directory)
            root = container / "evidence"
            root.mkdir()
            bundle = _fixture_bundle()
            references = _externalize_raw_inputs(bundle, root)
            outside = container / "outside-agent-runs.jsonl"
            outside.write_bytes((root / references["agent_runs"]["path"]).read_bytes())
            link = root / "agent-runs-link.jsonl"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                outside_directory = container / "outside"
                outside_directory.mkdir()
                junction_target = outside_directory / "agent-runs.jsonl"
                junction_target.write_bytes(outside.read_bytes())
                junction = root / "outside-link"
                created = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(junction), str(outside_directory)],
                    capture_output=True,
                    text=True,
                )
                if created.returncode != 0:
                    self.skipTest(
                        f"symlink and junction creation are unavailable: {exc}; {created.stderr}"
                    )
                bundle["raw"]["agent_runs"]["path"] = "outside-link/agent-runs.jsonl"
            else:
                bundle["raw"]["agent_runs"]["path"] = link.name

            report = verify_change_bundle(bundle, base_dir=root)

        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(
            any("agent_runs path" in error for error in report["errors"]),
            report["errors"],
        )


class PilotEvidenceWorkflowTests(unittest.TestCase):
    def test_duplicate_manual_or_tool_scope_id_is_explicitly_blocked(self) -> None:
        for side in ("manual", "tool"):
            with self.subTest(side=side):
                manual = {"selected_test_ids": ["T-1"]}
                tool = {"selected_test_ids": ["T-1"]}
                target = manual if side == "manual" else tool
                target["selected_test_ids"].append("T-1")

                draft = compare_scopes(manual, tool)
                replayed = compare_scopes(manual, tool)

                self.assertEqual(draft["status"], "BLOCKED")
                self.assertEqual(draft["code"], "DUPLICATE_SCOPE_ID")
                self.assertEqual(draft["decision_digest"], replayed["decision_digest"])
                self.assertTrue(any(side in error for error in draft["errors"]))
                self.assertTrue(validate_difference_draft(draft).ok)
                schema = json.loads(
                    evidence_schema_path("difference_draft").read_text(encoding="utf-8")
                )
                self.assertEqual(list(Draft7Validator(schema).iter_errors(draft)), [])

        bundle = _fixture_bundle()
        duplicate_id = bundle["manual_scope"]["selected_test_ids"][0]
        bundle["manual_scope"]["selected_test_ids"].append(duplicate_id)
        bundle["freeze"]["scope_digest"] = canonical_digest(bundle["manual_scope"])
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "DUPLICATE_SCOPE_ID")

    def test_verify_change_is_eligible_but_never_formally_releases(self) -> None:
        report = verify_change_bundle(_fixture_bundle())
        self.assertEqual(report["status"], "ELIGIBLE")
        self.assertEqual(report["formal_release_effect"], "NONE")
        self.assertEqual(report["raw_gate"], "PASS")
        self.assertFalse(report["formal_release_allowed"])
        self.assertTrue(report["decision_digest"].startswith("sha256:"))

    def test_pre_freeze_change_is_excluded_and_retained(self) -> None:
        bundle = _fixture_bundle()
        bundle["freeze"]["manual_frozen_at"] = "2026-08-18T08:05:00+08:00"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "EXCLUDED")
        self.assertEqual(report["code"], "EXCLUDED_PRE_FREEZE")
        self.assertTrue(report["retained_for_ledger"])

    def test_real_bundle_stays_blocked_while_g0_is_blocked(self) -> None:
        bundle = _fixture_bundle()
        bundle["mode"] = "SHADOW"
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["code"], "BLOCKED_BY_R2_G0")

    def test_evidence_overwrite_is_a_stop_trigger_not_an_exclusion(self) -> None:
        bundle = _fixture_bundle()
        bundle["evidence_overwritten"] = True
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "STOP_TRIGGERED")
        self.assertEqual(report["code"], "STOP_TRIGGERED")

    def test_retry_keeps_initial_failure_and_all_attempt_ids(self) -> None:
        bundle = _fixture_bundle()
        bundle["attempts"] = [
            bundle["attempts"][0]
            | {"status": "BLOCKED", "digest": "sha256:fixture-initial-failure"},
            {
                "attempt_id": "fixture-attempt-002",
                "kind": "rerun",
                "out_of_plan": False,
                "digest": "sha256:fixture-attempt-002",
                "started_at": "2026-08-18T08:10:00+08:00",
                "ended_at": "2026-08-18T08:10:01+08:00",
                "status": "PASS",
                "ref": "fixture://attempt/002",
                "initial_attempt_ref": "fixture://attempt/001",
            },
        ]
        report = verify_change_bundle(bundle)
        self.assertEqual(report["status"], "ELIGIBLE")
        self.assertEqual(
            report["attempt_ids"], ["fixture-attempt-001", "fixture-attempt-002"]
        )

    def test_difference_draft_has_no_machine_classification(self) -> None:
        draft = compare_scopes(
            {"selected_test_ids": ["T-1", "T-2"]},
            {"selected_test_ids": ["T-2", "T-3"]},
        )
        self.assertEqual(draft["contract"], "difference-draft@1.0")
        self.assertEqual(
            [item["test_id"] for item in draft["differences"]], ["T-1", "T-3"]
        )
        self.assertTrue(all("classification" not in item for item in draft["differences"]))
        self.assertEqual(draft["formal_release_effect"], "NONE")

    def test_adjudication_requires_evidence_and_closes_high_risk(self) -> None:
        draft = compare_scopes({"selected_test_ids": ["T-1"]}, {"selected_test_ids": []})
        base = {
            "contract": "adjudication@1.0",
            "identity": {"pilot_id": "p", "change_id": "c", "run_id": "r"},
            "difference_draft_digest": draft["decision_digest"],
            "items": [
                {
                    "difference_id": draft["differences"][0]["difference_id"],
                    "classification": "TOOL_FALSE_NEGATIVE_HIGH",
                    "evidence_refs": ["fixture://evidence/1"],
                    "high_risk": True,
                    "status": "CLOSED",
                    "adjudicator": "fixture-adjudicator",
                    "adjudicated_at": "2026-08-18T08:20:00+08:00",
                }
            ],
            "reviewer_id": "fixture-adjudicator",
            "reviewer_role": "test-owner",
            "adjudicated_at": "2026-08-18T08:20:00+08:00",
            "status": "CLOSED",
            "formal_release_effect": "NONE",
        }
        result = validate_adjudication_record(base)
        self.assertEqual(result["status"], "STOP_TRIGGERED")
        self.assertEqual(result["formal_release_effect"], "NONE")
        base["items"][0]["evidence_refs"] = []
        invalid = validate_adjudication_record(base)
        self.assertEqual(invalid["status"], "BLOCKED")

    def test_frozen_ledger_preserves_exclusions_and_rejects_duplicate_denominator(self) -> None:
        eligible = verify_change_bundle(_fixture_bundle())
        entry = {
            "pilot_id": "fixture-pilot",
            "iteration_id": "fixture-iteration-001",
            "change_id": "FIXTURE-CHANGE-001",
            "run_id": "fixture-run-001",
            "status": eligible["status"],
            "evidence_digest": eligible["decision_digest"],
            "attempt_ids": ["fixture-attempt-001"],
            "out_of_plan": False,
            "report_ref": "fixture://report/001",
        }
        ledger = freeze_ledger({"entries": [entry, copy.deepcopy(entry)]})
        self.assertEqual(ledger["status"], "BLOCKED")
        self.assertTrue(ledger["conflicts"])
        self.assertEqual(ledger["eligible_count"], 0)
        self.assertEqual(ledger["formal_release_effect"], "NONE")


class EvidenceCliTests(unittest.TestCase):
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

    def test_verify_change_output_conflict_is_structured_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle.json"
            output_path = root / "report.json"
            bundle_path.write_text(
                json.dumps(_fixture_bundle(), ensure_ascii=False), encoding="utf-8"
            )
            output_path.write_bytes(b"keep-me")
            result = self._run_cli(
                "verify-change", str(bundle_path), "--output", str(output_path)
            )
            self.assertEqual(result.returncode, 2)
            error = json.loads(result.stderr)
            self.assertFalse(error["ok"])
            for key in ("kind", "code", "message", "paths", "errors"):
                self.assertIn(key, error)
            self.assertEqual(output_path.read_bytes(), b"keep-me")

    def test_verify_change_e2e_writes_frozen_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle.json"
            output_path = root / "report.json"
            bundle_path.write_text(
                json.dumps(_fixture_bundle(), ensure_ascii=False), encoding="utf-8"
            )
            result = self._run_cli(
                "verify-change", str(bundle_path), "--output", str(output_path)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = read_json(output_path)
            self.assertEqual(report["status"], "ELIGIBLE")
            self.assertEqual(report["formal_release_effect"], "NONE")

    def test_draft_adjudication_and_ledger_commands_are_exclusive_json_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle.json"
            draft_path = root / "draft.json"
            adjudication_path = root / "adjudication.json"
            adjudication_status_path = root / "adjudication-status.json"
            ledger_input_path = root / "ledger-input.json"
            ledger_path = root / "ledger.json"
            bundle = _fixture_bundle()
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            draft = compare_scopes(
                {"selected_test_ids": ["T-1"]}, {"selected_test_ids": ["T-2"]}
            )
            adjudication = dict(bundle["adjudication"])
            adjudication["difference_draft_digest"] = draft["decision_digest"]
            adjudication["items"] = [
                {
                    "difference_id": item["difference_id"],
                    "classification": "NO_DIFFERENCE",
                    "evidence_refs": ["fixture://evidence/diff"],
                    "status": "CLOSED",
                    "adjudicator": "fixture-adjudicator",
                    "adjudicated_at": "2026-08-18T08:08:00+08:00",
                }
                for item in draft["differences"]
            ]
            adjudication_path.write_text(
                json.dumps(adjudication, ensure_ascii=False), encoding="utf-8"
            )
            ledger_input_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "pilot_id": "fixture-pilot",
                                "iteration_id": "fixture-iteration-001",
                                "change_id": "FIXTURE-CHANGE-001",
                                "run_id": "fixture-run-001",
                                "status": "EXCLUDED",
                                "evidence_digest": "sha256:fixture-excluded",
                                "out_of_plan": False,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            draft_result = self._run_cli(
                "draft-diff", str(bundle_path), "--output", str(draft_path)
            )
            self.assertEqual(draft_result.returncode, 0, draft_result.stderr)
            self.assertNotIn(
                "classification",
                json.dumps(read_json(draft_path), ensure_ascii=False),
            )
            adjudication_result = self._run_cli(
                "validate-adjudication",
                str(adjudication_path),
                "--output",
                str(adjudication_status_path),
            )
            self.assertEqual(adjudication_result.returncode, 0, adjudication_result.stderr)
            self.assertEqual(read_json(adjudication_status_path)["status"], "VALID")
            ledger_result = self._run_cli(
                "freeze-ledger", str(ledger_input_path), "--output", str(ledger_path)
            )
            self.assertEqual(ledger_result.returncode, 0, ledger_result.stderr)
            self.assertEqual(read_json(ledger_path)["status"], "FROZEN")


if __name__ == "__main__":
    unittest.main()
