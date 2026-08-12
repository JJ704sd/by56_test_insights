from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, TypedDict

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

try:
    from .view_model import build_quality_report_model, model_summary
except ImportError:  # Direct script execution.
    from view_model import build_quality_report_model, model_summary


UI_RESOURCE_URI = "ui://quality-gatekeeper/report/v1.html"
UI_HTML_PATH = Path(__file__).with_name("report-v1.html")


class DomainSummary(TypedDict):
    name: str
    status: str


class BlockerSummary(TypedDict):
    object_id: str
    domain: str
    status: str
    summary: str | None


class QualityReportModelSummary(TypedDict):
    contract_version: str
    read_only: bool
    decision_authority: str
    compatibility: str
    integrity: str
    change_id: str | None
    gate: str
    release_allowed: bool
    release_basis_status: str
    effective_release_allowed: bool
    domains: list[DomainSummary]
    blockers: list[BlockerSummary]
    versions: dict[str, Any]
    decision_digest: str
    evaluation_fingerprint: str | None


spike_mcp = MCPServer(
    "Quality Gatekeeper Embedded UI Spike",
    version="0.1.0-spike",
    instructions=(
        "This server is a read-only UI spike. The deterministic qualityctl core "
        "is the only release decision authority. The UI cannot approve or release."
    ),
)


@spike_mcp.resource(
    UI_RESOURCE_URI,
    name="quality-evidence-inspector-v1",
    title="Quality Evidence Inspector",
    description="Read-only inline card and fullscreen evidence inspector.",
    mime_type="text/html;profile=mcp-app",
    meta={
        "ui": {
            "visibility": ["app"],
            "prefersBorder": True,
            "csp": {
                "connectDomains": [],
                "resourceDomains": [],
                "frameDomains": [],
            },
        },
        "openai/widgetDescription": (
            "Read-only Quality Gatekeeper evidence inspector. It displays the "
            "deterministic Gate and cannot approve, waive, or release."
        ),
        "openai/widgetPrefersBorder": True,
        "openai/widgetCSP": {
            "connect_domains": [],
            "resource_domains": [],
            "frame_domains": [],
        },
    },
)
def quality_evidence_inspector_resource() -> str:
    return UI_HTML_PATH.read_text(encoding="utf-8")


@spike_mcp.tool(
    name="inspect_release_quality",
    title="Inspect release quality",
    description=(
        "Build a read-only quality evidence report from raw manifest, catalog, "
        "and optional Agent spec/runs. The tool recomputes the deterministic Gate "
        "once; callers cannot supply Gate or domain statuses."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
    meta={
        "ui": {"resourceUri": UI_RESOURCE_URI},
        "openai/outputTemplate": UI_RESOURCE_URI,
        "openai/toolInvocation/invoking": "Inspecting release evidence…",
        "openai/toolInvocation/invoked": "Release evidence inspected.",
    },
)
def inspect_release_quality(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    agent_spec: dict[str, Any] | None = None,
    agent_runs: list[dict[str, Any]] | None = None,
) -> Annotated[CallToolResult, QualityReportModelSummary]:
    report = build_quality_report_model(
        manifest,
        catalog,
        agent_spec=agent_spec,
        agent_runs=agent_runs,
    )
    summary = model_summary(report)
    domains = ", ".join(
        f"{item['name']}={item['status']}" for item in summary["domains"]
    )
    blockers = "; ".join(
        f"{item['domain']} {item['status']}: {item['summary']}"
        for item in summary["blockers"]
    ) or "none"
    if summary["release_basis_status"] == "VERIFIED":
        decision = (
            f"Gate {summary['gate']}; "
            f"raw_release_allowed={str(summary['release_allowed']).lower()}; "
            "release_basis_status=VERIFIED; "
            f"effective_release_allowed={str(summary['effective_release_allowed']).lower()}"
        )
    else:
        decision = (
            "Release basis is not verified and must not authorize release; "
            "release_basis_status=NOT_VERIFIED; effective_release_allowed=false; "
            f"raw_gate={summary['gate']}; "
            f"raw_release_allowed={str(summary['release_allowed']).lower()}"
        )
    text = (
        f"{decision}; domains: {domains}; blockers: {blockers}; "
        f"decision_digest={summary['decision_digest']}. "
        "This result is read-only and cannot approve, waive, or release."
    )
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structuredContent=summary,
        _meta={"qualityReport": report},
    )


def main() -> None:
    spike_mcp.run()


if __name__ == "__main__":
    main()
