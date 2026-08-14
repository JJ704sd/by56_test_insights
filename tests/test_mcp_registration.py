"""Guard tests around MCP server registration.

These tests verify that the production MCP server is wired correctly and that
``import qualityctl.mcp_server`` does not silently invoke the tool
functions. If a future refactor starts running tool bodies at import time
(e.g., by calling them during signature introspection), the original input
validation would raise ``ToolError`` and break every importer — including
LLM hosts that import the module for tool discovery only.
"""

from __future__ import annotations

import asyncio
import importlib
import unittest
from unittest import mock

from qualityctl.mcp_server import mcp as production_mcp


EXPECTED_TOOL_NAMES = {
    "validate_change_risks",
    "select_regression_scope",
    "evaluate_agent_evidence",
    "assess_automation_roi",
    "decide_release_gate",
}


class McpRegistrationTests(unittest.TestCase):
    def test_import_does_not_call_tool_functions(self) -> None:
        """Importing the module must not trigger any tool body execution.

        The production tools raise ``ToolError`` on structurally invalid input.
        If a future change causes the MCP SDK to invoke them at decoration
        time, an empty or stale argument set would raise immediately and break
        every caller. We patch the five tool entry points to record calls and
        assert none happen during a fresh import.
        """

        calls: list[tuple[str, tuple, dict]] = []

        def make_recorder(name: str):
            def record(*args, **kwargs):
                calls.append((name, args, kwargs))
                return {"status": "READY", "errors": []}

            return record

        # Patch the underlying functions in the module namespace so the
        # decoration-layer cannot short-circuit the call.
        import qualityctl.mcp_server as module

        patches = []
        for name in EXPECTED_TOOL_NAMES:
            patcher = mock.patch.object(module, name, make_recorder(name))
            patches.append(patcher)

        # Force a re-import to verify registration alone does not invoke.
        for patcher in patches:
            patcher.start()
        try:
            importlib.reload(module)
        finally:
            for patcher in patches:
                patcher.stop()

        self.assertEqual(
            calls,
            [],
            f"import-time tool invocations detected: {[c[0] for c in calls]}",
        )

    def test_five_tools_are_registered(self) -> None:
        async def names() -> list[str]:
            tools = await production_mcp.list_tools()
            return [tool.name for tool in tools]

        listed = asyncio.run(names())
        self.assertEqual(set(listed), EXPECTED_TOOL_NAMES)

    def test_each_tool_carries_input_schema(self) -> None:
        async def tools():
            return await production_mcp.list_tools()

        for tool in asyncio.run(tools()):
            self.assertTrue(tool.input_schema, f"{tool.name} has empty input_schema")
            self.assertIn(
                "properties",
                tool.input_schema,
                f"{tool.name} input_schema missing properties",
            )


if __name__ == "__main__":
    unittest.main()