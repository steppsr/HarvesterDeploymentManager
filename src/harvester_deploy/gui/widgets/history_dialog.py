"""Deploy history — per-node timeline and fleet run details."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import Harvester
from harvester_deploy.persistence.history import (
    DeployRunJobRow,
    get_run_summary,
    import_json_summaries,
    list_node_history,
    list_run_jobs,
)


def _format_when(row: DeployRunJobRow) -> str:
    when = row.finished_at or row.started_at or row.run_ts
    if not when:
        return row.run_ts
    return when.replace("T", " ").replace("+00:00", " UTC")[:22]


def _note_for_row(row: DeployRunJobRow) -> str:
    if row.skipped_upgrade:
        return "skipped (up to date)"
    if row.error:
        return (row.error or "")[:80]
    return row.version_after or "—"


class DeployRunDetailDialog(QDialog):
    """All nodes in one fleet deploy run."""

    def __init__(self, run_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Deploy run details")
        self.setMinimumSize(640, 360)

        summary = get_run_summary(run_id)
        jobs = list_run_jobs(run_id)

        layout = QVBoxLayout(self)
        if summary:
            dry = " (dry run)" if summary.dry_run else ""
            layout.addWidget(
                QLabel(
                    f"<b>Run {summary.run_ts}</b>{dry} — "
                    f"{summary.success_count} ok, {summary.failed_count} failed "
                    f"(of {summary.total})"
                )
            )
            if summary.json_path:
                path_row = QHBoxLayout()
                path_row.addWidget(QLabel(f"JSON: {summary.json_path}"))
                open_btn = QPushButton("Open folder")
                open_btn.clicked.connect(
                    lambda: QDesktopServices.openUrl(
                        Path(summary.json_path).parent.as_uri()
                    )
                )
                path_row.addWidget(open_btn)
                path_row.addStretch()
                layout.addLayout(path_row)

        table = QTableWidget(len(jobs), 5)
        table.setHorizontalHeaderLabels(
            ["ID", "State", "Before", "After / Note", "Skipped"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        for row_i, job in enumerate(jobs):
            table.setItem(row_i, 0, QTableWidgetItem(job.node_id))
            table.setItem(row_i, 1, QTableWidgetItem(job.state))
            table.setItem(row_i, 2, QTableWidgetItem(job.version_before or "—"))
            table.setItem(row_i, 3, QTableWidgetItem(_note_for_row(job)))
            table.setItem(
                row_i,
                4,
                QTableWidgetItem("yes" if job.skipped_upgrade else ""),
            )
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)


class HistoryDialog(QDialog):
    def __init__(
        self,
        harvesters: list[Harvester],
        *,
        initial_node_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Deploy history")
        self.setMinimumSize(760, 420)

        imported = import_json_summaries()
        if imported:
            QMessageBox.information(
                self,
                "History imported",
                f"Imported {imported} past run(s) from deployments/*.json.",
            )

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Timeline for the selected node. Skipped (up-to-date) runs are included. "
                "Double-click a row to view the full fleet run."
            )
        )

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Node:"))
        self._node_combo = QComboBox()
        self._node_combo.setMinimumWidth(200)
        ids = [h.id for h in harvesters]
        for hid in ids:
            h = next(x for x in harvesters if x.id == hid)
            self._node_combo.addItem(f"{h.display_name} ({hid})", hid)
        if initial_node_id and initial_node_id in ids:
            self._node_combo.setCurrentIndex(ids.index(initial_node_id))
        self._node_combo.currentIndexChanged.connect(self._reload_table)
        filter_row.addWidget(self._node_combo)
        filter_row.addStretch()
        import_btn = QPushButton("Import JSON…")
        import_btn.setToolTip("Scan deployments/ for summary.json not yet in SQLite")
        import_btn.clicked.connect(self._import_json)
        filter_row.addWidget(import_btn)
        layout.addLayout(filter_row)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["When", "Run", "State", "Before", "After / Note", "Dry run"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Stretch
        )
        self._table.doubleClicked.connect(self._open_run_detail)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        view_btn = QPushButton("View fleet run…")
        view_btn.clicked.connect(self._open_run_detail)
        btn_row.addWidget(view_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.clicked.connect(self.accept)
        layout.addWidget(buttons)

        self._reload_table()

    def _current_node_id(self) -> str:
        return self._node_combo.currentData(Qt.ItemDataRole.UserRole)

    def _reload_table(self) -> None:
        node_id = self._current_node_id()
        rows = list_node_history(node_id)
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            when_item = QTableWidgetItem(_format_when(row))
            when_item.setData(Qt.ItemDataRole.UserRole, row.run_id)
            self._table.setItem(i, 0, when_item)
            self._table.setItem(i, 1, QTableWidgetItem(row.run_ts))
            self._table.setItem(i, 2, QTableWidgetItem(row.state))
            self._table.setItem(i, 3, QTableWidgetItem(row.version_before or "—"))
            self._table.setItem(i, 4, QTableWidgetItem(_note_for_row(row)))
            self._table.setItem(
                i, 5, QTableWidgetItem("yes" if row.dry_run else "")
            )
        self._table.resizeColumnsToContents()

    def _selected_run_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        run_id = item.data(Qt.ItemDataRole.UserRole)
        return int(run_id) if run_id is not None else None

    def _open_run_detail(self) -> None:
        run_id = self._selected_run_id()
        if run_id is None:
            QMessageBox.information(
                self, "Deploy history", "Select a row to view the fleet run."
            )
            return
        DeployRunDetailDialog(run_id, self).exec()

    def _import_json(self) -> None:
        count = import_json_summaries()
        if count:
            QMessageBox.information(
                self, "Import complete", f"Imported {count} run(s)."
            )
            self._reload_table()
        else:
            QMessageBox.information(
                self,
                "Import complete",
                "No new summary.json files found under deployments/.",
            )
