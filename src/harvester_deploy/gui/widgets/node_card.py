"""Single-node dashboard card."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import (
    ChiaNetwork,
    DeployJob,
    Harvester,
    InstallMode,
    JobState,
    NodeRole,
)

CARD_MIN_WIDTH = 280
CARD_MAX_WIDTH = 400
_PACKAGE_NOTE_TEXT = (
    "Package install — upgrade via .deb (git deploy not supported)"
)


class NodeCard(QFrame):
    """Card showing one fleet node; emits action requests."""

    doctor_requested = Signal(str)
    test_ssh_requested = Signal(str)
    deploy_requested = Signal(str)
    history_requested = Signal(str)
    log_requested = Signal(str)

    def __init__(self, harvester: Harvester, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.harvester = harvester
        self.install_mode: str | None = None
        self.setObjectName("nodeCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Fixed width: up to CARD_MAX_WIDTH without stretching to fill the window.
        self.setFixedWidth(CARD_MAX_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        header = QHBoxLayout()
        self._title = QLabel(harvester.display_name)
        title_font = self._title.font()
        title_font.setPointSize(title_font.pointSize() + 2)
        title_font.setBold(True)
        self._title.setFont(title_font)
        self._title.setStyleSheet("color: #1a1a1a;")
        header.addWidget(self._title)
        header.addStretch()
        self._network_badge = QLabel(harvester.network_label)
        self._role_badge = QLabel(harvester.role_label)
        self._install_badge = QLabel("—")
        for badge in (self._network_badge, self._role_badge, self._install_badge):
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self._network_badge)
        header.addWidget(self._role_badge)
        header.addWidget(self._install_badge)
        root.addLayout(header)

        self._host = QLabel(f"Host: {harvester.host}")
        self._host.setStyleSheet("color: #666;")
        root.addWidget(self._host)

        self._deploy_step = QLabel("")
        self._deploy_step.setStyleSheet("color: #4a6fa5; font-weight: 600; font-size: 11px;")
        self._deploy_step.hide()
        root.addWidget(self._deploy_step)

        label_style = "color: #495057; font-weight: 600;"
        value_style = "color: #1a1a1a;"
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        self._version_value = QLabel("—")
        self._behind_value = QLabel("—")
        self._status_value = QLabel("—")
        self._status_value.setWordWrap(True)
        for row, (lbl, val) in enumerate(
            (
                ("Version", self._version_value),
                ("Behind", self._behind_value),
                ("Status", self._status_value),
            )
        ):
            name = QLabel(lbl)
            name.setStyleSheet(label_style)
            val.setStyleSheet(value_style)
            grid.addWidget(name, row, 0)
            grid.addWidget(val, row, 1)
        root.addLayout(grid)

        self._upgrade_hint = QLabel("")
        self._upgrade_hint.hide()
        root.addWidget(self._upgrade_hint)

        self._package_note = QLabel("")
        self._package_note.setWordWrap(True)
        self._package_note.setMinimumHeight(self._package_note_reserved_height())
        root.addWidget(self._package_note)
        self._set_package_note_row(show_text=False)

        actions = QHBoxLayout()
        self._btn_doctor = QPushButton("Doctor")
        self._btn_ssh = QPushButton("Test SSH")
        self._btn_history = QPushButton("History")
        self._btn_log = QPushButton("Log")
        self._btn_deploy = QPushButton("Deploy")
        self._btn_doctor.clicked.connect(
            lambda: self.doctor_requested.emit(self.harvester.id)
        )
        self._btn_ssh.clicked.connect(
            lambda: self.test_ssh_requested.emit(self.harvester.id)
        )
        self._btn_deploy.clicked.connect(
            lambda: self.deploy_requested.emit(self.harvester.id)
        )
        self._btn_history.clicked.connect(
            lambda: self.history_requested.emit(self.harvester.id)
        )
        self._btn_log.clicked.connect(
            lambda: self.log_requested.emit(self.harvester.id)
        )
        self._btn_log.setToolTip("Show this node's lines on the Logs tab")
        actions.addWidget(self._btn_doctor)
        actions.addWidget(self._btn_ssh)
        actions.addWidget(self._btn_history)
        actions.addWidget(self._btn_log)
        actions.addWidget(self._btn_deploy)
        root.addLayout(actions)

        self._apply_role_style()
        self._apply_network_style()
        self._update_deploy_button()
        self.set_busy(False)

    def _apply_network_style(self) -> None:
        if self.harvester.network == ChiaNetwork.TESTNET:
            self._network_badge.setStyleSheet(
                "background: #6f42c1; color: white; border-radius: 4px; padding: 2px 6px;"
            )
        else:
            self._network_badge.setStyleSheet(
                "background: #0d6efd; color: white; border-radius: 4px; padding: 2px 6px;"
            )

    def _apply_role_style(self) -> None:
        if self.harvester.role == NodeRole.FARMER:
            self._role_badge.setStyleSheet(
                "background: #4a6fa5; color: white; border-radius: 4px; padding: 2px 6px;"
            )
        else:
            self._role_badge.setStyleSheet(
                "background: #5a8f5a; color: white; border-radius: 4px; padding: 2px 6px;"
            )

    def _update_deploy_button(self) -> None:
        if self.install_mode == InstallMode.PACKAGE.value:
            self._btn_deploy.setEnabled(False)
            self._btn_deploy.setToolTip("Package install — upgrade via .deb")
        else:
            self._btn_deploy.setEnabled(True)
            self._btn_deploy.setToolTip("Deploy this node only")

    def set_busy(self, busy: bool) -> None:
        self._btn_doctor.setEnabled(not busy)
        self._btn_ssh.setEnabled(not busy)
        self._btn_history.setEnabled(not busy)
        self._btn_log.setEnabled(True)
        if self.install_mode != InstallMode.PACKAGE.value:
            self._btn_deploy.setEnabled(not busy)
        if busy:
            self._status_value.setText("Working…")
            self._status_value.setStyleSheet("color: #4a6fa5; font-weight: 600;")
            self.setProperty("busy", True)
        else:
            self._status_value.setStyleSheet("color: #1a1a1a;")
            self.setProperty("busy", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_deploying(self, active: bool) -> None:
        if active:
            self.set_busy(True)
            self._deploy_step.setText("Deploying…")
            self._deploy_step.show()
        else:
            self._deploy_step.hide()
            self.set_busy(False)

    def set_deploy_step(self, step_id: str) -> None:
        self._deploy_step.setText(f"Step: {step_id}")
        self._deploy_step.show()

    def apply_status(self, data: dict) -> None:
        mode = data.get("install_mode", "unknown")
        self.install_mode = mode
        self._install_badge.setText(mode)
        if mode == InstallMode.SOURCE.value:
            self._install_badge.setStyleSheet(
                "background: #e8f4e8; color: #2d5a2d; border-radius: 4px; padding: 2px 6px;"
            )
        elif mode == InstallMode.PACKAGE.value:
            self._install_badge.setStyleSheet(
                "background: #fff3cd; color: #856404; border-radius: 4px; padding: 2px 6px;"
            )
        else:
            self._install_badge.setStyleSheet(
                "background: #f0f0f0; color: #555; border-radius: 4px; padding: 2px 6px;"
            )

        self._version_value.setText(str(data.get("version", "—")))
        behind = data.get("commits_behind", "—")
        self._behind_value.setText(str(behind))
        summary = (data.get("summary") or "").strip()
        if summary:
            short = summary.splitlines()[0]
            if len(short) > 72:
                short = short[:69] + "…"
            self._status_value.setText(short)
        else:
            self._status_value.setText("—")

        self._show_upgrade_hint(behind)
        self._show_package_note(mode)
        self._update_deploy_button()
        self.set_busy(False)
        self.set_error(False)

    def apply_deploy_job(self, job: DeployJob) -> None:
        self._deploy_step.hide()
        self.setProperty("failed", job.state == JobState.FAILED)
        if job.skipped_upgrade:
            self._status_value.setText("Skipped (up to date)")
        elif job.state == JobState.SUCCESS:
            self._status_value.setText(f"OK → {job.version_after or '—'}")
            self._version_value.setText(job.version_after or "—")
        else:
            self._status_value.setText((job.error or "failed")[:80])
        self.set_busy(False)
        self.style().unpolish(self)
        self.style().polish(self)

    def _show_upgrade_hint(self, behind: str | int) -> None:
        try:
            n = int(str(behind))
        except (TypeError, ValueError):
            self._upgrade_hint.hide()
            return
        if n > 0:
            self._upgrade_hint.setText(f"Upgrade available ({n} commit(s) behind)")
            self._upgrade_hint.setStyleSheet("color: #c0392b; font-weight: bold;")
            self._upgrade_hint.show()
        else:
            self._upgrade_hint.hide()

    def _package_note_reserved_height(self) -> int:
        probe = QLabel(_PACKAGE_NOTE_TEXT)
        probe.setWordWrap(True)
        probe.setStyleSheet("color: #8a6d3b; font-size: 11px;")
        probe.setFont(self.font())
        width = CARD_MAX_WIDTH - 24
        height = probe.heightForWidth(width)
        return max(height, probe.sizeHint().height(), 20)

    def _set_package_note_row(self, *, show_text: bool) -> None:
        """Keep row height on all cards; text only for package installs."""
        self._package_note.show()
        if show_text:
            self._package_note.setText(_PACKAGE_NOTE_TEXT)
            self._package_note.setStyleSheet("color: #8a6d3b; font-size: 11px;")
        else:
            self._package_note.setText("")
            self._package_note.setStyleSheet("font-size: 11px;")

    def _show_package_note(self, mode: str) -> None:
        self._set_package_note_row(show_text=mode == InstallMode.PACKAGE.value)

    def set_error(self, message: str | bool) -> None:
        if message is False:
            self.setProperty("failed", False)
            self.style().unpolish(self)
            self.style().polish(self)
            return
        self.setProperty("failed", True)
        self._status_value.setText(str(message))
        self.set_busy(False)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_ssh_result(self, ok: bool) -> None:
        self.set_busy(False)
        if ok:
            self._status_value.setText("SSH: ok")
            self.set_error(False)
        else:
            self.set_error("SSH: failed")
