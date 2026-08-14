from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .agent_eval import evaluate_agent_runs
from .io import read_json, read_jsonl, write_json
from .risk import validate_risk_manifest
from .selection import select_regression_tests
from .validation import (
    ValidationResult,
    validate_agent_runs,
    validate_agent_spec,
    validate_catalog,
    validate_manifest,
)


def _exit_code(status: str) -> int:
    if status in {"READY", "PASS"}:
        return 0
    if status == "REVIEW_REQUIRED":
        return 1
    return 2


def _fail_validation(command: str, kind: str, result: ValidationResult) -> int:
    """Emit a structured validation error on stderr and return exit code 2."""

    payload = {
        "ok": False,
        "command": command,
        "kind": "structural_validation",
        "input": kind,
        "errors": list(result.errors),
    }
    print(
        json.dumps(payload, ensure_ascii=False, indent=2),
        file=sys.stderr,
    )
    return 2


def _validate_runs_or_fail(command: str, runs: list[dict[str, Any]]) -> int | None:
    failure = validate_agent_runs(runs)
    if failure is not None:
        return _fail_validation(command, "agent_run", failure)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qualityctl",
        description="Risk-driven regression selection and deterministic Agent evaluation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    risk = subparsers.add_parser("risk-check", help="validate a risk assessment manifest")
    risk.add_argument("manifest")
    risk.add_argument("--output", "-o")

    select = subparsers.add_parser("select", help="select the minimum effective regression set")
    select.add_argument("catalog")
    select.add_argument("manifest")
    select.add_argument("--output", "-o")

    agent = subparsers.add_parser("agent-eval", help="aggregate repeated Agent runs")
    agent.add_argument("spec")
    agent.add_argument("runs")
    agent.add_argument("--output", "-o")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: dict[str, Any]
        if args.command == "risk-check":
            manifest = read_json(args.manifest)
            check = validate_manifest(manifest)
            if not check.ok:
                return _fail_validation(args.command, "manifest", check)
            result = validate_risk_manifest(manifest)
            status = result["status"]
        elif args.command == "select":
            manifest = read_json(args.manifest)
            catalog = read_json(args.catalog)
            manifest_check = validate_manifest(manifest)
            if not manifest_check.ok:
                return _fail_validation(args.command, "manifest", manifest_check)
            catalog_check = validate_catalog(catalog)
            if not catalog_check.ok:
                return _fail_validation(args.command, "catalog", catalog_check)
            result = select_regression_tests(catalog, manifest)
            status = result["status"]
        else:
            spec = read_json(args.spec)
            runs = read_jsonl(args.runs)
            spec_check = validate_agent_spec(spec)
            if not spec_check.ok:
                return _fail_validation(args.command, "agent_spec", spec_check)
            run_exit = _validate_runs_or_fail(args.command, runs)
            if run_exit is not None:
                return run_exit
            result = evaluate_agent_runs(spec, runs)
            status = result["gate"]
        print(write_json(result, args.output))
        return _exit_code(status)
    except (OSError, ValueError, TypeError) as exc:
        print(f"qualityctl: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
