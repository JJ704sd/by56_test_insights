"""Risk-driven test intelligence primitives."""

from .agent_eval import evaluate_agent_runs
from .gate import decide_quality_gate
from .risk import RISK_DIMENSIONS, validate_risk_manifest
from .selection import evaluate_automation_candidate, select_regression_tests

__all__ = [
    "RISK_DIMENSIONS",
    "decide_quality_gate",
    "evaluate_agent_runs",
    "evaluate_automation_candidate",
    "select_regression_tests",
    "validate_risk_manifest",
]

__version__ = "0.1.0"
