from __future__ import annotations

import os
from pathlib import Path

import asyncssh

from harvester_deploy.domain.models import Harvester, LogCallback
from harvester_deploy.persistence.keyring_support import get_passphrase


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

        connect_kwargs: dict = {
            "host": self.harvester.host,
            "port": self.harvester.ssh_port,
            "username": self.harvester.ssh_user,
            "known_hosts": None,
        }
        passphrase = get_passphrase(key_path)
        if passphrase:
            connect_kwargs["client_keys"] = [
                asyncssh.import_private_key(key_path, passphrase=passphrase)
            ]
        else:
            connect_kwargs["client_keys"] = [key_path]

        self._conn = await asyncssh.connect(**connect_kwargs)
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

    async def expand_remote_path(self, path: str) -> str:
        """Expand leading ~ using the remote user's home directory."""
        path = path.strip()
        if not path.startswith("~"):
            return path
        # Unquoted ~ so the remote shell expands it (quoted "~" does not expand).
        _, stdout, _ = await self.run(f"echo {path}", check=False, timeout=15)
        line = stdout.strip().splitlines()[-1].strip() if stdout.strip() else ""
        return line or path

    def shell_prelude(self, chia_root: str | None = None) -> str:
        """bash prelude: exit on error, enter chia root (~ expands when unquoted)."""
        root = chia_root or self.harvester.chia_root
        return f"set -euo pipefail\ncd {root}\n"

    def with_venv(self, command: str, *, chia_root: str | None = None) -> str:
        activate = self.harvester.activate_cmd
        return f"{self.shell_prelude(chia_root)}{activate}\n{command}\n"
