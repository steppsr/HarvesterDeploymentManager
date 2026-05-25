"""Async fleet operations used by the GUI (same core as CLI)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from harvester_deploy.domain.models import DeployJob, Harvester, LogCallback
from harvester_deploy.orchestrator.runner import run_deployments
from harvester_deploy.recipes.engine import load_recipe, run_doctor, run_status, test_ssh


@dataclass
class DeployOptions:
    parallel: int = 2
    dry_run: bool = False
    force: bool = False
    recipe_name: str = "chia-upgrade-default"


async def fleet_status(harvesters: list[Harvester]) -> list[dict | BaseException]:
    """Status for each node; exceptions are returned per slot (gather)."""
    tasks = [run_status(h) for h in harvesters]
    return list(await asyncio.gather(*tasks, return_exceptions=True))


async def node_doctor(harvester: Harvester) -> dict:
    return await run_doctor(harvester)


async def node_test_ssh(harvester: Harvester) -> tuple[str, bool, BaseException | None]:
    ok, err = await test_ssh(harvester)
    return harvester.id, ok, err if not ok else None


async def fleet_deploy(
    harvesters: list[Harvester],
    options: DeployOptions,
    on_log: LogCallback | None = None,
) -> list[DeployJob]:
    recipe = load_recipe(options.recipe_name)
    return await run_deployments(
        harvesters,
        recipe,
        parallel=options.parallel,
        dry_run=options.dry_run,
        force=options.force,
        on_log=on_log,
    )
