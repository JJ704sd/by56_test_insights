---
name: quality-automation-roi
description: Assess whether a manual test or quality check is a worthwhile automation candidate based on stability, repeatability, oracle strength, frequency, setup cost, maintenance cost, and payback. Use for automation backlogs and investment decisions.
---

# Quality Automation ROI

Call `assess_automation_roi` only with a versioned approved ROI policy and after
collecting stability, repeatability, oracle type, data basis/window, monthly
frequency, manual time, setup, maintenance, residual review, flaky investigation,
runtime/API cost equivalent, and data-maintenance cost.

Prioritize high-frequency, stable, repeated, expensive checks with deterministic
oracles. Preserve these decisions:

- `CANDIDATE`: net-positive, within approved payback, and technically suitable.
- `DO_NOT_AUTOMATE_YET`: a suitability or economic condition is not met.
- `INSUFFICIENT_DATA`: gather missing cost or fit data.
- `KEEP`: existing automation remains worthwhile.
- `REPAIR_OR_RETIRE`: existing automation no longer clears the policy.

Do not recommend automation merely because a tool could be written. Rank valid
candidates by monthly minutes saved and payback period, then state assumptions.
