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


def test_theme_preference_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert paths.load_theme_preference() is None
    paths.save_theme_preference("dark")
    assert paths.load_theme_preference() == "dark"


def test_save_config_path_preserves_theme(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    cfg = tmp_path / "fleet.yaml"
    cfg.write_text("harvesters: []\n", encoding="utf-8")
    paths.save_theme_preference("dark")
    paths.save_persisted_config_path(cfg)

    assert paths.load_theme_preference() == "dark"
    assert paths.load_persisted_config_path() == cfg


def test_refresh_interval_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert paths.load_refresh_interval_seconds() is None
    paths.save_refresh_interval_seconds(180)
    assert paths.load_refresh_interval_seconds() == 180


def test_save_refresh_interval_preserves_other_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    cfg = tmp_path / "fleet.yaml"
    cfg.write_text("harvesters: []\n", encoding="utf-8")
    paths.save_theme_preference("dark")
    paths.save_persisted_config_path(cfg)
    paths.save_refresh_interval_seconds(240)

    assert paths.load_theme_preference() == "dark"
    assert paths.load_persisted_config_path() == cfg
    assert paths.load_refresh_interval_seconds() == 240


def test_window_state_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert paths.load_window_state() == (None, None, "normal")
    paths.save_window_state(width=1440, height=900, mode="fullscreen")

    assert paths.load_window_state() == (1440, 900, "fullscreen")


def test_save_window_state_preserves_other_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    cfg = tmp_path / "fleet.yaml"
    cfg.write_text("harvesters: []\n", encoding="utf-8")
    paths.save_theme_preference("dark")
    paths.save_persisted_config_path(cfg)
    paths.save_refresh_interval_seconds(240)
    paths.save_window_state(width=1280, height=720, mode="maximized")

    assert paths.load_theme_preference() == "dark"
    assert paths.load_persisted_config_path() == cfg
    assert paths.load_refresh_interval_seconds() == 240
    assert paths.load_window_state() == (1280, 720, "maximized")
