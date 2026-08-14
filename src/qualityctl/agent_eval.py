from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping
from typing import Any


MISSING = object()
MINIMUM_RUNS_BY_RISK = {"high": 3, "medium": 3, "low": 1}


from .validation import validate_agent_run, validate_agent_spec  # noqa: E402


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validate_assertion(assertion: Any) -> list[str]:
    if not isinstance(assertion, Mapping):
        return ["must be an object"]
    kind = assertion.get("type")
    if kind == "required":
        paths = assertion.get("paths")
        if not isinstance(paths, list) or not paths or not all(
            isinstance(path, str) and path.strip() for path in paths
        ):
            return ["required.paths must contain at least one non-empty path"]
        return []

    path = assertion.get("path")
    errors: list[str] = []
    if not isinstance(path, str) or not path.strip():
        errors.append("path is required")
    if kind == "equals":
        if "expected" not in assertion:
            errors.append("equals.expected is required")
    elif kind == "one_of":
        values = assertion.get("values")
        if not isinstance(values, list) or not values:
            errors.append("one_of.values must not be empty")
    elif kind == "matches":
        pattern = assertion.get("pattern")
        if not isinstance(pattern, str):
            errors.append("matches.pattern is required")
        else:
            try:
                re.compile(pattern)
            except re.error:
                errors.append("matches.pattern must be a valid regex")
    elif kind == "number":
        if not _finite_number(assertion.get("expected")):
            errors.append("number.expected must be a finite number")
        tolerance_keys = [
            key
            for key in ("absolute_tolerance", "relative_tolerance")
            if key in assertion
        ]
        if len(tolerance_keys) != 1:
            errors.append(
                "number requires exactly one absolute_tolerance or relative_tolerance"
            )
        elif not _finite_number(assertion.get(tolerance_keys[0])) or float(
            assertion[tolerance_keys[0]]
        ) < 0:
            errors.append("number tolerance must be a finite non-negative number")
    else:
        errors.append(f"unsupported assertion type: {kind!r}")
    return errors


def _get_path(data: Any, path: str) -> Any:
    current = data
    for token in path.split(".") if path else []:
        if isinstance(current, Mapping):
            if token not in current:
                return MISSING
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                return MISSING
            current = current[index]
        else:
            return MISSING
    return current


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return [round(max(0.0, center - margin), 6), round(min(1.0, center + margin), 6)]


def _judge_assertion(output: Any, assertion: Mapping[str, Any]) -> tuple[bool, str]:
    kind = assertion.get("type")
    if kind == "required":
        missing = [path for path in assertion.get("paths", []) if _get_path(output, path) is MISSING]
        return (not missing, f"missing required paths: {missing}" if missing else "required paths present")

    path = str(assertion.get("path", ""))
    actual = _get_path(output, path)
    if actual is MISSING:
        return False, f"{path}: path is missing"

    if kind == "equals":
        expected = assertion.get("expected")
        return actual == expected, f"{path}: expected {expected!r}, got {actual!r}"
    if kind == "one_of":
        expected = assertion.get("values", [])
        return actual in expected, f"{path}: expected one of {expected!r}, got {actual!r}"
    if kind == "matches":
        pattern = assertion.get("pattern")
        if not isinstance(pattern, str):
            return False, f"{path}: regex pattern is missing"
        matched = isinstance(actual, str) and re.search(pattern, actual) is not None
        return matched, f"{path}: value {actual!r} does not match {pattern!r}"
    if kind == "number":
        expected = assertion.get("expected")
        if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            return False, f"{path}: numeric assertion received non-number"
        has_abs = isinstance(assertion.get("absolute_tolerance"), (int, float))
        has_rel = isinstance(assertion.get("relative_tolerance"), (int, float))
        if has_abs == has_rel:
            return False, f"{path}: specify exactly one absolute_tolerance or relative_tolerance"
        difference = abs(float(actual) - float(expected))
        if has_abs:
            tolerance = float(assertion["absolute_tolerance"])
        else:
            tolerance = abs(float(expected)) * float(assertion["relative_tolerance"])
        return difference <= tolerance, (
            f"{path}: expected {expected!r} within {tolerance}, got {actual!r}"
        )
    return False, f"unsupported assertion type: {kind!r}"


def _evaluate_output(output: Any, assertions: list[Any]) -> tuple[bool, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    for index, raw_assertion in enumerate(assertions):
        if not isinstance(raw_assertion, Mapping):
            passed, detail = False, "assertion must be an object"
            assertion_type = None
        else:
            passed, detail = _judge_assertion(output, raw_assertion)
            assertion_type = raw_assertion.get("type")
        results.append(
            {
                "index": index,
                "type": assertion_type,
                "passed": passed,
                "detail": detail,
            }
        )
    return all(result["passed"] for result in results), results


def _blocked_evaluation(
    spec: Mapping[str, Any], errors: list[str]
) -> dict[str, Any]:
    """Return a deterministic BLOCKED evaluation result when the spec is
    structurally invalid. The shape mirrors the success path so callers do not
    branch on whether validation passed.
    """

    return {
        "gate": "BLOCKED",
        "agent_version": spec.get("agent_version") if isinstance(spec, Mapping) else None,
        "dataset_version": spec.get("dataset_version") if isinstance(spec, Mapping) else None,
        "threshold_profile": {
            "version": (
                spec.get("threshold_profile", {}).get("version")
                if isinstance(spec, Mapping) and isinstance(spec.get("threshold_profile"), Mapping)
                else None
            ),
            "source_ref": None,
            "approval_status": (
                spec.get("threshold_profile", {}).get("approval_status")
                if isinstance(spec, Mapping) and isinstance(spec.get("threshold_profile"), Mapping)
                else None
            ),
        },
        "run_counts": {
            "planned": 0,
            "observed": 0,
            "valid_outputs": 0,
            "runner_invalid": 0,
            "technical_failures": 0,
            "deterministic_failures": 0,
            "manual_review_failures": 0,
            "manual_review_missing": 0,
            "passed": 0,
        },
        "errors": errors,
        "case_results": [],
    }


def evaluate_agent_runs(spec: Mapping[str, Any], runs: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate repeated Agent runs without hiding invalid or technical failures.

    Pure structural validation (types, enums, presence, cross-field rules on
    assertions and runs) is delegated to
    :func:`qualityctl.validation.validate_agent_spec` and
    :func:`qualityctl.validation.validate_agent_run`. This function retains
    the evaluation semantics: fingerprint matching, Wilson intervals,
    failure-domain split, and the final gate roll-up.
    """

    errors: list[str] = []

    spec_check = validate_agent_spec(spec)
    if not spec_check.ok:
        return _blocked_evaluation(spec, spec_check.errors)

    for index, raw_run in enumerate(runs):
        if not isinstance(raw_run, Mapping):
            errors.append(f"runs[{index}]: must be a JSON object")
            continue
        run_check = validate_agent_run(raw_run)
        if not run_check.ok:
            errors.append(f"runs[{index}]: " + "; ".join(run_check.errors))

    execution_profile = spec.get("execution_profile", {})
    profile = spec.get("threshold_profile", {})
    approval_status = profile.get("approval_status")
    cases = spec.get("cases") if isinstance(spec, Mapping) else None
    if not isinstance(cases, list) or not cases:
        errors.append("cases must contain at least one case")
        cases = []

    runs_by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    seen_run_ids: set[tuple[str, str]] = set()
    expected_fingerprint = str(spec.get("evaluation_fingerprint", "")) if isinstance(spec, Mapping) else ""
    for run in runs:
        case_id = str(run.get("case_id", ""))
        run_id = str(run.get("run_id", ""))
        key = (case_id, run_id)
        if not case_id or not run_id:
            errors.append("each run requires case_id and run_id")
            continue
        if key in seen_run_ids:
            errors.append(f"duplicate run id: {case_id}/{run_id}")
            continue
        if str(run.get("evaluation_fingerprint", "")) != expected_fingerprint:
            errors.append(f"run fingerprint mismatch: {case_id}/{run_id}")
            continue
        seen_run_ids.add(key)
        runs_by_case[case_id].append(run)

    case_results: list[dict[str, Any]] = []
    global_fail = False
    global_blocked = bool(errors)
    global_review = False
    known_cases: set[str] = set()
    totals = {
        "planned": 0,
        "observed": 0,
        "valid_outputs": 0,
        "runner_invalid": 0,
        "technical_failures": 0,
        "deterministic_failures": 0,
        "manual_review_failures": 0,
        "manual_review_missing": 0,
        "passed": 0,
    }

    for index, raw_case in enumerate(cases):
        if not isinstance(raw_case, Mapping):
            errors.append(f"case row {index} must be an object")
            global_blocked = True
            continue
        case_id = str(raw_case.get("id", "")).strip()
        if not case_id or case_id in known_cases:
            errors.append(f"case row {index} has missing or duplicate id")
            global_blocked = True
            continue
        known_cases.add(case_id)
        risk = raw_case.get("risk", "medium")
        planned_runs = raw_case.get("planned_runs")
        min_pass_rate = raw_case.get("min_pass_rate")
        assertions = raw_case.get("assertions", [])
        semantic_required = raw_case.get("semantic_review_required") is True
        hard_fail_on_any = raw_case.get("hard_fail_on_any")
        if risk == "high":
            hard_fail_on_any = True
        elif hard_fail_on_any is None:
            hard_fail_on_any = False

        case_errors: list[str] = []
        if risk not in MINIMUM_RUNS_BY_RISK:
            case_errors.append("risk must be high, medium, or low")
            risk = "medium"
        if not isinstance(planned_runs, int) or planned_runs <= 0:
            case_errors.append("planned_runs must be a positive integer")
            planned_runs = 0
        elif planned_runs < MINIMUM_RUNS_BY_RISK[risk]:
            case_errors.append(
                f"planned_runs must be at least {MINIMUM_RUNS_BY_RISK[risk]} for {risk} risk"
            )
        if not isinstance(min_pass_rate, (int, float)) or not 0 <= float(min_pass_rate) <= 1:
            case_errors.append("min_pass_rate must be between 0 and 1")
            min_pass_rate = None
        if not isinstance(assertions, list) or not assertions:
            case_errors.append("assertions must contain at least one deterministic assertion")
            assertions = []
        for assertion_index, assertion in enumerate(assertions):
            case_errors.extend(
                f"assertions[{assertion_index}]: {message}"
                for message in _validate_assertion(assertion)
            )

        observed_runs = runs_by_case.get(case_id, [])
        if planned_runs and len(observed_runs) > planned_runs:
            case_errors.append(
                f"observed {len(observed_runs)} runs exceeds frozen plan of {planned_runs}"
            )
        totals["planned"] += planned_runs
        totals["observed"] += len(observed_runs)
        run_results: list[dict[str, Any]] = []
        passed = 0
        evaluated_attempts = 0
        runner_invalid = 0
        technical_failures = 0
        deterministic_failures = 0
        manual_failures = 0
        manual_missing = 0

        for run in observed_runs:
            technical_status = run.get("technical_status")
            result: dict[str, Any] = {
                "run_id": run.get("run_id"),
                "technical_status": technical_status,
            }
            if technical_status == "runner_invalid":
                runner_invalid += 1
                result["outcome"] = "INVALID"
                result["reason"] = run.get("error", "runner or collection failure")
                run_results.append(result)
                continue
            evaluated_attempts += 1
            if technical_status != "ok":
                technical_failures += 1
                result["outcome"] = "TECHNICAL_FAIL"
                result["reason"] = run.get("error", "Agent/system technical failure")
                run_results.append(result)
                continue

            totals["valid_outputs"] += 1
            assertion_pass, assertion_results = _evaluate_output(run.get("output"), assertions)
            result["assertions"] = assertion_results
            manual_review = run.get("manual_review")
            manual_status = (
                manual_review.get("status") if isinstance(manual_review, Mapping) else None
            )
            manual_evidence_valid = isinstance(manual_review, Mapping) and all(
                str(manual_review.get(field, "")).strip()
                for field in (
                    "reviewer_id",
                    "reviewer_role",
                    "rubric_version",
                    "evidence_ref",
                    "reviewed_at",
                )
            )
            if not assertion_pass:
                deterministic_failures += 1
                result["outcome"] = "DETERMINISTIC_FAIL"
            elif semantic_required and (
                manual_status not in {"pass", "fail"} or not manual_evidence_valid
            ):
                manual_missing += 1
                result["outcome"] = "REVIEW_REQUIRED"
            elif semantic_required and manual_status == "fail":
                manual_failures += 1
                result["outcome"] = "SEMANTIC_FAIL"
            else:
                passed += 1
                result["outcome"] = "PASS"
            run_results.append(result)

        pass_rate = round(passed / evaluated_attempts, 6) if evaluated_attempts else None
        interval = wilson_interval(passed, evaluated_attempts)
        insufficient_runs = evaluated_attempts < planned_runs
        threshold_failed = (
            min_pass_rate is not None
            and pass_rate is not None
            and pass_rate < float(min_pass_rate)
        )
        any_effective_failure = technical_failures + deterministic_failures + manual_failures > 0

        if case_errors or insufficient_runs:
            case_status = "BLOCKED"
            global_blocked = True
        elif hard_fail_on_any and any_effective_failure:
            case_status = "FAIL"
            global_fail = True
        elif manual_missing:
            case_status = "BLOCKED" if risk == "high" else "REVIEW_REQUIRED"
            global_blocked = global_blocked or risk == "high"
            global_review = global_review or risk != "high"
        elif approval_status == "APPROVED" and threshold_failed:
            case_status = "FAIL"
            global_fail = True
        elif approval_status != "APPROVED":
            case_status = "BLOCKED" if risk == "high" else "REVIEW_REQUIRED"
            global_blocked = global_blocked or risk == "high"
            global_review = global_review or risk != "high"
        else:
            case_status = "PASS"

        totals["runner_invalid"] += runner_invalid
        totals["technical_failures"] += technical_failures
        totals["deterministic_failures"] += deterministic_failures
        totals["manual_review_failures"] += manual_failures
        totals["manual_review_missing"] += manual_missing
        totals["passed"] += passed

        baseline_rate = raw_case.get("baseline_pass_rate")
        baseline_change = None
        if isinstance(baseline_rate, (int, float)) and pass_rate is not None:
            point_change = round(pass_rate - float(baseline_rate), 6)
            relative_degradation = (
                round((float(baseline_rate) - pass_rate) / float(baseline_rate), 6)
                if baseline_rate
                else None
            )
            baseline_change = {
                "baseline_pass_rate": baseline_rate,
                "percentage_point_change": point_change,
                "relative_degradation": relative_degradation,
            }

        case_results.append(
            {
                "case_id": case_id,
                "risk": risk,
                "status": case_status,
                "planned_runs": planned_runs,
                "observed_runs": len(observed_runs),
                "evaluated_attempts": evaluated_attempts,
                "runner_invalid": runner_invalid,
                "technical_failures": technical_failures,
                "deterministic_failures": deterministic_failures,
                "manual_review_failures": manual_failures,
                "manual_review_missing": manual_missing,
                "passed": passed,
                "pass_rate": pass_rate,
                "wilson_95": interval,
                "min_pass_rate": min_pass_rate,
                "hard_fail_on_any": bool(hard_fail_on_any),
                "baseline_change": baseline_change,
                "errors": case_errors,
                "runs": run_results,
            }
        )

    unexpected_case_ids = sorted(set(runs_by_case) - known_cases)
    if unexpected_case_ids:
        errors.append(f"runs reference unknown cases: {unexpected_case_ids}")
        global_blocked = True

    if global_fail:
        gate = "FAIL"
    elif global_blocked:
        gate = "BLOCKED"
    elif global_review:
        gate = "REVIEW_REQUIRED"
    else:
        gate = "PASS"

    return {
        "gate": gate,
        "agent_version": spec.get("agent_version") if isinstance(spec, Mapping) else None,
        "dataset_version": spec.get("dataset_version") if isinstance(spec, Mapping) else None,
        "threshold_profile": {
            "version": profile.get("version"),
            "source_ref": profile.get("source_ref"),
            "approval_status": approval_status,
        },
        "run_counts": totals,
        "errors": errors,
        "case_results": case_results,
    }
