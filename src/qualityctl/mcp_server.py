from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .agent_eval import evaluate_agent_runs
from .gate import decide_quality_gate
from .risk import validate_risk_manifest
from .selection import evaluate_automation_candidate, select_regression_tests
from .validation import (
    ValidationResult,
    validate_agent_run,
    validate_agent_runs,
    validate_agent_spec,
    validate_catalog,
    validate_manifest,
)


mcp = MCPServer(
    "Quality Gatekeeper",
    version="0.1.0",
    instructions=(
        "Use these deterministic tools to verify LLM-proposed quality evidence. "
        "Never reinterpret BLOCKED, FAIL, or REVIEW_REQUIRED as PASS. "
        "Do not invent missing evidence references. Inputs that fail structural "
        "validation are surfaced as a tool error (is_error=true) so the caller "
        "can correct the payload before any gate decision is made."
    ),
)


def _raise_validation_error(kind: str, result: ValidationResult) -> None:
    """Convert a failed :class:`ValidationResult` into a structured ToolError."""

    payload = {
        "ok": False,
        "kind": "structural_validation",
        "input": kind,
        "errors": list(result.errors),
    }
    raise ToolError(json.dumps(payload, ensure_ascii=False))


@mcp.tool()
def validate_change_risks(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate change risk coverage across business and technical dimensions.

    Call after an LLM or human drafts a risk manifest. READY means every
    required dimension has an explicit, evidenced disposition. A structurally
    invalid manifest is rejected with ``is_error=true`` before any rule runs.
    """

    check = validate_manifest(manifest)
    if not check.ok:
        _raise_validation_error("manifest", check)
    return validate_risk_manifest(manifest)


@mcp.tool()
def select_regression_scope(
    catalog: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    """Select a traceable regression set and report uncovered risk dimensions.

    Both the manifest and the catalog are structurally validated up front. A
    payload that does not parse is rejected with ``is_error=true``; otherwise the
    deterministic selector runs and returns its normal status / coverage shape.
    """

    manifest_check = validate_manifest(manifest)
    if not manifest_check.ok:
        _raise_validation_error("manifest", manifest_check)
    catalog_check = validate_catalog(catalog)
    if not catalog_check.ok:
        _raise_validation_error("catalog", catalog_check)
    return select_regression_tests(catalog, manifest)


@mcp.tool()
def evaluate_agent_evidence(
    spec: dict[str, Any], runs: list[dict[str, Any]]
) -> dict[str, Any]:
    """Evaluate repeated non-deterministic Agent runs against frozen rules.

    Technical failures, invalid runner attempts, deterministic assertion
    failures, and missing semantic reviews remain separate failure domains. The
    spec and every run row are structurally validated up front; invalid input
    is rejected with ``is_error=true``.
    """

    spec_check = validate_agent_spec(spec)
    if not spec_check.ok:
        _raise_validation_error("agent_spec", spec_check)
    run_failure = validate_agent_runs(runs)
    if run_failure is not None:
        _raise_validation_error("agent_run", run_failure)
    return evaluate_agent_runs(spec, runs)


@mcp.tool()
def assess_automation_roi(
    candidate: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    """Decide whether a stable repeated manual check is worth automating now.

    The candidate ``automation_fit`` object and the policy must be present and
    non-empty; otherwise the call is rejected with ``is_error=true`` so callers
    do not silently receive an INSUFFICIENT_DATA verdict for missing inputs.
    """

    if not isinstance(candidate, dict):
        raise ToolError(
            json.dumps(
                {
                    "ok": False,
                    "kind": "structural_validation",
                    "input": "candidate",
                    "errors": ["candidate must be a JSON object"],
                },
                ensure_ascii=False,
            )
        )
    if not isinstance(policy, dict):
        raise ToolError(
            json.dumps(
                {
                    "ok": False,
                    "kind": "structural_validation",
                    "input": "policy",
                    "errors": ["policy must be a JSON object"],
                },
                ensure_ascii=False,
            )
        )
    if "automation_fit" not in candidate:
        raise ToolError(
            json.dumps(
                {
                    "ok": False,
                    "kind": "structural_validation",
                    "input": "candidate",
                    "errors": ["candidate.automation_fit is required"],
                },
                ensure_ascii=False,
            )
        )
    if not policy.get("version") or not policy.get("source_ref"):
        raise ToolError(
            json.dumps(
                {
                    "ok": False,
                    "kind": "structural_validation",
                    "input": "policy",
                    "errors": [
                        "policy.version is required",
                        "policy.source_ref is required",
                    ],
                },
                ensure_ascii=False,
            )
        )
    return evaluate_automation_candidate(candidate, policy)


@mcp.tool()
def decide_release_gate(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    agent_spec: dict[str, Any] | None = None,
    agent_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute risk, regression, and Agent evidence into the release gate.

    Supply raw evidence rather than caller-claimed statuses. Automation ROI is
    advisory and intentionally excluded from the release decision. All provided
    inputs are structurally validated up front; an invalid payload is rejected
    with ``is_error=true``.
    """

    manifest_check = validate_manifest(manifest)
    if not manifest_check.ok:
        _raise_validation_error("manifest", manifest_check)
    catalog_check = validate_catalog(catalog)
    if not catalog_check.ok:
        _raise_validation_error("catalog", catalog_check)
    if agent_spec is not None:
        spec_check = validate_agent_spec(agent_spec)
        if not spec_check.ok:
            _raise_validation_error("agent_spec", spec_check)
    if agent_runs is not None:
        run_failure = validate_agent_runs(agent_runs)
        if run_failure is not None:
            _raise_validation_error("agent_run", run_failure)
    return decide_quality_gate(
        manifest,
        catalog,
        agent_spec=agent_spec,
        agent_runs=agent_runs,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()