from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from harvester_deploy.domain.models import Harvester


class DefaultsModel(BaseModel):
    ssh_port: int = 22
    ssh_user: str = "steve"
    ssh_key_path: str = "~/.ssh/id_ed25519"
    chia_root: str = "~/chia-blockchain"
    activate_cmd: str = ". ./activate"
    git_branch: str = "latest"
    upgrade_mode: str = "git"
    enabled: bool = True


class HarvesterEntry(BaseModel):
    id: str
    display_name: str | None = None
    host: str
    ssh_port: int | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    chia_root: str | None = None
    activate_cmd: str | None = None
    git_branch: str | None = None
    upgrade_mode: str | None = None
    enabled: bool | None = None
    last_known_version: str | None = None


class HarvestersFile(BaseModel):
    defaults: DefaultsModel = Field(default_factory=DefaultsModel)
    harvesters: list[HarvesterEntry] = Field(default_factory=list)


class AppConfig(BaseModel):
    defaults: DefaultsModel
    harvesters: list[Harvester]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_config_path() -> Path:
    return _project_root() / "config" / "harvesters.yaml"


def default_recipe_path(recipe: str = "chia-upgrade-default") -> Path:
    return _project_root() / "config" / "recipes" / f"{recipe}.yaml"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    parsed = HarvestersFile.model_validate(raw)

    harvesters: list[Harvester] = []
    for entry in parsed.harvesters:
        d = parsed.defaults
        harvesters.append(
            Harvester(
                id=entry.id,
                display_name=entry.display_name or entry.id.upper(),
                host=entry.host,
                ssh_port=entry.ssh_port if entry.ssh_port is not None else d.ssh_port,
                ssh_user=entry.ssh_user or d.ssh_user,
                ssh_key_path=entry.ssh_key_path or d.ssh_key_path,
                chia_root=entry.chia_root or d.chia_root,
                activate_cmd=entry.activate_cmd or d.activate_cmd,
                git_branch=entry.git_branch or d.git_branch,
                upgrade_mode=entry.upgrade_mode or d.upgrade_mode,
                enabled=entry.enabled if entry.enabled is not None else d.enabled,
                last_known_version=entry.last_known_version,
            )
        )

    return AppConfig(defaults=parsed.defaults, harvesters=harvesters)


def resolve_targets(config: AppConfig, target: str) -> list[Harvester]:
    if target == "all":
        return [h for h in config.harvesters if h.enabled]

    ids = [part.strip() for part in target.split(",") if part.strip()]
    matches: list[Harvester] = []
    for tid in ids:
        found = [h for h in config.harvesters if h.id == tid]
        if not found:
            known = ", ".join(h.id for h in config.harvesters)
            raise ValueError(f"Unknown target '{tid}'. Known: {known}")
        matches.append(found[0])
    return matches
