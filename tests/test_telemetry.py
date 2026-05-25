"""Farmer summary parsing for Phase 3 telemetry."""

from __future__ import annotations

from harvester_deploy.domain.models import ChiaNetwork
from harvester_deploy.domain.telemetry import parse_farm_summary


def test_parse_farm_summary_with_local_and_remote_harvesters() -> None:
    summary = """
Farming status: Farming
Last height farmed: 5845123
Local Harvester
   165 plots of size: 32.471 TiB
Remote Harvester for IP: 192.168.1.137
   500 plots of size: 102.345 TiB
Remote Harvester for IP: 192.168.1.145
   600 plots of size: 120.111 TiB
Plot count for all harvesters: 1,265
Total size of plots: 254.927 TiB
Estimated network space: 42.100 EiB
Expected time to win: 1 month
""".strip()

    telemetry = parse_farm_summary(summary, ChiaNetwork.MAINNET)

    assert telemetry is not None
    assert telemetry.network == ChiaNetwork.MAINNET
    assert telemetry.last_farmed_height == "5845123"
    assert telemetry.total_plot_count == 1265
    assert telemetry.total_plot_size == "254.927 TiB"
    assert telemetry.estimated_network_space == "42.100 EiB"
    assert telemetry.expected_time_to_win == "1 month"

    assert telemetry.local_harvester is not None
    assert telemetry.local_harvester.plot_count == 165
    assert telemetry.local_harvester.plot_size == "32.471 TiB"

    remote = telemetry.remote_harvesters["192.168.1.137"]
    assert remote.plot_count == 500
    assert remote.plot_size == "102.345 TiB"


def test_parse_farm_summary_returns_none_for_empty_text() -> None:
    assert parse_farm_summary("", ChiaNetwork.TESTNET) is None
