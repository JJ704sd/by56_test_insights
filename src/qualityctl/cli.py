from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .agent_eval import evaluate_agent_runs
from .evidence import (
    draft_difference,
    freeze_ledger,
    validate_adjudication_record,
    verify_change_bundle,
    write_json_exclusive,
)
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


def _evidence_error(
    command: str,
    code: str,
    message: str,
    *,
    paths: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": command,
        "kind": "evidence_error",
        "code": code,
        "message": message,
        "paths": list(paths or []),
        "errors": list(errors or []),
    }


def _print_evidence_error(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    return 2


def _evidence_exit_code(status: str) -> int:
    if status in {"ELIGIBLE", "FROZEN", "VALID", "DRAFT"}:
        return 0
    if status == "EXCLUDED":
        return 1
    return 2


def _run_evidence_command(args: argparse.Namespace) -> int:
    command = f"evidence {args.evidence_command}"
    input_path = str(args.input)
    output_path = str(args.output)
    try:
        payload = read_json(input_path)
    except FileNotFoundError as exc:
        return _print_evidence_error(
            _evidence_error(
                command,
                "INPUT_NOT_FOUND",
                str(exc),
                paths=[input_path],
            )
        )
    except (OSError, ValueError, TypeError) as exc:
        return _print_evidence_error(
            _evidence_error(
                command,
                "INPUT_READ_ERROR",
                str(exc),
                paths=[input_path],
            )
        )

    try:
        if args.evidence_command == "verify-change":
            result = verify_change_bundle(payload, base_dir=Path(input_path).parent)
        elif args.evidence_command == "draft-diff":
            result = draft_difference(payload, base_dir=Path(input_path).parent)
        elif args.evidence_command == "validate-adjudication":
            result = validate_adjudication_record(payload)
        else:
            result = freeze_ledger(payload)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return _print_evidence_error(
            _evidence_error(
                command,
                "PROCESSING_ERROR",
                str(exc),
                paths=[input_path],
            )
        )

    try:
        write_json_exclusive(result, output_path)
    except FileExistsError as exc:
        return _print_evidence_error(
            _evidence_error(
                command,
                "OUTPUT_EXISTS",
                "output path already exists; exclusive-create refused to overwrite it",
                paths=[output_path],
                errors=[str(exc)],
            )
        )
    except (OSError, TypeError, ValueError) as exc:
        return _print_evidence_error(
            _evidence_error(
                command,
                "OUTPUT_WRITE_ERROR",
                str(exc),
                paths=[output_path],
            )
        )
    return _evidence_exit_code(str(result.get("status", "BLOCKED")))


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

    evidence = subparsers.add_parser(
        "evidence", help="verify and freeze Round 2 pilot evidence"
    )
    evidence_subparsers = evidence.add_subparsers(
        dest="evidence_command", required=True
    )
    for name, help_text in (
        ("verify-change", "verify one Pilot Evidence change bundle"),
        ("draft-diff", "draft a machine-only manual/tool scope difference"),
        ("validate-adjudication", "validate an authorized difference adjudication"),
        ("freeze-ledger", "freeze eligible, excluded, and attempt ledger entries"),
    ):
        child = evidence_subparsers.add_parser(name, help=help_text)
        child.add_argument("input")
        child.add_argument("--output", "-o", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "evidence":
        return _run_evidence_command(args)
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
