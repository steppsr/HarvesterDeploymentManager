"""Resolve config, data, and bundle paths (dev tree vs PyInstaller frozen exe)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import yaml

_APP_DIR_NAME = "HarvesterDeploymentManager"
_SETTINGS_FILE = "settings.yaml"
_THEME_VALUES = {"light", "dark"}
_MIN_REFRESH_INTERVAL_SECONDS = 30
_MAX_REFRESH_INTERVAL_SECONDS = 3600
_MIN_WINDOW_WIDTH = 640
_MIN_WINDOW_HEIGHT = 480
_MAX_WINDOW_WIDTH = 10000
_MAX_WINDOW_HEIGHT = 10000
_WINDOW_MODES = {"normal", "maximized", "fullscreen"}


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


def _load_settings() -> dict:
    path = settings_path()
    if not path.is_file():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_settings(data: dict) -> None:
    home = user_data_dir()
    home.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        yaml.safe_dump(data, sort_keys=False),
        encoding="utf-8",
    )


def load_persisted_config_path() -> Path | None:
    """Last config file the user chose (GUI only), if it still exists."""
    raw = _load_settings()
    value = raw.get("config_yaml")
    if not value:
        return None
    config = Path(value).expanduser()
    return config if config.is_file() else None


def save_persisted_config_path(config_yaml: Path) -> None:
    """Remember which harvesters.yaml the installed app should use."""
    payload = _load_settings()
    payload["config_yaml"] = str(config_yaml.resolve())
    _write_settings(payload)


def clear_persisted_config_path() -> None:
    payload = _load_settings()
    payload.pop("config_yaml", None)
    if payload:
        _write_settings(payload)
    elif settings_path().is_file():
        settings_path().unlink()


def load_theme_preference() -> str | None:
    value = str(_load_settings().get("theme") or "").strip().lower()
    return value if value in _THEME_VALUES else None


def save_theme_preference(theme: str) -> None:
    value = str(theme).strip().lower()
    if value not in _THEME_VALUES:
        raise ValueError(f"Unsupported theme: {theme}")
    payload = _load_settings()
    payload["theme"] = value
    _write_settings(payload)


def load_refresh_interval_seconds() -> int | None:
    value = _load_settings().get("refresh_interval_seconds")
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None
    if _MIN_REFRESH_INTERVAL_SECONDS <= seconds <= _MAX_REFRESH_INTERVAL_SECONDS:
        return seconds
    return None


def save_refresh_interval_seconds(seconds: int) -> None:
    value = int(seconds)
    if not (_MIN_REFRESH_INTERVAL_SECONDS <= value <= _MAX_REFRESH_INTERVAL_SECONDS):
        raise ValueError(f"Unsupported refresh interval: {seconds}")
    payload = _load_settings()
    payload["refresh_interval_seconds"] = value
    _write_settings(payload)


def load_window_state() -> tuple[int | None, int | None, str]:
    raw = _load_settings()
    width = _coerce_window_dimension(
        raw.get("window_width"),
        minimum=_MIN_WINDOW_WIDTH,
        maximum=_MAX_WINDOW_WIDTH,
    )
    height = _coerce_window_dimension(
        raw.get("window_height"),
        minimum=_MIN_WINDOW_HEIGHT,
        maximum=_MAX_WINDOW_HEIGHT,
    )
    mode = str(raw.get("window_mode") or "").strip().lower()
    if mode not in _WINDOW_MODES:
        mode = "fullscreen" if _coerce_bool(raw.get("window_fullscreen")) else "normal"
    return width, height, mode


def save_window_state(*, width: int, height: int, mode: str) -> None:
    w = _coerce_window_dimension(
        width,
        minimum=_MIN_WINDOW_WIDTH,
        maximum=_MAX_WINDOW_WIDTH,
    )
    h = _coerce_window_dimension(
        height,
        minimum=_MIN_WINDOW_HEIGHT,
        maximum=_MAX_WINDOW_HEIGHT,
    )
    if w is None or h is None:
        raise ValueError(f"Unsupported window size: {width}x{height}")
    state = str(mode).strip().lower()
    if state not in _WINDOW_MODES:
        raise ValueError(f"Unsupported window mode: {mode}")
    payload = _load_settings()
    payload["window_width"] = w
    payload["window_height"] = h
    payload["window_mode"] = state
    payload["window_fullscreen"] = state == "fullscreen"
    _write_settings(payload)


def _coerce_window_dimension(
    value: object, *, minimum: int, maximum: int
) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if minimum <= number <= maximum:
        return number
    return None


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "on"}


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
