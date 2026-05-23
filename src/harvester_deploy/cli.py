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

_TARGET_HELP = (
    "Node id, comma-separated ids, or a group: "
    "all | harvesters | farmers"
)

app = typer.Typer(
    name="harvester-deploy",
    help="Deploy Chia upgrades to harvester and farmer nodes over SSH.",
    no_args_is_help=True,
)
console = Console()


def _run(coro):
    return asyncio.run(coro)


def _load_targets(config_path: Optional[Path], target: str):
    cfg = load_config(config_path)
    return cfg, resolve_targets(cfg, target)


@app.command("test-ssh")
def cmd_test_ssh(
    target: str = typer.Option("all", "--target", "-t", help=_TARGET_HELP),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="harvesters.yaml path"),
) -> None:
    """Test SSH connectivity to node(s)."""
    _, targets = _load_targets(config, target)
    reporter = ConsoleReporter()

    async def _go():
        results = []
        for h in targets:
            ok = await test_ssh(h, on_log=reporter.log)
            results.append((h.id, h.role_label, ok))
        return results

    results = _run(_go())
    table = Table(title="SSH test")
    table.add_column("ID")
    table.add_column("Role")
    table.add_column("Result")
    for hid, role, ok in results:
        table.add_row(hid, role, "[green]ok[/green]" if ok else "[red]fail[/red]")
    console.print(table)
    if not all(ok for _, _, ok in results):
        raise typer.Exit(code=1)


@app.command("status")
def cmd_status(
    target: str = typer.Option("all", "--target", "-t", help=_TARGET_HELP),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Report chia version and git drift per node."""
    _, targets = _load_targets(config, target)
    reporter = ConsoleReporter()

    async def _go():
        return [await run_status(h, on_log=reporter.log) for h in targets]

    rows = _run(_go())
    table = Table(title="Node status")
    table.add_column("ID")
    table.add_column("Role")
    table.add_column("Install")
    table.add_column("Host")
    table.add_column("Version")
    table.add_column("Behind")
    for r in rows:
        table.add_row(
            r["id"],
            r["role"],
            r.get("install_mode", "-"),
            r["host"],
            r["version"],
            r.get("commits_behind", "-"),
        )
    console.print(table)


@app.command("doctor")
def cmd_doctor(
    target: str = typer.Option("all", "--target", "-t", help=_TARGET_HELP),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run health checks: SSH, chia root, git, version, commits behind."""
    _, targets = _load_targets(config, target)
    reporter = ConsoleReporter()

    async def _go():
        return [await run_doctor(h, on_log=reporter.log) for h in targets]

    for checks in _run(_go()):
        title = f"{checks['id']} ({checks.get('role', '?')})"
        lines = "\n".join(f"{k}: {v}" for k, v in checks.items())
        console.print(Panel(lines, title=title))


@app.command("deploy")
def cmd_deploy(
    target: str = typer.Option("all", "--target", "-t", help=_TARGET_HELP),
    parallel: int = typer.Option(2, "--parallel", "-p", help="Max concurrent deployments"),
    dry_run: bool = typer.Option(False, "--dry-run", help="List steps without connecting"),
    force: bool = typer.Option(
        False,
        "--force",
        help="Run full upgrade even when already on origin/latest",
    ),
    recipe: str = typer.Option("chia-upgrade-default", "--recipe", "-r"),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
) -> None:
    """Run the Chia upgrade recipe on node(s)."""
    _, targets = _load_targets(config, target)
    rec = load_recipe(recipe)
    reporter = ConsoleReporter()

    if dry_run:
        console.print("[yellow]DRY RUN[/yellow] — no remote changes")
        for h in targets:
            for step in rec.steps:
                reporter.log(
                    h.id,
                    f"[dry-run] [{h.role_label}] {step.id}: {step.description}",
                )

    async def _go():
        return await run_deployments(
            targets,
            rec,
            parallel=parallel,
            dry_run=dry_run,
            force=force,
            on_log=reporter.log,
        )

    jobs = _run(_go())
    summary_path = write_summary(jobs, dry_run=dry_run)

    table = Table(title="Deployment summary")
    table.add_column("ID")
    table.add_column("Role")
    table.add_column("State")
    table.add_column("Before")
    table.add_column("After")
    table.add_column("Note")
    for job in jobs:
        note = ""
        if job.skipped_upgrade:
            note = "skipped (up to date)"
        elif job.error:
            note = (job.error or "")[:50]
        table.add_row(
            job.harvester.id,
            job.harvester.role_label,
            job.state.value,
            job.version_before or "-",
            job.version_after or "-",
            note,
        )
    console.print(table)
    console.print(f"Summary written to [bold]{summary_path}[/bold]")

    code = exit_code_for_jobs(jobs)
    if code:
        raise typer.Exit(code=code)


if __name__ == "__main__":
    app()
