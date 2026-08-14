from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .risk import RISK_DIMENSIONS, validate_risk_manifest
from .validation import validate_catalog


HIGH_RISK_DIMENSIONS = {
    "permissions",
    "data_consistency",
    "side_effects",
    "recoverability",
}
DETERMINISTIC_ORACLES = {"exact", "schema", "rule", "state", "contract"}


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if isinstance(item, str) and item}


def _finite_non_negative(value: Any, *, positive: bool = False) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and (float(value) > 0 if positive else float(value) >= 0)
    )


def evaluate_automation_candidate(
    test: Mapping[str, Any], policy: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Estimate whether one manual test is worth automating.

    The decision is intentionally conservative: an already automated test is
    reported as such, while unstable, non-repeatable, weak-oracle, incomplete,
    or net-negative candidates are not recommended for automation.
    """

    already_automated = test.get("automated") is True
    fit = test.get("automation_fit")
    if not isinstance(fit, Mapping):
        return {
            "test_id": test.get("id"),
            "decision": "INSUFFICIENT_DATA",
            "monthly_minutes_saved": None,
            "reasons": ["automation_fit is required, including for existing automation"],
        }

    data_errors: list[str] = []
    suitability_reasons: list[str] = []
    if fit.get("stable") is not True:
        suitability_reasons.append("behavior is not stable")
    if fit.get("repeatable") is not True:
        suitability_reasons.append("execution is not repeatable")
    oracle = fit.get("oracle")
    if oracle not in DETERMINISTIC_ORACLES:
        suitability_reasons.append("Oracle is not deterministic enough")

    if not isinstance(policy, Mapping):
        data_errors.append("approved automation policy is required")
        policy = {}
    else:
        if policy.get("approval_status") != "APPROVED":
            data_errors.append("automation policy is not approved")
        for field in ("version", "source_ref"):
            if not str(policy.get(field, "")).strip():
                data_errors.append(f"automation policy {field} is required")
        for field in ("max_payback_months", "min_monthly_net_minutes"):
            if not _finite_non_negative(
                policy.get(field), positive=field == "max_payback_months"
            ):
                data_errors.append(f"automation policy {field} must be finite and valid")

    if fit.get("data_basis") not in {"ESTIMATED", "OBSERVED"}:
        data_errors.append("data_basis must be ESTIMATED or OBSERVED")
    if not _finite_non_negative(fit.get("observation_window_days"), positive=True):
        data_errors.append("observation_window_days must be a finite positive number")

    numeric_fields = (
        "runs_per_month",
        "manual_minutes",
        "residual_review_minutes_per_run",
        "maintenance_minutes_per_month",
        "flaky_investigation_minutes_per_month",
        "execution_cost_minutes_equivalent_per_month",
        "data_maintenance_minutes_per_month",
        "setup_minutes",
    )
    for field in numeric_fields:
        if not _finite_non_negative(
            fit.get(field), positive=field == "runs_per_month"
        ):
            data_errors.append(f"{field} must be a finite valid number")

    if data_errors:
        monthly_saving = None
        payback_months = None
    else:
        monthly_saving = round(
            float(fit["runs_per_month"])
            * (
                float(fit["manual_minutes"])
                - float(fit["residual_review_minutes_per_run"])
            )
            - float(fit["maintenance_minutes_per_month"])
            - float(fit["flaky_investigation_minutes_per_month"])
            - float(fit["execution_cost_minutes_equivalent_per_month"])
            - float(fit["data_maintenance_minutes_per_month"]),
            2,
        )
        payback_months = (
            round(float(fit["setup_minutes"]) / monthly_saving, 2)
            if monthly_saving > 0
            else None
        )
        if monthly_saving < float(policy["min_monthly_net_minutes"]):
            suitability_reasons.append("monthly net saving is below approved policy")
        if not already_automated and (
            payback_months is None
            or payback_months > float(policy["max_payback_months"])
        ):
            suitability_reasons.append("payback exceeds approved policy")

    if data_errors:
        decision = "INSUFFICIENT_DATA"
        reasons = data_errors + suitability_reasons
    elif already_automated:
        decision = "KEEP" if not suitability_reasons else "REPAIR_OR_RETIRE"
        reasons = suitability_reasons or ["existing automation remains net-positive"]
    else:
        decision = "CANDIDATE" if not suitability_reasons else "DO_NOT_AUTOMATE_YET"
        reasons = suitability_reasons or [
            "stable, repeated, deterministic, net-positive, and within payback policy"
        ]
    result: dict[str, Any] = {
        "test_id": test.get("id"),
        "decision": decision,
        "monthly_minutes_saved": monthly_saving,
        "payback_months": payback_months,
        "data_basis": fit.get("data_basis"),
        "observation_window_days": fit.get("observation_window_days"),
        "policy_version": policy.get("version"),
        "reasons": reasons,
    }
    return result


def _automation_decision(
    test: Mapping[str, Any], policy: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    if test.get("automated") is True:
        return None
    return evaluate_automation_candidate(test, policy)


def select_regression_tests(
    catalog: Mapping[str, Any], manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Select a traceable minimum regression set from explicit change and risk facts."""

    risk_check = validate_risk_manifest(manifest)
    if risk_check["status"] == "BLOCKED":
        return {
            "status": "BLOCKED",
            "risk_check": risk_check,
            "errors": risk_check.get("errors", []),
            "selected": [],
            "excluded": [],
            "coverage_gaps": [],
            "automation_review": [],
        }

    catalog_check = validate_catalog(catalog)
    if not catalog_check.ok:
        return {
            "status": "BLOCKED",
            "risk_check": risk_check,
            "errors": catalog_check.errors,
            "selected": [],
            "excluded": [],
            "coverage_gaps": [],
            "automation_review": [],
        }

    tests = catalog["tests"]
    automation_policy = catalog.get("automation_policy")

    changed = _string_set(manifest.get("changed_components"))
    dependencies = manifest.get("dependencies", {})
    upstream = _string_set(dependencies.get("upstream", [])) if isinstance(dependencies, Mapping) else set()
    downstream = _string_set(dependencies.get("downstream", [])) if isinstance(dependencies, Mapping) else set()
    impacted_components = changed | upstream | downstream
    risk_signals = _string_set(manifest.get("risk_signals"))
    dimension_entries = manifest.get("dimensions", {})
    affected_dimensions = {
        name
        for name in RISK_DIMENSIONS
        if isinstance(dimension_entries, Mapping)
        and isinstance(dimension_entries.get(name), Mapping)
        and dimension_entries[name].get("status") == "affected"
    }
    version_type = manifest.get("version_type")

    selected: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    automation_review: list[dict[str, Any]] = []
    catalog_errors: list[str] = []
    seen_ids: set[str] = set()

    for index, raw_test in enumerate(tests):
        if not isinstance(raw_test, Mapping):
            catalog_errors.append(f"catalog row {index} is not an object")
            excluded.append({"test_id": None, "reason": f"catalog row {index} is not an object"})
            continue
        test_id = str(raw_test.get("id", "")).strip()
        if not test_id or test_id in seen_ids:
            catalog_errors.append(f"catalog row {index} has a missing or duplicate test id")
            excluded.append(
                {"test_id": test_id or None, "reason": "test id is missing or duplicated"}
            )
            continue
        seen_ids.add(test_id)
        components = _string_set(raw_test.get("components"))
        dimensions = _string_set(raw_test.get("dimensions"))
        risks = _string_set(raw_test.get("risks"))
        suites = _string_set(raw_test.get("suites"))
        labels = _string_set(raw_test.get("labels"))
        priority = raw_test.get("priority")
        reasons: list[str] = []

        component_hits = sorted(components & impacted_components)
        dimension_hits = sorted(dimensions & affected_dimensions)
        risk_hits = sorted(risks & risk_signals)
        scoped_risk_match = bool(component_hits or not components or "global_guardrail" in labels)

        if "smoke" in suites:
            reasons.append("mandatory smoke")
        if version_type == "major":
            reasons.append("major release requires full catalog")
        if component_hits:
            reasons.append(f"impacted components: {', '.join(component_hits)}")
        if dimension_hits and scoped_risk_match:
            reasons.append(f"affected risk dimensions: {', '.join(dimension_hits)}")
        if risk_hits and scoped_risk_match:
            reasons.append(f"risk signals: {', '.join(risk_hits)}")
        if "historical_escape" in labels and (component_hits or not components):
            reasons.append("historical escape coverage")
        if version_type == "daily" and priority == "CP0" and "core" in suites:
            reasons.append("daily CP0 core")

        if reasons:
            selected.append(
                {
                    "test_id": test_id,
                    "priority": priority,
                    "automated": bool(raw_test.get("automated")),
                    "reasons": reasons,
                }
            )
            automation = _automation_decision(raw_test, automation_policy)
            if automation is not None:
                automation_review.append(automation)
        else:
            excluded.append(
                {
                    "test_id": test_id,
                    "reason": "no version, component, dependency, risk, or history rule matched",
                }
            )

    selected_ids = {item["test_id"] for item in selected}
    coverage_gaps: list[dict[str, Any]] = []
    smoke_covered = any(
        isinstance(test, Mapping)
        and str(test.get("id")) in selected_ids
        and "smoke" in _string_set(test.get("suites"))
        for test in tests
    )
    if not smoke_covered:
        coverage_gaps.append(
            {
                "dimension": "smoke",
                "severity": "high",
                "reason": "every release requires at least one selected smoke test",
            }
        )
    for dimension in sorted(affected_dimensions):
        covered_by = [
            str(test.get("id"))
            for test in tests
            if isinstance(test, Mapping)
            and str(test.get("id")) in selected_ids
            and dimension in _string_set(test.get("dimensions"))
        ]
        if not covered_by:
            coverage_gaps.append(
                {
                    "dimension": dimension,
                    "severity": "high" if dimension in HIGH_RISK_DIMENSIONS else "medium",
                    "reason": "affected dimension has no selected test",
                }
            )

    automation_review.sort(
        key=lambda item: (
            item["decision"] != "CANDIDATE",
            -(item.get("monthly_minutes_saved") or 0),
            str(item.get("test_id")),
        )
    )

    if catalog_errors:
        status = "BLOCKED"
    elif coverage_gaps or risk_check["status"] == "REVIEW_REQUIRED":
        status = "REVIEW_REQUIRED"
    else:
        status = "READY"

    return {
        "status": status,
        "change_id": manifest.get("change_id"),
        "version_type": version_type,
        "risk_check": risk_check,
        "errors": catalog_errors,
        "selection_summary": {
            "catalog_count": len(tests),
            "selected_count": len(selected),
            "excluded_count": len(excluded),
            "impacted_components": sorted(impacted_components),
            "affected_dimensions": sorted(affected_dimensions),
        },
        "selected": selected,
        "excluded": excluded,
        "coverage_gaps": coverage_gaps,
        "automation_review": automation_review,
    }
