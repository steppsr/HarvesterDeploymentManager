"""App path resolution (dev vs frozen)."""

from __future__ import annotations

from harvester_deploy.persistence import paths


def test_repo_root_exists() -> None:
    root = paths.repo_root()
    assert (root / "pyproject.toml").is_file()


def test_default_config_path_under_repo_when_not_frozen(monkeypatch) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    cfg = paths.default_config_path()
    assert cfg.name == "harvesters.yaml"
    assert cfg.parent.name == "config"
    assert paths.repo_root() in cfg.parents


def test_frozen_user_data_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    data = paths.user_data_dir()
    assert data == tmp_path / "HarvesterDeploymentManager"
    assert paths.default_config_path() == data / "config" / "harvesters.yaml"


def test_seed_config_skips_when_db_has_nodes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from harvester_deploy.domain.models import Harvester
    from harvester_deploy.persistence.config import AppConfig, DefaultsModel
    from harvester_deploy.persistence.db import save_config_to_db

    cfg = AppConfig(
        defaults=DefaultsModel(),
        harvesters=[
            Harvester(id="solo", display_name="Solo", host="solo.lan"),
        ],
    )
    save_config_to_db(cfg)
    paths.seed_config_if_empty()
    assert not paths.default_config_path().is_file()
