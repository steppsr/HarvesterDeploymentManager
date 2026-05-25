"""Thread-safe deploy log forwarding to the Qt GUI."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from harvester_deploy.domain.models import LogCallback


class DeployLogHub(QObject):
    """Emit log lines on the GUI thread (safe from asyncio worker thread)."""

    line_emitted = Signal(str, str)  # node_id, line

    def __call__(self, node_id: str, line: str) -> None:
        self.line_emitted.emit(node_id, line)

    def callback(self) -> LogCallback:
        return self
