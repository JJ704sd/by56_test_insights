from __future__ import annotations

import copy
import unittest

from qualityctl.risk import RISK_DIMENSIONS, validate_risk_manifest


def complete_manifest() -> dict:
    return {
        "change_id": "C-1",
        "version_type": "daily",
        "changed_components": ["api"],
        "agent_evaluation": {
            "required": False,
            "approved_by": "qa-owner",
            "evidence_ref": "policy://traditional-service",
        },
        "dependencies": {"upstream": [], "downstream": []},
        "risk_signals": [],
        "dimensions": {
            name: {"status": "not_affected", "reason": "reviewed diff and contract"}
            for name in RISK_DIMENSIONS
        },
    }


class RiskManifestTests(unittest.TestCase):
    def test_complete_manifest_is_ready(self) -> None:
        result = validate_risk_manifest(complete_manifest())
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["errors"], [])

    def test_missing_dimension_blocks(self) -> None:
        manifest = complete_manifest()
        del manifest["dimensions"]["side_effects"]
        result = validate_risk_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("side_effects" in error for error in result["errors"]))

    def test_unknown_requires_owner_and_deadline_then_reviews(self) -> None:
        manifest = complete_manifest()
        manifest["dimensions"]["permissions"] = {
            "status": "unknown",
            "owner": "security",
            "resolve_by": "2026-08-12",
        }
        result = validate_risk_manifest(manifest)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["unknown_dimensions"], ["permissions"])

    def test_affected_requires_evidence_and_scenario(self) -> None:
        manifest = copy.deepcopy(complete_manifest())
        manifest["dimensions"]["boundaries"] = {"status": "affected"}
        result = validate_risk_manifest(manifest)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertGreaterEqual(len(result["errors"]), 2)


if __name__ == "__main__":
    unittest.main()
