"""Harvester Deployment Manager — main window."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
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
from harvester_deploy.domain.telemetry import NetworkTelemetry, parse_farm_summary
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
from harvester_deploy.gui.styles import (
    ThemeMode,
    apply_app_theme,
    current_theme_mode,
    theme_colors,
)
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
    SettingsDialog,
)
from harvester_deploy.gui.widgets.node_card import CARD_MAX_WIDTH
from harvester_deploy.persistence.config import resolve_targets
from harvester_deploy.persistence.paths import (
    default_config_dir,
    default_config_path,
    ensure_app_directories,
    is_frozen,
    load_refresh_interval_seconds,
    load_theme_preference,
    load_window_state,
    resolve_config_path,
    save_refresh_interval_seconds,
    save_theme_preference,
    save_persisted_config_path,
    save_window_state,
    seed_config_if_empty,
)
from harvester_deploy.persistence.fleet_store import config_dir, load_fleet
from harvester_deploy.recipes.engine import load_recipe
from harvester_deploy.reporting.summary import write_summary

_STEP_RE = re.compile(r"--- step:\s*(\S+)")
_IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
# Horizontal space per grid column (fixed card width + spacing).
_CARD_GRID_SPACING = 16
_CARD_CELL_WIDTH = CARD_MAX_WIDTH + _CARD_GRID_SPACING
_CARDS_AREA_MIN_HEIGHT = 100
_CARD_ROW_HEIGHT_FALLBACK = 340
_TAB_NODES = 0
_TAB_FLEET = 1
_TAB_LOGS = 2
_DEFAULT_REFRESH_SECONDS = 120
_STATUS_MESSAGE_RESERVE = 320

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
        self._network_telemetry: dict[ChiaNetwork, NetworkTelemetry] = {}
        self._theme_mode = current_theme_mode()
        self._refresh_interval_seconds = (
            load_refresh_interval_seconds() or _DEFAULT_REFRESH_SECONDS
        )
        self._restore_window_mode = "normal"
        self._filter = "all"
        self._last_card_cols: int | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self._refresh_interval_seconds * 1000)
        self._refresh_timer.timeout.connect(self._on_auto_refresh)

        self._build_menu()
        self._build_central()
        self.setStatusBar(QStatusBar())
        self.statusBar().setMinimumHeight(34)
        self._status_spacer = QWidget()
        self._status_spacer.setFixedWidth(_STATUS_MESSAGE_RESERVE)
        self._status_spacer.setStyleSheet("background: transparent;")
        (
            self._status_mainnet,
            self._status_mainnet_badge,
            self._status_mainnet_text,
        ) = self._build_status_section("Mainnet")
        self._status_gap = QWidget()
        self._status_gap.setFixedWidth(12)
        self._status_gap.setStyleSheet("background: transparent;")
        (
            self._status_testnet,
            self._status_testnet_badge,
            self._status_testnet_text,
        ) = self._build_status_section("Testnet")
        self.statusBar().addPermanentWidget(self._status_spacer)
        self.statusBar().addPermanentWidget(self._status_mainnet)
        self.statusBar().addPermanentWidget(self._status_gap)
        self.statusBar().addPermanentWidget(self._status_testnet)
        self.statusBar().showMessage("Ready")
        self._apply_widget_theme()
        self._restore_window_state()
        self._refresh_timer.start()

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

        view_menu = menu_bar.addMenu("&View")
        theme_menu = view_menu.addMenu("&Theme")
        self._theme_actions = QActionGroup(self)
        self._theme_actions.setExclusive(True)

        self._theme_light_action = QAction("&Light", self)
        self._theme_light_action.setCheckable(True)
        self._theme_light_action.triggered.connect(
            lambda checked: checked and self._set_theme(ThemeMode.LIGHT)
        )
        theme_menu.addAction(self._theme_light_action)
        self._theme_actions.addAction(self._theme_light_action)

        self._theme_dark_action = QAction("&Dark", self)
        self._theme_dark_action.setCheckable(True)
        self._theme_dark_action.triggered.connect(
            lambda checked: checked and self._set_theme(ThemeMode.DARK)
        )
        theme_menu.addAction(self._theme_dark_action)
        self._theme_actions.addAction(self._theme_dark_action)
        self._sync_theme_actions()

        settings_menu = menu_bar.addMenu("&Settings")
        settings_act = QAction("&Preferences…", self)
        settings_act.triggered.connect(self._open_settings)
        settings_menu.addAction(settings_act)

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

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(12)

        self._summary = QLabel("Loading fleet from config…")
        self._summary.setWordWrap(True)
        summary_row.addWidget(self._summary, stretch=1)

        self._btn_theme_toggle = QPushButton()
        self._btn_theme_toggle.setObjectName("themeToggleButton")
        self._btn_theme_toggle.clicked.connect(self._toggle_theme)
        self._btn_theme_toggle.setFixedSize(38, 26)
        summary_row.addWidget(
            self._btn_theme_toggle,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        self._sync_theme_actions()
        outer.addLayout(summary_row)

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

    def _restore_window_state(self) -> None:
        width, height, mode = load_window_state()
        if width is not None and height is not None:
            self.resize(width, height)
        self._restore_window_mode = mode

    def restore_window_mode(self) -> str:
        return self._restore_window_mode

    def _open_settings(self) -> None:
        dlg = SettingsDialog(
            refresh_interval_seconds=self._refresh_interval_seconds,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        seconds = dlg.refresh_interval_seconds()
        self._set_refresh_interval_seconds(seconds, persist=True)
        self.statusBar().showMessage(
            f"Auto refresh interval set to {seconds} seconds",
            5000,
        )

    def _build_status_section(self, label: str) -> tuple[QWidget, QLabel, QLabel]:
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(6)
        badge = QLabel(label)
        text = QLabel("")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setStyleSheet("background: transparent;")
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(text, alignment=Qt.AlignmentFlag.AlignVCenter)
        return host, badge, text

    def _sync_theme_actions(self) -> None:
        self._theme_light_action.setChecked(self._theme_mode == ThemeMode.LIGHT)
        self._theme_dark_action.setChecked(self._theme_mode == ThemeMode.DARK)
        if hasattr(self, "_btn_theme_toggle"):
            next_label = "🌙" if self._theme_mode == ThemeMode.LIGHT else "☀️"
            next_tip = "Switch to dark mode" if self._theme_mode == ThemeMode.LIGHT else "Switch to light mode"
            self._btn_theme_toggle.setText(next_label)
            self._btn_theme_toggle.setToolTip(
                next_tip
            )

    def _apply_widget_theme(self) -> None:
        for card in self._cards.values():
            card.apply_theme(self._theme_mode)
        if hasattr(self, "_fleet_summary"):
            self._fleet_summary.apply_theme(self._theme_mode)
        if hasattr(self, "_log_panel"):
            self._log_panel.apply_theme(self._theme_mode)
        self._apply_status_bar_theme()

    def _apply_status_bar_theme(self) -> None:
        colors = {
            ChiaNetwork.MAINNET: "#0d6efd",
            ChiaNetwork.TESTNET: "#6f42c1",
        }
        for network, badge in (
            (ChiaNetwork.MAINNET, self._status_mainnet_badge),
            (ChiaNetwork.TESTNET, self._status_testnet_badge),
        ):
            badge.setStyleSheet(
                "color: white; "
                f"background-color: {colors[network]}; "
                "border-radius: 7px; "
                "padding: 2px 8px; "
                "font-weight: 600;"
            )
        for label in (self._status_mainnet_text, self._status_testnet_text):
            label.setStyleSheet("background: transparent;")

    def _toggle_theme(self) -> None:
        next_theme = (
            ThemeMode.DARK
            if self._theme_mode == ThemeMode.LIGHT
            else ThemeMode.LIGHT
        )
        self._set_theme(next_theme)

    def _set_theme(self, theme: ThemeMode) -> None:
        app = QApplication.instance()
        if app is None:
            return
        apply_app_theme(app, theme)
        self._theme_mode = theme
        save_theme_preference(theme.value)
        self._sync_theme_actions()
        self._apply_widget_theme()

    def _set_refresh_interval_seconds(self, seconds: int, *, persist: bool) -> None:
        self._refresh_interval_seconds = int(seconds)
        interval_ms = self._refresh_interval_seconds * 1000
        self._refresh_timer.setInterval(interval_ms)
        if self._refresh_timer.isActive():
            self._refresh_timer.start(interval_ms)
        if persist:
            save_refresh_interval_seconds(self._refresh_interval_seconds)

    def _save_window_state(self) -> None:
        geometry = self.normalGeometry()
        if (self.isFullScreen() or self.isMaximized()) and geometry.isValid():
            width = geometry.width()
            height = geometry.height()
        else:
            width = self.width()
            height = self.height()
        if self.isFullScreen():
            mode = "fullscreen"
        elif self.isMaximized():
            mode = "maximized"
        else:
            mode = "normal"
        save_window_state(
            width=width,
            height=height,
            mode=mode,
        )

    def _reload_config(self) -> None:
        self._app_config, sync_note = load_fleet(self._config_path)
        self._harvesters = [h for h in self._app_config.harvesters if h.enabled]
        self._rebuild_cards()
        self._update_summary_label()
        self._clear_telemetry()
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
            card.apply_theme(self._theme_mode)
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
            f"<b>{n}</b> enabled node(s) — {harvesters} harvester(s), "
            f"{farmers} farmer(s); {mainnet} mainnet, {testnet} testnet"
        )

    def _clear_telemetry(self) -> None:
        self._network_telemetry = {}
        for card in self._cards.values():
            card.apply_telemetry()
        self._update_status_bar_telemetry()

    def _apply_telemetry(self, results: list[dict | BaseException]) -> None:
        self._network_telemetry = self._collect_network_telemetry(results)

        for harvester, result in zip(self._harvesters, results, strict=True):
            if isinstance(result, BaseException):
                continue

            ip_address = result.get("ip_address")
            plot_count = None
            plot_size = None
            network = self._network_telemetry.get(harvester.network)
            if network is not None:
                if harvester.role == NodeRole.FARMER and network.local_harvester is not None:
                    plot_count = network.local_harvester.plot_count
                    plot_size = network.local_harvester.plot_size
                else:
                    matched_ip = ip_address
                    if matched_ip is None and _IP_RE.match(harvester.host):
                        matched_ip = harvester.host
                    remote = (
                        network.remote_harvesters.get(matched_ip)
                        if matched_ip is not None
                        else None
                    )
                    if remote is not None:
                        plot_count = remote.plot_count
                        plot_size = remote.plot_size
                        ip_address = remote.ip_address or ip_address

            card = self._cards.get(harvester.id)
            if card is not None:
                card.apply_telemetry(
                    ip_address=ip_address,
                    plot_count=plot_count,
                    plot_size=plot_size,
                )

        self._update_status_bar_telemetry()

    def _collect_network_telemetry(
        self, results: list[dict | BaseException]
    ) -> dict[ChiaNetwork, NetworkTelemetry]:
        telemetry: dict[ChiaNetwork, NetworkTelemetry] = {}
        for harvester, result in zip(self._harvesters, results, strict=True):
            if harvester.role != NodeRole.FARMER or isinstance(result, BaseException):
                continue
            parsed = parse_farm_summary(result.get("summary", ""), harvester.network)
            if parsed is not None:
                telemetry[harvester.network] = parsed
        return telemetry

    def _update_status_bar_telemetry(self) -> None:
        show_mainnet = self._has_network_nodes(ChiaNetwork.MAINNET)
        show_testnet = self._has_network_nodes(ChiaNetwork.TESTNET)

        self._status_mainnet.setVisible(show_mainnet)
        self._status_testnet.setVisible(show_testnet)
        self._status_gap.setVisible(show_mainnet and show_testnet)

        self._status_mainnet_text.setText(
            self._format_network_status(ChiaNetwork.MAINNET) if show_mainnet else ""
        )
        self._status_testnet_text.setText(
            self._format_network_status(ChiaNetwork.TESTNET) if show_testnet else ""
        )

    def _has_network_nodes(self, network: ChiaNetwork) -> bool:
        return any(h.network == network for h in self._harvesters)

    def _format_network_status(self, network: ChiaNetwork) -> str:
        telemetry = self._network_telemetry.get(network)
        if telemetry is None:
            return ""
        colors = theme_colors(self._theme_mode)
        value_color = (
            colors.accent_pressed
            if self._theme_mode == ThemeMode.LIGHT
            else colors.accent_hover
        )
        parts: list[str] = []
        if telemetry.last_farmed_height:
            parts.append(
                f"<span style='color:{colors.text_muted}; font-weight:600;'>height</span> "
                f"<span style='color:{value_color};'>{html.escape(telemetry.last_farmed_height)}</span>"
            )
        if telemetry.total_plot_count is not None:
            parts.append(
                f"<span style='color:{colors.text_muted}; font-weight:600;'>plots</span> "
                f"<span style='color:{value_color};'>{telemetry.total_plot_count:,}</span>"
            )
        if telemetry.total_plot_size:
            parts.append(
                f"<span style='color:{colors.text_muted}; font-weight:600;'>size</span> "
                f"<span style='color:{colors.success};'>{html.escape(telemetry.total_plot_size)}</span>"
            )
        if telemetry.estimated_network_space:
            parts.append(
                f"<span style='color:{colors.text_muted}; font-weight:600;'>net</span> "
                f"<span style='color:{value_color};'>{html.escape(telemetry.estimated_network_space)}</span>"
            )
        if telemetry.expected_time_to_win:
            parts.append(
                f"<span style='color:{colors.text_muted}; font-weight:600;'>win</span> "
                f"<span style='color:{colors.warning};'>{html.escape(telemetry.expected_time_to_win)}</span>"
            )
        separator = f"<span style='color:{colors.text_muted};'> | </span>"
        return separator.join(parts)

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

    def _run_async(
        self,
        coro,
        on_success,
        *,
        busy_message: str | None,
        on_failure=None,
    ) -> None:
        self._inc_busy()
        if busy_message:
            self.statusBar().showMessage(busy_message)
        bridge = AsyncTaskBridge(self._async, parent=self)
        bridge.succeeded.connect(on_success)
        bridge.failed.connect(on_failure or self._on_async_failed)
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

    def _refresh_fleet(self, *, background: bool = False) -> None:
        if self._deploy_active or self._pending_ops > 0 or not self._harvesters:
            if not self._harvesters:
                self.statusBar().showMessage("No enabled nodes in config", 5000)
            return

        if not background:
            for card in self._cards.values():
                card.set_busy(True)

        def on_success(results: list) -> None:
            try:
                for harvester, result in zip(self._harvesters, results, strict=True):
                    card = self._cards.get(harvester.id)
                    if card is None:
                        continue
                    if isinstance(result, BaseException):
                        card.set_error(str(result))
                    else:
                        card.apply_status(result)
                self._apply_telemetry(results)
                self._fleet_summary.update_from_status(self._harvesters, results)
                if not background:
                    self.statusBar().showMessage("Fleet status updated", 5000)
                self._last_card_cols = None
                self._relayout_card_grid()
            except Exception as exc:
                for card in self._cards.values():
                    card.set_busy(False)
                if background:
                    self.statusBar().showMessage(
                        f"Auto refresh UI update failed: {exc}",
                        8000,
                    )
                else:
                    QMessageBox.warning(self, "Refresh failed", str(exc))
                    self.statusBar().showMessage(f"Refresh failed: {exc}", 8000)
            finally:
                self._dec_busy()

        self._run_async(
            fleet_status(self._harvesters),
            on_success,
            busy_message=None if background else "Refreshing fleet status…",
            on_failure=self._on_background_refresh_failed if background else None,
        )

    def _on_auto_refresh(self) -> None:
        self._refresh_fleet(background=True)

    def _on_background_refresh_failed(self, message: str) -> None:
        self._dec_busy()
        self.statusBar().showMessage(f"Auto refresh failed: {message}", 8000)

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
        try:
            self._save_window_state()
        except Exception:
            pass
        self._async.shutdown()
        super().closeEvent(event)

def run_gui(config_path: Path | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, ThemeMode(load_theme_preference() or ThemeMode.LIGHT.value))
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
    mode = window.restore_window_mode()
    if mode == "fullscreen":
        window.showFullScreen()
    elif mode == "maximized":
        window.showMaximized()
    else:
        window.show()
    return app.exec()
