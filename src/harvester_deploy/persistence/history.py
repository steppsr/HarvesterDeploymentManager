"""Deploy run history in SQLite (GUI timeline + CLI JSON compatibility)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from harvester_deploy.domain.models import DeployJob, JobState
from harvester_deploy.persistence.db import _connect, default_db_path, init_db
from harvester_deploy.persistence.paths import default_deployments_dir
from harvester_deploy.reporting.summary import _job_to_dict


@dataclass(frozen=True)
class DeployRunSummary:
    id: int
    run_ts: str
    created_at: str
    dry_run: bool
    json_path: str | None
    total: int
    success_count: int
    failed_count: int


@dataclass(frozen=True)
class DeployRunJobRow:
    id: int
    run_id: int
    node_id: str
    state: str
    skipped_upgrade: bool
    version_before: str | None
    version_after: str | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    run_ts: str
    dry_run: bool


def record_deploy_run(
    jobs: list[DeployJob],
    *,
    dry_run: bool = False,
    json_path: Path | str | None = None,
    db_path: Path | None = None,
) -> int:
    """Persist one fleet deploy run. Returns deploy_runs.id."""
    path = init_db(db_path or default_db_path())
    run_ts = _run_ts_from_json_path(json_path)
    created_at = datetime.now(timezone.utc).isoformat()
    success = sum(1 for j in jobs if j.state == JobState.SUCCESS)
    failed = sum(1 for j in jobs if j.state == JobState.FAILED)
    json_str = str(json_path) if json_path else None

    with _connect(path) as conn:
        existing = conn.execute(
            "SELECT id FROM deploy_runs WHERE run_ts = ?", (run_ts,)
        ).fetchone()
        if existing:
            return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO deploy_runs (
                run_ts, created_at, dry_run, json_path,
                total, success_count, failed_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_ts,
                created_at,
                1 if dry_run else 0,
                json_str,
                len(jobs),
                success,
                failed,
            ),
        )
        run_id = int(cur.lastrowid)
        for job in jobs:
            conn.execute(
                """
                INSERT INTO deploy_run_jobs (
                    run_id, node_id, state, skipped_upgrade,
                    version_before, version_after, error,
                    started_at, finished_at, steps_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    job.harvester.id,
                    job.state.value,
                    1 if job.skipped_upgrade else 0,
                    job.version_before,
                    job.version_after,
                    job.error,
                    job.started_at.isoformat() if job.started_at else None,
                    job.finished_at.isoformat() if job.finished_at else None,
                    json.dumps(_job_to_dict(job)["steps"]),
                ),
            )
        conn.commit()
    return run_id


def list_node_history(
    node_id: str,
    *,
    limit: int = 200,
    db_path: Path | None = None,
) -> list[DeployRunJobRow]:
    path = init_db(db_path or default_db_path())
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT j.*, r.run_ts, r.dry_run
            FROM deploy_run_jobs j
            JOIN deploy_runs r ON r.id = j.run_id
            WHERE j.node_id = ?
            ORDER BY r.created_at DESC, j.id DESC
            LIMIT ?
            """,
            (node_id, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def list_run_jobs(
    run_id: int,
    *,
    db_path: Path | None = None,
) -> list[DeployRunJobRow]:
    path = init_db(db_path or default_db_path())
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT j.*, r.run_ts, r.dry_run
            FROM deploy_run_jobs j
            JOIN deploy_runs r ON r.id = j.run_id
            WHERE j.run_id = ?
            ORDER BY j.node_id
            """,
            (run_id,),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_run_summary(
    run_id: int,
    *,
    db_path: Path | None = None,
) -> DeployRunSummary | None:
    path = init_db(db_path or default_db_path())
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM deploy_runs WHERE id = ?", (run_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_run(row)


def distinct_node_ids(*, db_path: Path | None = None) -> list[str]:
    path = init_db(db_path or default_db_path())
    with _connect(path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT node_id FROM deploy_run_jobs ORDER BY node_id"
        ).fetchall()
    return [r["node_id"] for r in rows]


def import_json_summaries(
    *,
    deployments_dir: Path | None = None,
    db_path: Path | None = None,
) -> int:
    """Import summary.json files not yet recorded. Returns count imported."""
    root = deployments_dir or default_deployments_dir()
    if not root.is_dir():
        return 0

    paths = sorted(root.glob("*/summary.json"), key=lambda p: p.stat().st_mtime)
    imported = 0
    for summary_path in paths:
        run_ts = summary_path.parent.name
        path = init_db(db_path or default_db_path())
        with _connect(path) as conn:
            if conn.execute(
                "SELECT 1 FROM deploy_runs WHERE run_ts = ?", (run_ts,)
            ).fetchone():
                continue

        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        jobs = _jobs_from_summary_payload(payload)
        if not jobs:
            continue
        record_deploy_run(
            jobs,
            dry_run=bool(payload.get("dry_run")),
            json_path=summary_path,
            db_path=db_path,
        )
        imported += 1
    return imported


def _run_ts_from_json_path(json_path: Path | str | None) -> str:
    if json_path:
        parent = Path(json_path).parent.name
        if parent and parent != "deployments":
            return parent
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _row_to_run(row: sqlite3.Row) -> DeployRunSummary:
    return DeployRunSummary(
        id=int(row["id"]),
        run_ts=row["run_ts"],
        created_at=row["created_at"],
        dry_run=bool(row["dry_run"]),
        json_path=row["json_path"],
        total=int(row["total"]),
        success_count=int(row["success_count"]),
        failed_count=int(row["failed_count"]),
    )


def _row_to_job(row: sqlite3.Row) -> DeployRunJobRow:
    return DeployRunJobRow(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        node_id=row["node_id"],
        state=row["state"],
        skipped_upgrade=bool(row["skipped_upgrade"]),
        version_before=row["version_before"],
        version_after=row["version_after"],
        error=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        run_ts=row["run_ts"],
        dry_run=bool(row["dry_run"]),
    )


def _jobs_from_summary_payload(payload: dict) -> list[DeployJob]:
    from harvester_deploy.domain.models import Harvester, NodeRole, StepResult, StepStatus

    jobs: list[DeployJob] = []
    for item in payload.get("jobs") or []:
        role_raw = (item.get("role") or "harvester").lower()
        try:
            role = NodeRole(role_raw)
        except ValueError:
            role = NodeRole.HARVESTER

        harvester = Harvester(
            id=item.get("harvester_id") or "unknown",
            display_name=item.get("display_name") or item.get("harvester_id") or "?",
            host=item.get("host") or "",
            role=role,
        )
        try:
            state = JobState(item.get("state") or JobState.FAILED.value)
        except ValueError:
            state = JobState.FAILED

        steps = []
        for s in item.get("steps") or []:
            try:
                status = StepStatus(s.get("status", StepStatus.PENDING.value))
            except ValueError:
                status = StepStatus.PENDING
            steps.append(
                StepResult(
                    step_id=s.get("step_id") or "?",
                    status=status,
                    message=s.get("message") or "",
                )
            )

        started = _parse_iso(item.get("started_at"))
        finished = _parse_iso(item.get("finished_at"))
        jobs.append(
            DeployJob(
                harvester=harvester,
                state=state,
                started_at=started,
                finished_at=finished,
                steps=steps,
                version_before=item.get("version_before"),
                version_after=item.get("version_after"),
                error=item.get("error"),
                skipped_upgrade=bool(item.get("skipped_upgrade")),
            )
        )
    return jobs


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
