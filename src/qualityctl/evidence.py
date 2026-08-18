"""Pilot Evidence v1 core.

The evidence pipeline is deliberately a narrow, local boundary around the
existing qualityctl rules.  It reads raw evidence, validates the pilot
contract, recomputes the existing gate, and writes new reports without ever
changing the raw inputs or the formal release decision.

This module is usable without the plugin or an external storage service.  The
CLI is an adapter over these functions; callers that already have parsed
objects can use the same public functions directly.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .gate import decide_quality_gate
from .io import read_json, read_jsonl
from .risk import RISK_DIMENSIONS
from .selection import select_regression_tests
from .validation import (
    validate_agent_runs,
    validate_agent_spec,
    validate_catalog,
    validate_manifest,
)


PILOT_EVIDENCE_SCHEMA_VERSION = "1.0"
FORMAL_RELEASE_EFFECT = "NONE"
KNOWN_CHANGE_STATUSES = {"ELIGIBLE", "EXCLUDED", "BLOCKED", "STOP_TRIGGERED"}
ADJUDICATION_CLASSES = {
    "TOOL_TRUE_POSITIVE",
    "TOOL_FALSE_POSITIVE",
    "TOOL_FALSE_NEGATIVE_HIGH",
    "TOOL_FALSE_NEGATIVE_OTHER",
    "HUMAN_BASELINE_ERROR",
    "CATALOG_OR_MAPPING_DEFECT",
    "POLICY_AMBIGUITY",
    "RUNNER_OR_ENVIRONMENT",
    "NO_DIFFERENCE",
}
PILOT_COMPATIBILITY_MATRIX = {
    "manifest": "1.0",
    "catalog": "1.0",
    "agent_spec": "1.0",
    "agent_run": "1.0",
    "pilot_evidence": "1.0",
    "difference_draft": "1.0",
    "adjudication": "1.0",
    "change_report": "1.0",
    "ledger": "1.0",
    "qualityctl": "0.1.x",
}


class EvidenceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class EvidenceValidationResult:
    """Stable result for a pilot contract validation attempt."""

    __slots__ = ("ok", "errors", "model", "code")

    def __init__(
        self,
        ok: bool,
        errors: list[str],
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
            "kind": "evidence_validation",
            "code": self.code,
            "message": self.errors[0] if self.errors else "validation passed",
            "paths": [],
            "errors": list(self.errors),
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
        }


class ReadinessResult:
    """Stable semantic result for catalog readiness."""

    __slots__ = ("ok", "errors", "details", "code")

    def __init__(
        self,
        ok: bool,
        errors: list[str],
        details: dict[str, Any],
        *,
        code: str = "OK",
    ) -> None:
        self.ok = ok
        self.errors = list(errors)
        self.details = details
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": "catalog_readiness",
            "status": "READY" if self.ok else "BLOCKED",
            "code": self.code,
            "message": self.errors[0] if self.errors else "catalog readiness passed",
            "paths": [],
            "errors": list(self.errors),
            **deepcopy(self.details),
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
        }


class ArtifactRefV1(EvidenceModel):
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size: int = Field(ge=0)
    digest: str = Field(min_length=1)


class EvidenceIdentityV1(EvidenceModel):
    pilot_id: str = Field(min_length=1)
    iteration_id: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    change_ref: str = Field(min_length=1)
    version_type: Literal["daily", "hotfix", "major"]


class EvidenceVersionsV1(EvidenceModel):
    core_version: str | None = Field(default=None, min_length=1)
    core_commit: str | None = Field(default=None, min_length=1)
    python_version: str = Field(min_length=1)
    input_schema_versions: dict[str, str] = Field(min_length=1)
    catalog_version: str = Field(min_length=1)
    mapping_version: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    agent_fingerprint_version: str | None = Field(default=None, min_length=1)
    agent_fingerprint: str | None = Field(default=None, min_length=1)
    agent_spec_digest: str | None = Field(default=None, min_length=1)
    frozen_agent_digest: str | None = Field(default=None, min_length=1)
    agent_fingerprint_digest: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _core_identity_required(self) -> "EvidenceVersionsV1":
        if not self.core_version and not self.core_commit:
            raise ValueError("versions requires core_version or core_commit")
        return self


class FreezeV1(EvidenceModel):
    scope_ref: str = Field(min_length=1)
    scope_digest: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    manual_frozen_at: str = Field(min_length=1)


class ToolRunV1(EvidenceModel):
    tool: str = Field(min_length=1)
    request_ref: str | None = Field(default=None, min_length=1)
    response_ref: str | None = Field(default=None, min_length=1)
    stdout_ref: str | None = Field(default=None, min_length=1)
    stderr_ref: str | None = Field(default=None, min_length=1)
    exit_code: int
    started_at: str = Field(min_length=1)
    ended_at: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class OrderingV1(EvidenceModel):
    tool_started_at: str = Field(min_length=1)
    tool_result_visible_at: str = Field(min_length=1)
    unblinded_at: str = Field(min_length=1)
    adjudicated_at: str | None = Field(default=None, min_length=1)


class AttemptV1(EvidenceModel):
    attempt_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    out_of_plan: bool = False
    digest: str = Field(min_length=1)
    started_at: str = Field(min_length=1)
    ended_at: str = Field(min_length=1)
    status: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    initial_attempt_ref: str | None = Field(default=None, min_length=1)


class AttestationV1(EvidenceModel):
    status: str = Field(min_length=1)
    version: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    approved_by: str | None = Field(default=None, min_length=1)
    expires_at: str | None = Field(default=None, min_length=1)
    release_effect: str | None = Field(default=None, min_length=1)
    sensitive_data: bool | None = None


class RawEvidenceV1(EvidenceModel):
    manifest: dict[str, Any]
    catalog: dict[str, Any]
    agent_spec: dict[str, Any] | None = None
    agent_runs: list[dict[str, Any]] | None = None
    tool_scope: dict[str, Any] | list[Any] | None = None
    formal_result: dict[str, Any] | None = None


class PilotEvidenceBundleV1(EvidenceModel):
    contract: str = Field(min_length=1)
    schema_version: str = PILOT_EVIDENCE_SCHEMA_VERSION
    # Fail closed: a bundle that does not explicitly identify itself as a
    # sanitized fixture is treated as a real shadow package.
    mode: str = "SHADOW"
    evidence_mode: str | None = None
    pilot_state: str | None = None
    g0_status: str = "BLOCKED_BY_R2_G0"
    g0_gate: str | None = None
    evidence_origin: str | None = None
    is_fixture: bool | None = None
    activation: dict[str, Any] | None = None
    evidence_overwritten: bool = False
    unauthorized_release: bool = False
    identity: EvidenceIdentityV1
    versions: EvidenceVersionsV1
    freeze: FreezeV1
    manual_scope: dict[str, Any] | list[Any] | None = None
    tool_runs: list[ToolRunV1] = Field(min_length=1)
    ordering: OrderingV1
    attempts: list[AttemptV1] = Field(min_length=1)
    attestations: dict[str, AttestationV1] = Field(min_length=1)
    catalog_readiness: dict[str, Any]
    artifacts: list[ArtifactRefV1] | None = None
    adjudication: dict[str, Any] | None = None
    adjudication_ref: str | None = Field(default=None, min_length=1)
    raw: RawEvidenceV1
    inputs: dict[str, Any] | None = None
    formal_release_effect: str = FORMAL_RELEASE_EFFECT


class DifferenceItemV1(EvidenceModel):
    difference_id: str = Field(min_length=1)
    test_id: str = Field(min_length=1)
    side: Literal["MANUAL_ONLY", "TOOL_ONLY"]
    manual_present: bool
    tool_present: bool
    risk: str | None = Field(default=None, min_length=1)
    high_risk: bool | None = None


class DifferenceDraftV1(EvidenceModel):
    contract: str = Field(min_length=1)
    status: Literal["DRAFT"] = "DRAFT"
    identity: dict[str, str] | None = None
    manual_scope: dict[str, Any] | list[Any]
    tool_scope: dict[str, Any] | list[Any]
    differences: list[DifferenceItemV1]
    counts: dict[str, int]
    generated_at: str = Field(min_length=1)
    formal_release_effect: str = FORMAL_RELEASE_EFFECT
    decision_digest: str = Field(min_length=1)


class AdjudicationItemV1(EvidenceModel):
    difference_id: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    high_risk: bool = False
    status: Literal["OPEN", "CLOSED"]
    adjudicator: str = Field(min_length=1)
    adjudicated_at: str = Field(min_length=1)


class AdjudicationV1(EvidenceModel):
    contract: str = Field(min_length=1)
    identity: dict[str, str]
    difference_draft_digest: str = Field(min_length=1)
    items: list[AdjudicationItemV1]
    reviewer_id: str = Field(min_length=1)
    reviewer_role: str = Field(min_length=1)
    adjudicated_at: str = Field(min_length=1)
    status: Literal["OPEN", "CLOSED"]
    formal_release_effect: str = FORMAL_RELEASE_EFFECT


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


def _validate_model(
    payload: Any,
    model_cls: type[BaseModel],
    *,
    kind: str,
) -> EvidenceValidationResult:
    if not isinstance(payload, Mapping):
        return EvidenceValidationResult(
            False,
            [f"{kind} payload must be a JSON object"],
            code="INVALID_PAYLOAD",
        )
    try:
        model = model_cls.model_validate(payload)
    except ValidationError as exc:
        return EvidenceValidationResult(
            False,
            _flatten_errors(exc),
            code="SCHEMA_VALIDATION_ERROR",
        )
    return EvidenceValidationResult(True, [], model)


def validate_pilot_evidence_bundle(payload: Any) -> EvidenceValidationResult:
    """Validate the structural Pilot Evidence v1 bundle contract."""

    return _validate_model(payload, PilotEvidenceBundleV1, kind="pilot_evidence_bundle")


def validate_difference_draft(payload: Any) -> EvidenceValidationResult:
    return _validate_model(payload, DifferenceDraftV1, kind="difference_draft")


def validate_adjudication(payload: Any) -> EvidenceValidationResult:
    return _validate_model(payload, AdjudicationV1, kind="adjudication")


def canonicalize(value: Any, *, purpose: Literal["artifact", "decision"] = "artifact") -> Any:
    """Return JSON-compatible canonical data without mutating the input.

    Decision digests intentionally omit display/runtime metadata that can
    change between equivalent runs.  Artifact digests retain every field.
    """

    volatile = {"generated_at", "local_root", "display_text"} if purpose == "decision" else set()
    if isinstance(value, Mapping):
        return {
            str(key): canonicalize(item, purpose=purpose)
            for key, item in value.items()
            if str(key) not in volatile
        }
    if isinstance(value, list):
        return [canonicalize(item, purpose=purpose) for item in value]
    if isinstance(value, tuple):
        return [canonicalize(item, purpose=purpose) for item in value]
    return value


def canonical_json(
    value: Any,
    *,
    purpose: Literal["artifact", "decision"] = "artifact",
) -> str:
    return json.dumps(
        canonicalize(value, purpose=purpose),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(
    value: Any,
    *,
    purpose: Literal["artifact", "decision"] = "artifact",
) -> bytes:
    return canonical_json(value, purpose=purpose).encode("utf-8")


def canonical_digest(
    value: Any,
    *,
    purpose: Literal["artifact", "decision"] = "artifact",
) -> str:
    encoded = canonical_bytes(value, purpose=purpose)
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def bytes_digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def artifact_digest(path: str | Path) -> str:
    return bytes_digest(Path(path).read_bytes())


def write_json_exclusive(data: Any, path: str | Path) -> str:
    """Create one JSON output and fail atomically if its path already exists."""

    rendered = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(rendered)
    return rendered


def _version(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _contract_version(contract: Any) -> tuple[str | None, str | None]:
    if not isinstance(contract, str) or "@" not in contract:
        return None, None
    name, version = contract.rsplit("@", 1)
    return name or None, version or None


def check_pilot_compatibility(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Check the pinned mixed-version matrix without changing old readers."""

    errors: list[str] = []
    if _version(bundle.get("schema_version")) != PILOT_EVIDENCE_SCHEMA_VERSION:
        errors.append(
            f"pilot evidence schema version {bundle.get('schema_version')!r} is not approved"
        )
    name, contract_version = _contract_version(bundle.get("contract"))
    if name != "pilot-evidence-bundle":
        errors.append("contract must be pilot-evidence-bundle@1.0")
    elif contract_version != PILOT_EVIDENCE_SCHEMA_VERSION:
        errors.append(
            f"pilot evidence contract version {contract_version!r} is not pinned to 1.0"
        )

    versions = bundle.get("versions")
    versions = versions if isinstance(versions, Mapping) else {}
    schema_versions = versions.get("input_schema_versions")
    schema_versions = schema_versions if isinstance(schema_versions, Mapping) else {}
    for kind in ("manifest", "catalog"):
        value = _version(schema_versions.get(kind))
        if value is None:
            errors.append(f"{kind} schema_version is missing")
        elif value != PILOT_COMPATIBILITY_MATRIX[kind]:
            errors.append(f"{kind} schema version {value!r} is not approved")

    raw = bundle.get("raw")
    raw = raw if isinstance(raw, Mapping) else {}
    manifest = raw.get("manifest") if isinstance(raw.get("manifest"), Mapping) else {}
    catalog = raw.get("catalog") if isinstance(raw.get("catalog"), Mapping) else {}
    for kind, payload in (("manifest", manifest), ("catalog", catalog)):
        actual = _version(payload.get("schema_version"))
        expected = _version(schema_versions.get(kind))
        if actual is None:
            errors.append(f"raw {kind}.schema_version is missing")
        elif expected is not None and actual != expected:
            errors.append(f"raw {kind}.schema_version disagrees with frozen version")

    agent_required = (
        isinstance(manifest.get("agent_evaluation"), Mapping)
        and manifest["agent_evaluation"].get("required") is True
    )
    if agent_required:
        agent_spec_version = _version(schema_versions.get("agent_spec"))
        if agent_spec_version != PILOT_COMPATIBILITY_MATRIX["agent_spec"]:
            errors.append(
                f"agent_spec schema version {agent_spec_version!r} is not approved"
            )
        agent_spec = raw.get("agent_spec")
        if not isinstance(agent_spec, Mapping):
            errors.append("raw agent_spec is required by the manifest policy")
        else:
            actual = _version(agent_spec.get("schema_version"))
            if actual != agent_spec_version:
                errors.append("raw agent_spec.schema_version disagrees with frozen version")
        if _version(schema_versions.get("agent_run")) != PILOT_COMPATIBILITY_MATRIX["agent_run"]:
            errors.append("agent_run schema version is not approved")
        if not isinstance(raw.get("agent_runs"), list):
            errors.append("raw agent_runs is required by the manifest policy")

    ok = not errors
    return {
        "ok": ok,
        "kind": "pilot_compatibility",
        "status": "COMPATIBLE" if ok else "BLOCKED",
        "code": "OK" if ok else "UNSUPPORTED_SCHEMA",
        "message": errors[0] if errors else "pinned compatibility matrix passed",
        "paths": [],
        "errors": errors,
        "matrix": deepcopy(PILOT_COMPATIBILITY_MATRIX),
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
    }


def _readiness_meta(
    catalog: Mapping[str, Any], readiness: Mapping[str, Any] | None
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    if "tests" not in catalog and isinstance(catalog.get("catalog"), Mapping):
        raw_catalog = catalog["catalog"]
        embedded = catalog.get("readiness")
        return (
            raw_catalog,
            readiness or (embedded if isinstance(embedded, Mapping) else {}),
        )
    return catalog, readiness or {}


def _as_nonempty_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray, str)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def validate_catalog_readiness(
    catalog: Mapping[str, Any],
    readiness: Mapping[str, Any] | None = None,
    *,
    min_tests: int = 30,
    max_tests: int = 50,
    required_dimensions: Sequence[str] = RISK_DIMENSIONS,
) -> ReadinessResult:
    """Fail closed on pilot catalog quality beyond the old v1 structure."""

    raw_catalog, meta = _readiness_meta(catalog, readiness)
    structural = validate_catalog(raw_catalog)
    errors: list[str] = []
    if not structural.ok:
        errors.extend(f"catalog schema: {error}" for error in structural.errors)
    tests = raw_catalog.get("tests") if isinstance(raw_catalog, Mapping) else None
    tests = tests if isinstance(tests, list) else []
    count = len(tests)
    if not min_tests <= count <= max_tests:
        errors.append(f"catalog must contain between {min_tests} and {max_tests} tests; got {count}")

    source_ref = meta.get("source_ref") or meta.get("catalog_source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        errors.append("catalog readiness source_ref is required")

    reviewers = _as_nonempty_strings(
        meta.get("reviewer_ids") or meta.get("reviewers") or meta.get("reviewer_id")
    )
    if len(set(reviewers)) < 2:
        errors.append("catalog readiness requires two independent reviewer_ids")

    ids = {
        str(test.get("id"))
        for test in tests
        if isinstance(test, Mapping) and isinstance(test.get("id"), str)
    }
    oracle_refs = meta.get("oracle_refs") or meta.get("oracle_coverage") or meta.get("oracles")
    if isinstance(oracle_refs, Mapping):
        oracle_ids = {
            str(key)
            for key, value in oracle_refs.items()
            if isinstance(value, str) and value.strip()
        }
    else:
        oracle_ids = set(_as_nonempty_strings(oracle_refs))
    if ids and oracle_ids != ids:
        missing = sorted(ids - oracle_ids)
        errors.append(
            "catalog readiness requires a non-empty oracle reference for every test"
            + (f"; missing {missing[:5]}" if missing else "")
        )

    dimensions = set(_as_nonempty_strings(meta.get("dimension_coverage")))
    required = set(required_dimensions)
    if dimensions != required:
        errors.append(
            "catalog readiness dimension_coverage must enumerate all approved dimensions"
        )

    history = _as_nonempty_strings(
        meta.get("historical_escape_refs")
        or meta.get("historical_escapes")
        or meta.get("history_refs")
    )
    if not history:
        errors.append("catalog readiness requires historical_escape_refs")

    details = {
        "catalog_count": count,
        "catalog_version": raw_catalog.get("catalog_version"),
        "source_ref": source_ref if isinstance(source_ref, str) else None,
        "reviewer_ids": sorted(set(reviewers)),
        "oracle_covered_count": len(ids & oracle_ids),
        "dimension_coverage": sorted(dimensions),
        "historical_escape_refs": sorted(history),
    }
    return ReadinessResult(
        not errors,
        errors,
        details,
        code="OK" if not errors else "CATALOG_NOT_READY",
    )


def _parse_time(value: Any, label: str, errors: list[str]) -> datetime | None:
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


def _scope_items(scope: Any) -> dict[str, Mapping[str, Any]]:
    if isinstance(scope, Mapping):
        for key in ("selected_test_ids", "selected", "selected_tests", "tests"):
            if key in scope:
                value = scope[key]
                break
        else:
            value = []
    else:
        value = scope
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray, str)):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for item in value:
        if isinstance(item, str) and item.strip():
            result[item.strip()] = {"test_id": item.strip()}
        elif isinstance(item, Mapping):
            identifier = item.get("test_id") or item.get("id")
            if isinstance(identifier, str) and identifier.strip():
                result[identifier.strip()] = item
    return result


def compare_scopes(
    manual_scope: Any,
    tool_scope: Any,
    *,
    identity: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Produce a deterministic scope difference draft without classifications."""

    manual = _scope_items(manual_scope)
    tool = _scope_items(tool_scope)
    differences: list[dict[str, Any]] = []
    for test_id in sorted(set(manual) - set(tool)):
        source = manual[test_id]
        item = {
            "difference_id": f"difference:manual-only:{test_id}",
            "test_id": test_id,
            "side": "MANUAL_ONLY",
            "manual_present": True,
            "tool_present": False,
        }
        if isinstance(source.get("risk"), str):
            item["risk"] = source["risk"]
        if isinstance(source.get("high_risk"), bool):
            item["high_risk"] = source["high_risk"]
        differences.append(item)
    for test_id in sorted(set(tool) - set(manual)):
        source = tool[test_id]
        item = {
            "difference_id": f"difference:tool-only:{test_id}",
            "test_id": test_id,
            "side": "TOOL_ONLY",
            "manual_present": False,
            "tool_present": True,
        }
        if isinstance(source.get("risk"), str):
            item["risk"] = source["risk"]
        if isinstance(source.get("high_risk"), bool):
            item["high_risk"] = source["high_risk"]
        differences.append(item)
    draft_without_digest = {
        "contract": "difference-draft@1.0",
        "status": "DRAFT",
        "identity": dict(identity) if identity is not None else None,
        "manual_scope": deepcopy(manual_scope),
        "tool_scope": deepcopy(tool_scope),
        "differences": differences,
        "counts": {
            "manual_only": sum(item["side"] == "MANUAL_ONLY" for item in differences),
            "tool_only": sum(item["side"] == "TOOL_ONLY" for item in differences),
            "total": len(differences),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
    }
    draft_without_digest["decision_digest"] = canonical_digest(
        draft_without_digest, purpose="decision"
    )
    return draft_without_digest


def _adjudication_status(
    payload: Mapping[str, Any],
    *,
    expected_difference_ids: set[str] | None = None,
) -> dict[str, Any]:
    validation = validate_adjudication(payload)
    if not validation.ok:
        return {
            "ok": False,
            "kind": "adjudication_validation",
            "status": "BLOCKED",
            "code": "ADJUDICATION_SCHEMA_INVALID",
            "message": validation.errors[0] if validation.errors else "invalid adjudication",
            "paths": [],
            "errors": validation.errors,
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
        }
    model = validation.model
    assert isinstance(model, AdjudicationV1)
    errors: list[str] = []
    identity = model.identity
    name, version = _contract_version(model.contract)
    if name != "adjudication" or version != "1.0":
        errors.append("adjudication contract must be adjudication@1.0")
    if model.formal_release_effect != FORMAL_RELEASE_EFFECT:
        return {
            "ok": False,
            "kind": "adjudication_validation",
            "status": "STOP_TRIGGERED",
            "code": "UNAUTHORIZED_RELEASE_EFFECT",
            "message": "formal_release_effect must remain NONE",
            "paths": [],
            "errors": ["formal_release_effect must remain NONE"],
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
        }
    item_ids = {item.difference_id for item in model.items}
    if expected_difference_ids is not None and item_ids != expected_difference_ids:
        missing = sorted(expected_difference_ids - item_ids)
        extra = sorted(item_ids - expected_difference_ids)
        if missing:
            errors.append(f"unadjudicated differences: {missing}")
        if extra:
            errors.append(f"adjudication references unknown differences: {extra}")
    stop_classes = {
        "TOOL_FALSE_NEGATIVE_HIGH",
        "ERROR_PASS",
        "SENSITIVE_DATA_EVENT",
        "UNAUTHORIZED_AUTOMATIC_RELEASE",
        "ORIGINAL_EVIDENCE_OVERWRITTEN",
    }
    for item in model.items:
        if item.classification not in ADJUDICATION_CLASSES and item.classification not in stop_classes:
            errors.append(
                f"{item.difference_id}: unsupported adjudication classification {item.classification!r}"
            )
        if item.status != "CLOSED":
            errors.append(f"{item.difference_id}: adjudication is not closed")
        if item.high_risk and item.status != "CLOSED":
            errors.append(f"{item.difference_id}: high-risk difference is not closed")

    if any(item.classification in stop_classes for item in model.items):
        return {
            "ok": False,
            "kind": "adjudication_validation",
            "status": "STOP_TRIGGERED",
            "code": "STOP_TRIGGERED",
            "message": (errors or ["adjudication contains a Round 2 stop classification"])[0],
            "paths": [],
            "errors": errors
            or ["adjudication contains a Round 2 stop classification"],
            "identity": deepcopy(identity),
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
            "decision_digest": canonical_digest(model.model_dump(), purpose="decision"),
        }
    if errors or model.status != "CLOSED":
        if model.status != "CLOSED":
            errors.append("adjudication status must be CLOSED")
        return {
            "ok": False,
            "kind": "adjudication_validation",
            "status": "BLOCKED",
            "code": "ADJUDICATION_NOT_CLOSED",
            "message": errors[0] if errors else "adjudication is not closed",
            "paths": [],
            "errors": errors,
            "identity": deepcopy(identity),
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
            "decision_digest": canonical_digest(model.model_dump(), purpose="decision"),
        }
    return {
        "ok": True,
        "kind": "adjudication_validation",
        "status": "VALID",
        "code": "OK",
        "message": "adjudication validated",
        "paths": [],
        "errors": [],
        "identity": deepcopy(identity),
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
        "decision_digest": canonical_digest(model.model_dump(), purpose="decision"),
    }


def validate_adjudication_record(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {
            "ok": False,
            "kind": "adjudication_validation",
            "status": "BLOCKED",
            "code": "INVALID_PAYLOAD",
            "message": "adjudication payload must be a JSON object",
            "paths": [],
            "errors": ["adjudication payload must be a JSON object"],
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
        }
    return _adjudication_status(payload)


def _load_raw_inputs(bundle: Mapping[str, Any], base_dir: Path | None) -> dict[str, Any]:
    raw = bundle.get("raw")
    raw = deepcopy(raw) if isinstance(raw, Mapping) else {}
    if isinstance(bundle.get("inputs"), Mapping):
        for key, value in bundle["inputs"].items():
            raw.setdefault(key, deepcopy(value))
    if base_dir is None:
        return raw
    for key in ("manifest", "catalog", "agent_spec"):
        value = raw.get(key)
        if isinstance(value, Mapping) and isinstance(value.get("path"), str):
            path = base_dir / value["path"]
            try:
                raw[key] = read_json(path)
                file_size = path.stat().st_size
            except (OSError, ValueError, TypeError) as exc:
                raw.setdefault("_load_errors", []).append(f"{key} read failed: {exc}")
                continue
            expected_size = value.get("size")
            if isinstance(expected_size, int) and file_size != expected_size:
                raw.setdefault("_load_errors", []).append(
                    f"{key} size mismatch: expected {expected_size}, got {path.stat().st_size}"
                )
            expected = value.get("digest")
            if isinstance(expected, str):
                actual = bytes_digest(path.read_bytes())
                if actual != expected:
                    raw.setdefault("_load_errors", []).append(
                        f"{key} digest mismatch: expected {expected}, got {actual}"
                    )
    value = raw.get("agent_runs")
    if isinstance(value, Mapping) and isinstance(value.get("path"), str):
        path = base_dir / value["path"]
        try:
            raw["agent_runs"] = read_jsonl(path)
            file_size = path.stat().st_size
        except (OSError, ValueError, TypeError) as exc:
            raw.setdefault("_load_errors", []).append(f"agent_runs read failed: {exc}")
            return raw
        expected_size = value.get("size")
        if isinstance(expected_size, int) and file_size != expected_size:
            raw.setdefault("_load_errors", []).append(
                f"agent_runs size mismatch: expected {expected_size}, got {path.stat().st_size}"
            )
        expected = value.get("digest")
        if isinstance(expected, str):
            actual = bytes_digest(path.read_bytes())
            if actual != expected:
                raw.setdefault("_load_errors", []).append(
                    f"agent_runs digest mismatch: expected {expected}, got {actual}"
                )
    return raw


def _is_real_bundle(bundle: Mapping[str, Any]) -> bool:
    if bundle.get("is_fixture") is True:
        return False
    mode = str(bundle.get("evidence_mode") or bundle.get("mode", "")).upper()
    state = str(bundle.get("pilot_state", "")).upper()
    if mode in {"SHADOW", "REAL", "BUSINESS", "PRODUCTION", "SHADOW_RUNNING"}:
        return True
    if state in {"SHADOW", "REAL", "BUSINESS", "PRODUCTION", "SHADOW_RUNNING"}:
        return True
    if bundle.get("is_fixture") is False:
        return True
    origin = str(bundle.get("evidence_origin", "")).upper()
    return origin in {"REAL", "BUSINESS", "PRODUCTION", "REAL_BUSINESS"}


def _g0_status(bundle: Mapping[str, Any]) -> str:
    activation = bundle.get("activation")
    activation_status = (
        activation.get("g0_status")
        if isinstance(activation, Mapping)
        else None
    )
    return str(
        bundle.get("g0_status")
        or bundle.get("g0_gate")
        or activation_status
        or "BLOCKED_BY_R2_G0"
    ).upper()


def _status_report(
    bundle: Mapping[str, Any],
    *,
    status: str,
    code: str,
    errors: Sequence[str] = (),
    **fields: Any,
) -> dict[str, Any]:
    identity = bundle.get("identity")
    identity = deepcopy(identity) if isinstance(identity, Mapping) else {}
    error_list = list(errors)
    report: dict[str, Any] = {
        "contract": "change-evidence-report@1.0",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": identity,
        "status": status,
        "code": code,
        "kind": "pilot_evidence_report",
        "message": error_list[0] if error_list else code,
        "paths": [],
        "errors": error_list,
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
        "formal_release_allowed": False,
        "retained_for_ledger": True,
        **fields,
    }
    stable = deepcopy(report)
    stable.pop("decision_digest", None)
    report["decision_digest"] = canonical_digest(stable, purpose="decision")
    return report


def _agent_failure_shape_errors(runs: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(runs, list):
        return ["agent_runs must be a list"]
    for index, run in enumerate(runs):
        if not isinstance(run, Mapping):
            errors.append(f"runs[{index}] must be an object")
            continue
        status = run.get("technical_status")
        if status != "ok" and "output" in run:
            errors.append(
                f"runs[{index}]: non-ok Agent failure must not carry output"
            )
    return errors


def validate_agent_failure_evidence(runs: Any) -> dict[str, Any]:
    """Validate the pilot-only failure shape without changing the v1 reader."""

    errors = _agent_failure_shape_errors(runs)
    return {
        "ok": not errors,
        "kind": "agent_failure_evidence",
        "status": "VALID" if not errors else "BLOCKED",
        "code": "OK" if not errors else "INVALID_AGENT_FAILURE_EVIDENCE",
        "message": errors[0] if errors else "Agent failure evidence passed",
        "paths": [],
        "errors": errors,
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
    }


def _agent_digest_check(bundle: Mapping[str, Any], raw: Mapping[str, Any]) -> tuple[list[str], dict[str, str]]:
    spec = raw.get("agent_spec")
    if not isinstance(spec, Mapping):
        return [], {}
    computed = {"agent_spec": canonical_digest(spec), "agent_runs": canonical_digest(raw.get("agent_runs", []))}
    versions = bundle.get("versions")
    versions = versions if isinstance(versions, Mapping) else {}
    declared = next(
        (
            versions.get(name)
            for name in (
                "agent_spec_digest",
                "frozen_agent_digest",
                "agent_fingerprint_digest",
            )
            if isinstance(versions.get(name), str) and versions.get(name).strip()
        ),
        None,
    )
    if declared is None and isinstance(bundle.get("agent_spec_digest"), str):
        declared = bundle["agent_spec_digest"]
    errors: list[str] = []
    if declared is not None and declared != computed["agent_spec"]:
        errors.append(
            f"frozen Agent content digest mismatch: expected {declared}, recomputed {computed['agent_spec']}"
        )
    fingerprint = spec.get("evaluation_fingerprint")
    if isinstance(versions.get("agent_fingerprint"), str) and isinstance(fingerprint, str):
        if versions["agent_fingerprint"] != fingerprint:
            errors.append("frozen Agent evaluation fingerprint disagrees with agent_spec")
    return errors, computed


def _attempt_errors(bundle: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    attempts = bundle.get("attempts")
    if not isinstance(attempts, list):
        return ["attempts must be a list"], []
    seen: set[str] = set()
    digests: set[str] = set()
    errors: list[str] = []
    stop_errors: list[str] = []
    initial_ids: list[str] = []
    for index, attempt in enumerate(attempts):
        if not isinstance(attempt, Mapping):
            errors.append(f"attempts[{index}] must be an object")
            continue
        attempt_id = str(attempt.get("attempt_id", "")).strip()
        digest = str(attempt.get("digest", "")).strip()
        if not attempt_id:
            errors.append(f"attempts[{index}].attempt_id is required")
        elif attempt_id in seen:
            stop_errors.append(f"duplicate attempt_id: {attempt_id}")
        seen.add(attempt_id)
        if digest in digests:
            stop_errors.append(f"duplicate attempt digest: {digest}")
        if digest:
            digests.add(digest)
        kind = str(attempt.get("kind", "")).lower()
        if kind in {"initial", "first"}:
            initial_ids.append(attempt_id)
        if kind in {"rerun", "retry"} and not attempt.get("initial_attempt_ref"):
            errors.append(f"{attempt_id or index}: rerun must reference the initial attempt")
    if len(initial_ids) != 1:
        stop_errors.append("attempt ledger must retain exactly one initial attempt")
    return errors, stop_errors


def verify_change_bundle(
    payload: Mapping[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Verify one bundle and return a non-authorizing change report."""

    if not isinstance(payload, Mapping):
        return _status_report(
            {},
            status="BLOCKED",
            code="INVALID_BUNDLE",
            errors=["pilot evidence bundle must be a JSON object"],
        )
    structural = validate_pilot_evidence_bundle(payload)
    if not structural.ok:
        return _status_report(
            payload,
            status="BLOCKED",
            code="INVALID_BUNDLE",
            errors=structural.errors,
        )
    bundle = structural.model.model_dump() if structural.model is not None else dict(payload)
    raw = _load_raw_inputs(bundle, Path(base_dir) if base_dir is not None else None)
    bundle["raw"] = raw

    stop_errors: list[str] = []
    formal_effects = [
        bundle.get("formal_release_effect"),
        *[
            item.get("release_effect")
            for item in bundle.get("attestations", {}).values()
            if isinstance(item, Mapping) and item.get("release_effect") is not None
        ],
        raw.get("formal_result", {}).get("release_effect")
        if isinstance(raw.get("formal_result"), Mapping)
        else None,
    ]
    if any(effect not in (None, FORMAL_RELEASE_EFFECT) for effect in formal_effects):
        stop_errors.append("incoming formal release effect is not NONE")
    secret_scan = bundle.get("attestations", {}).get("secret_scan")
    if isinstance(secret_scan, Mapping):
        scan_status = str(secret_scan.get("status", "")).upper()
        if scan_status in {"FAIL", "FAILED", "DETECTED", "UNSAFE", "SECRET_DETECTED"} or secret_scan.get("sensitive_data") is True:
            stop_errors.append("Secret or unsanitized data attestation failed")
    if bundle.get("evidence_overwritten") is True or bundle.get("unauthorized_release") is True:
        stop_errors.append("evidence overwrite or unauthorized release was attested")
    attempt_errors, attempt_stop_errors = _attempt_errors(bundle)
    stop_errors.extend(attempt_stop_errors)
    if stop_errors:
        return _status_report(
            bundle,
            status="STOP_TRIGGERED",
            code="STOP_TRIGGERED",
            errors=stop_errors,
            raw_gate=None,
        )

    compatibility = check_pilot_compatibility(bundle)
    if not compatibility["ok"]:
        return _status_report(
            bundle,
            status="BLOCKED",
            code=compatibility["code"],
            errors=compatibility["errors"],
            compatibility=compatibility,
            raw_gate=None,
        )

    if _is_real_bundle(bundle) and _g0_status(bundle) not in {
        "READY",
        "R2-G0_READY",
    }:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="BLOCKED_BY_R2_G0",
            errors=["R2-G0 is not READY; real evidence cannot start the shadow clock"],
            compatibility=compatibility,
            raw_gate=None,
        )

    required_attestations = {
        "secret_scan",
        "controlled_storage",
        "formal_result",
        "least_privilege",
    }
    attestations = bundle.get("attestations")
    attestations = attestations if isinstance(attestations, Mapping) else {}
    missing_attestations = sorted(required_attestations - set(attestations))
    if missing_attestations:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="MISSING_ATTESTATION",
            errors=[f"required attestations missing: {missing_attestations}"],
            compatibility=compatibility,
            raw_gate=None,
        )
    for name in ("controlled_storage", "formal_result", "least_privilege"):
        attestation = attestations.get(name)
        if not isinstance(attestation, Mapping) or str(attestation.get("status", "")).upper() in {
            "FAIL",
            "FAILED",
            "UNSAFE",
            "MISSING",
        }:
            return _status_report(
                bundle,
                status="BLOCKED",
                code="ATTESTATION_NOT_READY",
                errors=[f"attestation {name} is not ready"],
                compatibility=compatibility,
                raw_gate=None,
            )

    freeze = bundle.get("freeze")
    manual_scope = bundle.get("manual_scope")
    if manual_scope is None:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="MISSING_MANUAL_SCOPE",
            errors=["manual scope content is required for deterministic scope comparison"],
            compatibility=compatibility,
            raw_gate=None,
        )
    if isinstance(freeze, Mapping) and isinstance(manual_scope, (Mapping, list)):
        expected_freeze_digest = freeze.get("scope_digest")
        if isinstance(expected_freeze_digest, str) and expected_freeze_digest != canonical_digest(manual_scope):
            return _status_report(
                bundle,
                status="BLOCKED",
                code="FREEZE_DIGEST_MISMATCH",
                errors=["manual scope digest does not match the frozen content"],
                compatibility=compatibility,
                raw_gate=None,
            )

    readiness = validate_catalog_readiness(
        raw.get("catalog", {}), bundle.get("catalog_readiness")
    )
    if not readiness.ok:
        return _status_report(
            bundle,
            status="BLOCKED",
            code=readiness.code,
            errors=readiness.errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )

    ordering_errors: list[str] = []
    manual_frozen = _parse_time(
        bundle.get("freeze", {}).get("manual_frozen_at"),
        "freeze.manual_frozen_at",
        ordering_errors,
    )
    ordering = bundle.get("ordering", {})
    tool_started = _parse_time(ordering.get("tool_started_at"), "ordering.tool_started_at", ordering_errors)
    visible = _parse_time(ordering.get("tool_result_visible_at"), "ordering.tool_result_visible_at", ordering_errors)
    unblinded = _parse_time(ordering.get("unblinded_at"), "ordering.unblinded_at", ordering_errors)
    adjudicated = (
        _parse_time(ordering.get("adjudicated_at"), "ordering.adjudicated_at", ordering_errors)
        if ordering.get("adjudicated_at") is not None
        else None
    )
    if ordering_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="INVALID_ORDERING",
            errors=ordering_errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )
    if manual_frozen is not None and tool_started is not None and manual_frozen >= tool_started:
        return _status_report(
            bundle,
            status="EXCLUDED",
            code="EXCLUDED_PRE_FREEZE",
            errors=["manual_frozen_at must be earlier than first tool_started_at"],
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )
    if tool_started is not None and visible is not None and tool_started > visible:
        ordering_errors.append("tool_result_visible_at precedes tool_started_at")
    if visible is not None and unblinded is not None and visible > unblinded:
        ordering_errors.append("unblinded_at precedes tool_result_visible_at")
    if unblinded is not None and adjudicated is not None and unblinded > adjudicated:
        ordering_errors.append("adjudicated_at precedes unblinded_at")
    if ordering_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="INVALID_ORDERING",
            errors=ordering_errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )

    if attempt_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="ATTEMPT_LEDGER_INVALID",
            errors=attempt_errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )
    load_errors = raw.get("_load_errors")
    if isinstance(load_errors, list) and load_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="RAW_DIGEST_MISMATCH",
            errors=[str(error) for error in load_errors],
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )

    manifest = raw.get("manifest")
    catalog = raw.get("catalog")
    manifest_check = validate_manifest(manifest)
    catalog_check = validate_catalog(catalog)
    raw_errors: list[str] = []
    if not manifest_check.ok:
        raw_errors.extend(f"manifest: {error}" for error in manifest_check.errors)
    if not catalog_check.ok:
        raw_errors.extend(f"catalog: {error}" for error in catalog_check.errors)
    agent_errors = (
        []
        if raw.get("agent_runs") is None
        else validate_agent_failure_evidence(raw.get("agent_runs"))["errors"]
    )
    if agent_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="INVALID_AGENT_FAILURE_EVIDENCE",
            errors=agent_errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )
    digest_errors, recomputed_agent_digests = _agent_digest_check(bundle, raw)
    if digest_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="AGENT_DIGEST_MISMATCH",
            errors=digest_errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            recomputed_digests=recomputed_agent_digests,
            raw_gate=None,
        )
    if raw_errors:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="RAW_INPUT_INVALID",
            errors=raw_errors,
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )

    agent_spec = raw.get("agent_spec")
    agent_runs = raw.get("agent_runs")
    agent_policy = manifest.get("agent_evaluation") if isinstance(manifest, Mapping) else None
    if isinstance(agent_policy, Mapping) and agent_policy.get("required") is True:
        if not isinstance(agent_spec, Mapping) or not isinstance(agent_runs, list):
            return _status_report(
                bundle,
                status="BLOCKED",
                code="MISSING_AGENT_EVIDENCE",
                errors=["required Agent evidence is missing"],
                compatibility=compatibility,
                catalog_readiness=readiness.to_dict(),
                raw_gate=None,
            )
        spec_check = validate_agent_spec(agent_spec)
        runs_check = validate_agent_runs(agent_runs)
        if not spec_check.ok or runs_check is not None:
            errors = [f"agent_spec: {error}" for error in spec_check.errors]
            if runs_check is not None:
                errors.extend(runs_check.errors)
            return _status_report(
                bundle,
                status="BLOCKED",
                code="AGENT_EVIDENCE_INVALID",
                errors=errors,
                compatibility=compatibility,
                catalog_readiness=readiness.to_dict(),
                raw_gate=None,
            )

    try:
        gate = decide_quality_gate(
            manifest,
            catalog,
            agent_spec=agent_spec,
            agent_runs=agent_runs,
        )
    except (TypeError, ValueError, KeyError) as exc:
        return _status_report(
            bundle,
            status="BLOCKED",
            code="RAW_GATE_RECOMPUTE_FAILED",
            errors=[str(exc)],
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=None,
        )

    tool_scope = raw.get("tool_scope")
    if tool_scope is None and isinstance(raw.get("manifest"), Mapping) and isinstance(raw.get("catalog"), Mapping):
        selection = select_regression_tests(raw["catalog"], raw["manifest"])
        tool_scope = {"selected_test_ids": [item["test_id"] for item in selection.get("selected", [])]}
    draft = compare_scopes(
        bundle.get("manual_scope", {}),
        tool_scope or {},
        identity=bundle.get("identity") if isinstance(bundle.get("identity"), Mapping) else None,
    )
    adjudication = bundle.get("adjudication")
    if not isinstance(adjudication, Mapping):
        return _status_report(
            bundle,
            status="BLOCKED",
            code="MISSING_ADJUDICATION",
            errors=["adjudication is required before a change can enter the denominator"],
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=gate.get("gate"),
            raw_release_allowed=gate.get("release_allowed"),
            draft_digest=draft["decision_digest"],
        )
    adjudication_result = _adjudication_status(
        adjudication,
        expected_difference_ids={item["difference_id"] for item in draft["differences"]},
    )
    if adjudication_result["status"] == "STOP_TRIGGERED":
        return _status_report(
            bundle,
            status="STOP_TRIGGERED",
            code=adjudication_result["code"],
            errors=adjudication_result.get("errors", []),
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=gate.get("gate"),
            raw_release_allowed=gate.get("release_allowed"),
            draft_digest=draft["decision_digest"],
        )
    if not adjudication_result["ok"]:
        return _status_report(
            bundle,
            status="BLOCKED",
            code=adjudication_result["code"],
            errors=adjudication_result.get("errors", []),
            compatibility=compatibility,
            catalog_readiness=readiness.to_dict(),
            raw_gate=gate.get("gate"),
            raw_release_allowed=gate.get("release_allowed"),
            draft_digest=draft["decision_digest"],
        )

    input_digests = {
        "manifest": canonical_digest(manifest),
        "catalog": canonical_digest(catalog),
        "agent_spec": canonical_digest(agent_spec) if isinstance(agent_spec, Mapping) else None,
        "agent_runs": canonical_digest(agent_runs) if isinstance(agent_runs, list) else None,
    }
    return _status_report(
        bundle,
        status="ELIGIBLE",
        code="OK",
        errors=[],
        compatibility=compatibility,
        catalog_readiness=readiness.to_dict(),
        raw_gate=gate.get("gate"),
        raw_release_allowed=gate.get("release_allowed"),
        blocking_checks=gate.get("blocking_checks", []),
        draft_digest=draft["decision_digest"],
        adjudication_digest=adjudication_result.get("decision_digest"),
        input_digests=input_digests,
        recomputed_digests=recomputed_agent_digests,
        attempt_ids=[str(item.get("attempt_id")) for item in bundle.get("attempts", [])],
    )


def draft_difference(
    bundle: Mapping[str, Any],
    *,
    base_dir: str | Path | None = None,
) -> dict[str, Any]:
    structural = validate_pilot_evidence_bundle(bundle)
    if not structural.ok:
        return {
            "contract": "difference-draft@1.0",
            "status": "BLOCKED",
            "code": "INVALID_BUNDLE",
            "kind": "difference_draft",
            "message": structural.errors[0] if structural.errors else "invalid bundle",
            "paths": [],
            "errors": structural.errors,
            "differences": [],
            "formal_release_effect": FORMAL_RELEASE_EFFECT,
            "decision_digest": canonical_digest(
                {"status": "BLOCKED", "errors": structural.errors}, purpose="decision"
            ),
        }
    parsed = structural.model.model_dump() if structural.model is not None else dict(bundle)
    raw = _load_raw_inputs(parsed, Path(base_dir) if base_dir is not None else None)
    tool_scope = raw.get("tool_scope")
    if tool_scope is None and isinstance(raw.get("manifest"), Mapping) and isinstance(raw.get("catalog"), Mapping):
        selection = select_regression_tests(raw["catalog"], raw["manifest"])
        tool_scope = {"selected_test_ids": [item["test_id"] for item in selection.get("selected", [])]}
    draft = compare_scopes(
        parsed.get("manual_scope", {}),
        tool_scope or {},
        identity=parsed.get("identity") if isinstance(parsed.get("identity"), Mapping) else None,
    )
    return draft


def freeze_ledger(index: Mapping[str, Any] | Sequence[Any]) -> dict[str, Any]:
    """Freeze all candidate/excluded/attempt records without duplicate counts."""

    if isinstance(index, Mapping):
        raw_entries = index.get("entries") or index.get("changes") or index.get("candidates") or []
        raw_attempts = index.get("attempts") or []
    else:
        raw_entries = index
        raw_attempts = []
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes, bytearray)):
        raw_entries = []
        initial_entry_error = "ledger entries must be a list"
    else:
        initial_entry_error = None
    if not isinstance(raw_attempts, Sequence) or isinstance(raw_attempts, (str, bytes, bytearray)):
        raw_attempts = []
        initial_attempt_error = "ledger attempts must be a list"
    else:
        initial_attempt_error = None
    entries = [item for item in raw_entries if isinstance(item, Mapping)] if isinstance(raw_entries, Sequence) and not isinstance(raw_entries, (str, bytes, bytearray)) else []
    attempts = [item for item in raw_attempts if isinstance(item, Mapping)] if isinstance(raw_attempts, Sequence) and not isinstance(raw_attempts, (str, bytes, bytearray)) else []
    if not attempts:
        for entry in entries:
            embedded_attempts = entry.get("attempts") if isinstance(entry, Mapping) else None
            if isinstance(embedded_attempts, Sequence) and not isinstance(embedded_attempts, (str, bytes, bytearray)):
                for attempt in embedded_attempts:
                    if isinstance(attempt, Mapping):
                        enriched = deepcopy(dict(attempt))
                        for key in ("pilot_id", "change_id", "run_id"):
                            enriched.setdefault(key, entry.get(key))
                        attempts.append(enriched)
    conflicts: list[str] = []
    if initial_entry_error:
        conflicts.append(initial_entry_error)
    if initial_attempt_error:
        conflicts.append(initial_attempt_error)
    if isinstance(raw_entries, Sequence) and not isinstance(raw_entries, (str, bytes, bytearray)):
        conflicts.extend(
            f"entries[{position}] must be an object"
            for position, item in enumerate(raw_entries)
            if not isinstance(item, Mapping)
        )
    if isinstance(raw_attempts, Sequence) and not isinstance(raw_attempts, (str, bytes, bytearray)):
        conflicts.extend(
            f"attempts[{position}] must be an object"
            for position, item in enumerate(raw_attempts)
            if not isinstance(item, Mapping)
        )
    seen_keys: set[tuple[str, str, str]] = set()
    seen_digests: set[str] = set()
    duplicate_keys: set[tuple[str, str, str]] = set()
    duplicate_digests: set[str] = set()
    normalized_entries: list[dict[str, Any]] = []
    for position, entry in enumerate(entries):
        pilot_id = str(entry.get("pilot_id", "")).strip()
        change_id = str(entry.get("change_id", "")).strip()
        run_id = str(entry.get("run_id", "")).strip()
        status = str(entry.get("status", "")).strip()
        key = (pilot_id, change_id, run_id)
        digest = str(entry.get("evidence_digest", "")).strip()
        if not all(key):
            conflicts.append(f"entries[{position}] is missing pilot_id/change_id/run_id")
        if status not in KNOWN_CHANGE_STATUSES:
            conflicts.append(f"entries[{position}] has unsupported status {status!r}")
        if key in seen_keys:
            conflicts.append(f"duplicate change/run identity: {key}")
            duplicate_keys.add(key)
        seen_keys.add(key)
        if digest and digest in seen_digests:
            conflicts.append(f"duplicate evidence digest: {digest}")
            duplicate_digests.add(digest)
        if digest:
            seen_digests.add(digest)
        normalized = deepcopy(dict(entry))
        normalized.setdefault("out_of_plan", False)
        normalized_entries.append(normalized)

    seen_attempts: set[tuple[tuple[str, str, str], str]] = set()
    normalized_attempts: list[dict[str, Any]] = []
    for position, attempt in enumerate(attempts):
        key = (
            str(attempt.get("pilot_id", "")),
            str(attempt.get("change_id", "")),
            str(attempt.get("run_id", "")),
        )
        attempt_id = str(attempt.get("attempt_id", ""))
        if not all(key) or not attempt_id:
            conflicts.append(f"attempts[{position}] is missing identity or attempt_id")
        identity = (key, attempt_id)
        if identity in seen_attempts:
            conflicts.append(f"duplicate attempt identity: {identity}")
        seen_attempts.add(identity)
        normalized_attempts.append(deepcopy(dict(attempt)))

    eligible = [
        item
        for item in normalized_entries
        if item.get("status") == "ELIGIBLE"
        and item.get("out_of_plan") is not True
        and (
            str(item.get("pilot_id", "")),
            str(item.get("change_id", "")),
            str(item.get("run_id", "")),
        ) not in duplicate_keys
        and str(item.get("evidence_digest", "")) not in duplicate_digests
    ]
    excluded = [item for item in normalized_entries if item.get("status") == "EXCLUDED"]
    stable = {
        "contract": "evidence-ledger@1.0",
        "schema_version": "1.0",
        "entries": normalized_entries,
        "attempts": normalized_attempts,
        "eligible_count": len(eligible),
        "excluded_count": len(excluded),
        "conflicts": sorted(set(conflicts)),
        "formal_release_effect": FORMAL_RELEASE_EFFECT,
    }
    output = {
        **stable,
        "status": "BLOCKED" if conflicts else "FROZEN",
        "kind": "evidence_ledger",
        "message": conflicts[0] if conflicts else "ledger frozen",
        "paths": [],
        "eligible_change_ids": sorted({str(item.get("change_id")) for item in eligible}),
        "excluded_change_ids": sorted({str(item.get("change_id")) for item in excluded}),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    output["decision_digest"] = canonical_digest(output, purpose="decision")
    return output


__all__ = [
    "ADJUDICATION_CLASSES",
    "ArtifactRefV1",
    "Adjudication",
    "AttestationV1",
    "AttemptV1",
    "DifferenceDraftV1",
    "DifferenceDraft",
    "EvidenceIdentityV1",
    "EvidenceVersionsV1",
    "FORMAL_RELEASE_EFFECT",
    "PILOT_COMPATIBILITY_MATRIX",
    "PILOT_EVIDENCE_SCHEMA_VERSION",
    "PilotEvidenceBundleV1",
    "PilotEvidenceBundle",
    "ReadinessResult",
    "RISK_DIMENSIONS",
    "canonical_digest",
    "canonical_bytes",
    "canonical_json",
    "canonicalize",
    "bytes_digest",
    "artifact_digest",
    "compute_digest",
    "check_pilot_compatibility",
    "compare_scopes",
    "draft_difference",
    "draft_diff",
    "freeze_ledger",
    "build_frozen_ledger",
    "validate_adjudication",
    "validate_adjudication_record",
    "validate_agent_failure_evidence",
    "validate_catalog_readiness",
    "validate_difference_draft",
    "validate_pilot_evidence_bundle",
    "exclusive_create_json",
    "verify_change",
    "verify_change_bundle",
    "write_json_exclusive",
]


# Short aliases keep the public seam easy to discover while the versioned
# names remain available for schema-oriented callers.
PilotEvidenceBundle = PilotEvidenceBundleV1
DifferenceDraft = DifferenceDraftV1
Adjudication = AdjudicationV1
verify_change = verify_change_bundle
draft_diff = draft_difference
build_frozen_ledger = freeze_ledger
exclusive_create_json = write_json_exclusive
compute_digest = canonical_digest
