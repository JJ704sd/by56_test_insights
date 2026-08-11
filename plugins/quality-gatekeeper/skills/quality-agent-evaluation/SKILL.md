---
name: quality-agent-evaluation
description: Evaluate non-deterministic Agent behavior using frozen cases, repeated runs, deterministic assertions, approved thresholds, uncertainty reporting, and separated failure domains. Use for LLM or Agent release evaluation.
---

# Quality Agent Evaluation

Freeze the dataset, Agent, prompt, model parameters, toolset, knowledge snapshot,
runner, threshold profile, planned run count, and assertions before examining
outputs. Record one evaluation fingerprint in the spec and every run. Do not
tune thresholds after seeing a candidate's results.

Call `evaluate_agent_evidence` with the frozen spec and all collected runs.
Keep runner-invalid attempts, system/technical failures, deterministic behavior
failures, and semantic-review outcomes separate. For high-risk cases, one
effective failure may be a hard fail. Use repeated results and Wilson intervals
to communicate uncertainty; never average a critical failure away.

If required runs, approvals, or semantic reviews are missing, preserve
`BLOCKED` or `REVIEW_REQUIRED` rather than asking the LLM to judge itself.
Manual semantic review must be a structured record with reviewer identity/role,
rubric version, evidence reference, and timestamp; a bare `"pass"` is invalid.
