"""Application settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, *, refresh_interval_seconds: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Configure application preferences. Manual <b>Refresh fleet</b> remains "
            "available regardless of the auto-refresh interval."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self._refresh_interval = QSpinBox()
        self._refresh_interval.setRange(30, 3600)
        self._refresh_interval.setSingleStep(30)
        self._refresh_interval.setSuffix(" sec")
        self._refresh_interval.setValue(refresh_interval_seconds)
        self._refresh_interval.setToolTip("How often fleet telemetry refreshes automatically.")
        form.addRow("Fleet refresh interval:", self._refresh_interval)
        layout.addLayout(form)

        hint = QLabel("Recommended starting value: 120 seconds.")
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def refresh_interval_seconds(self) -> int:
        return int(self._refresh_interval.value())
