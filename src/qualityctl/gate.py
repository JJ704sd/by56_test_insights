from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .agent_eval import evaluate_agent_runs
from .risk import validate_risk_manifest
from .selection import select_regression_tests


def decide_quality_gate(
    manifest: Mapping[str, Any],
    catalog: Mapping[str, Any],
    *,
    agent_spec: Mapping[str, Any] | None = None,
    agent_runs: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute every required domain and return the final release gate.

    The caller supplies raw evidence, never claimed statuses. This prevents an
    LLM from inventing a PASS check, changing requiredness, or forging an
    evidence reference. Automation ROI is intentionally advisory and is not a
    release gate in the MVP policy.
    """

    errors: list[str] = []
    risk_result = validate_risk_manifest(manifest)
    regression_result = select_regression_tests(catalog, manifest)

    agent_policy = manifest.get("agent_evaluation") if isinstance(manifest, Mapping) else None
    agent_result: dict[str, Any] | None
    if not isinstance(agent_policy, Mapping) or not isinstance(
        agent_policy.get("required"), bool
    ):
        errors.append("validated agent_evaluation policy is required")
        agent_status = "BLOCKED"
        agent_result = None
    elif agent_policy["required"]:
        if not isinstance(agent_spec, Mapping):
            errors.append("agent_spec is required by agent_evaluation policy")
        if not isinstance(agent_runs, list):
            errors.append("agent_runs is required by agent_evaluation policy")
        if errors:
            agent_status = "BLOCKED"
            agent_result = None
        else:
            assert agent_spec is not None
            assert agent_runs is not None
            agent_result = evaluate_agent_runs(agent_spec, agent_runs)
            agent_status = str(agent_result["gate"])
    else:
        agent_status = "NOT_APPLICABLE"
        agent_result = None

    checks = [
        {
            "name": "risk",
            "status": risk_result["status"],
            "evidence": {
                "change_id": risk_result.get("change_id"),
                "errors": risk_result.get("errors", []),
                "unknown_dimensions": risk_result.get("unknown_dimensions", []),
            },
        },
        {
            "name": "regression",
            "status": regression_result["status"],
            "evidence": {
                "change_id": regression_result.get("change_id"),
                "selected_count": regression_result.get("selection_summary", {}).get(
                    "selected_count", 0
                ),
                "coverage_gaps": regression_result.get("coverage_gaps", []),
                "errors": regression_result.get("errors", []),
            },
        },
        {
            "name": "agent-evaluation",
            "status": agent_status,
            "evidence": (
                {
                    "agent_version": agent_result.get("agent_version"),
                    "dataset_version": agent_result.get("dataset_version"),
                    "threshold_profile": agent_result.get("threshold_profile"),
                    "run_counts": agent_result.get("run_counts"),
                    "errors": agent_result.get("errors", []),
                }
                if agent_result is not None
                else {
                    "approved_by": agent_policy.get("approved_by")
                    if isinstance(agent_policy, Mapping)
                    else None,
                    "evidence_ref": agent_policy.get("evidence_ref")
                    if isinstance(agent_policy, Mapping)
                    else None,
                }
            ),
        },
    ]

    statuses = {str(check["status"]) for check in checks}
    if errors:
        gate = "BLOCKED"
    elif "FAIL" in statuses:
        gate = "FAIL"
    elif "BLOCKED" in statuses:
        gate = "BLOCKED"
    elif "REVIEW_REQUIRED" in statuses:
        gate = "REVIEW_REQUIRED"
    else:
        gate = "PASS"

    return {
        "gate": gate,
        "release_allowed": gate == "PASS",
        "policy_version": "mvp-v1",
        "errors": errors,
        "blocking_checks": [
            check
            for check in checks
            if check["status"] in {"FAIL", "BLOCKED", "REVIEW_REQUIRED"}
        ],
        "checks": checks,
        "results": {
            "risk": risk_result,
            "regression": regression_result,
            "agent_evaluation": agent_result,
        },
    }
