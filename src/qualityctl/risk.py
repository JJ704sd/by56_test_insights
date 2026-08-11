from __future__ import annotations

from collections.abc import Mapping
from typing import Any


RISK_DIMENSIONS = (
    "business_flow",
    "exception_paths",
    "boundaries",
    "permissions",
    "data_consistency",
    "upstream_downstream",
    "side_effects",
    "recoverability",
)

ALLOWED_STATUSES = {"affected", "not_affected", "not_applicable", "unknown"}


def _non_empty_strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def validate_risk_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that a change has been assessed across every risk dimension."""

    errors: list[str] = []
    warnings: list[str] = []
    unknown_dimensions: list[str] = []
    assessed: dict[str, str] = {}

    if not isinstance(manifest, Mapping):
        return {
            "status": "BLOCKED",
            "errors": ["risk manifest must be a JSON object"],
            "warnings": [],
            "unknown_dimensions": [],
            "assessed_dimensions": {},
        }

    if not str(manifest.get("change_id", "")).strip():
        errors.append("change_id is required")
    if manifest.get("version_type") not in {"daily", "hotfix", "major"}:
        errors.append("version_type must be daily, hotfix, or major")
    if not _non_empty_strings(manifest.get("changed_components")):
        errors.append("changed_components must contain at least one component")

    agent_evaluation = manifest.get("agent_evaluation")
    if not isinstance(agent_evaluation, Mapping):
        errors.append("agent_evaluation must be an object")
    else:
        if not isinstance(agent_evaluation.get("required"), bool):
            errors.append("agent_evaluation.required must be boolean")
        if not str(agent_evaluation.get("approved_by", "")).strip():
            errors.append("agent_evaluation.approved_by is required")
        if not str(agent_evaluation.get("evidence_ref", "")).strip():
            errors.append("agent_evaluation.evidence_ref is required")

    dimensions = manifest.get("dimensions")
    if not isinstance(dimensions, Mapping):
        errors.append("dimensions must be an object")
        dimensions = {}

    for name in RISK_DIMENSIONS:
        entry = dimensions.get(name)
        if not isinstance(entry, Mapping):
            errors.append(f"dimensions.{name} is required")
            continue
        status = entry.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(
                f"dimensions.{name}.status must be one of {sorted(ALLOWED_STATUSES)}"
            )
            continue
        assessed[name] = str(status)
        if status == "affected":
            if not str(entry.get("evidence", "")).strip():
                errors.append(f"dimensions.{name}.evidence is required when affected")
            if not _non_empty_strings(entry.get("scenarios")):
                errors.append(
                    f"dimensions.{name}.scenarios must contain an observable risk scenario"
                )
        elif status in {"not_affected", "not_applicable"}:
            if not str(entry.get("reason", "")).strip():
                errors.append(f"dimensions.{name}.reason is required for {status}")
        else:
            unknown_dimensions.append(name)
            if not str(entry.get("owner", "")).strip():
                errors.append(f"dimensions.{name}.owner is required when unknown")
            if not str(entry.get("resolve_by", "")).strip():
                errors.append(f"dimensions.{name}.resolve_by is required when unknown")

    dependencies = manifest.get("dependencies", {})
    if not isinstance(dependencies, Mapping):
        errors.append("dependencies must be an object with upstream/downstream arrays")
    else:
        for direction in ("upstream", "downstream"):
            value = dependencies.get(direction, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"dependencies.{direction} must be an array of strings")

    risk_signals = manifest.get("risk_signals", [])
    if not isinstance(risk_signals, list) or not all(
        isinstance(item, str) and item.strip() for item in risk_signals
    ):
        errors.append("risk_signals must be an array of non-empty strings")

    signal_expectations = {
        "permissions": {"auth", "permission", "security", "privacy"},
        "data_consistency": {"data_consistency", "billing", "data_migration"},
        "side_effects": {"side_effect", "billing", "write", "external_dependency"},
    }
    normalized_signals = {str(item).lower() for item in risk_signals}
    for dimension, expected in signal_expectations.items():
        if assessed.get(dimension) == "affected" and not normalized_signals.intersection(expected):
            warnings.append(
                f"{dimension} is affected but risk_signals has no matching high-risk marker"
            )

    if errors:
        status = "BLOCKED"
    elif unknown_dimensions:
        status = "REVIEW_REQUIRED"
    else:
        status = "READY"

    return {
        "status": status,
        "change_id": manifest.get("change_id"),
        "version_type": manifest.get("version_type"),
        "agent_evaluation": dict(agent_evaluation) if isinstance(agent_evaluation, Mapping) else None,
        "errors": errors,
        "warnings": warnings,
        "unknown_dimensions": unknown_dimensions,
        "assessed_dimensions": assessed,
    }
