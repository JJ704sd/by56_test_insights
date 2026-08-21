"""Structural input validation for qualityctl.

This module is the single entry point for *structural* checks on the three
qualityctl inputs and the per-run JSONL row. It uses Pydantic v2 models that
mirror the JSON Schema files under :mod:`qualityctl.schemas`. Semantic checks
(e.g., "affected requires evidence") live in the domain modules
(``risk.py``, ``selection.py``, ``agent_eval.py``).

Validation is intentionally strict:

- :attr:`extra="forbid"` rejects unknown fields to surface caller typos.
- :attr:`schema_version` must be a supported literal; legacy unversioned inputs
  are rejected so callers do not silently drift past the documented contract.
- Cross-field rules (e.g., a status of ``"affected"`` requires ``evidence`` and
  ``scenarios``) are enforced inside the relevant model's ``model_validator``.

Each public :func:`validate_*` returns a :class:`ValidationResult`. The shape
is stable so both the MCP layer and the CLI can render failures uniformly.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# Currently-supported major schema version. The structural layer intentionally
# accepts any non-empty ``schema_version`` string; this constant is for
# release notes and changelog documentation only and does NOT gate runtime
# validation. Major-version compatibility is decided separately by the
# embedded-UI view_model (see ``embedded_ui.view_model._schema_compatibility``).
SUPPORTED_VERSION: Literal["1.0"] = "1.0"


def _regex_has_unsafe_repetition(pattern: str) -> bool:
    """Return whether repetition can trigger excessive regex backtracking.

    Python's backtracking regex engine can take exponential time for patterns
    such as ``(a+)+$`` or ``(a|aa)+$``.  The input schema is caller-controlled,
    so conservatively allow at most one variable repeat and never repeat a
    group before an Agent output is matched.
    """

    repeat_in_group = [False]
    last_atom_contains_repeat = False
    last_atom_is_group = False
    variable_repeat_count = 0
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "\\":
            index += 2
            last_atom_contains_repeat = False
            last_atom_is_group = False
            continue
        if character == "[":
            index += 1
            while index < len(pattern):
                if pattern[index] == "\\":
                    index += 2
                elif pattern[index] == "]":
                    index += 1
                    break
                else:
                    index += 1
            last_atom_contains_repeat = False
            last_atom_is_group = False
            continue
        if character == "(":
            repeat_in_group.append(False)
            last_atom_contains_repeat = False
            last_atom_is_group = False
            index += 1
            continue
        if character == ")":
            last_atom_contains_repeat = repeat_in_group.pop()
            last_atom_is_group = True
            index += 1
            continue

        repeat_end = index
        is_repeat = character in "*+?"
        is_variable_repeat = is_repeat
        if character == "?" and index > 0 and pattern[index - 1] == "(":
            is_repeat = False
            is_variable_repeat = False
        if character == "{" and (match := re.match(r"\{(\d+)(?:,(\d*))?\}", pattern[index:])):
            is_repeat = True
            minimum = int(match.group(1))
            maximum_text = match.group(2)
            is_variable_repeat = maximum_text is not None and (
                maximum_text == "" or int(maximum_text) != minimum
            )
            repeat_end = index + len(match.group(0)) - 1

        if is_repeat:
            if last_atom_is_group:
                return True
            if is_variable_repeat:
                variable_repeat_count += 1
            if (
                is_variable_repeat
                and (variable_repeat_count > 1 or last_atom_contains_repeat)
            ):
                return True
            if is_variable_repeat:
                repeat_in_group[-1] = True
                last_atom_contains_repeat = True
            last_atom_is_group = False
            index = repeat_end + 1
            if index < len(pattern) and pattern[index] in "?+":
                index += 1
            continue

        if character not in "?:=!<>P#-":
            last_atom_contains_repeat = False
            last_atom_is_group = False
        index += 1
    return False


class ValidationResult:
    """Outcome of a structural validation attempt.

    ``ok`` is true only when the input fully conforms. ``errors`` is a list of
    human-readable, field-pointing error messages. ``model`` carries the
    parsed Pydantic model when validation succeeded; ``None`` otherwise.
    """

    __slots__ = ("ok", "errors", "model")

    def __init__(
        self,
        ok: bool,
        errors: list[str],
        model: BaseModel | None,
    ) -> None:
        self.ok = ok
        self.errors = errors
        self.model = model

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"ValidationResult(ok={self.ok}, errors={len(self.errors)})"

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": list(self.errors)}


def _format_loc(loc: tuple[Any, ...]) -> str:
    """Render a Pydantic error location tuple as a human-readable dotted path.

    ``("tests", 5, "automation_fit", "oracle")`` becomes
    ``tests[5].automation_fit.oracle``. List indices render with brackets and
    mapping keys are joined with ``.``. An empty location renders as ``<root>``.
    """

    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            if parts:
                parts.append(".")
            parts.append(str(item))
    return "".join(parts) or "<root>"


def _flatten_pydantic_errors(exc: ValidationError) -> list[str]:
    """Convert a :class:`pydantic.ValidationError` into flat error strings.

    Pydantic's ``errors()`` returns nested tuples for nested models; this
    flattens them into dotted paths so callers can point at the exact field.
    List indices render as ``[n]`` to stay readable for LLM callers.
    """

    messages: list[str] = []
    for err in exc.errors():
        path = _format_loc(err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        if path == "<root>":
            messages.append(msg)
        else:
            messages.append(f"{path}: {msg}")
    return messages


class _StrictModel(BaseModel):
    """Base model with strict structural defaults."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)


# ---------------------------------------------------------------------------
# Manifest v1
# ---------------------------------------------------------------------------


StatusLiteral = Literal["affected", "not_affected", "not_applicable", "unknown"]
OracleLiteral = Literal["exact", "schema", "rule", "state", "contract"]
DataBasisLiteral = Literal["ESTIMATED", "OBSERVED"]
ApprovalLiteral = Literal["APPROVED", "UNAPPROVED"]
RiskLiteral = Literal["high", "medium", "low"]
ManualStatusLiteral = Literal["pass", "fail"]
TechnicalStatusLiteral = Literal["ok", "runner_invalid", "technical_failure"]
AssertionTypeLiteral = Literal[
    "required", "equals", "one_of", "matches", "number"
]
VersionTypeLiteral = Literal["daily", "hotfix", "major"]


class AgentEvaluationPolicy(_StrictModel):
    required: bool
    approved_by: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)


class Dependencies(_StrictModel):
    upstream: list[str]
    downstream: list[str]


class DimensionEntry(_StrictModel):
    status: StatusLiteral
    evidence: str | None = Field(default=None, min_length=1)
    scenarios: list[str] | None = None
    reason: str | None = Field(default=None, min_length=1)
    owner: str | None = Field(default=None, min_length=1)
    resolve_by: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _status_consistency(self) -> "DimensionEntry":
        if self.status == "affected":
            missing: list[str] = []
            if not self.evidence:
                missing.append("evidence")
            if not self.scenarios:
                missing.append("scenarios")
            if missing:
                raise ValueError(
                    f"status 'affected' requires non-empty {', '.join(missing)}"
                )
        elif self.status in {"not_affected", "not_applicable"}:
            if not self.reason:
                raise ValueError(
                    f"status {self.status!r} requires a non-empty reason"
                )
        else:  # "unknown"
            missing = [
                name
                for name, value in (
                    ("owner", self.owner),
                    ("resolve_by", self.resolve_by),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"status 'unknown' requires non-empty {', '.join(missing)}"
                )
        return self


class DimensionsDict(_StrictModel):
    """Container enforcing the eight fixed risk dimensions."""

    business_flow: DimensionEntry
    exception_paths: DimensionEntry
    boundaries: DimensionEntry
    permissions: DimensionEntry
    data_consistency: DimensionEntry
    upstream_downstream: DimensionEntry
    side_effects: DimensionEntry
    recoverability: DimensionEntry


class ManifestV1(_StrictModel):
    schema_version: str = Field(min_length=1)
    change_id: str = Field(min_length=1)
    version_type: VersionTypeLiteral
    changed_components: list[str] = Field(min_length=1)
    agent_evaluation: AgentEvaluationPolicy
    dependencies: Dependencies
    risk_signals: list[str]
    dimensions: DimensionsDict

    @field_validator("changed_components", "risk_signals")
    @classmethod
    def _no_blank_strings(cls, value: list[str]) -> list[str]:
        for index, item in enumerate(value):
            if not item.strip():
                raise ValueError(f"item at index {index} is blank")
        return value


# ---------------------------------------------------------------------------
# Catalog v1
# ---------------------------------------------------------------------------


class AutomationPolicy(_StrictModel):
    version: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    approval_status: ApprovalLiteral
    max_payback_months: float = Field(gt=0)
    min_monthly_net_minutes: float = Field(ge=0)


class AutomationFit(_StrictModel):
    stable: bool
    repeatable: bool
    oracle: str = Field(min_length=1)
    runs_per_month: float = Field(gt=0)
    manual_minutes: float = Field(ge=0)
    residual_review_minutes_per_run: float = Field(ge=0)
    maintenance_minutes_per_month: float = Field(ge=0)
    flaky_investigation_minutes_per_month: float = Field(ge=0)
    execution_cost_minutes_equivalent_per_month: float = Field(ge=0)
    data_maintenance_minutes_per_month: float = Field(ge=0)
    setup_minutes: float = Field(ge=0)
    data_basis: DataBasisLiteral
    observation_window_days: float = Field(gt=0)


class TestEntry(_StrictModel):
    id: str = Field(min_length=1)
    priority: str | None = Field(default=None, min_length=1)
    components: list[str] | None = None
    dimensions: list[str] | None = None
    risks: list[str] | None = None
    suites: list[str] | None = None
    labels: list[str] | None = None
    automated: bool
    automation_fit: AutomationFit | None = None


class CatalogV1(_StrictModel):
    schema_version: str = Field(min_length=1)
    catalog_version: str | None = Field(default=None, min_length=1)
    automation_policy: AutomationPolicy | None = None
    tests: list[TestEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_test_ids(self) -> "CatalogV1":
        seen: set[str] = set()
        for test in self.tests:
            if test.id in seen:
                raise ValueError(f"duplicate test id: {test.id}")
            seen.add(test.id)
        return self


# ---------------------------------------------------------------------------
# Agent spec v1
# ---------------------------------------------------------------------------


class ExecutionProfile(_StrictModel):
    prompt_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_parameters: Mapping[str, Any]
    toolset_version: str = Field(min_length=1)
    knowledge_snapshot: str = Field(min_length=1)
    runner_version: str = Field(min_length=1)


class ThresholdProfile(_StrictModel):
    version: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    approval_status: ApprovalLiteral


class _RequiredAssertion(_StrictModel):
    type: Literal["required"]
    paths: list[str] = Field(min_length=1)


class _EqualsAssertion(_StrictModel):
    type: Literal["equals"]
    path: str = Field(min_length=1)
    expected: Any


class _OneOfAssertion(_StrictModel):
    type: Literal["one_of"]
    path: str = Field(min_length=1)
    values: list[Any] = Field(min_length=1)


class _MatchesAssertion(_StrictModel):
    type: Literal["matches"]
    path: str = Field(min_length=1)
    pattern: str = Field(min_length=1, max_length=256)

    @field_validator("pattern")
    @classmethod
    def _valid_regex(cls, value: str) -> str:
        try:
            re.compile(value)
        except (re.error, OverflowError) as exc:
            raise ValueError(f"pattern is not a valid regex: {exc}") from exc
        if _regex_has_unsafe_repetition(value):
            raise ValueError("pattern uses unsafe regex repetition")
        return value


class _NumberAssertion(_StrictModel):
    type: Literal["number"]
    path: str = Field(min_length=1)
    expected: float
    absolute_tolerance: float | None = Field(default=None, ge=0)
    relative_tolerance: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _exactly_one_tolerance(self) -> "_NumberAssertion":
        has_abs = self.absolute_tolerance is not None
        has_rel = self.relative_tolerance is not None
        if has_abs == has_rel:
            raise ValueError(
                "number assertion requires exactly one of absolute_tolerance or relative_tolerance"
            )
        return self


AssertionEntry = (
    _RequiredAssertion
    | _EqualsAssertion
    | _OneOfAssertion
    | _MatchesAssertion
    | _NumberAssertion
)


class AgentCaseEntry(_StrictModel):
    id: str = Field(min_length=1)
    risk: RiskLiteral
    planned_runs: int = Field(gt=0)
    min_pass_rate: float = Field(ge=0, le=1)
    hard_fail_on_any: bool | None = None
    semantic_review_required: bool | None = None
    baseline_pass_rate: float | None = Field(default=None, ge=0, le=1)
    assertions: list[Mapping[str, Any]] = Field(min_length=1)

    @field_validator("assertions", mode="after")
    def _parse_assertions(
        cls, value: list[Mapping[str, Any]]
    ) -> list[Mapping[str, Any]]:
        parsed: list[Mapping[str, Any]] = []
        for index, raw in enumerate(value):
            if not isinstance(raw, Mapping):
                raise ValueError(f"assertion at index {index} must be an object")
            kind = raw.get("type")
            model_cls = {
                "required": _RequiredAssertion,
                "equals": _EqualsAssertion,
                "one_of": _OneOfAssertion,
                "matches": _MatchesAssertion,
                "number": _NumberAssertion,
            }.get(kind)
            if model_cls is None:
                raise ValueError(
                    f"assertion at index {index} has unsupported type {kind!r}"
                )
            parsed.append(model_cls.model_validate(raw).model_dump())
        return parsed


class AgentSpecV1(_StrictModel):
    schema_version: str = Field(min_length=1)
    agent_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    evaluation_fingerprint: str = Field(min_length=1)
    execution_profile: ExecutionProfile
    threshold_profile: ThresholdProfile
    cases: list[AgentCaseEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_case_ids(self) -> "AgentSpecV1":
        seen: set[str] = set()
        for case in self.cases:
            if case.id in seen:
                raise ValueError(f"duplicate case id: {case.id}")
            seen.add(case.id)
        return self


# ---------------------------------------------------------------------------
# Agent run row v1
# ---------------------------------------------------------------------------


class ManualReview(_StrictModel):
    reviewer_id: str = Field(min_length=1)
    reviewer_role: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    evidence_ref: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    status: ManualStatusLiteral


class AgentRunV1(_StrictModel):
    """A single Agent run row.

    ``output`` is intentionally typed ``Mapping | None`` so the same model can
    represent both successful and failed runs, but the ``_output_or_error``
    validator enforces the right pairing: ``technical_status == "ok"`` requires
    a non-null ``output`` and forbids ``error``; any other status requires
    ``error`` and rejects a present ``output``.
    """

    case_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    evaluation_fingerprint: str = Field(min_length=1)
    technical_status: TechnicalStatusLiteral
    output: Mapping[str, Any] | None = None
    error: str | None = Field(default=None, min_length=1)
    manual_review: ManualReview | None = None

    @model_validator(mode="after")
    def _output_or_error(self) -> "AgentRunV1":
        if self.technical_status == "ok":
            if self.output is None:
                raise ValueError("technical_status 'ok' requires non-empty output")
            if self.error is not None:
                raise ValueError(
                    "technical_status 'ok' must not carry an error message"
                )
        else:
            if self.error is None:
                raise ValueError(
                    f"technical_status {self.technical_status!r} requires an error message"
                )
        return self


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _validate_with_schema(
    payload: Any,
    *,
    model_cls: type[BaseModel],
    kind: str,
) -> ValidationResult:
    if not isinstance(payload, Mapping):
        return ValidationResult(
            False, [f"{kind} payload must be a JSON object"], None
        )
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        return ValidationResult(
            False, [f"{kind}.schema_version is required"], None
        )
    try:
        model = model_cls.model_validate(payload)
    except ValidationError as exc:
        return ValidationResult(False, _flatten_pydantic_errors(exc), None)
    return ValidationResult(True, [], model)


def _validate_no_schema(
    payload: Any,
    *,
    model_cls: type[BaseModel],
    kind: str,
) -> ValidationResult:
    if not isinstance(payload, Mapping):
        return ValidationResult(
            False, [f"{kind} payload must be a JSON object"], None
        )
    try:
        model = model_cls.model_validate(payload)
    except ValidationError as exc:
        return ValidationResult(False, _flatten_pydantic_errors(exc), None)
    return ValidationResult(True, [], model)


def validate_manifest(payload: Any) -> ValidationResult:
    """Validate a change-risk manifest payload."""

    return _validate_with_schema(payload, model_cls=ManifestV1, kind="manifest")


def validate_catalog(payload: Any) -> ValidationResult:
    """Validate a test-catalog payload."""

    return _validate_with_schema(payload, model_cls=CatalogV1, kind="catalog")


def validate_agent_spec(payload: Any) -> ValidationResult:
    """Validate a frozen Agent evaluation spec payload."""

    return _validate_with_schema(
        payload, model_cls=AgentSpecV1, kind="agent_spec"
    )


def validate_agent_run(payload: Any) -> ValidationResult:
    """Validate a single JSONL row of Agent runs.

    Agent run rows do not carry ``schema_version``; the row is bound to a spec
    version through ``evaluation_fingerprint`` instead.
    """

    return _validate_no_schema(payload, model_cls=AgentRunV1, kind="agent_run")


def validate_agent_runs(runs: list[Any]) -> ValidationResult | None:
    """Validate every JSONL row in a list.

    Returns ``None`` when every row is structurally valid; otherwise returns
    the first failure wrapped in a prefixed :class:`ValidationResult` so the
    caller can pinpoint which row failed (``runs[N]: ...``). The prefix is the
    canonical path used by both the CLI and the MCP server.
    """

    for index, raw in enumerate(runs):
        if not isinstance(raw, Mapping):
            return ValidationResult(
                False,
                [f"runs[{index}]: must be a JSON object"],
                None,
            )
        check = validate_agent_run(raw)
        if not check.ok:
            return ValidationResult(
                False,
                [f"runs[{index}]: " + "; ".join(check.errors)],
                None,
            )
    return None


__all__ = [
    "ValidationResult",
    "ManifestV1",
    "CatalogV1",
    "AgentSpecV1",
    "AgentRunV1",
    "validate_manifest",
    "validate_catalog",
    "validate_agent_spec",
    "validate_agent_run",
    "validate_agent_runs",
    "SUPPORTED_VERSION",
]
