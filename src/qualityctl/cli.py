from __future__ import annotations

import argparse
import sys
from typing import Any

from .agent_eval import evaluate_agent_runs
from .io import read_json, read_jsonl, write_json
from .risk import validate_risk_manifest
from .selection import select_regression_tests


def _exit_code(status: str) -> int:
    if status in {"READY", "PASS"}:
        return 0
    if status == "REVIEW_REQUIRED":
        return 1
    return 2


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
            result = validate_risk_manifest(read_json(args.manifest))
            status = result["status"]
        elif args.command == "select":
            result = select_regression_tests(
                read_json(args.catalog), read_json(args.manifest)
            )
            status = result["status"]
        else:
            result = evaluate_agent_runs(read_json(args.spec), read_jsonl(args.runs))
            status = result["gate"]
        print(write_json(result, args.output))
        return _exit_code(status)
    except (OSError, ValueError, TypeError) as exc:
        print(f"qualityctl: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
