from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from .agent_eval import evaluate_agent_runs
from .gate import decide_quality_gate
from .risk import validate_risk_manifest
from .selection import evaluate_automation_candidate, select_regression_tests


mcp = MCPServer(
    "Quality Gatekeeper",
    version="0.1.0",
    instructions=(
        "Use these deterministic tools to verify LLM-proposed quality evidence. "
        "Never reinterpret BLOCKED, FAIL, or REVIEW_REQUIRED as PASS. "
        "Do not invent missing evidence references."
    ),
)


@mcp.tool()
def validate_change_risks(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate change risk coverage across business and technical dimensions.

    Call after an LLM or human drafts a risk manifest. READY means every
    required dimension has an explicit, evidenced disposition.
    """

    return validate_risk_manifest(manifest)


@mcp.tool()
def select_regression_scope(
    catalog: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    """Select a traceable regression set and report uncovered risk dimensions."""

    return select_regression_tests(catalog, manifest)


@mcp.tool()
def evaluate_agent_evidence(
    spec: dict[str, Any], runs: list[dict[str, Any]]
) -> dict[str, Any]:
    """Evaluate repeated non-deterministic Agent runs against frozen rules.

    Technical failures, invalid runner attempts, deterministic assertion
    failures, and missing semantic reviews remain separate failure domains.
    """

    return evaluate_agent_runs(spec, runs)


@mcp.tool()
def assess_automation_roi(
    candidate: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    """Decide whether a stable repeated manual check is worth automating now."""

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
    advisory and intentionally excluded from the release decision.
    """

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
