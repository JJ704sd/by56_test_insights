from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations


EMBEDDED_UI = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = EMBEDDED_UI.parent
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from embedded_ui.server import (  # noqa: E402
    QualityReportModelSummary,
    UI_RESOURCE_URI,
    inspect_release_quality as inspect_base,
)


UI_RESOURCE_V2_URI = "ui://quality-gatekeeper/report/v2-host-validation.html"
BROKEN_RESOURCE_URI = "ui://quality-gatekeeper/report/missing-host-validation.html"
UI_HTML_PATH = EMBEDDED_UI / "report-v1.html"
UI_HTML_V2_PATH = EMBEDDED_UI / "validation" / "report-v2-host-validation.html"
COMPONENT_ONLY_CANARY = f"COMPONENT_ONLY_CANARY_{secrets.token_hex(8)}"

RESOURCE_META = {
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
        "Host-validation-only Quality Gatekeeper evidence inspector. Read-only; "
        "it cannot approve, waive, or release."
    ),
    "openai/widgetPrefersBorder": True,
    "openai/widgetCSP": {
        "connect_domains": [],
        "resource_domains": [],
        "frame_domains": [],
    },
}

TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

validation_mcp = MCPServer(
    "Quality Gatekeeper UI Host Validation",
    version="0.1.0-host-validation",
    instructions=(
        "This isolated server is only for host validation with synthetic fixtures. "
        "qualityctl.gate.decide_quality_gate remains the only release authority."
    ),
)


def _tool_result(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
    agent_spec: dict[str, Any] | None,
    agent_runs: list[dict[str, Any]] | None,
) -> CallToolResult:
    result = inspect_base(manifest, catalog, agent_spec, agent_runs)
    return CallToolResult(
        content=result.content,
        structuredContent=result.structured_content,
        _meta={
            "qualityReport": result.meta["qualityReport"],
            "componentOnlyCanary": COMPONENT_ONLY_CANARY,
        },
    )


def _register_resource(uri: str, name: str, path: Path) -> None:
    @validation_mcp.resource(
        uri,
        name=name,
        title="Quality Evidence Inspector host validation",
        description="Isolated, offline MCP Apps host-validation resource.",
        mime_type="text/html;profile=mcp-app",
        meta=RESOURCE_META,
    )
    def resource() -> str:
        return path.read_text(encoding="utf-8")


_register_resource(UI_RESOURCE_URI, "quality-evidence-inspector-v1-host-validation", UI_HTML_PATH)
_register_resource(UI_RESOURCE_V2_URI, "quality-evidence-inspector-v2-host-validation", UI_HTML_V2_PATH)
_register_resource(BROKEN_RESOURCE_URI, "quality-evidence-inspector-broken-host-validation", EMBEDDED_UI / "validation" / "does-not-exist.html")


def _register_inspector(name: str, title: str, resource_uri: str) -> None:
    @validation_mcp.tool(
        name=name,
        title=title,
        description=(
            "Host-validation-only read-only inspector. It accepts raw manifest, catalog, "
            "optional Agent spec/runs, and recomputes the deterministic Gate once."
        ),
        annotations=TOOL_ANNOTATIONS,
        meta={
            "ui": {"resourceUri": resource_uri},
            "openai/outputTemplate": resource_uri,
            "openai/toolInvocation/invoking": "Inspecting synthetic release evidence…",
            "openai/toolInvocation/invoked": "Synthetic release evidence inspected.",
        },
    )
    def inspector(
        manifest: dict[str, Any],
        catalog: dict[str, Any],
        agent_spec: dict[str, Any] | None = None,
        agent_runs: list[dict[str, Any]] | None = None,
    ) -> Annotated[CallToolResult, QualityReportModelSummary]:
        return _tool_result(manifest, catalog, agent_spec, agent_runs)


_register_inspector("inspect_release_quality", "Inspect release quality (host validation)", UI_RESOURCE_URI)
_register_inspector("inspect_release_quality_v2_host_validation", "Inspect with v2 resource (host validation)", UI_RESOURCE_V2_URI)
_register_inspector("inspect_release_quality_broken_resource_host_validation", "Inspect with missing resource (host validation)", BROKEN_RESOURCE_URI)


def main() -> None:
    validation_mcp.run()


if __name__ == "__main__":
    main()
