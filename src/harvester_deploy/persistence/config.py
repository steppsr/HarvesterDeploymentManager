from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from harvester_deploy.domain.models import ChiaNetwork, Harvester, NodeRole
from harvester_deploy.domain.network import parse_network
from harvester_deploy.persistence.paths import (  # noqa: F401 — re-exported
    default_config_path,
    default_recipe_path,
)


class DefaultsModel(BaseModel):
    ssh_port: int = 22
    ssh_user: str = "steve"
    ssh_key_path: str = "~/.ssh/id_ed25519"
    chia_root: str = "~/chia-blockchain"
    chia_config_dir: str = "~/.chia/mainnet/config"
    activate_cmd: str = ". ./activate"
    git_branch: str = "latest"
    upgrade_mode: str = "git"
    enabled: bool = True
    role: str = "harvester"
    network: str = "mainnet"


class HarvesterEntry(BaseModel):
    id: str
    display_name: str | None = None
    host: str
    role: str | None = None
    ssh_port: int | None = None
    ssh_user: str | None = None
    ssh_key_path: str | None = None
    chia_root: str | None = None
    chia_config_dir: str | None = None
    activate_cmd: str | None = None
    git_branch: str | None = None
    upgrade_mode: str | None = None
    enabled: bool | None = None
    last_known_version: str | None = None
    farmer_host: str | None = None
    network: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {r.value for r in NodeRole}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}, got '{v}'")
        return v

    @field_validator("network")
    @classmethod
    def validate_network(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {n.value for n in ChiaNetwork}
        if v not in allowed:
            raise ValueError(f"network must be one of {allowed}, got '{v}'")
        return v


class HarvestersFile(BaseModel):
    defaults: DefaultsModel = Field(default_factory=DefaultsModel)
    harvesters: list[HarvesterEntry] = Field(default_factory=list)


class AppConfig(BaseModel):
    defaults: DefaultsModel
    harvesters: list[Harvester]


def _parse_role(value: str) -> NodeRole:
    return NodeRole(value)


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or default_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    parsed = HarvestersFile.model_validate(raw)

    harvesters: list[Harvester] = []
    for entry in parsed.harvesters:
        d = parsed.defaults
        role_str = entry.role if entry.role is not None else d.role
        network_str = entry.network if entry.network is not None else d.network
        network = parse_network(network_str)
        harvesters.append(
            Harvester(
                id=entry.id,
                display_name=entry.display_name or entry.id.upper(),
                host=entry.host,
                role=_parse_role(role_str),
                network=network,
                ssh_port=entry.ssh_port if entry.ssh_port is not None else d.ssh_port,
                ssh_user=entry.ssh_user or d.ssh_user,
                ssh_key_path=entry.ssh_key_path or d.ssh_key_path,
                chia_root=entry.chia_root or d.chia_root,
                chia_config_dir=entry.chia_config_dir or d.chia_config_dir,
                activate_cmd=entry.activate_cmd or d.activate_cmd,
                git_branch=entry.git_branch or d.git_branch,
                upgrade_mode=entry.upgrade_mode or d.upgrade_mode,
                enabled=entry.enabled if entry.enabled is not None else d.enabled,
                last_known_version=entry.last_known_version,
                farmer_host=entry.farmer_host,
            )
        )

    return AppConfig(defaults=parsed.defaults, harvesters=harvesters)


TARGET_ALIASES = frozenset({"all", "harvesters", "farmers"})


def resolve_targets(config: AppConfig, target: str) -> list[Harvester]:
    """Resolve CLI --target: all | harvesters | farmers | id | id1,id2."""
    if target == "all":
        return [h for h in config.harvesters if h.enabled]
    if target == "harvesters":
        return [
            h
            for h in config.harvesters
            if h.enabled and h.role == NodeRole.HARVESTER
        ]
    if target == "farmers":
        return [
            h
            for h in config.harvesters
            if h.enabled and h.role == NodeRole.FARMER
        ]

    ids = [part.strip() for part in target.split(",") if part.strip()]
    matches: list[Harvester] = []
    for tid in ids:
        if tid in TARGET_ALIASES:
            raise ValueError(
                f"Use --target {tid} alone, not in a comma-separated list."
            )
        found = [h for h in config.harvesters if h.id == tid]
        if not found:
            known = ", ".join(h.id for h in config.harvesters)
            raise ValueError(
                f"Unknown target '{tid}'. Known ids: {known}. "
                f"Groups: all, harvesters, farmers"
            )
        matches.append(found[0])
    return matches
