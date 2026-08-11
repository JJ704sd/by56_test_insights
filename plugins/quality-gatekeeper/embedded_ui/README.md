# Quality Evidence Inspector spike

This directory is deliberately isolated from `src/qualityctl`: it imports the
deterministic core but does not change risk, selection, Agent-evaluation, ROI,
or Gate rules.

Contents:

- `view_model.py`: one-call, read-only Report View Model adapter.
- `server.py`: Python MCP SDK resource and `inspect_release_quality` spike.
- `report.ts`: Vanilla TypeScript/DOM source (browser-native syntax only).
- `report-shell.html` and `build_resource.py`: offline resource shell and build step.
- `report-v1.html`: generated, versioned MCP Apps UI resource.
- `generate_harness.py`: derives PASS / FAIL / BLOCKED / REVIEW_REQUIRED from
  existing examples and generates a standalone `harness.html`.
- `smoke_test.py`: exercises tool metadata, the UI resource, and the PASS call
  over a real stdio MCP session.

Run the harness generator from the repository root:

```powershell
python plugins/quality-gatekeeper/embedded_ui/build_resource.py
python plugins/quality-gatekeeper/embedded_ui/generate_harness.py
```

Run the isolated stdio MCP server:

```powershell
python plugins/quality-gatekeeper/embedded_ui/server.py
```

The production plugin continues to launch `qualityctl-mcp`, so its existing
five headless tools are unchanged. This spike is not installed or submitted as
a production UI.
