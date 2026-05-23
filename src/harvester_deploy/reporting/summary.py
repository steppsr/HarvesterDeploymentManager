from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from harvester_deploy.domain.models import DeployJob, JobState


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _job_to_dict(job: DeployJob) -> dict:
    return {
        "harvester_id": job.harvester.id,
        "display_name": job.harvester.display_name,
        "host": job.harvester.host,
        "role": job.harvester.role_label,
        "skipped_upgrade": job.skipped_upgrade,
        "state": job.state.value,
        "version_before": job.version_before,
        "version_after": job.version_after,
        "error": job.error,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "steps": [
            {
                "step_id": s.step_id,
                "status": s.status.value,
                "message": s.message,
            }
            for s in job.steps
        ],
    }


def write_summary(jobs: list[DeployJob], *, dry_run: bool = False) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = _project_root() / "deployments" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp": ts,
        "dry_run": dry_run,
        "jobs": [_job_to_dict(j) for j in jobs],
        "summary": {
            "total": len(jobs),
            "success": sum(1 for j in jobs if j.state == JobState.SUCCESS),
            "failed": sum(1 for j in jobs if j.state == JobState.FAILED),
        },
    }

    path = out_dir / "summary.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
