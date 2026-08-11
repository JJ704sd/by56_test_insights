---
name: quality-risk-review
description: Review a software change across business flow, exception, boundary, permission, consistency, dependency, side-effect, and recoverability risks, then validate the structured risk manifest. Use for change impact analysis or pre-regression risk review.
---

# Quality Risk Review

Use source requirements, diffs, contracts, incidents, and dependency evidence
to draft the risk manifest. Think beyond existing test cases.

For every dimension, record exactly one disposition:

- `affected`: include evidence and at least one observable scenario.
- `not_affected` or `not_applicable`: include a concrete reason.
- `unknown`: include an owner and resolution date.

Cover business flow, exception paths, boundaries, permissions, data
consistency, upstream/downstream behavior, side effects, and recoverability.
Also require an auditable Agent-evaluation applicability decision with an owner
and evidence reference; the LLM must not create its own exemption.
Call `validate_change_risks`. Treat `READY`, `REVIEW_REQUIRED`, and `BLOCKED` as
authoritative; do not fill missing facts with plausible guesses.
