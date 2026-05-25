"""Chia network (mainnet / testnet) — fleet labeling and filters only."""

from __future__ import annotations

from harvester_deploy.domain.models import ChiaNetwork

# Typical Chia install path; network badge does not change this.
DEFAULT_CHIA_CONFIG_DIR = "~/.chia/mainnet/config"


def parse_network(value: str | None) -> ChiaNetwork:
    """Explicit YAML/DB value only; missing or invalid defaults to mainnet."""
    if value:
        try:
            return ChiaNetwork(value.lower())
        except ValueError:
            pass
    return ChiaNetwork.MAINNET
