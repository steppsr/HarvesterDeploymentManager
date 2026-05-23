from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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


@dataclass
class Harvester:
    id: str
    display_name: str
    host: str
    ssh_port: int = 22
    ssh_user: str = "steve"
    ssh_key_path: str = "~/.ssh/id_ed25519"
    chia_root: str = "~/chia-blockchain"
    activate_cmd: str = ". ./activate"
    git_branch: str = "latest"
    upgrade_mode: str = "git"
    enabled: bool = True
    last_known_version: str | None = None


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


LogCallback = Callable[[str, str], None]  # (harvester_id, line)
