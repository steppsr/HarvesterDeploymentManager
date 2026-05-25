"""Resolve config, data, and bundle paths (dev tree vs PyInstaller frozen exe)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import yaml

_APP_DIR_NAME = "HarvesterDeploymentManager"
_SETTINGS_FILE = "settings.yaml"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """PyInstaller extract dir (read-only bundled assets)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parents[3]


def repo_root() -> Path:
    """Git checkout root when running from source (never the frozen temp extract)."""
    if is_frozen():
        return user_data_dir()
    return Path(__file__).resolve().parents[3]


def user_data_dir() -> Path:
    """
    Writable app home.

    - Frozen GUI: %LOCALAPPDATA%\\HarvesterDeploymentManager
    - Dev: repository root (config/, data/, deployments/ as today)
    """
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / _APP_DIR_NAME
        return Path.home() / _APP_DIR_NAME
    return Path(__file__).resolve().parents[3]


def settings_path() -> Path:
    return user_data_dir() / _SETTINGS_FILE


def load_persisted_config_path() -> Path | None:
    """Last config file the user chose (GUI only), if it still exists."""
    path = settings_path()
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    value = raw.get("config_yaml")
    if not value:
        return None
    config = Path(value).expanduser()
    return config if config.is_file() else None


def save_persisted_config_path(config_yaml: Path) -> None:
    """Remember which harvesters.yaml the installed app should use."""
    home = user_data_dir()
    home.mkdir(parents=True, exist_ok=True)
    payload = {"config_yaml": str(config_yaml.resolve())}
    settings_path().write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def clear_persisted_config_path() -> None:
    if settings_path().is_file():
        settings_path().unlink()


def default_config_dir() -> Path:
    return user_data_dir() / "config"


def default_config_path() -> Path:
    return default_config_dir() / "harvesters.yaml"


def default_data_dir() -> Path:
    return user_data_dir() / "data"


def default_db_path() -> Path:
    path = default_data_dir() / "hdm.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def default_deployments_dir() -> Path:
    path = user_data_dir() / "deployments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_recipe_path(recipe: str = "chia-upgrade-default") -> Path:
    name = f"{recipe}.yaml"
    bundled = bundle_root() / "config" / "recipes" / name
    if bundled.is_file():
        return bundled
    user_recipe = default_config_dir() / "recipes" / name
    if user_recipe.is_file():
        return user_recipe
    if is_frozen():
        raise FileNotFoundError(f"Recipe not found in app bundle: {name}")
    return Path(__file__).resolve().parents[3] / "config" / "recipes" / name


def example_config_path() -> Path | None:
    bundled = bundle_root() / "config" / "harvesters.example.yaml"
    if bundled.is_file():
        return bundled
    if not is_frozen():
        dev_example = Path(__file__).resolve().parents[3] / "config" / "harvesters.example.yaml"
        if dev_example.is_file():
            return dev_example
    return None


def ensure_app_directories() -> None:
    """Create writable config/data/deployments folders."""
    default_config_dir().mkdir(parents=True, exist_ok=True)
    default_data_dir().mkdir(parents=True, exist_ok=True)
    default_deployments_dir()


def seed_config_if_empty() -> Path:
    """
    Copy bundled example YAML only when there is no config file and no DB yet.
    Does not recreate YAML if the user deleted it but still has a database.
    """
    ensure_app_directories()
    config_path = default_config_path()
    if config_path.is_file():
        return config_path

    # Installed app should start empty for a truly clean first-run experience.
    if is_frozen():
        return config_path

    from harvester_deploy.persistence.db import init_db, node_count

    db = default_db_path()
    init_db(db)
    if node_count(db) > 0:
        return config_path

    example = example_config_path()
    if example is not None:
        shutil.copy2(example, config_path)
    return config_path


def resolve_config_path(explicit: Path | None = None) -> Path:
    """Config file for this session: CLI arg > saved choice > default location."""
    if explicit is not None:
        return explicit
    persisted = load_persisted_config_path()
    if persisted is not None:
        return persisted
    return default_config_path()


def ensure_user_layout() -> Path:
    """Backward-compatible entry: directories + seed only when truly empty."""
    return seed_config_if_empty()
