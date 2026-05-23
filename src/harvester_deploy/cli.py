from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from harvester_deploy.domain.models import JobState
from harvester_deploy.orchestrator.runner import exit_code_for_jobs, run_deployments
from harvester_deploy.persistence.config import load_config, resolve_targets
from harvester_deploy.recipes.engine import load_recipe, run_doctor, run_status, test_ssh
from harvester_deploy.reporting.console import ConsoleReporter
from harvester_deploy.reporting.summary import write_summary

app = typer.Typer(
    name="harvester-deploy",
    help="Deploy Chia upgrades to harvester machines over SSH.",
    no_args_is_help=True,
)
console = Console()


def _run(coro):
    return asyncio.run(coro)


@app.command("test-ssh")
def cmd_test_ssh(
    target: str = typer.Option(
        "all",
        "--target",
        "-t",
        help="Harvester id, comma-separated ids, or 'all'",
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="harvesters.yaml path"),
) -> None:
    """Test SSH connectivity to harvester(s)."""
    cfg = load_config(config)
    targets = resolve_targets(cfg, target)
    reporter = ConsoleReporter()

    async def _go():
        results = []
        for h in targets:
            ok = await test_ssh(h, on_log=reporter.log)
            results.append((h.id, ok))
        return results

    results = _run(_go())
    table = Table(title="SSH test")
    table.add_column("Harvester")
    table.add_column("Result")
    for hid, ok in results:
        table.add_row(hid, "[green]ok[/green]" if ok else "[red]fail[/red]")
    console.print(table)
    if not all(ok for _, ok in results):
        raise typer.Exit(code=1)


@app.command("status")
def cmd_status(
    target: str = typer.Option("all", "--target", "-t"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Report chia version (and brief farm summary) on harvester(s)."""
    cfg = load_config(config)
    targets = resolve_targets(cfg, target)
    reporter = ConsoleReporter()

    async def _go():
        return [await run_status(h, on_log=reporter.log) for h in targets]

    rows = _run(_go())
    table = Table(title="Harvester status")
    table.add_column("ID")
    table.add_column("Host")
    table.add_column("Version")
    for r in rows:
        table.add_row(r["id"], r["host"], r["version"])
    console.print(table)


@app.command("doctor")
def cmd_doctor(
    target: str = typer.Option("all", "--target", "-t"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run health checks: SSH, chia root, git status, version."""
    cfg = load_config(config)
    targets = resolve_targets(cfg, target)
    reporter = ConsoleReporter()

    async def _go():
        return [await run_doctor(h, on_log=reporter.log) for h in targets]

    for checks in _run(_go()):
        lines = "\n".join(f"{k}: {v}" for k, v in checks.items())
        console.print(Panel(lines, title=checks["id"]))


@app.command("deploy")
def cmd_deploy(
    target: str = typer.Option(
        "all",
        "--target",
        "-t",
        help="Harvester id, comma-separated ids, or 'all'",
    ),
    parallel: int = typer.Option(2, "--parallel", "-p", help="Max concurrent deployments"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List steps without connecting"),
    recipe: str = typer.Option("chia-upgrade-default", "--recipe", "-r"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run the Chia upgrade recipe on harvester(s)."""
    cfg = load_config(config)
    targets = resolve_targets(cfg, target)
    rec = load_recipe(recipe)
    reporter = ConsoleReporter()

    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] — no remote changes")
        for h in targets:
            for step in rec.steps:
                reporter.log(h.id, f"[dry-run] {step.id}: {step.description}")

    async def _go():
        return await run_deployments(
            targets,
            rec,
            parallel=parallel,
            dry_run=dry_run,
            on_log=reporter.log,
        )

    jobs = _run(_go())
    summary_path = write_summary(jobs, dry_run=dry_run)

    table = Table(title="Deployment summary")
    table.add_column("Harvester")
    table.add_column("State")
    table.add_column("Before")
    table.add_column("After")
    table.add_column("Error")
    for job in jobs:
        table.add_row(
            job.harvester.id,
            job.state.value,
            job.version_before or "-",
            job.version_after or "-",
            (job.error or "")[:60],
        )
    console.print(table)
    console.print(f"Summary written to [bold]{summary_path}[/bold]")

    code = exit_code_for_jobs(jobs)
    if code:
        raise typer.Exit(code=code)


if __name__ == "__main__":
    app()
