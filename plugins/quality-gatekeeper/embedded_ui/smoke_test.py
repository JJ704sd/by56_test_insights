from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def smoke_test() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[3]
    examples = repository_root / "examples"
    manifest = json.loads((examples / "risk-manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((examples / "test-catalog.json").read_text(encoding="utf-8"))
    spec = json.loads((examples / "agent-cases.json").read_text(encoding="utf-8"))
    runs = [
        json.loads(line)
        for line in (examples / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("server.py"))],
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            inspector = next(tool for tool in tools.tools if tool.name == "inspect_release_quality")
            resources = await session.list_resources()
            resource = next(
                item
                for item in resources.resources
                if str(item.uri) == "ui://quality-gatekeeper/report/v1.html"
            )
            loaded = await session.read_resource(resource.uri)
            called = await session.call_tool(
                "inspect_release_quality",
                arguments={
                    "manifest": manifest,
                    "catalog": catalog,
                    "agent_spec": spec,
                    "agent_runs": runs,
                },
            )
            if called.is_error or called.structured_content.get("gate") != "PASS":
                raise RuntimeError(f"inspect tool failed: {called.content}")
            return {
                "tool": inspector.name,
                "resource": str(resource.uri),
                "mime_type": resource.mime_type,
                "resource_loaded": bool(loaded.contents),
                "gate": called.structured_content["gate"],
                "has_component_meta": bool(called.meta.get("qualityReport")),
            }


def main() -> None:
    print(json.dumps(asyncio.run(smoke_test()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
