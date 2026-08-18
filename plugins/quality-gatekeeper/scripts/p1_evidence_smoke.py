"""P1 Pilot Evidence smoke using only the repository's synthetic fixtures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from qualityctl.evidence import (  # noqa: E402
    compare_scopes,
    freeze_ledger,
    validate_adjudication_record,
)
from test_evidence import _fixture_bundle  # noqa: E402


def main() -> None:
    bundle = _fixture_bundle()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bundle_path = root / "fixture-bundle.json"
        report_path = root / "fixture-report.json"
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False), encoding="utf-8"
        )
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(ROOT / "src")
        command = [
            sys.executable,
            "-m",
            "qualityctl",
            "evidence",
            "verify-change",
            str(bundle_path),
            "--output",
            str(report_path),
        ]
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            env=environment,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "ELIGIBLE":
            raise RuntimeError(f"unexpected fixture report: {report}")
        if report.get("formal_release_effect") != "NONE":
            raise RuntimeError("fixture report changed formal release effect")

        draft = compare_scopes(
            {"selected_test_ids": ["FIXTURE-TEST-001"]},
            {"selected_test_ids": ["FIXTURE-TEST-002"]},
        )
        if any("classification" in item for item in draft["differences"]):
            raise RuntimeError("difference draft self-adjudicated")
        adjudication = dict(bundle["adjudication"])
        adjudication["difference_draft_digest"] = draft["decision_digest"]
        adjudication["items"] = [
            {
                "difference_id": item["difference_id"],
                "classification": "NO_DIFFERENCE",
                "evidence_refs": ["fixture://adjudication/evidence"],
                "status": "CLOSED",
                "adjudicator": "fixture-adjudicator",
                "adjudicated_at": "2026-08-18T08:08:00+08:00",
            }
            for item in draft["differences"]
        ]
        if validate_adjudication_record(adjudication)["status"] != "VALID":
            raise RuntimeError("fixture adjudication did not validate")
        ledger = freeze_ledger(
            {
                "entries": [
                    {
                        "pilot_id": "fixture-pilot",
                        "iteration_id": "fixture-iteration-001",
                        "change_id": "FIXTURE-CHANGE-001",
                        "run_id": "fixture-run-001",
                        "status": report["status"],
                        "evidence_digest": report["decision_digest"],
                        "attempt_ids": report["attempt_ids"],
                        "out_of_plan": False,
                    }
                ]
            }
        )
        if ledger["status"] != "FROZEN" or ledger["formal_release_effect"] != "NONE":
            raise RuntimeError(f"unexpected fixture ledger: {ledger}")
    print(
        json.dumps(
            {
                "fixture": "synthetic-p1",
                "verify_change": "ELIGIBLE",
                "draft_diff": "PASS",
                "adjudication": "VALID",
                "ledger": "FROZEN",
                "formal_release_effect": "NONE",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
