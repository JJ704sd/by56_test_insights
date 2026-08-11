# Quality Gatekeeper plugin

This repository-local plugin connects an LLM host to deterministic quality
gate tools through MCP. The LLM may discover risks and explain results; it may
not convert `FAIL`, `BLOCKED`, or `REVIEW_REQUIRED` into `PASS`.

Architecture, data contracts, extension rules, and production boundaries are
documented in `../../docs/plugin-developer-guide.md`.

## Runtime setup

From the repository root, install the Python package and official MCP SDK:

```powershell
python -m pip install -e .
```

The plugin launches the installed `qualityctl-mcp` entry point over stdio.
Verify the real MCP handshake, tool discovery, and one tool call with:

```powershell
python plugins/quality-gatekeeper/scripts/smoke_test.py
```

## Contents

- Four focused assistant skills: risk review, regression planning, Agent
  evaluation, and automation ROI.
- One orchestration skill that gathers their evidence and calls the final gate.
- Five MCP tools backed by the tested `qualityctl` rule core.

This scaffold is intentionally repo-local and is not added to a personal
marketplace automatically. Remote/team distribution is a later packaging step.
