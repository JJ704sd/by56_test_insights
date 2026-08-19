"""Strict, local iteration evidence contracts and deterministic aggregation.

The iteration core accepts only a frozen, versioned reference index.  It does
not discover evidence, call remote systems, or make a release decision.  All
references are resolved below an explicit local root and every JSON artifact
is checked against its recorded bytes digest before it can affect a summary.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    ValidationError,
    model_validator,
)

from .evidence import (
    FORMAL_RELEASE_EFFECT,
    bytes_digest,
    canonical_digest,
    compare_scopes,
    verify_change_bundle,
)


ITERATION_INDEX_CONTRACT = "iteration-index@1.0"
ITERATION_SUMMARY_CONTRACT = "iteration-summary@1.0"
ITERATION_SCHEMA_VERSION = "1.0"
CANONICALIZATION_VERSION = "canonical-json@1.0"
APPROVED_CORE_VERSION = "0.1.0"
# The P1b fixture matrix is pinned to the repository baseline.  A future real
# matrix must be reviewed and changed explicitly; it is never inferred from
# a caller-supplied branch name or version range.
APPROVED_CORE_COMMIT = "ff11ddb7615ede298d26e2d5b7e3bc5d75664bc6"
APPROVED_QUALITYCTL_VERSION = "0.1.0"
APPROVED_POLICY_VERSION = "fixture-roi-policy@1.0"
APPROVED_POLICY_DIGEST = "sha256:fixture-roi-policy"
APPROVED_MAPPING_VERSION = "fixture-mapping@1.0"
APPROVED_CATALOG_VERSION = "fixture-catalog@1.0"
APPROVED_THRESHOLD_VERSION = "fixture-threshold@1.0"
EXACT_COMPATIBILITY_MATRIX = {
    "qualityctl_version": APPROVED_QUALITYCTL_VERSION,
    "core_version": APPROVED_CORE_VERSION,
    "core_commit": APPROVED_CORE_COMMIT,
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
    "canonicalization": CANONICALIZATION_VERSION,
    "catalog_version": APPROVED_CATALOG_VERSION,
    "mapping_version": APPROVED_MAPPING_VERSION,
    "threshold_version": APPROVED_THRESHOLD_VERSION,
    "roi_policy_version": APPROVED_POLICY_VERSION,
    "roi_policy_digest": APPROVED_POLICY_DIGEST,
}

ATTESTATION_SUCCESS_ALLOWLIST: dict[str, str] = {
    "secret_scan": "PASS",
    "controlled_storage": "PASS",
    "formal_result": "RECORDED",
    "least_privilege": "PASS",
}
ATTESTATION_NAMES = tuple(ATTESTATION_SUCCESS_ALLOWLIST)

METRIC_STATES = {"OBSERVED", "NOT_OBSERVED", "NOT_COMPUTABLE", "BLOCKED"}
SUMMARY_STATUSES = {"VALID", "BLOCKED", "STOP_TRIGGERED"}
LEDGER_STATUSES = {"FROZEN", "BLOCKED"}
CHANGE_STATUSES = {"ELIGIBLE", "EXCLUDED", "BLOCKED", "STOP_TRIGGERED"}

_Number = StrictInt | StrictFloat


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ContractValidationResult:
    """Small stable result shared by the strict contract validators."""

    __slots__ = ("ok", "errors", "model", "code")

    def __init__(
        self,
        ok: bool,
        errors: Sequence[str] = (),
        model: BaseModel | None = None,
        *,
        code: str = "OK",
    ) -> None:
        self.ok = ok
        self.errors = list(errors)
        self.model = model
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": "contract_validation",
            "code": self.code,
            "message": self.errors[0] if self.errors else "validation passed",
            "paths": [],
            "errors": list(self.errors),
        }


class ArtifactRefV1(StrictModel):
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size: StrictInt = Field(ge=0)
    digest: str = Field(min_length=1)


class IterationIdentityV1(StrictModel):
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    evidence_class: Literal["FIXTURE", "REAL"]


class ChangeIdentityV1(StrictModel):
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)


class FreezeIndexV1(StrictModel):
    frozen_at: str = Field(min_length=1)
    frozen_by: str = Field(min_length=1)
    freeze_ref: str = Field(min_length=1)
    freeze_digest: str = Field(min_length=1)


class ActivationV1(StrictModel):
    r2_g0_status: str = Field(min_length=1)
    approval_ref: str = Field(min_length=1)
    approval_digest: str = Field(min_length=1)
    day0: str | None = None


class SchemaVersionsV1(StrictModel):
    pilot_evidence: Literal["1.0"]
    manifest: Literal["1.0"]
    catalog: Literal["1.0"]
    agent_spec: Literal["1.0"]
    agent_run: Literal["1.0"]
    difference_draft: Literal["1.0"]
    adjudication: Literal["1.0"]
    change_report: Literal["1.0"]
    ledger: Literal["1.0"]
    iteration_index: Literal["1.0"]
    iteration_summary: Literal["1.0"]


class IterationVersionsV1(StrictModel):
    schema_versions: SchemaVersionsV1
    qualityctl_version: str = Field(min_length=1)
    core_version: str = Field(min_length=1)
    core_commit: str = Field(min_length=1)
    python_version: str = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    mapping_version: str = Field(min_length=1)
    threshold_version: str = Field(min_length=1)
    roi_policy_version: str = Field(min_length=1)
    canonicalization_version: str = Field(min_length=1)
    writer_reader_matrix: str = Field(min_length=1)
    matrix_approved_by: str = Field(min_length=1)
    matrix_approved_at: str = Field(min_length=1)
    matrix_valid_until: str = Field(min_length=1)


class CostPolicyV1(StrictModel):
    build_minutes: _Number | None = Field(default=None, ge=0)
    gross_savings_minutes: _Number | None = Field(default=None, ge=0)
    maintenance_minutes: _Number | None = Field(default=None, ge=0)
    false_positive_minutes: _Number | None = Field(default=None, ge=0)
    flaky_minutes: _Number | None = Field(default=None, ge=0)
    runner_minutes: _Number | None = Field(default=None, ge=0)
    llm_minutes: _Number | None = Field(default=None, ge=0)
    run_minutes: _Number | None = Field(default=None, ge=0)
    data_minutes: _Number | None = Field(default=None, ge=0)


class PolicyRefV1(StrictModel):
    version: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    approved_at: str = Field(min_length=1)
    valid_until: str = Field(min_length=1)
    formula_version: str = Field(min_length=1)
    costs: CostPolicyV1 = Field(default_factory=CostPolicyV1)


class AttestationRefV1(StrictModel):
    status: str = Field(min_length=1)
    version: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    approved_by: str | None = Field(default=None, min_length=1)
    expires_at: str | None = Field(default=None, min_length=1)
    release_effect: str | None = Field(default=None, min_length=1)
    sensitive_data: bool | None = None


class LedgerEntryV1(StrictModel):
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: Literal["ELIGIBLE", "EXCLUDED", "BLOCKED", "STOP_TRIGGERED"]
    evidence_digest: str = Field(min_length=1)
    attempt_ids: list[str] = Field(default_factory=list)
    out_of_plan: bool = False
    report_ref: str | None = Field(default=None, min_length=1)


class LedgerAttemptV1(StrictModel):
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    out_of_plan: bool = False
    digest: str = Field(min_length=1)
    started_at: str = Field(min_length=1)
    ended_at: str = Field(min_length=1)
    status: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    initial_attempt_ref: str | None = Field(default=None, min_length=1)


class EvidenceLedgerV1(StrictModel):
    contract: Literal["evidence-ledger@1.0"]
    schema_version: Literal["1.0"]
    status: Literal["FROZEN", "BLOCKED"]
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    entries: list[LedgerEntryV1]
    attempts: list[LedgerAttemptV1]
    conflicts: list[str]
    formal_release_effect: Literal["NONE"]
    decision_digest: str = Field(min_length=1)
    generated_at: str | None = Field(default=None, min_length=1)
    eligible_count: StrictInt | None = Field(default=None, ge=0)
    excluded_count: StrictInt | None = Field(default=None, ge=0)
    kind: Literal["evidence_ledger"] | None = None
    message: str | None = None
    paths: list[str] = Field(default_factory=list)
    eligible_change_ids: list[str] = Field(default_factory=list)
    excluded_change_ids: list[str] = Field(default_factory=list)


class ChangeRefsV1(StrictModel):
    report: ArtifactRefV1
    bundle: ArtifactRefV1
    draft: ArtifactRefV1
    adjudication: ArtifactRefV1


class ChangeIndexEntryV1(StrictModel):
    identity: ChangeIdentityV1
    status: Literal["ELIGIBLE", "EXCLUDED", "BLOCKED", "STOP_TRIGGERED"]
    evidence_digest: str = Field(min_length=1)
    report: ArtifactRefV1
    bundle: ArtifactRefV1
    draft: ArtifactRefV1
    adjudication: ArtifactRefV1
    attempt_ids: list[str] = Field(default_factory=list)
    out_of_plan: bool = False


class FormalEvidenceV1(StrictModel):
    planned_runs: StrictInt | None = Field(default=None, ge=0)
    observed_runs: StrictInt | None = Field(default=None, ge=0)
    failures: StrictInt | None = Field(default=None, ge=0)
    attributed_failures: StrictInt | None = Field(default=None, ge=0)
    runner_invalid: StrictInt | None = Field(default=None, ge=0)
    retry_groups: StrictInt | None = Field(default=None, ge=0)
    retry_groups_complete: StrictInt | None = Field(default=None, ge=0)
    tool_added_items: StrictInt | None = Field(default=None, ge=0)
    tool_false_positive: StrictInt | None = Field(default=None, ge=0)
    high_risk_false_negative: StrictInt | None = Field(default=None, ge=0)
    error_pass: StrictInt | None = Field(default=None, ge=0)
    refs: list[ArtifactRefV1] = Field(default_factory=list)


class IterationIndexV1(StrictModel):
    contract: Literal["iteration-index@1.0"]
    schema_version: Literal["1.0"]
    identity: IterationIdentityV1
    freeze: FreezeIndexV1
    activation: ActivationV1
    versions: IterationVersionsV1
    ledger: ArtifactRefV1
    changes: list[ChangeIndexEntryV1] = Field(min_length=1)
    formal_evidence: FormalEvidenceV1
    policy: PolicyRefV1
    attestations: dict[str, AttestationRefV1]
    formal_release_effect: Literal["NONE"]

    @model_validator(mode="after")
    def _required_attestations(self) -> "IterationIndexV1":
        missing = set(ATTESTATION_NAMES) - set(self.attestations)
        if missing:
            raise ValueError(f"required attestations missing: {sorted(missing)}")
        unknown = set(self.attestations) - set(ATTESTATION_NAMES)
        if unknown:
            raise ValueError(f"unsupported attestation types: {sorted(unknown)}")
        return self


class MetricResultV1(StrictModel):
    state: Literal["OBSERVED", "NOT_OBSERVED", "NOT_COMPUTABLE", "BLOCKED"]
    numerator: _Number | None = None
    denominator: _Number | None = None
    value: _Number | None = None
    unit: Literal["ratio", "minutes", "months", "count"]
    evidence_refs: list[str] = Field(default_factory=list)
    formula_version: str = Field(min_length=1)


class DenominatorV1(StrictModel):
    candidate_count: StrictInt = Field(ge=0)
    eligible_count: StrictInt = Field(ge=0)
    excluded_count: StrictInt = Field(ge=0)
    blocked_count: StrictInt = Field(ge=0)
    stop_triggered_count: StrictInt = Field(ge=0)
    out_of_plan_count: StrictInt = Field(ge=0)
    attempt_count: StrictInt = Field(ge=0)
    retry_group_count: StrictInt = Field(ge=0)
    candidate_ids: list[str]
    eligible_ids: list[str]
    excluded_ids: list[str]
    blocked_ids: list[str]
    stop_triggered_ids: list[str]
    out_of_plan_ids: list[str]
    attempt_ids: list[str]
    retry_group_ids: list[str]


class MetricsV1(StrictModel):
    evidence_completeness_rate: MetricResultV1
    run_availability_rate: MetricResultV1
    failure_attribution_rate: MetricResultV1
    retry_retention_rate: MetricResultV1
    tool_false_positive_rate: MetricResultV1
    high_risk_false_negative_count: MetricResultV1
    error_pass_count: MetricResultV1
    net_savings: MetricResultV1
    payback_months: MetricResultV1


class RoiV1(StrictModel):
    formula_version: str = Field(min_length=1)
    net_savings: MetricResultV1
    payback_months: MetricResultV1
    costs: CostPolicyV1
    evidence_refs: list[str] = Field(default_factory=list)


class IterationSummaryV1(StrictModel):
    contract: Literal["iteration-summary@1.0"]
    schema_version: Literal["1.0"]
    status: Literal["VALID", "BLOCKED", "STOP_TRIGGERED"]
    code: str = Field(min_length=1)
    errors: list[str]
    identity: IterationIdentityV1
    evidence_class: Literal["FIXTURE", "REAL"]
    business_evidence: bool
    versions: IterationVersionsV1
    policy: PolicyRefV1
    denominator: DenominatorV1
    metrics: MetricsV1
    roi: RoiV1
    stop_triggers: list[str]
    conflicts: list[str]
    missing_evidence: list[str]
    source_refs: list[str]
    source_digests: list[str]
    formal_release_effect: Literal["NONE"]
    formal_release_allowed: Literal[False]
    decision_digest: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def _business_evidence_is_derived(self) -> "IterationSummaryV1":
        expected = self.evidence_class == "REAL" and self.status == "VALID"
        if self.business_evidence != expected:
            raise ValueError(
                "business_evidence must be true only for a VALID REAL summary"
            )
        return self


class ReportIdentityV1(StrictModel):
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    change_ref: str = Field(min_length=1)
    version_type: Literal["daily", "hotfix", "major"]


class CompatibilityMatrixV1(StrictModel):
    manifest: str
    catalog: str
    agent_spec: str
    agent_run: str
    pilot_evidence: str
    difference_draft: str
    adjudication: str
    change_report: str
    ledger: str
    qualityctl: str


class CompatibilityResultV1(StrictModel):
    ok: bool
    kind: Literal["pilot_compatibility"]
    status: Literal["COMPATIBLE", "BLOCKED"]
    code: str
    message: str
    paths: list[str]
    errors: list[str]
    matrix: CompatibilityMatrixV1
    formal_release_effect: Literal["NONE"]


class CatalogReadinessReportV1(StrictModel):
    ok: bool
    kind: Literal["catalog_readiness"]
    status: Literal["READY", "BLOCKED"]
    code: str
    message: str
    paths: list[str]
    errors: list[str]
    catalog_count: StrictInt | None = None
    catalog_version: str | None = None
    source_ref: str | None = None
    reviewer_ids: list[str] = Field(default_factory=list)
    oracle_covered_count: StrictInt | None = None
    dimension_coverage: list[str] = Field(default_factory=list)
    historical_escape_refs: list[str] = Field(default_factory=list)
    formal_release_effect: Literal["NONE"]


class ReportDigestsV1(StrictModel):
    manifest: str | None = None
    catalog: str | None = None
    agent_spec: str | None = None
    agent_runs: str | None = None


class ChangeEvidenceReportV1(StrictModel):
    contract: Literal["change-evidence-report@1.0"]
    schema_version: Literal["1.0"]
    generated_at: str = Field(min_length=1)
    identity: ReportIdentityV1
    status: Literal["ELIGIBLE", "EXCLUDED", "BLOCKED", "STOP_TRIGGERED"]
    code: str = Field(min_length=1)
    kind: Literal["pilot_evidence_report"]
    message: str
    paths: list[str]
    errors: list[str]
    formal_release_effect: Literal["NONE"]
    formal_release_allowed: Literal[False]
    retained_for_ledger: bool
    decision_digest: str = Field(min_length=1)
    compatibility: CompatibilityResultV1 | None = None
    catalog_readiness: CatalogReadinessReportV1 | None = None
    raw_gate: str | None = None
    raw_release_allowed: bool | None = None
    blocking_checks: list[str] = Field(default_factory=list)
    draft_digest: str | None = None
    adjudication_digest: str | None = None
    input_digests: ReportDigestsV1 | None = None
    recomputed_digests: ReportDigestsV1 | None = None
    attempt_ids: list[str] = Field(default_factory=list)


class AdjudicationIdentityV1(StrictModel):
    pilot_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)


class AdjudicationItemV1(StrictModel):
    difference_id: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    high_risk: bool = False
    status: Literal["OPEN", "CLOSED"]
    adjudicator: str = Field(min_length=1)
    adjudicated_at: str = Field(min_length=1)


class AdjudicationV1(StrictModel):
    contract: Literal["adjudication@1.0"]
    identity: AdjudicationIdentityV1
    difference_draft_digest: str = Field(min_length=1)
    items: list[AdjudicationItemV1]
    reviewer_id: str = Field(min_length=1)
    reviewer_role: str = Field(min_length=1)
    adjudicated_at: str = Field(min_length=1)
    status: Literal["OPEN", "CLOSED"]
    formal_release_effect: Literal["NONE"]


def _flatten_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for item in exc.errors():
        location = item.get("loc", ())
        path = ""
        for part in location:
            if isinstance(part, int):
                path += f"[{part}]"
            else:
                path += ("." if path else "") + str(part)
        errors.append(f"{path or '<root>'}: {item.get('msg', 'invalid value')}")
    return errors


def _validate_model(payload: Any, model_cls: type[BaseModel], kind: str) -> ContractValidationResult:
    if not isinstance(payload, Mapping):
        return ContractValidationResult(
            False,
            [f"{kind} payload must be a JSON object"],
            code="INVALID_PAYLOAD",
        )
    try:
        model = model_cls.model_validate(payload)
    except ValidationError as exc:
        return ContractValidationResult(
            False,
            _flatten_errors(exc),
            code="SCHEMA_VALIDATION_ERROR",
        )
    return ContractValidationResult(True, model=model)


def validate_iteration_index(payload: Any) -> ContractValidationResult:
    return _validate_model(payload, IterationIndexV1, "iteration_index")


def validate_iteration_summary(payload: Any) -> ContractValidationResult:
    return _validate_model(payload, IterationSummaryV1, "iteration_summary")


def validate_evidence_ledger(payload: Any) -> ContractValidationResult:
    return _validate_model(payload, EvidenceLedgerV1, "evidence_ledger")


def validate_change_evidence_report(payload: Any) -> ContractValidationResult:
    return _validate_model(payload, ChangeEvidenceReportV1, "change_evidence_report")


def validate_adjudication(payload: Any) -> ContractValidationResult:
    return _validate_model(payload, AdjudicationV1, "adjudication")


def _safe_iso(value: str, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be an RFC 3339 timestamp with timezone")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be an RFC 3339 timestamp with timezone")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{label} must include a timezone")
        return None
    return parsed


def _metric(
    state: Literal["OBSERVED", "NOT_OBSERVED", "NOT_COMPUTABLE", "BLOCKED"],
    *,
    numerator: float | int | None = None,
    denominator: float | int | None = None,
    value: float | int | None = None,
    unit: Literal["ratio", "minutes", "months", "count"],
    refs: Sequence[str] = (),
    formula_version: str = "metrics@1.0",
) -> dict[str, Any]:
    return {
        "state": state,
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "unit": unit,
        "evidence_refs": sorted(set(str(ref) for ref in refs if ref)),
        "formula_version": formula_version,
    }


def _default_versions() -> dict[str, Any]:
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
        "qualityctl_version": APPROVED_QUALITYCTL_VERSION,
        "core_version": APPROVED_CORE_VERSION,
        "core_commit": APPROVED_CORE_COMMIT,
        "python_version": "3.11",
        "catalog_version": APPROVED_CATALOG_VERSION,
        "mapping_version": APPROVED_MAPPING_VERSION,
        "threshold_version": APPROVED_THRESHOLD_VERSION,
        "roi_policy_version": APPROVED_POLICY_VERSION,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "writer_reader_matrix": "fixture-writer-reader@1.0",
        "matrix_approved_by": "fixture-release-owner",
        "matrix_approved_at": "2026-08-18T08:00:00+08:00",
        "matrix_valid_until": "2099-12-31T23:59:59+00:00",
    }


def _default_policy() -> dict[str, Any]:
    return {
        "version": APPROVED_POLICY_VERSION,
        "ref": "fixture://policy/roi-001",
        "digest": APPROVED_POLICY_DIGEST,
        "approved_by": "fixture-policy-owner",
        "approved_at": "2026-08-18T08:00:00+08:00",
        "valid_until": "2099-12-31T23:59:59+00:00",
        "formula_version": "roi-formula@1.0",
        "costs": {},
    }


def _empty_denominator() -> dict[str, Any]:
    return {
        "candidate_count": 0,
        "eligible_count": 0,
        "excluded_count": 0,
        "blocked_count": 0,
        "stop_triggered_count": 0,
        "out_of_plan_count": 0,
        "attempt_count": 0,
        "retry_group_count": 0,
        "candidate_ids": [],
        "eligible_ids": [],
        "excluded_ids": [],
        "blocked_ids": [],
        "stop_triggered_ids": [],
        "out_of_plan_ids": [],
        "attempt_ids": [],
        "retry_group_ids": [],
    }


def _blocked_metrics() -> dict[str, Any]:
    return {
        "evidence_completeness_rate": _metric("BLOCKED", unit="ratio"),
        "run_availability_rate": _metric("BLOCKED", unit="ratio"),
        "failure_attribution_rate": _metric("BLOCKED", unit="ratio"),
        "retry_retention_rate": _metric("BLOCKED", unit="ratio"),
        "tool_false_positive_rate": _metric("BLOCKED", unit="ratio"),
        "high_risk_false_negative_count": _metric("BLOCKED", unit="count"),
        "error_pass_count": _metric("BLOCKED", unit="count"),
        "net_savings": _metric("BLOCKED", unit="minutes"),
        "payback_months": _metric("BLOCKED", unit="months"),
    }


class _SummaryProblem(Exception):
    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path


def _resolve_json_ref(ref: ArtifactRefV1, base_dir: Path) -> tuple[Any, str]:
    raw_path = ref.path
    if ref.media_type != "application/json":
        raise _SummaryProblem(
            "UNSUPPORTED_MEDIA_TYPE",
            f"JSON artifact requires media_type application/json: {ref.media_type}",
            path=raw_path,
        )
    candidate_path = Path(raw_path)
    if candidate_path.is_absolute() or any(part == ".." for part in candidate_path.parts):
        raise _SummaryProblem("UNSAFE_EVIDENCE_PATH", f"artifact path escapes base_dir: {raw_path}", path=raw_path)
    try:
        root = base_dir.resolve(strict=True)
        resolved = (root / candidate_path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _SummaryProblem("INPUT_NOT_FOUND", f"artifact path cannot be resolved: {raw_path}: {exc}", path=raw_path) from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise _SummaryProblem("UNSAFE_EVIDENCE_PATH", f"artifact path escapes base_dir: {raw_path}", path=raw_path) from exc
    if resolved.is_dir():
        raise _SummaryProblem("INPUT_READ_ERROR", f"artifact path is a directory: {raw_path}", path=raw_path)
    try:
        data = resolved.read_bytes()
    except OSError as exc:
        raise _SummaryProblem("INPUT_READ_ERROR", str(exc), path=raw_path) from exc
    if len(data) != ref.size:
        raise _SummaryProblem(
            "ARTIFACT_DIGEST_MISMATCH",
            f"artifact size mismatch for {raw_path}: expected {ref.size}, got {len(data)}",
            path=raw_path,
        )
    actual = bytes_digest(data)
    if actual != ref.digest:
        raise _SummaryProblem(
            "ARTIFACT_DIGEST_MISMATCH",
            f"artifact digest mismatch for {raw_path}: expected {ref.digest}, got {actual}",
            path=raw_path,
        )
    try:
        return json.loads(data.decode("utf-8")), actual
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _SummaryProblem("INPUT_READ_ERROR", f"invalid JSON in {raw_path}: {exc}", path=raw_path) from exc


def _validate_versions(index: IterationIndexV1) -> list[tuple[str, str]]:
    versions = index.versions
    errors: list[tuple[str, str]] = []
    if versions.qualityctl_version != APPROVED_QUALITYCTL_VERSION:
        errors.append(("UNSUPPORTED_CORE", "qualityctl version is not in the approved exact matrix"))
    if versions.core_version != APPROVED_CORE_VERSION or versions.core_commit != APPROVED_CORE_COMMIT:
        errors.append(("UNSUPPORTED_CORE", "core version/commit is not in the approved exact matrix"))
    if versions.canonicalization_version != CANONICALIZATION_VERSION:
        errors.append(("UNSUPPORTED_SCHEMA", "canonicalization version is not approved"))
    if versions.catalog_version != APPROVED_CATALOG_VERSION:
        errors.append(("UNSUPPORTED_POLICY", "catalog version is not in the approved fixture matrix"))
    if versions.mapping_version != APPROVED_MAPPING_VERSION:
        errors.append(("UNSUPPORTED_POLICY", "mapping version is not in the approved fixture matrix"))
    if versions.threshold_version != APPROVED_THRESHOLD_VERSION:
        errors.append(("UNSUPPORTED_POLICY", "threshold version is not in the approved fixture matrix"))
    if versions.roi_policy_version != APPROVED_POLICY_VERSION:
        errors.append(("UNSUPPORTED_POLICY", "ROI policy version is not in the approved exact matrix"))
    if index.policy.version != versions.roi_policy_version:
        errors.append(("UNSUPPORTED_POLICY", "policy version disagrees with the pinned matrix"))
    if index.policy.digest != APPROVED_POLICY_DIGEST:
        errors.append(("UNSUPPORTED_POLICY", "policy digest is not in the approved exact matrix"))
    matrix_errors: list[str] = []
    frozen_at = _safe_iso(index.freeze.frozen_at, "freeze.frozen_at", matrix_errors)
    approved_at = _safe_iso(versions.matrix_approved_at, "versions.matrix_approved_at", matrix_errors)
    valid_until = _safe_iso(versions.matrix_valid_until, "versions.matrix_valid_until", matrix_errors)
    policy_approved_at = _safe_iso(index.policy.approved_at, "policy.approved_at", matrix_errors)
    policy_valid_until = _safe_iso(index.policy.valid_until, "policy.valid_until", matrix_errors)
    if matrix_errors:
        errors.append(("INVALID_APPROVAL_WINDOW", "; ".join(matrix_errors)))
    else:
        if approved_at is not None and valid_until is not None and approved_at > valid_until:
            errors.append(("INVALID_APPROVAL_WINDOW", "matrix approval window is reversed"))
        if frozen_at is not None and valid_until is not None and frozen_at > valid_until:
            errors.append(("MATRIX_EXPIRED", "compatibility matrix is expired"))
        if policy_approved_at is not None and policy_valid_until is not None and policy_approved_at > policy_valid_until:
            errors.append(("INVALID_APPROVAL_WINDOW", "policy approval window is reversed"))
        if frozen_at is not None and policy_valid_until is not None and frozen_at > policy_valid_until:
            errors.append(("POLICY_EXPIRED", "ROI policy approval is expired"))
    return errors


def _validate_attestations(attestations: Mapping[str, AttestationRefV1]) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    for name, expected in ATTESTATION_SUCCESS_ALLOWLIST.items():
        item = attestations.get(name)
        if item is None:
            errors.append(("ATTESTATION_NOT_APPROVED", f"required attestation missing: {name}"))
            continue
        if item.status != expected:
            errors.append(("ATTESTATION_NOT_APPROVED", f"attestation {name} status {item.status!r} is not {expected!r}"))
        if name == "formal_result" and item.release_effect != FORMAL_RELEASE_EFFECT:
            errors.append(("STOP_TRIGGERED", "formal result attestation has a release effect"))
        if name == "secret_scan" and item.sensitive_data is True:
            errors.append(("STOP_TRIGGERED", "secret scan attestation reports sensitive data"))
    return errors


def _identity_key(identity: ChangeIdentityV1) -> tuple[str, str, str]:
    return (identity.pilot_id, identity.change_id, identity.run_id)


def _check_identity(index: IterationIndexV1, entry: ChangeIndexEntryV1, ledger_entry: LedgerEntryV1) -> list[tuple[str, str]]:
    expected = (index.identity.pilot_id, index.identity.iteration_id)
    errors: list[tuple[str, str]] = []
    for candidate in (entry.identity, ledger_entry):
        if candidate.pilot_id != expected[0] or candidate.iteration_id != expected[1]:
            errors.append(("MIXED_ITERATION_IDENTITY", "candidate identity is from a different pilot or iteration"))
    if _identity_key(entry.identity) != _identity_key(
        ChangeIdentityV1(
            pilot_id=ledger_entry.pilot_id,
            iteration_id=ledger_entry.iteration_id,
            change_id=ledger_entry.change_id,
            run_id=ledger_entry.run_id,
        )
    ):
        errors.append(("MIXED_ITERATION_IDENTITY", "index and ledger change identities disagree"))
    if entry.status != ledger_entry.status:
        errors.append(("LEDGER_STATUS_MISMATCH", "index and ledger statuses disagree"))
    if entry.evidence_digest != ledger_entry.evidence_digest:
        errors.append(("EVIDENCE_DIGEST_MISMATCH", "index and ledger evidence digests disagree"))
    return errors


def _build_denominator(index: IterationIndexV1, ledger: EvidenceLedgerV1) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    errors: list[tuple[str, str]] = []
    ledger_by_key = {
        (item.pilot_id, item.change_id, item.run_id): item
        for item in ledger.entries
    }
    seen_keys: set[tuple[str, str, str]] = set()
    seen_digests: set[str] = set()
    conflicts = False
    for entry in index.changes:
        key = _identity_key(entry.identity)
        if key in seen_keys:
            errors.append(("DUPLICATE_CHANGE_IDENTITY", f"duplicate change identity: {key}"))
            conflicts = True
        seen_keys.add(key)
        if entry.evidence_digest in seen_digests:
            errors.append(("DUPLICATE_EVIDENCE_DIGEST", f"duplicate evidence digest: {entry.evidence_digest}"))
            conflicts = True
        seen_digests.add(entry.evidence_digest)
        ledger_entry = ledger_by_key.get(key)
        if ledger_entry is None:
            errors.append(("LEDGER_MISSING_ENTRY", f"ledger has no entry for {key}"))
            conflicts = True
        else:
            identity_errors = _check_identity(index, entry, ledger_entry)
            errors.extend(identity_errors)
            if identity_errors:
                conflicts = True
    if len(ledger.entries) != len(index.changes):
        errors.append(("LEDGER_COMPLETENESS_ERROR", "ledger must retain every indexed candidate exactly once"))
        conflicts = True
    entries = [] if conflicts else index.changes
    candidate_ids = sorted(entry.identity.change_id for entry in entries)
    eligible = [entry for entry in entries if entry.status == "ELIGIBLE" and not entry.out_of_plan]
    excluded = [entry for entry in entries if entry.status == "EXCLUDED"]
    blocked = [entry for entry in entries if entry.status == "BLOCKED"]
    stopped = [entry for entry in entries if entry.status == "STOP_TRIGGERED"]
    out_of_plan = [entry for entry in entries if entry.out_of_plan]
    attempts = sorted({attempt_id for entry in entries for attempt_id in entry.attempt_ids})
    retry_group_ids = sorted(
        {
            str(attempt.initial_attempt_ref or attempt.attempt_id)
            for attempt in ledger.attempts
            if attempt.initial_attempt_ref is not None or attempt.kind.lower() in {"rerun", "retry"}
        }
    )
    denominator = {
        "candidate_count": len(entries),
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "blocked_count": len(blocked),
        "stop_triggered_count": len(stopped),
        "out_of_plan_count": len(out_of_plan),
        "attempt_count": len(attempts),
        "retry_group_count": len(retry_group_ids),
        "candidate_ids": candidate_ids,
        "eligible_ids": sorted(entry.identity.change_id for entry in eligible),
        "excluded_ids": sorted(entry.identity.change_id for entry in excluded),
        "blocked_ids": sorted(entry.identity.change_id for entry in blocked),
        "stop_triggered_ids": sorted(entry.identity.change_id for entry in stopped),
        "out_of_plan_ids": sorted(entry.identity.change_id for entry in out_of_plan),
        "attempt_ids": attempts,
        "retry_group_ids": retry_group_ids,
    }
    return denominator, errors


def _decision_digest(summary: Mapping[str, Any]) -> str:
    stable = copy.deepcopy(dict(summary))
    for key in ("generated_at", "errors", "message", "paths", "decision_digest"):
        stable.pop(key, None)
    return canonical_digest(stable, purpose="decision")


def _summary_payload(
    *,
    identity: Mapping[str, Any],
    versions: Mapping[str, Any],
    policy: Mapping[str, Any],
    evidence_class: str,
    status: str,
    code: str,
    errors: Sequence[str],
    denominator: Mapping[str, Any],
    metrics: Mapping[str, Any],
    roi: Mapping[str, Any],
    stop_triggers: Sequence[str] = (),
    conflicts: Sequence[str] = (),
    missing_evidence: Sequence[str] = (),
    source_refs: Sequence[str] = (),
    source_digests: Sequence[str] = (),
    generated_at: str | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "contract": ITERATION_SUMMARY_CONTRACT,
        "schema_version": ITERATION_SCHEMA_VERSION,
        "status": status,
        "code": code,
        "errors": list(errors),
        "identity": dict(identity),
        "evidence_class": evidence_class,
        "business_evidence": evidence_class == "REAL" and status == "VALID",
        "versions": copy.deepcopy(dict(versions)),
        "policy": copy.deepcopy(dict(policy)),
        "denominator": copy.deepcopy(dict(denominator)),
        "metrics": copy.deepcopy(dict(metrics)),
        "roi": copy.deepcopy(dict(roi)),
        "stop_triggers": sorted(set(stop_triggers)),
        "conflicts": sorted(set(conflicts)),
        "missing_evidence": sorted(set(missing_evidence)),
        "source_refs": sorted(set(str(item) for item in source_refs if item)),
        "source_digests": sorted(set(str(item) for item in source_digests if item)),
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
        "formal_release_allowed": False,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
    }
    output["decision_digest"] = _decision_digest(output)
    return output


def _calculate_metrics(
    index: IterationIndexV1,
    denominator: Mapping[str, Any],
    *,
    source_refs: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[tuple[str, str]]]:
    formal = index.formal_evidence
    refs = list(source_refs)
    problems: list[tuple[str, str]] = []
    eligible_count = int(denominator["eligible_count"])
    candidate_count = int(denominator["candidate_count"])
    if eligible_count == 0:
        evidence_metric = _metric("BLOCKED", unit="ratio", refs=refs)
    else:
        evidence_metric = _metric(
            "OBSERVED",
            numerator=eligible_count,
            denominator=eligible_count,
            value=1.0,
            unit="ratio",
            refs=refs,
        )

    if formal.planned_runs is None or formal.observed_runs is None or formal.planned_runs == 0:
        run_metric = _metric("BLOCKED", unit="ratio", refs=refs)
        problems.append(("MISSING_FORMAL_EVIDENCE", "planned and observed runs are required"))
    else:
        effective_runs = max(0, formal.observed_runs - int(formal.runner_invalid or 0))
        run_metric = _metric(
            "OBSERVED",
            numerator=effective_runs,
            denominator=formal.planned_runs,
            value=effective_runs / formal.planned_runs,
            unit="ratio",
            refs=refs,
        )

    failures = formal.failures
    if failures == 0:
        failure_metric = _metric("NOT_OBSERVED", unit="ratio", refs=refs)
    elif failures is None or formal.attributed_failures is None:
        failure_metric = _metric("BLOCKED", unit="ratio", refs=refs)
        problems.append(("MISSING_FORMAL_EVIDENCE", "failure attribution is required when failures exist"))
    else:
        failure_metric = _metric(
            "OBSERVED",
            numerator=formal.attributed_failures,
            denominator=failures,
            value=formal.attributed_failures / failures,
            unit="ratio",
            refs=refs,
        )

    retry_groups = formal.retry_groups
    if retry_groups == 0:
        retry_metric = _metric("NOT_OBSERVED", unit="ratio", refs=refs)
    elif retry_groups is None or formal.retry_groups_complete is None:
        retry_metric = _metric("BLOCKED", unit="ratio", refs=refs)
        problems.append(("MISSING_FORMAL_EVIDENCE", "retry retention is required when retries exist"))
    else:
        retry_metric = _metric(
            "OBSERVED",
            numerator=formal.retry_groups_complete,
            denominator=retry_groups,
            value=formal.retry_groups_complete / retry_groups,
            unit="ratio",
            refs=refs,
        )

    tool_added = formal.tool_added_items
    if tool_added == 0:
        false_positive_metric = _metric("NOT_OBSERVED", unit="ratio", refs=refs)
    elif tool_added is None or formal.tool_false_positive is None:
        false_positive_metric = _metric("BLOCKED", unit="ratio", refs=refs)
        problems.append(("MISSING_FORMAL_EVIDENCE", "tool false-positive count is required when tool items exist"))
    else:
        false_positive_metric = _metric(
            "OBSERVED",
            numerator=formal.tool_false_positive,
            denominator=tool_added,
            value=formal.tool_false_positive / tool_added,
            unit="ratio",
            refs=refs,
        )

    high_risk = formal.high_risk_false_negative
    high_risk_metric = (
        _metric("BLOCKED", unit="count", refs=refs)
        if high_risk is None
        else _metric("OBSERVED", numerator=high_risk, denominator=candidate_count, value=high_risk, unit="count", refs=refs)
    )
    if high_risk is None:
        problems.append(("MISSING_FORMAL_EVIDENCE", "high-risk false-negative count is required"))
    error_pass = formal.error_pass
    error_pass_metric = (
        _metric("BLOCKED", unit="count", refs=refs)
        if error_pass is None
        else _metric("OBSERVED", numerator=error_pass, denominator=candidate_count, value=error_pass, unit="count", refs=refs)
    )
    if error_pass is None:
        problems.append(("MISSING_FORMAL_EVIDENCE", "error-pass count is required"))

    costs = index.policy.costs.model_dump()
    required_costs = (
        "build_minutes",
        "gross_savings_minutes",
        "maintenance_minutes",
        "false_positive_minutes",
        "flaky_minutes",
        "runner_minutes",
        "llm_minutes",
        "run_minutes",
        "data_minutes",
    )
    missing_costs = [name for name in required_costs if costs.get(name) is None]
    if missing_costs:
        net_metric = _metric("BLOCKED", unit="minutes", refs=refs)
        payback_metric = _metric("BLOCKED", unit="months", refs=refs)
        problems.append(("MISSING_ROI_COST", f"required ROI costs missing: {sorted(missing_costs)}"))
    else:
        net_value = float(costs["gross_savings_minutes"]) - sum(
            float(costs[name])
            for name in required_costs
            if name not in {"build_minutes", "gross_savings_minutes"}
        )
        net_metric = _metric(
            "OBSERVED",
            numerator=net_value,
            denominator=1,
            value=net_value,
            unit="minutes",
            refs=refs,
        )
        if net_value <= 0:
            payback_metric = _metric(
                "NOT_COMPUTABLE",
                numerator=costs["build_minutes"],
                denominator=net_value,
                value=None,
                unit="months",
                refs=refs,
            )
        else:
            payback_metric = _metric(
                "OBSERVED",
                numerator=costs["build_minutes"],
                denominator=net_value,
                value=float(costs["build_minutes"]) / net_value,
                unit="months",
                refs=refs,
            )

    metrics = {
        "evidence_completeness_rate": evidence_metric,
        "run_availability_rate": run_metric,
        "failure_attribution_rate": failure_metric,
        "retry_retention_rate": retry_metric,
        "tool_false_positive_rate": false_positive_metric,
        "high_risk_false_negative_count": high_risk_metric,
        "error_pass_count": error_pass_metric,
        "net_savings": net_metric,
        "payback_months": payback_metric,
    }
    roi = {
        "formula_version": index.policy.formula_version,
        "net_savings": net_metric,
        "payback_months": payback_metric,
        "costs": costs,
        "evidence_refs": sorted(set(refs)),
    }
    metric_stops: list[str] = []
    if high_risk is not None and high_risk > 0:
        metric_stops.append("HIGH_RISK_FALSE_NEGATIVE")
    if error_pass is not None and error_pass > 0:
        metric_stops.append("ERROR_PASS")
    return metrics, roi, metric_stops, problems


def summarize_iteration(
    index: Mapping[str, Any],
    *,
    base_dir: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Recompute one frozen iteration summary from local fixture artifacts.

    ``now`` is injectable for approval-window tests.  It is display metadata
    only and never enters ``decision_digest``.
    """

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    structural = validate_iteration_index(index)
    if not structural.ok:
        fallback_identity = {
            "pilot_id": "unknown-pilot",
            "iteration_id": "unknown-iteration",
            "evidence_class": "FIXTURE",
        }
        unsupported_contract = isinstance(index, Mapping) and (
            index.get("contract") != ITERATION_INDEX_CONTRACT
            or index.get("schema_version") != ITERATION_SCHEMA_VERSION
        )
        output = _summary_payload(
            identity=fallback_identity,
            versions=_default_versions(),
            policy=_default_policy(),
            evidence_class="FIXTURE",
            status="BLOCKED",
            code="UNSUPPORTED_SCHEMA" if unsupported_contract else "INVALID_INDEX",
            errors=structural.errors,
            denominator=_empty_denominator(),
            metrics=_blocked_metrics(),
            roi={
                "formula_version": "roi-formula@1.0",
                "net_savings": _metric("BLOCKED", unit="minutes"),
                "payback_months": _metric("BLOCKED", unit="months"),
                "costs": {},
                "evidence_refs": [],
            },
        )
        return output
    parsed = structural.model
    assert isinstance(parsed, IterationIndexV1)
    identity = parsed.identity.model_dump()
    versions = parsed.versions.model_dump()
    policy = parsed.policy.model_dump()
    source_refs: list[str] = []
    source_digests: list[str] = []
    errors: list[tuple[str, str]] = []
    stop_triggers: list[str] = []
    missing_evidence: list[str] = []
    conflicts: list[str] = []

    if parsed.identity.evidence_class == "REAL" and parsed.activation.r2_g0_status not in {"READY", "R2-G0_READY"}:
        return _summary_payload(
            identity=identity,
            versions=versions,
            policy=policy,
            evidence_class=parsed.identity.evidence_class,
            status="BLOCKED",
            code="BLOCKED_BY_R2_G0",
            errors=["R2-G0 is not READY; real evidence cannot enter the summary"],
            denominator=_empty_denominator(),
            metrics=_blocked_metrics(),
            roi={
                "formula_version": parsed.policy.formula_version,
                "net_savings": _metric("BLOCKED", unit="minutes"),
                "payback_months": _metric("BLOCKED", unit="months"),
                "costs": parsed.policy.costs.model_dump(),
                "evidence_refs": [],
            },
            generated_at=current.isoformat(),
        )

    errors.extend(_validate_versions(parsed))
    errors.extend(_validate_attestations(parsed.attestations))
    for code, message in errors:
        if code == "STOP_TRIGGERED":
            stop_triggers.append("UNAUTHORIZED_RELEASE_OR_SENSITIVE_DATA")
        if code.startswith("MISSING"):
            missing_evidence.append(message)

    base = Path(base_dir).resolve() if base_dir is not None else Path.cwd().resolve()
    try:
        ledger_payload, ledger_digest = _resolve_json_ref(parsed.ledger, base)
        source_refs.append(parsed.ledger.path)
        source_digests.append(ledger_digest)
    except _SummaryProblem as problem:
        errors.append((problem.code, problem.message))
        ledger_payload = None

    ledger_model: EvidenceLedgerV1 | None = None
    if ledger_payload is not None:
        ledger_result = validate_evidence_ledger(ledger_payload)
        if not ledger_result.ok:
            errors.append(("INVALID_LEDGER", ledger_result.errors[0] if ledger_result.errors else "invalid ledger"))
        else:
            ledger_model = ledger_result.model
            assert isinstance(ledger_model, EvidenceLedgerV1)
            if ledger_model.status != "FROZEN":
                errors.append(("INVALID_LEDGER", "only a FROZEN ledger can enter an iteration summary"))
            if ledger_model.pilot_id != parsed.identity.pilot_id or ledger_model.iteration_id != parsed.identity.iteration_id:
                errors.append(("MIXED_ITERATION_IDENTITY", "ledger identity does not match the index"))

    if ledger_model is None:
        denominator = _empty_denominator()
    else:
        denominator, denominator_errors = _build_denominator(parsed, ledger_model)
        errors.extend(denominator_errors)

    for entry in parsed.changes:
        refs = (entry.report, entry.bundle, entry.draft, entry.adjudication)
        try:
            report_payload, report_digest = _resolve_json_ref(entry.report, base)
            bundle_payload, bundle_digest = _resolve_json_ref(entry.bundle, base)
            draft_payload, draft_digest = _resolve_json_ref(entry.draft, base)
            adjudication_payload, adjudication_digest = _resolve_json_ref(entry.adjudication, base)
            source_refs.extend(ref.path for ref in refs)
            source_digests.extend((report_digest, bundle_digest, draft_digest, adjudication_digest))
        except _SummaryProblem as problem:
            errors.append((problem.code, problem.message))
            missing_evidence.append(problem.path or "unknown artifact")
            continue
        report_result = validate_change_evidence_report(report_payload)
        if not report_result.ok:
            errors.append(("INVALID_CHANGE_REPORT", report_result.errors[0] if report_result.errors else "invalid change report"))
            continue
        report_model = report_result.model
        assert isinstance(report_model, ChangeEvidenceReportV1)
        if report_model.decision_digest != entry.evidence_digest:
            errors.append(("EVIDENCE_DIGEST_MISMATCH", f"report digest does not match index for {entry.identity.change_id}"))
        expected_report_identity = {
            "pilot_id": entry.identity.pilot_id,
            "iteration_id": entry.identity.iteration_id,
            "change_id": entry.identity.change_id,
            "run_id": entry.identity.run_id,
        }
        if report_model.identity.model_dump(include=set(expected_report_identity)) != expected_report_identity:
            errors.append(("MIXED_ITERATION_IDENTITY", f"report identity does not match {entry.identity.change_id}"))
        if report_model.status == "STOP_TRIGGERED":
            stop_triggers.append(report_model.code)
        if report_model.status != entry.status:
            errors.append(("REPORT_STATUS_MISMATCH", f"report status disagrees with index for {entry.identity.change_id}"))

        if not isinstance(bundle_payload, Mapping):
            errors.append(("INVALID_BUNDLE", f"bundle for {entry.identity.change_id} must be an object"))
            continue
        recomputed = verify_change_bundle(bundle_payload, base_dir=base)
        if recomputed.get("status") == "STOP_TRIGGERED":
            stop_triggers.append(str(recomputed.get("code", "STOP_TRIGGERED")))
        if recomputed.get("status") != report_model.status or recomputed.get("decision_digest") != report_model.decision_digest:
            errors.append(("REPORT_RECOMPUTE_MISMATCH", f"report for {entry.identity.change_id} is not reproducible from the bundle"))

        if not isinstance(draft_payload, Mapping) or not isinstance(adjudication_payload, Mapping):
            errors.append(("INVALID_ADJUDICATION", f"draft/adjudication for {entry.identity.change_id} must be objects"))
        else:
            adjudication_result = validate_adjudication(adjudication_payload)
            if not adjudication_result.ok:
                errors.append(("INVALID_ADJUDICATION", adjudication_result.errors[0] if adjudication_result.errors else "invalid adjudication"))
            else:
                adjudication_model = adjudication_result.model
                assert isinstance(adjudication_model, AdjudicationV1)
                expected_adjudication_identity = {
                    "pilot_id": entry.identity.pilot_id,
                    "change_id": entry.identity.change_id,
                    "run_id": entry.identity.run_id,
                }
                if adjudication_model.identity.model_dump() != expected_adjudication_identity:
                    errors.append(("ADJUDICATION_IDENTITY_MISMATCH", f"adjudication identity does not match {entry.identity.change_id}"))
                if draft_payload.get("decision_digest") != adjudication_model.difference_draft_digest:
                    errors.append(("ADJUDICATION_DIGEST_MISMATCH", f"adjudication draft digest does not match {entry.identity.change_id}"))
                raw = bundle_payload.get("raw") if isinstance(bundle_payload.get("raw"), Mapping) else {}
                expected_draft = compare_scopes(
                    bundle_payload.get("manual_scope", {}),
                    raw.get("tool_scope", {}) if isinstance(raw, Mapping) else {},
                    identity=bundle_payload.get("identity") if isinstance(bundle_payload.get("identity"), Mapping) else None,
                )
                if draft_payload.get("decision_digest") != expected_draft.get("decision_digest"):
                    errors.append(("ADJUDICATION_DIGEST_MISMATCH", f"draft is stale for {entry.identity.change_id}"))
    metrics, roi, metric_stops, metric_problems = _calculate_metrics(parsed, denominator, source_refs=source_refs)
    stop_triggers.extend(metric_stops)
    errors.extend(metric_problems)
    conflicts.extend(message for code, message in errors if code.startswith("DUPLICATE") or code.startswith("MIXED") or code.endswith("MISMATCH"))
    if any(code == "STOP_TRIGGERED" for code, _ in errors) or stop_triggers:
        status = "STOP_TRIGGERED"
        code = "STOP_TRIGGERED"
    elif errors or any(metric["state"] == "BLOCKED" for metric in metrics.values()):
        status = "BLOCKED"
        code = errors[0][0] if errors else "METRIC_BLOCKED"
    else:
        status = "VALID"
        code = "OK"
    error_text = [message for _, message in errors]
    return _summary_payload(
        identity=identity,
        versions=versions,
        policy=policy,
        evidence_class=parsed.identity.evidence_class,
        status=status,
        code=code,
        errors=error_text,
        denominator=denominator,
        metrics=metrics,
        roi=roi,
        stop_triggers=stop_triggers,
        conflicts=conflicts,
        missing_evidence=missing_evidence,
        source_refs=source_refs,
        source_digests=source_digests,
        generated_at=current.isoformat(),
    )


__all__ = [
    "APPROVED_CORE_COMMIT",
    "APPROVED_CORE_VERSION",
    "APPROVED_POLICY_VERSION",
    "APPROVED_POLICY_DIGEST",
    "APPROVED_QUALITYCTL_VERSION",
    "ATTESTATION_SUCCESS_ALLOWLIST",
    "EXACT_COMPATIBILITY_MATRIX",
    "ArtifactRefV1",
    "ArtifactRef",
    "AdjudicationV1",
    "CANONICALIZATION_VERSION",
    "ChangeEvidenceReportV1",
    "ChangeEvidenceReport",
    "CostPolicyV1",
    "EvidenceLedgerV1",
    "EvidenceLedger",
    "IterationIndexV1",
    "IterationIndex",
    "IterationSummaryV1",
    "IterationSummary",
    "ITERATION_INDEX_CONTRACT",
    "ITERATION_SCHEMA_VERSION",
    "ITERATION_SUMMARY_CONTRACT",
    "MetricResultV1",
    "MetricResult",
    "PolicyRefV1",
    "PolicyRef",
    "validate_adjudication",
    "validate_change_evidence_report",
    "validate_evidence_ledger",
    "validate_iteration_index",
    "validate_iteration_summary",
    "summarize_iteration",
]


# Short aliases mirror the existing versioned evidence API.
ArtifactRef = ArtifactRefV1
ChangeEvidenceReport = ChangeEvidenceReportV1
EvidenceLedger = EvidenceLedgerV1
IterationIndex = IterationIndexV1
IterationSummary = IterationSummaryV1
MetricResult = MetricResultV1
PolicyRef = PolicyRefV1
