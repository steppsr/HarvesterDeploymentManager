"""Deploy history persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from harvester_deploy.domain.models import DeployJob, Harvester, JobState
from harvester_deploy.persistence.history import (
    import_json_summaries,
    list_node_history,
    record_deploy_run,
)
from harvester_deploy.persistence.db import init_db


def _sample_job(node_id: str = "alpha", *, skipped: bool = False) -> DeployJob:
    h = Harvester(id=node_id, display_name=node_id.upper(), host=f"{node_id}.lan")
    return DeployJob(
        harvester=h,
        state=JobState.SUCCESS,
        skipped_upgrade=skipped,
        version_before="2.7.0",
        version_after="2.8.0" if not skipped else "2.7.0",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )


def test_record_and_list_node_history(tmp_path: Path) -> None:
    db = init_db(tmp_path / "hdm.db")
    jobs = [_sample_job("alpha"), _sample_job("beta")]
    record_deploy_run(jobs, dry_run=False, json_path=None, db_path=db)

    alpha_rows = list_node_history("alpha", db_path=db)
    assert len(alpha_rows) == 1
    assert alpha_rows[0].node_id == "alpha"
    assert alpha_rows[0].state == JobState.SUCCESS.value
    assert not alpha_rows[0].skipped_upgrade


def test_import_json_summaries(tmp_path: Path) -> None:
    db = init_db(tmp_path / "hdm.db")
    run_dir = tmp_path / "deployments" / "20260101-120000"
    run_dir.mkdir(parents=True)
    payload = {
        "timestamp": "20260101-120000",
        "dry_run": True,
        "jobs": [
            {
                "harvester_id": "tarkin",
                "display_name": "Tarkin",
                "host": "tarkin",
                "role": "harvester",
                "skipped_upgrade": True,
                "state": "success",
                "version_before": "2.7.0",
                "version_after": "2.7.0",
                "error": None,
                "started_at": None,
                "finished_at": None,
                "steps": [],
            }
        ],
        "summary": {"total": 1, "success": 1, "failed": 0},
    }
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")

    count = import_json_summaries(deployments_dir=tmp_path / "deployments", db_path=db)
    assert count == 1
    rows = list_node_history("tarkin", db_path=db)
    assert len(rows) == 1
    assert rows[0].skipped_upgrade
    assert rows[0].dry_run
