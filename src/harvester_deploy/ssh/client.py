from __future__ import annotations

import os
from pathlib import Path

import asyncssh

from harvester_deploy.domain.models import Harvester, LogCallback


def expand_key_path(path: str) -> str:
    return str(Path(path).expanduser())


class SshSession:
    """Async SSH session for one harvester."""

    def __init__(self, harvester: Harvester, on_log: LogCallback | None = None) -> None:
        self.harvester = harvester
        self._on_log = on_log
        self._conn: asyncssh.SSHClientConnection | None = None

    def _log(self, line: str) -> None:
        if self._on_log:
            self._on_log(self.harvester.id, line)

    async def connect(self) -> None:
        key_path = expand_key_path(self.harvester.ssh_key_path)
        if not Path(key_path).is_file():
            raise FileNotFoundError(f"SSH key not found: {key_path}")

        self._conn = await asyncssh.connect(
            self.harvester.host,
            port=self.harvester.ssh_port,
            username=self.harvester.ssh_user,
            client_keys=[key_path],
            known_hosts=None,
        )
        self._log(f"Connected to {self.harvester.ssh_user}@{self.harvester.host}")

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    async def run(
        self,
        script: str,
        *,
        check: bool = True,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        if not self._conn:
            raise RuntimeError("Not connected")

        self._log(f"$ {script[:120]}{'...' if len(script) > 120 else ''}")

        result = await self._conn.run(
            script,
            check=False,
            timeout=timeout,
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = (stdout + stderr).strip()

        for line in combined.splitlines():
            self._log(line)

        exit_status = result.exit_status if result.exit_status is not None else 1
        if check and exit_status != 0:
            detail = (stderr or stdout or "").strip()
            raise RuntimeError(
                f"Remote command failed (exit {exit_status})"
                + (f": {detail}" if detail else "")
            )

        return exit_status, stdout, stderr

    def shell_prelude(self) -> str:
        """bash prelude: exit on error, enter chia root."""
        root = self.harvester.chia_root
        return f"set -euo pipefail\ncd {root}\n"

    def with_venv(self, command: str) -> str:
        activate = self.harvester.activate_cmd
        return f"{self.shell_prelude()}{activate}\n{command}\n"
