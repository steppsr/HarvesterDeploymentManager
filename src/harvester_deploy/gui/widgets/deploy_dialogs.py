"""Deploy target, options, confirm, and summary dialogs."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import DeployJob, Harvester, JobState
from harvester_deploy.gui.services import DeployOptions
from harvester_deploy.recipes.engine import Recipe, load_recipe


@dataclass
class DeployTargetChoice:
    target_key: str  # all | harvesters | farmers | node id
    label: str


_TARGET_ROLE = Qt.ItemDataRole.UserRole


class DeployWizardDialog(QDialog):
    """Choose targets and advanced options."""

    def __init__(
        self,
        harvesters: list[Harvester],
        parent: QWidget | None = None,
        *,
        preset_target: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Deploy")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Deploy targets</b>"))
        self._target = QComboBox()
        self._add_target_item("All enabled nodes", "all")
        self._add_target_item("Harvesters only", "harvesters")
        self._add_target_item("Farmers only", "farmers")
        for h in harvesters:
            self._add_target_item(f"Single node: {h.display_name} ({h.id})", h.id)
        if preset_target:
            idx = self._target.findData(preset_target, _TARGET_ROLE)
            if idx >= 0:
                self._target.setCurrentIndex(idx)
            self._target.setEnabled(False)
        layout.addWidget(self._target)

        layout.addWidget(QLabel("<b>Advanced options</b>"))
        form = QFormLayout()
        self._parallel = QSpinBox()
        self._parallel.setRange(1, 6)
        self._parallel.setValue(2)
        form.addRow("Parallel jobs:", self._parallel)

        self._dry_run = QCheckBox("Dry run (list steps only, no changes)")
        self._force = QCheckBox("Force full upgrade even when git is up to date")
        form.addRow(self._dry_run)
        form.addRow(self._force)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_target_item(self, label: str, key: str) -> None:
        self._target.addItem(label)
        self._target.setItemData(self._target.count() - 1, key, _TARGET_ROLE)

    def target_key(self) -> str:
        key = self._target.currentData(_TARGET_ROLE)
        return str(key) if key is not None else "all"

    def options(self) -> DeployOptions:
        return DeployOptions(
            parallel=self._parallel.value(),
            dry_run=self._dry_run.isChecked(),
            force=self._force.isChecked(),
        )


class ConfirmDeployDialog(QDialog):
    def __init__(
        self,
        targets: list[Harvester],
        recipe: Recipe,
        *,
        dry_run: bool,
        excluded_package: list[Harvester],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm deploy")
        self.setMinimumSize(520, 400)

        layout = QVBoxLayout(self)

        if dry_run:
            layout.addWidget(
                QLabel("<b style='color:#856404'>DRY RUN</b> — no remote changes will be made.")
            )
        else:
            layout.addWidget(
                QLabel(
                    "<b>Warning:</b> This will stop Chia, update git, run install.sh, "
                    "and restart services. Expect downtime on each node."
                )
            )

        layout.addWidget(QLabel(f"<b>Nodes to deploy ({len(targets)}):</b>"))
        node_list = QListWidget()
        for h in targets:
            node_list.addItem(f"{h.display_name} ({h.id}) — {h.host} [{h.role_label}]")
        layout.addWidget(node_list)

        if excluded_package:
            layout.addWidget(
                QLabel(
                    f"<b>Excluded ({len(excluded_package)}):</b> package install "
                    "(upgrade via .deb, not git deploy)"
                )
            )
            ex = QListWidget()
            for h in excluded_package:
                ex.addItem(f"{h.display_name} ({h.id})")
            layout.addWidget(ex)

        layout.addWidget(QLabel(f"<b>Recipe:</b> {recipe.name}"))
        steps = QListWidget()
        for step in recipe.steps:
            steps.addItem(f"{step.id}: {step.description}")
        steps.setMaximumHeight(140)
        layout.addWidget(steps)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start deploy")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class DeploySummaryDialog(QDialog):
    def __init__(
        self,
        jobs: list[DeployJob],
        summary_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Deploy complete")
        self.setMinimumSize(640, 320)

        layout = QVBoxLayout(self)
        success = sum(1 for j in jobs if j.state == JobState.SUCCESS)
        failed = sum(1 for j in jobs if j.state == JobState.FAILED)
        layout.addWidget(
            QLabel(
                f"<b>Finished:</b> {success} succeeded, {failed} failed "
                f"(of {len(jobs)} total)"
            )
        )

        table = QTableWidget(len(jobs), 5)
        table.setHorizontalHeaderLabels(
            ["ID", "Role", "State", "Before", "After / Note"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        for row, job in enumerate(jobs):
            note = ""
            if job.skipped_upgrade:
                note = "skipped (up to date)"
            elif job.error:
                note = (job.error or "")[:60]
            after = job.version_after or note or "-"
            table.setItem(row, 0, QTableWidgetItem(job.harvester.id))
            table.setItem(row, 1, QTableWidgetItem(job.harvester.role_label))
            table.setItem(row, 2, QTableWidgetItem(job.state.value))
            table.setItem(row, 3, QTableWidgetItem(job.version_before or "-"))
            table.setItem(row, 4, QTableWidgetItem(after))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        layout.addWidget(QLabel(f"Summary JSON: {summary_path}"))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)
