from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .validation import validate_manifest


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


def validate_risk_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that a change has been assessed across every risk dimension.

    Pure structural validation (types, enums, presence, cross-field rules on a
    single dimension) is delegated to :func:`qualityctl.validation.validate_manifest`.
    This function retains the semantic checks that need the full manifest
    picture: signal-to-dimension cross-checks and the
    ``READY / REVIEW_REQUIRED / BLOCKED`` roll-up.
    """

    structural = validate_manifest(manifest)
    if not structural.ok:
        return {
            "status": "BLOCKED",
            "change_id": (
                manifest.get("change_id") if isinstance(manifest, Mapping) else None
            ),
            "version_type": (
                manifest.get("version_type") if isinstance(manifest, Mapping) else None
            ),
            "agent_evaluation": (
                dict(manifest["agent_evaluation"])
                if isinstance(manifest, Mapping)
                and isinstance(manifest.get("agent_evaluation"), Mapping)
                else None
            ),
            "errors": structural.errors,
            "warnings": [],
            "unknown_dimensions": [],
            "assessed_dimensions": {},
        }

    # structural.model is the validated Pydantic ManifestV1; safe to read fields.
    warnings: list[str] = []
    unknown_dimensions: list[str] = []
    assessed: dict[str, str] = {}

    dimensions = manifest["dimensions"]
    for name in RISK_DIMENSIONS:
        entry = dimensions[name]
        status = entry["status"]
        assessed[name] = status
        if status == "unknown":
            unknown_dimensions.append(name)

    risk_signals = manifest.get("risk_signals", [])
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

    if unknown_dimensions:
        status = "REVIEW_REQUIRED"
    else:
        status = "READY"

    return {
        "status": status,
        "change_id": manifest.get("change_id"),
        "version_type": manifest.get("version_type"),
        "agent_evaluation": dict(manifest["agent_evaluation"]),
        "errors": [],
        "warnings": warnings,
        "unknown_dimensions": unknown_dimensions,
        "assessed_dimensions": assessed,
    }