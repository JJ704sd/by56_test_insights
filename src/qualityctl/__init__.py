"""Risk-driven test intelligence primitives."""

from .agent_eval import evaluate_agent_runs
from .evidence import (
    FORMAL_RELEASE_EFFECT,
    canonical_digest,
    compare_scopes,
    freeze_ledger,
    validate_catalog_readiness,
    verify_change_bundle,
)
from .gate import decide_quality_gate
from .risk import RISK_DIMENSIONS, validate_risk_manifest
from .selection import evaluate_automation_candidate, select_regression_tests

__all__ = [
    "RISK_DIMENSIONS",
    "FORMAL_RELEASE_EFFECT",
    "canonical_digest",
    "compare_scopes",
    "decide_quality_gate",
    "evaluate_agent_runs",
    "evaluate_automation_candidate",
    "freeze_ledger",
    "select_regression_tests",
    "validate_catalog_readiness",
    "validate_risk_manifest",
    "verify_change_bundle",
]

__version__ = "0.1.0"
