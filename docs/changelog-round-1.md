# Changelog: Round 1 — Schema Hardening + CI Baseline

**Date**: 2026-08-12  
**Status**: ✅ Shipped (single PR; all acceptance criteria met)  
**Roadmap slot**: `plugin-developer-guide.md §10` priority 1 + 4 (CI baseline)

## What changed

### New modules

| Path | Purpose |
|---|---|
| `src/qualityctl/schemas/__init__.py` | Versioned schema directory + `schema_path()` helper |
| `src/qualityctl/schemas/v1/manifest.schema.json` | Manifest v1 JSON Schema |
| `src/qualityctl/schemas/v1/catalog.schema.json` | Catalog v1 JSON Schema |
| `src/qualityctl/schemas/v1/agent_spec.schema.json` | AgentSpec v1 JSON Schema |
| `src/qualityctl/schemas/v1/agent_run.schema.json` | AgentRun JSONL row v1 JSON Schema |
| `src/qualityctl/validation.py` | Pydantic v2 models + `validate_manifest / validate_catalog / validate_agent_spec / validate_agent_run` |
| `tests/test_validation.py` | 35 new unit tests covering boundary + structural rules |
| `tests/fixtures/invalid/manifest_missing_schema_version.json` | etc.: five deliberately invalid fixtures |
| `.github/workflows/python-qualityctl.yml` | windows-latest Python 3.11 + pip cache + unittest + MCP smoke |
| `docs/schemas/v1/README.md` | Public field table + error-format spec |

### Modified modules

| Path | Change |
|---|---|
| `pyproject.toml` | Adds `pydantic>=2,<3` as a direct dependency |
| `src/qualityctl/risk.py` | Delegates pure structural checks to `validate_manifest`; keeps signal-to-dimension cross-checks |
| `src/qualityctl/selection.py` | Adds `validate_catalog` boundary guard; removes redundant `isinstance(tests, list)` check |
| `src/qualityctl/agent_eval.py` | Validates spec + each run row up front; aggregates run errors and short-circuits on spec failure |
| `src/qualityctl/mcp_server.py` | Every tool runs `validation.*` before the domain function and raises `ToolError` on structural failure so MCP returns `is_error=true` with a JSON message in the model-visible content |
| `src/qualityctl/cli.py` | Runs `validate_manifest / validate_catalog / validate_agent_spec / validate_agent_run` per subcommand and emits a structured error JSON to stderr with exit code 2 |

### Tests

| Suite | Before | After | Delta |
|---|---|---|---|
| `tests/test_risk.py` | 4 | 4 | unchanged semantics |
| `tests/test_selection.py` | 9 | 9 | unchanged semantics |
| `tests/test_agent_eval.py` | 13 | 13 | one assertion updated to BLOCKED (now stricter) |
| `tests/test_gate.py` | 6 | 6 | unchanged |
| `tests/test_embedded_ui.py` | 26 | 26 | unchanged |
| `tests/test_validation.py` | — | 37 | **new** (+ 2 path-format tests) |
| `tests/test_mcp_registration.py` | — | 3 | **new** (import + schema guards) |
| **Total** | **58** | **98** *(now 100)* | **+40** *(+2 self-check follow-ups)* |

All existing fixtures updated to include `"schema_version": "1.0"`.

## Compatibility matrix

| Aspect | v1.0 (current) | v1.1 (future) | v2 (far future) |
|---|---|---|---|
| Field set | strict (`extra="forbid"`) | only additive | rename / restructure allowed |
| `schema_version` | any non-empty string; compatibility decides | same | bump |
| Read side | Pydantic accepts `v1.x` | accepts both | accepts only v2 |
| Write side | emits `v1.0` | emits `v1.1` | emits `v2` |
| Examples | already v1.0 | bump on introduce | delete on contract |

This round is **expand** phase only. No `v1.1` introduced.

## Acceptance evidence

- All 100 unit tests green (`python -m unittest discover -s tests`); the later self-check additions are included in the 100-test total above.
- `python plugins/quality-gatekeeper/scripts/smoke_test.py` PASS (real stdio MCP session)
- `qualityctl risk-check examples/risk-manifest.json` ⇒ exit 0, `READY`
- `qualityctl risk-check tests/fixtures/invalid/manifest_missing_schema_version.json` ⇒ exit 2, JSON to stderr
- `qualityctl select examples/test-catalog.json examples/risk-manifest.json` ⇒ exit 0, `READY`
- `qualityctl agent-eval examples/agent-cases.json examples/agent-runs.jsonl` ⇒ exit 0, `PASS`
- `.github/workflows/python-qualityctl.yml` validated by `PyYAML.safe_load`

## Risks surfaced and resolved

1. **Strict `schema_version` broke the embedded-UI compatibility test.**  
   Resolution: structural layer accepts any non-empty string; the compatibility
   layer in `embedded_ui/view_model.py` separately detects major version
   mismatch. `UNSUPPORTED_SCHEMA` fixture still produces raw `PASS` and
   `release_basis_status=NOT_VERIFIED`.

2. **Bare-string `manual_review: "pass"` used to mean "missing review" (REVIEW_REQUIRED).**  
   Resolution: now means "malformed" (BLOCKED). The old lenient behavior
   silently hid malformed review records; the new strict behavior surfaces
   them. The corresponding test was updated to assert `BLOCKED`.

3. **CI on `windows-latest` could be slow / flaky for stdio MCP smoke.**  
   Mitigation: 15-minute timeout, pip cache, `concurrency.cancel-in-progress`.
   Fallback (skip smoke, run only unittest) can be added on a follow-up PR if
   needed; current local run completes in <2 s on the same Python 3.14.6.

4. **Pydantic default error paths are LLM-hostile** (`tests.. 5.. automation_fit.. oracle`).  
   Resolution: `validation._format_loc` renders list indices with `[n]` and
   joins keys with `.`, so callers now see `tests[1].automation_fit.oracle`.
   Covered by `tests/test_validation.py::ErrorPathFormatTests`.

5. **MCP tool bodies must not run during import.**  
   Resolution: `tests/test_mcp_registration.py::test_import_does_not_call_tool_functions`
   patches the five tool entry points and reloads the module to assert no call
   happens. Future refactors that introduce an at-decoration side effect will
   trip this guard.

## Breaking change notice (external callers)

Round 1 is **a breaking change for direct callers of the rule core** (anyone
calling `qualityctl.risk.validate_risk_manifest` / `select_regression_tests` /
`evaluate_agent_runs` from their own scripts rather than through the MCP server
or the CLI):

| Before                                 | After (Round 1)                                                          |
|----------------------------------------|--------------------------------------------------------------------------|
| Missing `schema_version` silently OK   | `ValidationResult(ok=False)` with `manifest.schema_version is required`   |
| Extra fields (e.g., typo in key name)  | `extra="forbid"` rejects as `"Extra inputs are not permitted"`           |
| `manual_review: "pass"` (bare string)  | Rejected at structure → `BLOCKED` (was `REVIEW_REQUIRED`)                |
| `version_type: "weekly"`               | Rejected as `Input should be 'daily', 'hotfix' or 'major'`               |
| `min_pass_rate: 1.5` (out of range)    | Rejected at structure (was caught later, with a different error format)  |
| `tests: []`                             | Rejected as `List should have at least 1 item`                           |

Migration path for external callers:

1. Add `"schema_version": "1.0"` to all input payloads (manifest, catalog,
   agent spec). `agent_run` rows do **not** carry `schema_version`; their
   version is bound via the spec's `evaluation_fingerprint`.
2. Remove any unknown fields. If you need a field that the v1 schema does
   not model, propose a v1.1 schema bump in a follow-up PR (do not invent
   fields and rely on `extra="ignore"`).
3. Wrap any direct `validate_risk_manifest(...)` calls with
   `validate_manifest(payload)` first to get the structured error list before
   the domain function reports a less specific `BLOCKED`.
4. Replace any `"manual_review": "pass"` shortcuts with a structured
   `manual_review` object (see `docs/schemas/v1/README.md#agent_run`).

The plugin's MCP server and CLI have already been updated to perform this
validation up front, so LLM callers and shell users are unaffected.

## Self-check follow-up (post-round-1)

After the round-1 self-check surfaced duplicate code in `validation.py` and a
mismatched error format between the CLI and the MCP server, the following
mechanical fixes were applied without changing public semantics:

| # | Finding | Fix |
|---|---|---|
| S1 | `agent_eval.py` had the same `from .validation import …` line twice | Removed the duplicate |
| S2 | `validation.py` imported `SUPPORTED_SCHEMA_VERSIONS` but never used it | Removed the import; clarified that `SUPPORTED_VERSION` is documentation-only and runtime gating is done by the compatibility layer |
| S4 | A 33 KB `test_run.log` debug capture was left at the repo root | Added to `.gitignore` and deleted the file |
| S6 | `cli.py` and `mcp_server.py` each had a private `_validate_each_run` loop with divergent error-formatting | Moved a single `validate_agent_runs()` into `validation.py`; both call sites now share the same helper |
| S7 | `AgentRunV1.output` was typed `Optional` while the validator made it conditionally required | Added a class-level docstring spelling out the pairing rules |

### Behavior change shipped by S6 (visible to CLI consumers)

The CLI's structured validation error JSON now matches the MCP server's
shape. **Before the refactor**, when a single JSONL run row produced
multiple Pydantic errors, the CLI emitted one entry per error:

```json
{
  "ok": false,
  "kind": "structural_validation",
  "input": "agent_run",
  "errors": ["runs[0]: technical_status is required", "runs[0]: case_id is required"]
}
```

**After the refactor**, the same failure collapses into a single entry
with `; `-joined errors (matching the MCP helper):

```json
{
  "ok": false,
  "kind": "structural_validation",
  "input": "agent_run",
  "errors": ["runs[0]: technical_status is required; case_id is required"]
}
```

External scripts that iterate `errors` as a list of strings and look for
`runs[N]:` still work; scripts that previously assumed one entry per
Pydantic error need to split on `; ` if they want per-error granularity.
The new `CliErrorFormatTests` locks this shape.

This is intentional: the CLI and the MCP server now share a single error
path, so any future change to the error format has to be reviewed in one
place.

## Out of scope (deferred)

- Policy signing / registry (B2 from `plugin-developer-guide.md §10`)
- Streamable HTTP deployment (B3)
- Multiple `schema_version` strict whitelist enforcement (currently the
  compatibility layer is the single authority)
- Linux / macOS CI matrix
- Linux MCP stdio smoke (stdio is wired through the bundled CLI; Windows is the
  current supported environment)

## References

- [`docs/schemas/v1/README.md`](schemas/v1/README.md) — full field table
- `docs/plugin-developer-guide.md §10` — productization roadmap
- `pyproject.toml` — declares `pydantic>=2,<3` and `mcp>=2,<3`
- `.github/workflows/python-qualityctl.yml` — pinned action SHAs
