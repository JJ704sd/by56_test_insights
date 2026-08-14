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


__all__ = [
    "SCHEMA_DIR",
    "V1_DIR",
    "SUPPORTED_INPUTS",
    "SUPPORTED_SCHEMA_VERSIONS",
    "schema_path",
]