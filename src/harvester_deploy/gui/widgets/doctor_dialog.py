"""Modal showing doctor check results for one node."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from harvester_deploy.gui.styles import current_theme_mode, theme_colors


class DoctorDialog(QDialog):
    def __init__(self, node_id: str, checks: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Doctor — {node_id}")
        self.setMinimumSize(480, 360)
        colors = theme_colors(current_theme_mode())

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Health checks for <b>{node_id}</b>"))

        text = QTextEdit()
        text.setReadOnly(True)
        text.setFontFamily("Consolas")
        text.setStyleSheet(
            f"background-color: {colors.input_bg}; color: {colors.input_text}; "
            f"border: 1px solid {colors.border};"
        )
        lines = [f"{key}: {value}" for key, value in checks.items()]
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
