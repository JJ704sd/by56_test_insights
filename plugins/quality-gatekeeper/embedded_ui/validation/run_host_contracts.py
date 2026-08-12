from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]


def _fixtures() -> dict[str, object]:
    examples = REPOSITORY_ROOT / "examples"
    return {
        "manifest": json.loads((examples / "risk-manifest.json").read_text(encoding="utf-8")),
        "catalog": json.loads((examples / "test-catalog.json").read_text(encoding="utf-8")),
        "agent_spec": json.loads((examples / "agent-cases.json").read_text(encoding="utf-8")),
        "agent_runs": [
            json.loads(line)
            for line in (examples / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ],
    }


async def run() -> dict[str, object]:
    parameters = StdioServerParameters(command=sys.executable, args=[str(HERE / "host_validation_server.py")])
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            resources = await session.list_resources()
            by_uri = {str(item.uri): item for item in resources.resources}
            v1 = await session.read_resource("ui://quality-gatekeeper/report/v1.html")
            v2 = await session.read_resource("ui://quality-gatekeeper/report/v2-host-validation.html")
            called = await session.call_tool("inspect_release_quality", arguments=_fixtures())
            broken_resource_error = None
            try:
                await session.read_resource("ui://quality-gatekeeper/report/missing-host-validation.html")
            except Exception as error:  # The failing resource is the behavior under test.
                broken_resource_error = type(error).__name__
            after_failure = await session.call_tool(
                "inspect_release_quality_broken_resource_host_validation",
                arguments=_fixtures(),
            )
            encoded_model_visible = json.dumps(
                {"content": [item.model_dump() for item in called.content], "structuredContent": called.structured_content},
                ensure_ascii=False,
            )
            canary = called.meta["componentOnlyCanary"]
            return {
                "tools": [tool.name for tool in tools.tools],
                "resources": list(by_uri),
                "v1_loaded": "Quality Evidence Inspector" in v1.contents[0].text,
                "v2_loaded": "RESOURCE_VERSION_V2_HOST_VALIDATION" in v2.contents[0].text,
                "mime_types": {uri: item.mime_type for uri, item in by_uri.items()},
                "gate": called.structured_content["gate"],
                "component_canary_in_meta": canary.startswith("COMPONENT_ONLY_CANARY_"),
                "component_canary_absent_from_model_visible_result": canary not in encoded_model_visible,
                "broken_resource_error": broken_resource_error,
                "tool_after_resource_failure_gate": after_failure.structured_content["gate"],
                "digest_stable_after_resource_failure": (
                    called.structured_content["decision_digest"]
                    == after_failure.structured_content["decision_digest"]
                ),
            }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
