from __future__ import annotations

import asyncio

from harvester_deploy.domain.models import DeployJob, Harvester, JobState, LogCallback
from harvester_deploy.recipes.engine import Recipe, run_upgrade


async def run_deployments(
    harvesters: list[Harvester],
    recipe: Recipe,
    *,
    parallel: int = 2,
    dry_run: bool = False,
    force: bool = False,
    on_log: LogCallback | None = None,
) -> list[DeployJob]:
    sem = asyncio.Semaphore(max(1, parallel))

    async def _one(h: Harvester) -> DeployJob:
        async with sem:
            if on_log:
                on_log(
                    h.id,
                    f"=== deploy {h.display_name} ({h.host}) [{h.role_label}] ===",
                )
            return await run_upgrade(
                h, recipe, dry_run=dry_run, force=force, on_log=on_log
            )

    return await asyncio.gather(*[_one(h) for h in harvesters])


def exit_code_for_jobs(jobs: list[DeployJob]) -> int:
    successes = sum(1 for j in jobs if j.state == JobState.SUCCESS)
    if successes == len(jobs):
        return 0
    if successes == 0:
        return 1
    return 2
