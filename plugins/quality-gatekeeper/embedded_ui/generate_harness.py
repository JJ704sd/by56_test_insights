from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from .view_model import build_quality_report_model
except ImportError:  # Direct script execution.
    from view_model import build_quality_report_model


def _load_inputs(repository_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    examples = repository_root / "examples"
    manifest = json.loads((examples / "risk-manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((examples / "test-catalog.json").read_text(encoding="utf-8"))
    spec = json.loads((examples / "agent-cases.json").read_text(encoding="utf-8"))
    runs = [
        json.loads(line)
        for line in (examples / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return manifest, catalog, spec, runs


def build_fixtures(repository_root: Path) -> dict[str, dict[str, Any]]:
    manifest, catalog, spec, runs = _load_inputs(repository_root)

    fail_runs = deepcopy(runs)
    fail_runs[0]["output"]["pieces"] = 999

    blocked_runs = deepcopy(runs)
    blocked_runs.pop(2)

    review_runs = deepcopy(runs)
    for run in review_runs:
        if run["case_id"] == "AGENT-RECOMMEND-001":
            run.pop("manual_review", None)
            break

    variants = {
        "PASS": runs,
        "FAIL": fail_runs,
        "BLOCKED": blocked_runs,
        "REVIEW_REQUIRED": review_runs,
    }
    return {
        name: build_quality_report_model(
            manifest,
            catalog,
            agent_spec=spec,
            agent_runs=variant_runs,
        )
        for name, variant_runs in variants.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the standalone UI harness")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("harness.html"),
    )
    args = parser.parse_args()
    template = Path(__file__).with_name("report-v1.html").read_text(encoding="utf-8")
    fixtures_json = json.dumps(
        build_fixtures(args.repository_root), ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    harness_data = f"<script>window.__QUALITY_HARNESS_FIXTURES__={fixtures_json};</script>"
    rendered = template.replace("<!-- QUALITY_HARNESS_DATA -->", harness_data)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
