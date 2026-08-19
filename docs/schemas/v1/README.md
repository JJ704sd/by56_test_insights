# qualityctl input schemas v1.0

Version 1.0 is the first **structurally enforced** input contract. Before this
round, structural checks lived as ad-hoc Python guards in `risk.py`,
`selection.py`, and `agent_eval.py`; callers could submit malformed payloads and
either crash the tool or silently get a half-passing gate. Round 1 closes that
gap by introducing Pydantic v2 models in `qualityctl.validation` plus matching
JSON Schema files in `qualityctl/schemas/v1/`.

## Scope

Three required inputs and one per-run row:

| Input kind    | Where it is consumed                                       | Validator                  | Schema file                                            |
|---------------|------------------------------------------------------------|----------------------------|--------------------------------------------------------|
| `manifest`    | `validate_change_risks`, `decide_release_gate`             | `validate_manifest`        | [`manifest.schema.json`](./manifest.schema.json)       |
| `catalog`     | `select_regression_scope`, `decide_release_gate`           | `validate_catalog`         | [`catalog.schema.json`](./catalog.schema.json)         |
| `agent_spec`  | `evaluate_agent_evidence`, `decide_release_gate`           | `validate_agent_spec`      | [`agent_spec.schema.json`](./agent_spec.schema.json)   |
| `agent_run`   | JSONL rows for `evaluate_agent_evidence`                   | `validate_agent_run`       | [`agent_run.schema.json`](./agent_run.schema.json)     |

## Layering: structural vs semantic vs compatibility

| Concern              | Layer                          | What it does                                                                 | Failure mode                                       |
|----------------------|--------------------------------|------------------------------------------------------------------------------|----------------------------------------------------|
| **Structural**       | `qualityctl.validation`        | Types, enums, presence, length, regex, cross-field rules on a single entry   | `ValidationResult(ok=False, errors=[...])`         |
| **Semantic**         | `risk.py / selection.py / agent_eval.py` | Signal-to-dimension cross-checks, regression coverage, fingerprint matching, Wilson intervals, gate roll-up | `status = BLOCKED / REVIEW_REQUIRED / FAIL`        |
| **Compatibility**    | `embedded_ui/view_model.py`    | Reports whether the input's `schema_version` is supported by the current rule core | `compatibility.status = LEGACY_UNVERIFIED / UNSUPPORTED / DEGRADED / VERIFIED` |

Unknown major `schema_version` values (e.g., `"2.0"`) **pass** structural
validation but are flagged `UNSUPPORTED` by the compatibility layer, so the
`release_basis_status` becomes `NOT_VERIFIED` and `effective_release_allowed`
becomes `false` even when the raw gate says `PASS`. This preserves the
"structurally valid → gate still computes; compatibility decides release"
separation.

## Required fields by input

### `manifest`

| Field                   | Type                                       | Notes                                                 |
|-------------------------|--------------------------------------------|-------------------------------------------------------|
| `schema_version`        | string                                     | required, any non-empty string; compatibility decides |
| `change_id`             | string                                     | non-empty                                             |
| `version_type`          | `daily` \| `hotfix` \| `major`             | enum                                                 |
| `changed_components`    | string[]                                   | at least one, no blanks                              |
| `agent_evaluation`      | `{required: bool, approved_by: str, evidence_ref: str}` | all three fields required                |
| `dependencies`          | `{upstream: string[], downstream: string[]}`| both arrays required                                  |
| `risk_signals`          | string[]                                   | may be empty                                          |
| `dimensions`            | object with all 8 keys                     | each entry must satisfy `status`-driven cross-field rules |

### `dimension_entry` (per dimension)

| `status`          | Required extra fields                                            |
|-------------------|------------------------------------------------------------------|
| `affected`        | `evidence: string`, `scenarios: string[]` (at least one)         |
| `not_affected`    | `reason: string`                                                 |
| `not_applicable`  | `reason: string`                                                 |
| `unknown`         | `owner: string`, `resolve_by: string`                            |

`extra` fields are rejected with `extra="forbid"`. Use the semantic layer in
`risk.py` for the dimension-signal cross-check; that is not expressed here.

### `catalog`

| Field              | Type                                       | Notes                                                |
|--------------------|--------------------------------------------|------------------------------------------------------|
| `schema_version`   | string                                     | required                                             |
| `catalog_version`  | string \| null                             | optional version label                               |
| `automation_policy`| object \| null                             | see below; null means no ROI gating                 |
| `tests`            | object[]                                   | at least one; `id` must be unique                   |

`automation_policy` requires `version`, `source_ref`, `approval_status ∈
{APPROVED, UNAPPROVED}`, `max_payback_months > 0`, `min_monthly_net_minutes ≥ 0`.

`tests[].automation_fit` (when present) requires the full numeric cost matrix
described in `selection.py`. `oracle` is intentionally a free-form string; the
semantic layer rejects non-deterministic oracles (`!= exact | schema | rule |
state | contract`).

### `agent_spec`

| Field                  | Type                                                              |
|------------------------|-------------------------------------------------------------------|
| `schema_version`       | string (required)                                                 |
| `agent_version`        | string (required)                                                 |
| `dataset_version`      | string (required)                                                 |
| `evaluation_fingerprint` | string (required)                                                |
| `execution_profile`    | `{prompt_version, model_id, model_parameters, toolset_version, knowledge_snapshot, runner_version}` |
| `threshold_profile`    | `{version, source_ref, approval_status ∈ {APPROVED, UNAPPROVED}}`  |
| `cases`                | `case_entry[]` (at least one; unique `id`)                        |

`assertions[]` is a tagged union with `type ∈ {required, equals, one_of,
matches, number}`. The `number` variant requires exactly one of
`absolute_tolerance` or `relative_tolerance`.

### `agent_run` (per JSONL row)

| Field                   | Type                                                                |
|-------------------------|---------------------------------------------------------------------|
| `case_id`               | string                                                              |
| `run_id`                | string                                                              |
| `evaluation_fingerprint` | string                                                             |
| `technical_status`      | `ok` \| `runner_invalid` \| `technical_failure`                    |
| `output`                | object (required iff `technical_status == "ok"`)                    |
| `error`                 | string (required iff `technical_status != "ok"`)                    |
| `manual_review`         | `{reviewer_id, reviewer_role, rubric_version, evidence_ref, reviewed_at, status ∈ {pass, fail}}` \| null |

Bare strings (e.g., `manual_review: "pass"`) are rejected at the boundary as
malformed; the evaluation becomes `BLOCKED` rather than quietly promoting to
"missing review".

## Error format

Every validation failure uses one stable shape so LLM callers can branch on it
without parsing free-form text:

```json
{
  "ok": false,
  "kind": "structural_validation",
  "input": "manifest",
  "errors": [
    "manifest.schema_version is required",
    "dimensions.business_flow: status 'affected' requires non-empty evidence, scenarios"
  ]
}
```

- MCP tools raise `mcp.server.mcpserver.exceptions.ToolError` with this JSON
  as the message text, so the failure reaches the model verbatim as
  `CallToolResult(is_error=true, content=[TextContent(...)])`.
- The CLI prints the same JSON to stderr and exits with code `2`.

## Round 2 Pilot Evidence v1

`qualityctl.evidence` adds an outer, append-only evidence contract without
changing the four Round 1 input schemas. The pinned resources are
[`pilot-evidence-bundle.schema.json`](../../../src/qualityctl/schemas/v1/pilot-evidence-bundle.schema.json),
[`difference-draft.schema.json`](../../../src/qualityctl/schemas/v1/difference-draft.schema.json),
[`adjudication.schema.json`](../../../src/qualityctl/schemas/v1/adjudication.schema.json),
[`change-evidence-report.schema.json`](../../../src/qualityctl/schemas/v1/change-evidence-report.schema.json),
and [`evidence-ledger.schema.json`](../../../src/qualityctl/schemas/v1/evidence-ledger.schema.json).

The Pilot reader accepts only the pinned `1.0` matrix, recomputes canonical
SHA-256 digests, rejects stale output attached to failed Agent runs, and writes
new reports with exclusive-create. Every Pilot output has
`formal_release_effect: "NONE"`; a raw Gate `release_allowed: true` never
becomes a formal release action. During the current `BLOCKED_BY_R2_G0` phase,
only an explicit `FIXTURE_DRY_RUN` bundle may be verified.

### P1b frozen iteration contracts

P1b adds strict, append-only-derived contracts for the local fixture path:

| Contract | Pydantic seam | JSON Schema |
| --- | --- | --- |
| `change-evidence-report@1.0` | `validate_change_evidence_report` | [`change-evidence-report.schema.json`](../../../src/qualityctl/schemas/v1/change-evidence-report.schema.json) |
| `evidence-ledger@1.0` | `validate_evidence_ledger` | [`evidence-ledger.schema.json`](../../../src/qualityctl/schemas/v1/evidence-ledger.schema.json) |
| `iteration-index@1.0` | `validate_iteration_index` | [`iteration-index.schema.json`](../../../src/qualityctl/schemas/v1/iteration-index.schema.json) |
| `iteration-summary@1.0` | `validate_iteration_summary` | [`iteration-summary.schema.json`](../../../src/qualityctl/schemas/v1/iteration-summary.schema.json) |

All four contracts reject unknown fields at their nested object boundaries.
The iteration core verifies local bytes digests and base-directory containment,
recomputes change eligibility from the bundle, and only accepts the exact P1b
fixture matrix (`qualityctl 0.1.0`, baseline commit, schema `1.0`,
`canonical-json@1.0`, and the pinned fixture policy versions). It treats
`PENDING`/`UNKNOWN` attestations as non-success and keeps
`OBSERVED`/`NOT_OBSERVED`/`NOT_COMPUTABLE`/`BLOCKED` distinct. A valid fixture
summary is not a release gate and never creates a business denominator.

Pilot raw `manifest`、`catalog`、`agent_spec` 和 JSONL `agent_runs` 可以保持 inline，或使用
完整的 `{path, media_type, size, digest}` artifact ref。四类 ref 共享同一个 local resolver：
拒绝绝对路径、`..` 和解析后逃出 `base_dir` 的 symlink/junction，在解析 JSON/JSONL 前核对
stat size、实际 bytes 长度、media type 和 SHA-256。manual/tool scope 的重复 test ID 返回
`BLOCKED/DUPLICATE_SCOPE_ID`，不会再由 map 静默保留最后一项。JSON Schema parity 依赖由
`.[test]` extra 提供，不增加 production runtime dependency。

## References

- `docs/plugin-developer-guide.md §10` — productization roadmap
- `docs/changelog-round-1.md` — what changed in this round
