"""Fleet inventory manager — add, edit, remove nodes."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import Harvester, NodeRole
from harvester_deploy.gui.async_runner import AsyncLoopThread
from harvester_deploy.gui.widgets.node_editor_dialog import NodeEditorDialog
from harvester_deploy.persistence.config import AppConfig, DefaultsModel
from harvester_deploy.persistence.fleet_store import import_yaml_into_db, save_fleet
from harvester_deploy.persistence.paths import save_persisted_config_path


class InventoryDialog(QDialog):
    """Edit fleet nodes; Save writes SQLite + harvesters.yaml."""

    def __init__(
        self,
        config: AppConfig,
        config_path: Path,
        *,
        async_thread: AsyncLoopThread,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fleet inventory")
        self.setMinimumSize(720, 420)
        self._initial_config_path = config_path.resolve()
        self.config_path = config_path
        self._async = async_thread
        self._config = deepcopy(config)
        self.saved = False
        self.config_path_changed = False

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Manage nodes in the fleet. <b>Save</b> updates the local database "
                "and syncs <code>harvesters.yaml</code> for the CLI."
            )
        )

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Display", "Host", "Role", "Network", "Enabled"]
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        row = QHBoxLayout()
        add_btn = QPushButton("Add…")
        add_btn.clicked.connect(self._add)
        edit_btn = QPushButton("Edit…")
        edit_btn.clicked.connect(self._edit)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove)
        import_btn = QPushButton("Import from YAML…")
        import_btn.setToolTip("Load fleet from a harvesters.yaml file (file picker)")
        import_btn.clicked.connect(self._import_yaml)
        row.addWidget(add_btn)
        row.addWidget(edit_btn)
        row.addWidget(remove_btn)
        row.addStretch()
        row.addWidget(import_btn)
        layout.addLayout(row)

        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        save_btn.clicked.connect(self._save_all)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_table()

    def _defaults_hint(self) -> str:
        d = self._config.defaults
        return (
            f"ssh={d.ssh_user}, network={d.network}, "
            f"chia_root={d.chia_root}"
        )

    def _refresh_table(self) -> None:
        self._table.setRowCount(len(self._config.harvesters))
        for row, h in enumerate(self._config.harvesters):
            self._table.setItem(row, 0, QTableWidgetItem(h.id))
            self._table.setItem(row, 1, QTableWidgetItem(h.display_name))
            self._table.setItem(row, 2, QTableWidgetItem(h.host))
            self._table.setItem(row, 3, QTableWidgetItem(h.role_label))
            self._table.setItem(row, 4, QTableWidgetItem(h.network_label))
            enabled = "yes" if h.enabled else "no"
            self._table.setItem(row, 5, QTableWidgetItem(enabled))
        self._table.resizeColumnsToContents()

    def _selected_index(self) -> int | None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _add(self) -> None:
        dlg = NodeEditorDialog(
            None,
            self._config.harvesters,
            defaults_display=self._defaults_hint(),
            parent=self,
            async_thread=self._async,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.result_harvester is None:
            return
        self._config.harvesters.append(dlg.result_harvester)
        self._refresh_table()

    def _edit(self) -> None:
        idx = self._selected_index()
        if idx is None:
            QMessageBox.information(self, "Edit node", "Select a node first.")
            return
        current = self._config.harvesters[idx]
        dlg = NodeEditorDialog(
            current,
            self._config.harvesters,
            defaults_display=self._defaults_hint(),
            parent=self,
            async_thread=self._async,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.result_harvester is None:
            return
        self._config.harvesters[idx] = dlg.result_harvester
        self._refresh_table()

    def _remove(self) -> None:
        idx = self._selected_index()
        if idx is None:
            QMessageBox.information(self, "Remove node", "Select a node first.")
            return
        h = self._config.harvesters[idx]
        answer = QMessageBox.question(
            self,
            "Remove node",
            f"Remove {h.display_name} ({h.id}) from the fleet?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self._config.harvesters[idx]
        self._refresh_table()

    def _import_yaml(self) -> None:
        start_dir = self.config_path.parent
        if not start_dir.is_dir():
            from harvester_deploy.persistence.paths import default_config_dir

            start_dir = default_config_dir()
            start_dir.mkdir(parents=True, exist_ok=True)

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import harvesters.yaml",
            str(start_dir),
            "YAML files (*.yaml *.yml)",
        )
        if not path:
            return

        picked = Path(path)
        answer = QMessageBox.question(
            self,
            "Import from YAML",
            f"Replace the current inventory with:\n{picked}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._config = import_yaml_into_db(picked)
            self.config_path = picked
            self.config_path_changed = picked.resolve() != self._initial_config_path
            save_persisted_config_path(picked)
            self._refresh_table()
            QMessageBox.information(
                self,
                "Import complete",
                f"Inventory loaded from:\n{picked}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def _save_all(self) -> None:
        try:
            save_fleet(self._config, self.config_path)
            save_persisted_config_path(self.config_path)
            self.saved = True
            QMessageBox.information(
                self,
                "Saved",
                f"Fleet saved.\n\nDatabase and\n{self.config_path}",
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
