"""Load and save fleet inventory (SQLite + YAML sync)."""

from __future__ import annotations

from pathlib import Path

import yaml

from harvester_deploy.domain.models import ChiaNetwork, Harvester, NodeRole
from harvester_deploy.persistence.config import (
    AppConfig,
    DefaultsModel,
    default_config_path,
    load_config,
)
from harvester_deploy.persistence.db import (
    default_db_path,
    init_db,
    load_config_from_db,
    node_count,
    save_config_to_db,
)


def _harvester_to_entry(h: Harvester, defaults: DefaultsModel) -> dict:
    """YAML entry with only fields that differ from defaults (keeps file tidy)."""
    entry: dict = {
        "id": h.id,
        "host": h.host,
    }
    if h.display_name and h.display_name != h.id.upper():
        entry["display_name"] = h.display_name
    if h.role != NodeRole(defaults.role):
        entry["role"] = h.role.value
    if h.network != ChiaNetwork(defaults.network):
        entry["network"] = h.network.value
    if h.ssh_port != defaults.ssh_port:
        entry["ssh_port"] = h.ssh_port
    if h.ssh_user != defaults.ssh_user:
        entry["ssh_user"] = h.ssh_user
    if h.ssh_key_path != defaults.ssh_key_path:
        entry["ssh_key_path"] = h.ssh_key_path
    if h.chia_root != defaults.chia_root:
        entry["chia_root"] = h.chia_root
    if h.chia_config_dir != defaults.chia_config_dir:
        entry["chia_config_dir"] = h.chia_config_dir
    if h.activate_cmd != defaults.activate_cmd:
        entry["activate_cmd"] = h.activate_cmd
    if h.git_branch != defaults.git_branch:
        entry["git_branch"] = h.git_branch
    if h.upgrade_mode != defaults.upgrade_mode:
        entry["upgrade_mode"] = h.upgrade_mode
    if h.enabled != defaults.enabled:
        entry["enabled"] = h.enabled
    if h.last_known_version:
        entry["last_known_version"] = h.last_known_version
    if h.farmer_host:
        entry["farmer_host"] = h.farmer_host
    return entry


def write_yaml(config: AppConfig, path: Path) -> None:
    payload = {
        "defaults": config.defaults.model_dump(),
        "harvesters": [_harvester_to_entry(h, config.defaults) for h in config.harvesters],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Managed by Harvester Deployment Manager.\n"
        "# CLI (hdm) reads this file; the GUI syncs here on save.\n"
    )
    path.write_text(
        header + yaml.safe_dump(payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _fleet_ids(config: AppConfig) -> set[str]:
    return {h.id for h in config.harvesters}


def should_sync_db_from_yaml(
    yaml_path: Path,
    db_path: Path,
    yaml_cfg: AppConfig,
    db_cfg: AppConfig,
) -> str | None:
    """Return a short reason to refresh SQLite from YAML, or None to keep the DB."""
    if not yaml_path.is_file():
        return None
    if node_count(db_path) == 0:
        return "database empty"
    if len(yaml_cfg.harvesters) != len(db_cfg.harvesters):
        return (
            f"node count differs (yaml={len(yaml_cfg.harvesters)}, "
            f"db={len(db_cfg.harvesters)})"
        )
    if _fleet_ids(yaml_cfg) != _fleet_ids(db_cfg):
        return "node ids differ"
    try:
        if yaml_path.stat().st_mtime > db_path.stat().st_mtime:
            return "harvesters.yaml is newer than the database"
    except OSError:
        pass
    return None


def load_fleet(
    config_path: Path | None = None,
    db_path: Path | None = None,
) -> tuple[AppConfig, str | None]:
    """
    Load fleet inventory.

    Returns (config, sync_note). sync_note is set when SQLite was refreshed from YAML.
    """
    yaml_path = config_path or default_config_path()
    db = db_path or default_db_path()
    init_db(db)

    if not yaml_path.is_file():
        if node_count(db) > 0:
            return load_config_from_db(db), (
                "harvesters.yaml not found at "
                f"{yaml_path} — showing fleet from the local database ({db}). "
                "Import YAML or Save inventory to write a new config file."
            )
        empty = AppConfig(defaults=DefaultsModel(), harvesters=[])
        save_config_to_db(empty, db)
        return empty, None

    yaml_cfg = load_config(yaml_path)

    if node_count(db) == 0:
        save_config_to_db(yaml_cfg, db)
        return yaml_cfg, "loaded harvesters.yaml into new database"

    db_cfg = load_config_from_db(db)
    reason = should_sync_db_from_yaml(yaml_path, db, yaml_cfg, db_cfg)
    if reason:
        save_config_to_db(yaml_cfg, db)
        return yaml_cfg, f"synced from harvesters.yaml ({reason})"

    return db_cfg, None


def save_fleet(
    config: AppConfig,
    config_path: Path | None = None,
    db_path: Path | None = None,
) -> tuple[Path, Path]:
    """Persist to SQLite and sync harvesters.yaml for the CLI."""
    yaml_path = config_path or default_config_path()
    db = db_path or default_db_path()
    save_config_to_db(config, db)
    write_yaml(config, yaml_path)
    return db, yaml_path


def import_yaml_into_db(config_path: Path | None = None) -> AppConfig:
    """Replace SQLite contents from harvesters.yaml."""
    yaml_path = config_path or default_config_path()
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Config not found: {yaml_path}")
    cfg = load_config(yaml_path)
    save_config_to_db(cfg)
    return cfg


def config_dir(config_path: Path | None = None) -> Path:
    return (config_path or default_config_path()).parent
