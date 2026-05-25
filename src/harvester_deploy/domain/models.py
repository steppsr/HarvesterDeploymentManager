from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable


class JobState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeRole(str, Enum):
    """Chia node role on a machine (harvester-only host vs full farmer node)."""

    HARVESTER = "harvester"
    FARMER = "farmer"


class ChiaNetwork(str, Enum):
    """Chia blockchain network for config paths and fleet grouping."""

    MAINNET = "mainnet"
    TESTNET = "testnet"


class InstallMode(str, Enum):
    """How Chia is installed on the remote host."""

    SOURCE = "source"  # git clone at chia_root (install.sh workflow)
    PACKAGE = "package"  # chia on PATH (.deb / GUI), no source tree
    UNKNOWN = "unknown"


@dataclass
class Harvester:
    """A deploy target: dedicated harvester or farmer machine (e.g. JABBA)."""

    id: str
    display_name: str
    host: str
    role: NodeRole = NodeRole.HARVESTER
    network: ChiaNetwork = ChiaNetwork.MAINNET
    ssh_port: int = 22
    ssh_user: str = "steve"
    ssh_key_path: str = "~/.ssh/id_ed25519"
    chia_root: str = "~/chia-blockchain"
    chia_config_dir: str = "~/.chia/mainnet/config"
    activate_cmd: str = ". ./activate"
    git_branch: str = "latest"
    upgrade_mode: str = "git"
    enabled: bool = True
    last_known_version: str | None = None
    farmer_host: str | None = None

    @property
    def start_service(self) -> str:
        """chia start argument: harvester | farmer."""
        return "farmer" if self.role == NodeRole.FARMER else "harvester"

    @property
    def role_label(self) -> str:
        return self.role.value

    @property
    def network_label(self) -> str:
        return "Mainnet" if self.network == ChiaNetwork.MAINNET else "Testnet"


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    message: str = ""
    output: str = ""


@dataclass
class DeployJob:
    harvester: Harvester
    state: JobState = JobState.IDLE
    started_at: datetime | None = None
    finished_at: datetime | None = None
    steps: list[StepResult] = field(default_factory=list)
    version_before: str | None = None
    version_after: str | None = None
    error: str | None = None
    skipped_upgrade: bool = False


LogCallback = Callable[[str, str], None]  # (node_id, line)
