from __future__ import annotations

import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]


def _fixtures() -> dict[str, Any]:
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


def _fixture_variants() -> dict[str, dict[str, Any]]:
    base = _fixtures()
    variants: dict[str, dict[str, Any]] = {}

    variants["PASS"] = deepcopy(base)
    variants["FAIL"] = deepcopy(base)
    variants["FAIL"]["agent_runs"][0]["output"]["pieces"] = 999
    variants["BLOCKED"] = deepcopy(base)
    variants["BLOCKED"]["agent_runs"].pop(2)
    variants["REVIEW_REQUIRED"] = deepcopy(base)
    for run in variants["REVIEW_REQUIRED"]["agent_runs"]:
        if run["case_id"] == "AGENT-RECOMMEND-001":
            run.pop("manual_review", None)
            break
    variants["UNSUPPORTED_SCHEMA"] = deepcopy(base)
    variants["UNSUPPORTED_SCHEMA"]["manifest"]["schema_version"] = "2.0"
    return variants


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
            called_by_state = {
                state: await session.call_tool("inspect_release_quality", arguments=arguments)
                for state, arguments in _fixture_variants().items()
            }
            expected_gates = {
                "PASS": "PASS",
                "FAIL": "FAIL",
                "BLOCKED": "BLOCKED",
                "REVIEW_REQUIRED": "REVIEW_REQUIRED",
                "UNSUPPORTED_SCHEMA": "PASS",
            }
            state_results = {}
            for state, called in called_by_state.items():
                summary = called.structured_content
                if called.is_error or not summary or not called.content or not called.meta:
                    raise RuntimeError(f"{state} did not return the complete MCP result envelope")
                if summary["gate"] != expected_gates[state]:
                    raise RuntimeError(f"{state} returned unexpected Gate: {summary['gate']}")
                if state == "UNSUPPORTED_SCHEMA" and (
                    summary["release_basis_status"] != "NOT_VERIFIED"
                    or summary["effective_release_allowed"] is not False
                ):
                    raise RuntimeError("unsupported schema did not fail closed")
                state_results[state] = {
                    "gate": summary["gate"],
                    "release_basis_status": summary["release_basis_status"],
                    "effective_release_allowed": summary["effective_release_allowed"],
                    "content_readable": bool(called.content[0].text),
                }
            called = called_by_state["PASS"]
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
            if (
                after_failure.is_error
                or not after_failure.content
                or not after_failure.structured_content
                or not after_failure.meta
            ):
                raise RuntimeError("tool result envelope was damaged by resource failure")
            return {
                "tools": [tool.name for tool in tools.tools],
                "resources": list(by_uri),
                "v1_loaded": "Quality Evidence Inspector" in v1.contents[0].text,
                "v2_loaded": "RESOURCE_VERSION_V2_HOST_VALIDATION" in v2.contents[0].text,
                "mime_types": {uri: item.mime_type for uri, item in by_uri.items()},
                "gate": called.structured_content["gate"],
                "state_results": state_results,
                "component_canary_in_meta": canary.startswith("COMPONENT_ONLY_CANARY_"),
                "component_canary_absent_from_model_visible_result": canary not in encoded_model_visible,
                "broken_resource_error": broken_resource_error,
                "tool_after_resource_failure_gate": after_failure.structured_content["gate"],
                "tool_after_resource_failure_content_readable": bool(after_failure.content[0].text),
                "tool_after_resource_failure_meta_complete": "qualityReport" in after_failure.meta,
                "digest_stable_after_resource_failure": (
                    called.structured_content["decision_digest"]
                    == after_failure.structured_content["decision_digest"]
                ),
            }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run()), ensure_ascii=False, indent=2))
