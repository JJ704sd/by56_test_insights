"""Versioned JSON Schema definitions for qualityctl inputs.

The Pydantic models in ``qualityctl.validation`` are the authoritative runtime
validators. The JSON Schema files in this package mirror them for documentation
and interop (e.g., editor autocomplete, third-party validation). When the
Pydantic models change, the matching JSON Schema file must be updated in the
same change.
"""

from __future__ import annotations

from pathlib import Path


SCHEMA_DIR: Path = Path(__file__).resolve().parent
V1_DIR: Path = SCHEMA_DIR / "v1"


SUPPORTED_INPUTS = ("manifest", "catalog", "agent_spec", "agent_run")
SUPPORTED_SCHEMA_VERSIONS = ("1.0",)
SUPPORTED_EVIDENCE_SCHEMAS = (
    "pilot_evidence_bundle",
    "difference_draft",
    "adjudication",
    "change_evidence_report",
    "evidence_ledger",
    "iteration_index",
    "iteration_summary",
)


def schema_path(kind: str) -> Path:
    """Return the absolute path to the v1 JSON Schema for ``kind``.

    ``kind`` must be one of :data:`SUPPORTED_INPUTS`. The returned path always
    points at the v1 schema; future versions will live under ``v2/``.
    """

    if kind not in SUPPORTED_INPUTS:
        raise ValueError(
            f"unknown schema kind: {kind!r}; expected one of {SUPPORTED_INPUTS}"
        )
    return V1_DIR / f"{kind}.schema.json"


def evidence_schema_path(kind: str) -> Path:
    """Return the JSON Schema resource for a Pilot Evidence v1 contract."""

    kind = kind.replace("-", "_").replace("@1.0", "")
    kind = {
        "pilot_evidence": "pilot_evidence_bundle",
        "change_report": "change_evidence_report",
        "ledger": "evidence_ledger",
        "iteration-index": "iteration_index",
        "iteration-summary": "iteration_summary",
    }.get(kind, kind)
    if kind not in SUPPORTED_EVIDENCE_SCHEMAS:
        raise ValueError(
            f"unknown evidence schema kind: {kind!r}; expected one of {SUPPORTED_EVIDENCE_SCHEMAS}"
        )
    filenames = {
        "pilot_evidence_bundle": "pilot-evidence-bundle.schema.json",
        "difference_draft": "difference-draft.schema.json",
        "adjudication": "adjudication.schema.json",
        "change_evidence_report": "change-evidence-report.schema.json",
        "evidence_ledger": "evidence-ledger.schema.json",
        "iteration_index": "iteration-index.schema.json",
        "iteration_summary": "iteration-summary.schema.json",
    }
    return V1_DIR / filenames[kind]


__all__ = [
    "SCHEMA_DIR",
    "V1_DIR",
    "SUPPORTED_INPUTS",
    "SUPPORTED_EVIDENCE_SCHEMAS",
    "SUPPORTED_SCHEMA_VERSIONS",
    "evidence_schema_path",
    "schema_path",
]
