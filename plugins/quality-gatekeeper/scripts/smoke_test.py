from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


EXPECTED_TOOLS = {
    "validate_change_risks",
    "select_regression_scope",
    "evaluate_agent_evidence",
    "assess_automation_roi",
    "decide_release_gate",
}


async def smoke_test() -> dict[str, object]:
    repository_root = Path(__file__).resolve().parents[3]
    manifest = json.loads(
        (repository_root / "examples" / "risk-manifest.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (repository_root / "examples" / "test-catalog.json").read_text(encoding="utf-8")
    )
    agent_spec = json.loads(
        (repository_root / "examples" / "agent-cases.json").read_text(encoding="utf-8")
    )
    agent_runs = [
        json.loads(line)
        for line in (repository_root / "examples" / "agent-runs.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    parameters = StdioServerParameters(command="qualityctl-mcp", args=[])
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            missing = sorted(EXPECTED_TOOLS - names)
            if missing:
                raise RuntimeError(f"missing MCP tools: {missing}")
            called = await session.call_tool(
                "assess_automation_roi",
                arguments={
                    "candidate": {
                        "id": "SMOKE-ROI",
                        "automated": False,
                        "automation_fit": {
                            "stable": True,
                            "repeatable": True,
                            "oracle": "state",
                            "runs_per_month": 10,
                            "manual_minutes": 20,
                            "residual_review_minutes_per_run": 2,
                            "maintenance_minutes_per_month": 20,
                            "flaky_investigation_minutes_per_month": 5,
                            "execution_cost_minutes_equivalent_per_month": 5,
                            "data_maintenance_minutes_per_month": 0,
                            "setup_minutes": 180,
                            "data_basis": "ESTIMATED",
                            "observation_window_days": 30,
                        },
                    },
                    "policy": {
                        "version": "roi-v1",
                        "source_ref": "approved://roi-v1",
                        "approval_status": "APPROVED",
                        "max_payback_months": 3,
                        "min_monthly_net_minutes": 30,
                    },
                },
            )
            if called.is_error:
                raise RuntimeError(f"tool call failed: {called.content}")
            gated = await session.call_tool(
                "decide_release_gate",
                arguments={
                    "manifest": manifest,
                    "catalog": catalog,
                    "agent_spec": agent_spec,
                    "agent_runs": agent_runs,
                },
            )
            if gated.is_error or not gated.structured_content:
                raise RuntimeError(f"gate call failed: {gated.content}")
            if gated.structured_content.get("gate") != "PASS":
                raise RuntimeError(
                    f"example release gate is not PASS: {gated.structured_content}"
                )
            return {
                "tools": sorted(names),
                "roi_call": "PASS",
                "release_gate_call": "PASS",
            }


def main() -> None:
    print(json.dumps(asyncio.run(smoke_test()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
