"""GUI entry point for harvest-deploy."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

try:
    from harvester_deploy.gui.main_window import run_gui
except ImportError as exc:
    raise SystemExit(
        "GUI dependencies missing. Install with: pip install -e \".[gui]\""
    ) from exc

gui_app = typer.Typer(
    name="harvest-deploy",
    help="Harvester Deployment Manager — desktop GUI.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@gui_app.callback()
def main(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to harvesters.yaml",
    ),
) -> None:
    """Launch the Harvester Deployment Manager window."""
    raise SystemExit(run_gui(config))


def main_entry() -> None:
    """Console script entry (harvest-deploy)."""
    try:
        gui_app()
    except SystemExit as exc:
        code = exc.code
        if code is None:
            code = 0
        raise SystemExit(code) from exc


if __name__ == "__main__":
    main_entry()
