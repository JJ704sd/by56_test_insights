---
name: quality-gatekeeper
description: Coordinate evidence-driven risk review, regression selection, Agent evaluation, automation ROI, and a final release gate. Use for release readiness, change impact testing, regression planning, or end-to-end QA reviews that span multiple quality concerns.
---

# Quality Gatekeeper

Act as the coordinator, not the quality oracle. LLM reasoning may propose risks,
scenarios, mappings, and explanations. Only tool outputs determine gate status.

## Workflow

1. Establish the change identifier, release type, changed components, known
   dependencies, and source evidence. Require the manifest's audited
   `agent_evaluation` policy (`required`, `approved_by`, `evidence_ref`). The
   coordinator must not decide Agent applicability itself.
2. Apply the `quality-risk-review` role and call `validate_change_risks`.
3. When the risk status is not `BLOCKED`, apply `quality-regression-planning`
   and call `select_regression_scope`.
4. For Agent or other non-deterministic behavior, apply
   `quality-agent-evaluation` and call `evaluate_agent_evidence`. Otherwise add
   a required `NOT_APPLICABLE` Agent check with the reason in the evidence.
5. For selected manual tests, apply `quality-automation-roi`. Assess only stable,
   repeated work with an observable oracle; do not turn ROI review into a
   release blocker unless the project explicitly requires it.
6. Call `decide_release_gate` with the raw manifest, catalog, and raw Agent
   spec/runs when the manifest requires them. The tool recomputes every required
   domain; never pass caller-authored statuses or evidence references.

## Gate invariants

- Never paraphrase `FAIL`, `BLOCKED`, or `REVIEW_REQUIRED` as approval.
- Never use majority vote, confidence language, or an assistant opinion to
  override a deterministic check.
- A tool error or missing required evidence is `BLOCKED`, not an assumed pass.
- Human review may resolve evidence or approve a versioned threshold profile;
  it must not silently rewrite historical tool output.

## Response

Return the final gate first, then blocking checks, evidence references,
selected regression scope, Agent evaluation summary when applicable, and ROI
candidates. End with the smallest concrete action needed to unblock the gate.
