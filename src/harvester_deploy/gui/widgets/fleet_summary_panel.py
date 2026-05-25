"""Farmer fleet summary (chia farm summary) from refresh."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import Harvester, NodeRole


class FleetSummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(
            QLabel(
                "<b>Farmer fleet summary</b> — from <code>chia farm summary</code> "
                "on farmer node(s). Use <b>Refresh fleet</b> on the Nodes tab."
            )
        )

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlaceholderText(
            "Refresh fleet to load chia farm summary from farmer node(s)."
        )
        self._text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._text, stretch=1)

    def update_from_status(
        self,
        harvesters: list[Harvester],
        results: list[dict | BaseException],
    ) -> None:
        blocks: list[str] = []
        for harvester, result in zip(harvesters, results, strict=True):
            if harvester.role != NodeRole.FARMER:
                continue
            if isinstance(result, BaseException):
                blocks.append(
                    f"=== {harvester.display_name} ({harvester.network_label}) ===\n"
                    f"Error: {result}"
                )
                continue
            summary = (result.get("summary") or "").strip()
            if not summary:
                summary = "(no farm summary — package node or command unavailable)"
            blocks.append(
                f"=== {harvester.display_name} ({harvester.network_label}) ===\n"
                f"{summary}"
            )

        if blocks:
            self._text.setPlainText("\n\n".join(blocks))
        else:
            self._text.setPlainText(
                "No farmer nodes in fleet, or refresh has not completed yet."
            )
