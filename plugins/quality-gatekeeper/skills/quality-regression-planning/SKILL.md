---
name: quality-regression-planning
description: Select a minimum effective regression set from a validated change-risk manifest and test catalog, with traceable inclusion reasons and explicit coverage gaps. Use for daily, hotfix, or major release regression planning.
---

# Quality Regression Planning

Require a risk manifest and a catalog whose tests map to components, risk
dimensions, signals, suites, and historical escapes. Call
`select_regression_scope` with both objects.

Do not add or remove tests merely to make the list look balanced. Report:

- selected tests and their rule-based reasons;
- excluded tests and the non-match reason;
- uncovered affected dimensions;
- manual selected tests that need separate ROI review.

`BLOCKED` means invalid inputs. `REVIEW_REQUIRED` means evidence or coverage is
incomplete. Only `READY` can feed an automatic passing release check.
