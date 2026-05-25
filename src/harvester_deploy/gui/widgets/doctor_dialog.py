"""Modal showing doctor check results for one node."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class DoctorDialog(QDialog):
    def __init__(self, node_id: str, checks: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Doctor — {node_id}")
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Health checks for <b>{node_id}</b>"))

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFontFamily("Consolas")
        text.setStyleSheet(
            "background-color: #ffffff; color: #1a1a1a; border: 1px solid #c8cdd3;"
        )
        lines = [f"{key}: {value}" for key, value in checks.items()]
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
