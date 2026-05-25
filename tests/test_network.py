"""Chia network field and filtering helpers."""

from __future__ import annotations

from harvester_deploy.domain.models import ChiaNetwork, Harvester, NodeRole
from harvester_deploy.domain.network import DEFAULT_CHIA_CONFIG_DIR, parse_network


def test_parse_network_defaults_mainnet() -> None:
    assert parse_network(None) == ChiaNetwork.MAINNET
    assert parse_network("") == ChiaNetwork.MAINNET
    assert parse_network("bogus") == ChiaNetwork.MAINNET


def test_parse_network_explicit() -> None:
    assert parse_network("testnet") == ChiaNetwork.TESTNET
    assert parse_network("mainnet") == ChiaNetwork.MAINNET


def test_default_chia_config_dir_is_mainnet_path() -> None:
    assert "mainnet" in DEFAULT_CHIA_CONFIG_DIR
    assert "testnet" not in DEFAULT_CHIA_CONFIG_DIR


def test_harvester_network_label() -> None:
    h = Harvester(id="x", display_name="X", host="x", network=ChiaNetwork.TESTNET)
    assert h.network_label == "Testnet"


def test_filter_mainnet_harvesters() -> None:
    fleet = [
        Harvester(id="a", display_name="A", host="a", network=ChiaNetwork.MAINNET),
        Harvester(
            id="b",
            display_name="B",
            host="b",
            role=NodeRole.FARMER,
            network=ChiaNetwork.TESTNET,
        ),
    ]
    mainnet = [h for h in fleet if h.network == ChiaNetwork.MAINNET]
    assert len(mainnet) == 1
    assert mainnet[0].id == "a"
