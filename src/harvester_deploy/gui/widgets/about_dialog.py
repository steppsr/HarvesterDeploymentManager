"""About dialog for Harvester Deployment Manager."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from harvester_deploy import __version__
from harvester_deploy.gui.resources import app_icon, icon_path
from harvester_deploy.gui.styles import current_theme_mode, theme_colors


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Harvester Deployment Manager")
        self.setMinimumWidth(736)
        icon = app_icon()
        if icon is not None:
            self.setWindowIcon(icon)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        colors = theme_colors(current_theme_mode())

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 72, 0)
        logo = QLabel()
        logo_path = icon_path()
        if logo_path is not None:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        64,
                        64,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        header.addWidget(logo, alignment=Qt.AlignmentFlag.AlignTop)

        body = QLabel(
            f"""
<h2 style="margin:0;">Harvester Deployment Manager</h2>
<p style="margin:4px 0 12px 0;"><b>Version {__version__}</b></p>
<p>A personal tool for managing and deploying Chia updates across your
harvester fleet.</p>
<p>Built to make upgrading your Ubuntu harvesters fast, reliable, and
painless — with live monitoring and one-click (or one-command) deployments
from your Windows machine.</p>
<p><b>Features:</b></p>
<ul style="margin-top:4px;">
<li>SSH-based agentless deployments</li>
<li>Individual or bulk harvester updates</li>
<li>Real-time progress and logging</li>
<li>Harvester inventory management</li>
</ul>
<p style="margin-top:16px;"><b>Created by Steve Stepp</b> (steppsr)<br>
For my personal Chia farm</p>
<p style="color:{colors.text_muted}; margin-top:12px;">
Copyright © 2026 Steve Stepp<br>
Licensed under the Apache License, Version 2.0.
See the <b>LICENSE</b> file in the project repository for full terms.</p>
<p style="color:{colors.text_muted}; font-size:11px; margin-top:8px;">
This is a personal, open-source project and is not affiliated with or
endorsed by Chia Network Inc.</p>
"""
        )
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setOpenExternalLinks(True)
        body.setStyleSheet(f"color: {colors.text_primary};")
        header.addWidget(body, stretch=1)
        layout.addLayout(header)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
