"""Farmer summary parsing and fleet telemetry models."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from harvester_deploy.domain.models import ChiaNetwork

_COUNT_RE = re.compile(r"([\d,]+)")
_PLOT_DETAIL_RE = re.compile(
    r"^\s{3,}(?P<count>[\d,]+)\s+plots?\s+of\s+size:\s*(?P<size>.+?)\s*$",
    re.IGNORECASE,
)
_REMOTE_RE = re.compile(
    r"^Remote\s+Harvester\s+for\s+IP:\s*(?P<ip>\S+)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HarvesterTelemetry:
    plot_count: int | None = None
    plot_size: str | None = None
    ip_address: str | None = None
    is_local: bool = False


@dataclass
class NetworkTelemetry:
    network: ChiaNetwork
    raw_summary: str = ""
    last_farmed_height: str | None = None
    total_plot_count: int | None = None
    total_plot_size: str | None = None
    estimated_network_space: str | None = None
    expected_time_to_win: str | None = None
    local_harvester: HarvesterTelemetry | None = None
    remote_harvesters: dict[str, HarvesterTelemetry] = field(default_factory=dict)

    def has_metrics(self) -> bool:
        return any(
            (
                self.last_farmed_height,
                self.total_plot_count is not None,
                self.total_plot_size,
                self.estimated_network_space,
                self.expected_time_to_win,
            )
        )


def parse_farm_summary(summary: str, network: ChiaNetwork) -> NetworkTelemetry | None:
    """Parse `chia farm summary` output into a structured model."""
    text = summary.strip()
    if not text:
        return None

    telemetry = NetworkTelemetry(network=network, raw_summary=text)
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip()
        line = raw.strip()
        if not line:
            index += 1
            continue

        if line == "Local Harvester":
            detail = _parse_detail_line(lines, index + 1)
            telemetry.local_harvester = HarvesterTelemetry(
                plot_count=detail[0],
                plot_size=detail[1],
                is_local=True,
            )
            index += 2
            continue

        remote = _REMOTE_RE.match(line)
        if remote:
            ip_address = remote.group("ip")
            detail = _parse_detail_line(lines, index + 1)
            telemetry.remote_harvesters[ip_address] = HarvesterTelemetry(
                plot_count=detail[0],
                plot_size=detail[1],
                ip_address=ip_address,
                is_local=False,
            )
            index += 2
            continue

        value = _value_after_colon(line)
        if value is not None:
            if line.startswith("Last height farmed:"):
                telemetry.last_farmed_height = value
            elif line.startswith("Plot count for all harvesters:"):
                telemetry.total_plot_count = _parse_count(value)
            elif line.startswith("Total size of plots:"):
                telemetry.total_plot_size = value
            elif line.startswith("Estimated network space:"):
                telemetry.estimated_network_space = value
            elif line.startswith("Expected time to win:"):
                telemetry.expected_time_to_win = value

        index += 1

    return telemetry if telemetry.has_metrics() or telemetry.local_harvester else None


def _value_after_colon(line: str) -> str | None:
    if ":" not in line:
        return None
    return line.split(":", 1)[1].strip()


def _parse_count(value: str) -> int | None:
    match = _COUNT_RE.search(value)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _parse_detail_line(lines: list[str], index: int) -> tuple[int | None, str | None]:
    if index >= len(lines):
        return None, None
    match = _PLOT_DETAIL_RE.match(lines[index].rstrip())
    if not match:
        return None, None
    count = int(match.group("count").replace(",", ""))
    size = match.group("size").strip()
    return count, size
