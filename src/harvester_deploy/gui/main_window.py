"""Harvester Deployment Manager — main window."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import (
    ChiaNetwork,
    Harvester,
    InstallMode,
    JobState,
    NodeRole,
)
from harvester_deploy.persistence.config import AppConfig
from harvester_deploy.gui.async_runner import AsyncLoopThread, AsyncTaskBridge
from harvester_deploy.gui.log_hub import DeployLogHub
from harvester_deploy.gui.services import (
    DeployOptions,
    fleet_deploy,
    fleet_status,
    node_doctor,
    node_test_ssh,
)
from harvester_deploy.gui.resources import app_icon
from harvester_deploy.gui.styles import APP_STYLESHEET
from harvester_deploy.gui.widgets.fleet_summary_panel import FleetSummaryPanel
from harvester_deploy.gui.widgets import (
    AboutDialog,
    ConfirmDeployDialog,
    InventoryDialog,
    DeploySummaryDialog,
    DeployWizardDialog,
    DoctorDialog,
    HistoryDialog,
    LogPanel,
    NodeCard,
)
from harvester_deploy.gui.widgets.node_card import CARD_MAX_WIDTH
from harvester_deploy.persistence.config import resolve_targets
from harvester_deploy.persistence.paths import (
    default_config_dir,
    default_config_path,
    ensure_app_directories,
    is_frozen,
    resolve_config_path,
    save_persisted_config_path,
    seed_config_if_empty,
)
from harvester_deploy.persistence.fleet_store import config_dir, load_fleet
from harvester_deploy.recipes.engine import load_recipe
from harvester_deploy.reporting.summary import write_summary

_STEP_RE = re.compile(r"--- step:\s*(\S+)")
# Horizontal space per grid column (fixed card width + spacing).
_CARD_GRID_SPACING = 16
_CARD_CELL_WIDTH = CARD_MAX_WIDTH + _CARD_GRID_SPACING
_CARDS_AREA_MIN_HEIGHT = 100
_CARD_ROW_HEIGHT_FALLBACK = 340
_TAB_NODES = 0
_TAB_FLEET = 1
_TAB_LOGS = 2

_FILTER_OPTIONS: list[tuple[str, str]] = [
    ("All nodes", "all"),
    ("Harvesters only", "harvesters"),
    ("Farmers only", "farmers"),
    ("Mainnet only", "mainnet"),
    ("Testnet only", "testnet"),
]


class MainWindow(QMainWindow):
    def __init__(self, config_path: Path | None = None) -> None:
        super().__init__()
        self._config_path = resolve_config_path(config_path)
        self._async = AsyncLoopThread()
        self._async.start()
        self._pending_ops = 0
        self._deploy_active = False
        self._deploying_ids: set[str] = set()

        self._log_hub = DeployLogHub(self)
        self._log_hub.line_emitted.connect(self._on_deploy_log_line)

        self.setWindowTitle("Harvester Deployment Manager")
        self.resize(1200, 820)

        self._app_config: AppConfig | None = None
        self._harvesters: list[Harvester] = []
        self._cards: dict[str, NodeCard] = {}
        self._filter = "all"
        self._last_card_cols: int | None = None

        self._build_menu()
        self._build_central()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        try:
            self._reload_config()
        except FileNotFoundError as exc:
            self._prompt_for_config(str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Config error", str(exc))

        QTimer.singleShot(500, self._refresh_fleet)

    def _build_menu(self) -> None:
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)

        fleet_menu = menu_bar.addMenu("&Fleet")
        self._menu_refresh = QAction("&Refresh fleet", self)
        self._menu_refresh.setShortcut(QKeySequence("Ctrl+R"))
        self._menu_refresh.triggered.connect(self._refresh_fleet)
        fleet_menu.addAction(self._menu_refresh)

        self._menu_deploy = QAction("&Deploy…", self)
        self._menu_deploy.setShortcut(QKeySequence("Ctrl+D"))
        self._menu_deploy.triggered.connect(self._open_deploy_wizard)
        fleet_menu.addAction(self._menu_deploy)
        fleet_menu.addSeparator()
        fleet_menu.addAction("Manage &inventory…", self._manage_inventory)
        fleet_menu.addAction("Deploy &history…", self._open_deploy_history)
        fleet_menu.addAction("Choose config &file…", self._choose_config_file)
        fleet_menu.addAction("Open config &folder", self._open_config_folder)

        help_menu = menu_bar.addMenu("&Help")
        about_act = QAction("&About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setSpacing(12)
        outer.setContentsMargins(12, 12, 12, 12)

        self._summary = QLabel("Loading fleet from config…")
        self._summary.setWordWrap(True)
        outer.addWidget(self._summary)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # --- Nodes tab (action bar + card grid) ---
        nodes_tab = QWidget()
        nodes_layout = QVBoxLayout(nodes_tab)
        nodes_layout.setSpacing(10)
        nodes_layout.setContentsMargins(8, 8, 8, 8)

        action_bar = QFrame()
        action_bar.setObjectName("actionBar")
        action_row = QHBoxLayout(action_bar)
        action_row.setContentsMargins(12, 10, 12, 10)
        action_row.setSpacing(12)

        self._btn_refresh = QPushButton("Refresh fleet")
        self._btn_refresh.clicked.connect(self._refresh_fleet)
        action_row.addWidget(self._btn_refresh)

        self._btn_deploy = QPushButton("Deploy…")
        self._btn_deploy.setToolTip("Deploy upgrade to selected targets (Ctrl+D)")
        self._btn_deploy.clicked.connect(self._open_deploy_wizard)
        action_row.addWidget(self._btn_deploy)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedWidth(160)
        self._progress.hide()
        action_row.addWidget(self._progress)

        action_row.addSpacing(16)
        filter_caption = QLabel("Show:")
        filter_caption.setObjectName("inlineCaption")
        action_row.addWidget(filter_caption)

        self._filter_combo = QComboBox()
        self._filter_combo.setMinimumWidth(180)
        for label, key in _FILTER_OPTIONS:
            self._filter_combo.addItem(label, key)
        self._filter_combo.currentIndexChanged.connect(self._on_filter_index)
        action_row.addWidget(self._filter_combo)
        action_row.addStretch()
        nodes_layout.addWidget(action_bar)

        self._card_scroll = QScrollArea()
        self._card_scroll.setWidgetResizable(True)
        self._card_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._grid_host = QWidget()
        self._grid_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(_CARD_GRID_SPACING)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._card_scroll.setWidget(self._grid_host)
        self._card_scroll.viewport().installEventFilter(self)
        nodes_layout.addWidget(self._card_scroll, stretch=1)

        self._tabs.addTab(nodes_tab, "Nodes")

        self._fleet_summary = FleetSummaryPanel()
        self._tabs.addTab(self._fleet_summary, "Fleet summary")

        self._log_panel = LogPanel()
        self._tabs.addTab(self._log_panel, "Logs")

        outer.addWidget(self._tabs, stretch=1)

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _reload_config(self) -> None:
        self._app_config, sync_note = load_fleet(self._config_path)
        self._harvesters = [h for h in self._app_config.harvesters if h.enabled]
        self._rebuild_cards()
        self._update_summary_label()
        all_ids = [h.id for h in self._app_config.harvesters]
        self._log_panel.set_nodes(all_ids)
        if sync_note:
            self.statusBar().showMessage(sync_note, 10000)

    def _manage_inventory(self) -> None:
        if self._app_config is None:
            return
        dlg = InventoryDialog(
            self._app_config,
            self._config_path,
            async_thread=self._async,
            parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and (
            dlg.saved or dlg.config_path_changed
        ):
            self._config_path = dlg.config_path
            self._last_card_cols = None
            self._reload_config()
            QTimer.singleShot(300, self._refresh_fleet)

    def _open_config_folder(self) -> None:
        folder = config_dir(self._config_path)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _choose_config_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        start = self._config_path.parent if self._config_path.parent.is_dir() else default_config_dir()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose harvesters.yaml",
            str(start),
            "YAML files (*.yaml *.yml)",
        )
        if not path:
            return
        self._config_path = Path(path)
        try:
            save_persisted_config_path(self._config_path)
            self._reload_config()
            self.statusBar().showMessage(f"Using config: {self._config_path}", 8000)
        except Exception as exc:
            QMessageBox.critical(self, "Config error", str(exc))

    def _prompt_for_config(self, message: str) -> None:
        from PySide6.QtWidgets import QFileDialog

        hint = message
        if is_frozen():
            hint += (
                "\n\nThe installed app keeps config under:\n"
                f"{default_config_dir()}"
            )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Fleet config")
        box.setText(hint)
        choose = box.addButton("Choose harvesters.yaml…", QMessageBox.ButtonRole.AcceptRole)
        open_folder = box.addButton("Open config folder", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        clicked = box.clickedButton()
        if clicked == choose:
            start = default_config_dir()
            start.mkdir(parents=True, exist_ok=True)
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose harvesters.yaml",
                str(start),
                "YAML files (*.yaml *.yml)",
            )
            if path:
                self._config_path = Path(path)
                try:
                    save_persisted_config_path(self._config_path)
                    self._reload_config()
                except Exception as exc:
                    QMessageBox.critical(self, "Config error", str(exc))
        elif clicked == open_folder:
            ensure_app_directories()
            seed_config_if_empty()
            self._config_path = default_config_path()
            self._open_config_folder()

    def _open_deploy_history(self, node_id: str | None = None) -> None:
        if not self._harvesters:
            QMessageBox.information(
                self, "Deploy history", "No nodes in fleet inventory."
            )
            return
        HistoryDialog(
            self._harvesters,
            initial_node_id=node_id,
            parent=self,
        ).exec()

    def _on_node_history(self, node_id: str) -> None:
        self._open_deploy_history(node_id)

    def _rebuild_cards(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

        for harvester in self._harvesters:
            card = NodeCard(harvester)
            card.doctor_requested.connect(self._on_doctor)
            card.test_ssh_requested.connect(self._on_test_ssh)
            card.history_requested.connect(self._on_node_history)
            card.deploy_requested.connect(self._deploy_single_node)
            card.log_requested.connect(self._on_node_log)
            self._cards[harvester.id] = card

        self._last_card_cols = None
        self._relayout_card_grid()

    def _harvester_by_id(self, node_id: str) -> Harvester | None:
        for h in self._harvesters:
            if h.id == node_id:
                return h
        return None

    def _on_node_log(self, node_id: str) -> None:
        self._tabs.setCurrentIndex(_TAB_LOGS)
        self._log_panel.focus_node(node_id)

    def _on_filter_index(self, index: int) -> None:
        key = self._filter_combo.itemData(index, Qt.ItemDataRole.UserRole)
        self._filter = key if key else "all"
        self._last_card_cols = None
        self._relayout_card_grid()

    def _filtered_harvesters(self) -> list[Harvester]:
        nodes = list(self._harvesters)
        if self._filter == "harvesters":
            nodes = [h for h in nodes if h.role == NodeRole.HARVESTER]
        elif self._filter == "farmers":
            nodes = [h for h in nodes if h.role == NodeRole.FARMER]
        elif self._filter == "mainnet":
            nodes = [h for h in nodes if h.network == ChiaNetwork.MAINNET]
        elif self._filter == "testnet":
            nodes = [h for h in nodes if h.network == ChiaNetwork.TESTNET]
        return nodes

    def _cards_viewport_width(self) -> int:
        width = self._card_scroll.viewport().width()
        if width > 0:
            return width
        return max(self._tabs.width(), self.width() - 48, _CARD_CELL_WIDTH)

    def _column_count(self) -> int:
        return max(1, self._cards_viewport_width() // _CARD_CELL_WIDTH)

    def _relayout_card_grid(self) -> None:
        while self._grid.count():
            self._grid.takeAt(0)

        visible = self._filtered_harvesters()
        visible_ids = {h.id for h in visible}
        cols = self._column_count()

        align = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        for index, harvester in enumerate(visible):
            card = self._cards[harvester.id]
            card.show()
            row, col = index // cols, index % cols
            self._grid.addWidget(card, row, col, align)

        for c in range(cols):
            self._grid.setColumnStretch(c, 0)
        self._grid.setColumnStretch(cols, 1)

        for harvester in self._harvesters:
            if harvester.id not in visible_ids:
                self._cards[harvester.id].hide()

        if visible:
            cols = self._column_count()
            content_h = self._estimate_cards_area_height()
            content_w = (
                cols * CARD_MAX_WIDTH
                + max(0, cols - 1) * self._grid.spacing()
            )
            vp_w = self._cards_viewport_width()
            self._grid_host.setMinimumHeight(content_h)
            # Keep scroll content at least viewport-wide so the card area matches the pane.
            self._grid_host.setMinimumWidth(max(content_w, vp_w))
        else:
            self._grid_host.setMinimumHeight(_CARDS_AREA_MIN_HEIGHT)
            self._grid_host.setMinimumWidth(0)

        self._grid_host.updateGeometry()

    def _card_grid_rows(self) -> tuple[int, int]:
        visible = self._filtered_harvesters()
        cols = max(1, self._column_count())
        if not visible:
            return 0, cols
        rows = (len(visible) + cols - 1) // cols
        return rows, cols

    def _estimate_card_row_height(self) -> int:
        visible = self._filtered_harvesters()
        if not visible:
            return _CARD_ROW_HEIGHT_FALLBACK
        heights: list[int] = []
        for harvester in visible:
            card = self._cards[harvester.id]
            measured = max(card.height(), card.sizeHint().height())
            if measured > 50:
                heights.append(measured)
        return max(heights) if heights else _CARD_ROW_HEIGHT_FALLBACK

    def _estimate_cards_area_height(self) -> int:
        rows, _ = self._card_grid_rows()
        if rows == 0:
            return _CARDS_AREA_MIN_HEIGHT
        row_h = self._estimate_card_row_height()
        spacing = self._grid.spacing()
        margins = self._grid.contentsMargins()
        chrome = margins.top() + margins.bottom() + 8
        return rows * row_h + max(0, rows - 1) * spacing + chrome

    def eventFilter(self, watched, event) -> bool:
        if (
            watched == self._card_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._relayout_card_grid()
        return super().eventFilter(watched, event)

    def _update_summary_label(self) -> None:
        n = len(self._harvesters)
        farmers = sum(1 for h in self._harvesters if h.role == NodeRole.FARMER)
        harvesters = n - farmers
        mainnet = sum(1 for h in self._harvesters if h.network == ChiaNetwork.MAINNET)
        testnet = n - mainnet
        self._summary.setText(
            f"<b>{n}</b> enabled node(s) — {harvesters} harvester(s), {farmers} farmer(s); "
            f"{mainnet} mainnet, {testnet} testnet<br>"
            f"Config: <code>{self._config_path}</code>"
        )

    def _set_fleet_busy(self, busy: bool) -> None:
        enabled = not busy and not self._deploy_active
        self._btn_refresh.setEnabled(enabled)
        self._btn_deploy.setEnabled(enabled)
        self._filter_combo.setEnabled(enabled)
        self._menu_refresh.setEnabled(enabled)
        self._menu_deploy.setEnabled(enabled)

    def _inc_busy(self) -> None:
        self._pending_ops += 1
        self._set_fleet_busy(True)

    def _dec_busy(self) -> None:
        self._pending_ops = max(0, self._pending_ops - 1)
        if self._pending_ops == 0:
            self._set_fleet_busy(False)

    def _run_async(self, coro, on_success, *, busy_message: str) -> None:
        self._inc_busy()
        self.statusBar().showMessage(busy_message)
        bridge = AsyncTaskBridge(self._async, parent=self)
        bridge.succeeded.connect(on_success)
        bridge.failed.connect(self._on_async_failed)
        bridge.submit(coro)

    def _on_async_failed(self, message: str) -> None:
        if not self._deploy_active:
            self._dec_busy()
            for card in self._cards.values():
                card.set_busy(False)
        QMessageBox.warning(self, "Operation failed", message)
        self.statusBar().showMessage(f"Failed: {message}", 8000)

    def _on_deploy_log_line(self, node_id: str, line: str) -> None:
        self._log_panel.append_line(node_id, line)
        match = _STEP_RE.search(line)
        if match:
            card = self._cards.get(node_id)
            if card:
                card.set_deploy_step(match.group(1))

    def _partition_deployable(
        self, targets: list[Harvester]
    ) -> tuple[list[Harvester], list[Harvester]]:
        ok: list[Harvester] = []
        excluded: list[Harvester] = []
        for h in targets:
            card = self._cards.get(h.id)
            mode = card.install_mode if card else None
            if mode == InstallMode.PACKAGE.value:
                excluded.append(h)
            else:
                ok.append(h)
        return ok, excluded

    def _open_deploy_wizard(self) -> None:
        if self._deploy_active:
            return
        dlg = DeployWizardDialog(self._harvesters, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._begin_deploy(dlg.target_key(), dlg.options())

    def _deploy_single_node(self, node_id: str) -> None:
        if self._deploy_active:
            return
        h = self._harvester_by_id(node_id)
        if h is None:
            return
        card = self._cards.get(node_id)
        if card and card.install_mode == InstallMode.PACKAGE.value:
            QMessageBox.information(
                self,
                "Deploy not supported",
                f"{h.display_name} uses a package install (.deb). "
                "Upgrade via your OS package manager.",
            )
            return
        dlg = DeployWizardDialog(
            self._harvesters, self, preset_target=node_id
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._begin_deploy(dlg.target_key(), dlg.options())

    def _begin_deploy(self, target_key: str, options: DeployOptions) -> None:
        cfg = self._app_config or load_fleet(self._config_path)[0]
        try:
            targets = resolve_targets(cfg, target_key)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid target", str(exc))
            return

        deployable, excluded = self._partition_deployable(targets)
        if not deployable:
            QMessageBox.information(
                self,
                "Nothing to deploy",
                "No source-install nodes in the selected target. "
                "Package nodes must be upgraded via .deb.",
            )
            return

        recipe = load_recipe(options.recipe_name)
        confirm = ConfirmDeployDialog(
            deployable,
            recipe,
            dry_run=options.dry_run,
            excluded_package=excluded,
            parent=self,
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        self._start_deploy(deployable, options)

    def _start_deploy(self, targets: list[Harvester], options: DeployOptions) -> None:
        self._deploy_active = True
        self._deploying_ids = {h.id for h in targets}
        self._set_fleet_busy(True)
        self._progress.show()
        self._tabs.setCurrentIndex(_TAB_LOGS)
        self._log_panel.clear()
        self._log_panel.set_nodes([h.id for h in self._harvesters])

        for hid, card in self._cards.items():
            if hid in self._deploying_ids:
                card.set_deploying(True)
            else:
                card.setEnabled(False)

        mode = "Dry run" if options.dry_run else "Deploy"
        self.statusBar().showMessage(f"{mode} in progress…")

        def on_success(jobs: list) -> None:
            self._finish_deploy(jobs, options)

        bridge = AsyncTaskBridge(self._async, parent=self)
        bridge.succeeded.connect(on_success)
        bridge.failed.connect(self._on_deploy_failed)
        bridge.submit(
            fleet_deploy(targets, options, on_log=self._log_hub.callback())
        )

    def _on_deploy_failed(self, message: str) -> None:
        self._cleanup_deploy_ui()
        QMessageBox.critical(self, "Deploy failed", message)
        self.statusBar().showMessage("Deploy failed", 8000)

    def _finish_deploy(self, jobs: list, options: DeployOptions) -> None:
        summary_path = write_summary(jobs, dry_run=options.dry_run)
        for job in jobs:
            card = self._cards.get(job.harvester.id)
            if card:
                card.apply_deploy_job(job)

        self._cleanup_deploy_ui()

        failed = [j for j in jobs if j.state == JobState.FAILED]
        success = len(jobs) - len(failed)
        self.statusBar().showMessage(
            f"Deploy finished: {success} ok, {len(failed)} failed", 10000
        )

        DeploySummaryDialog(jobs, str(summary_path), self).exec()

        if not options.dry_run:
            QTimer.singleShot(400, self._refresh_fleet)

    def _cleanup_deploy_ui(self) -> None:
        self._deploy_active = False
        self._deploying_ids.clear()
        self._progress.hide()
        for card in self._cards.values():
            card.setEnabled(True)
            card.set_deploying(False)
        self._set_fleet_busy(False)

    def _refresh_fleet(self) -> None:
        if self._deploy_active or not self._harvesters:
            if not self._harvesters:
                self.statusBar().showMessage("No enabled nodes in config", 5000)
            return

        for card in self._cards.values():
            card.set_busy(True)

        def on_success(results: list) -> None:
            for harvester, result in zip(self._harvesters, results, strict=True):
                card = self._cards.get(harvester.id)
                if card is None:
                    continue
                if isinstance(result, BaseException):
                    card.set_error(str(result))
                else:
                    card.apply_status(result)
            self._fleet_summary.update_from_status(self._harvesters, results)
            self._dec_busy()
            self.statusBar().showMessage("Fleet status updated", 5000)
            self._last_card_cols = None
            self._relayout_card_grid()

        self._run_async(
            fleet_status(self._harvesters),
            on_success,
            busy_message="Refreshing fleet status…",
        )

    def _on_doctor(self, node_id: str) -> None:
        if self._deploy_active:
            return
        harvester = self._harvester_by_id(node_id)
        if harvester is None:
            return
        card = self._cards[node_id]
        card.set_busy(True)
        self._inc_busy()
        self.statusBar().showMessage(f"Running doctor on {node_id}…")

        def on_success(checks: dict) -> None:
            card.set_busy(False)
            self._dec_busy()
            self.statusBar().showMessage(f"Doctor finished for {node_id}", 5000)
            DoctorDialog(node_id, checks, self).exec()

        bridge = AsyncTaskBridge(self._async, parent=self)
        bridge.succeeded.connect(on_success)
        bridge.failed.connect(lambda msg: self._on_doctor_failed(node_id, msg))
        bridge.submit(node_doctor(harvester))

    def _on_doctor_failed(self, node_id: str, message: str) -> None:
        card = self._cards.get(node_id)
        if card:
            card.set_error(message)
        self._dec_busy()
        QMessageBox.warning(self, "Doctor failed", message)

    def _on_test_ssh(self, node_id: str) -> None:
        if self._deploy_active:
            return
        harvester = self._harvester_by_id(node_id)
        if harvester is None:
            return
        card = self._cards[node_id]
        card.set_busy(True)
        self._inc_busy()
        self.statusBar().showMessage(f"Testing SSH to {node_id}…")

        def on_success(result: tuple[str, bool, BaseException | None]) -> None:
            _, ok, err = result
            card.set_ssh_result(ok)
            self._dec_busy()
            if ok:
                self.statusBar().showMessage(f"SSH test {node_id}: ok", 5000)
                return
            from harvester_deploy.ssh.client import expand_key_path
            from harvester_deploy.ssh.errors import explain_ssh_failure

            msg, _ = explain_ssh_failure(
                err,
                host=harvester.host,
                key_path=expand_key_path(harvester.ssh_key_path),
            )
            card.set_error(msg.splitlines()[0])
            self._on_test_ssh_failed(node_id, msg)

        bridge = AsyncTaskBridge(self._async, parent=self)
        bridge.succeeded.connect(on_success)
        bridge.failed.connect(lambda msg: self._on_test_ssh_failed(node_id, msg))
        bridge.submit(node_test_ssh(harvester))

    def _on_test_ssh_failed(self, node_id: str, message: str) -> None:
        card = self._cards.get(node_id)
        if card:
            card.set_error(message.splitlines()[0])
        self._dec_busy()
        QMessageBox.warning(self, "SSH test failed", message)

    def closeEvent(self, event) -> None:
        self._async.shutdown()
        super().closeEvent(event)


def _apply_app_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f0f2f5"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#1a1a1a"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#e9ecef"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1a1a1a"))
    app.setPalette(palette)
    app.setStyleSheet(APP_STYLESHEET)


def run_gui(config_path: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    _apply_app_theme(app)
    app.setApplicationName("Harvester Deployment Manager")
    app.setOrganizationName("harvester-deploy")
    ensure_app_directories()
    seed_config_if_empty()
    config_path = resolve_config_path(config_path)
    window_icon = app_icon()
    if window_icon is not None:
        app.setWindowIcon(window_icon)
    window = MainWindow(config_path=config_path)
    if window_icon is not None:
        window.setWindowIcon(window_icon)
    window.show()
    return app.exec()
