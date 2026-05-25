"""Bundled GUI assets (icon, etc.)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon


def assets_dir() -> Path:
    package_assets = Path(__file__).resolve().parents[1] / "assets"
    repo_assets = Path(__file__).resolve().parents[3] / "assets"
    if repo_assets.is_dir():
        return repo_assets
    return package_assets


def icon_path() -> Path | None:
    for name in ("hdm.png", "hdm.ico", "hdm.svg"):
        path = assets_dir() / name
        if path.is_file():
            return path
    return None


def app_icon() -> QIcon | None:
    """Build a QIcon from all available icon assets."""
    paths = [assets_dir() / name for name in ("hdm.ico", "hdm.png", "hdm.svg")]
    existing = [path for path in paths if path.is_file()]
    if not existing:
        return None

    icon = QIcon()
    for path in existing:
        icon.addFile(str(path))
    return icon if not icon.isNull() else None
