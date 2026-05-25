from __future__ import annotations

from harvester_deploy.domain.models import LogCallback
from rich.console import Console
from rich.panel import Panel


class ConsoleReporter:
    """Prefix log lines by harvester and print to the console."""

    def __init__(self) -> None:
        self.console = Console()
        self._buffers: dict[str, list[str]] = {}

    def log(self, harvester_id: str, line: str) -> None:
        self._buffers.setdefault(harvester_id, []).append(line)
        self.console.print(f"[cyan]{harvester_id}[/cyan] | {line}")

    def print_job_summary(self, harvester_id: str, state: str, error: str | None = None) -> None:
        style = "green" if state == "success" else "red"
        body = error or "completed"
        self.console.print(
            Panel(body, title=f"{harvester_id}: {state}", border_style=style)
        )


def log_callback(quiet: bool = False) -> LogCallback | None:
    """Return a console log handler, or None when --quiet suppresses step output."""
    if quiet:
        return None
    return ConsoleReporter().log
