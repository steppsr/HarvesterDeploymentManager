"""Lightweight GUI smoke tests (no display required)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_filter_options_cover_network() -> None:
    from harvester_deploy.gui.main_window import _FILTER_OPTIONS, _TAB_LOGS, _TAB_NODES

    keys = {k for _, k in _FILTER_OPTIONS}
    assert "mainnet" in keys
    assert "testnet" in keys
    assert _TAB_NODES == 0
    assert _TAB_LOGS == 2


def test_footer_status_hides_missing_network_and_uses_blank_default() -> None:
    from harvester_deploy.domain.models import ChiaNetwork, Harvester
    from harvester_deploy.domain.telemetry import NetworkTelemetry
    from harvester_deploy.gui.main_window import MainWindow
    from harvester_deploy.gui.styles import ThemeMode

    w = MainWindow.__new__(MainWindow)
    w._harvesters = [
        Harvester(id="a", display_name="A", host="a", network=ChiaNetwork.MAINNET)
    ]
    w._theme_mode = ThemeMode.LIGHT
    w._network_telemetry = {}

    assert w._has_network_nodes(ChiaNetwork.MAINNET) is True
    assert w._has_network_nodes(ChiaNetwork.TESTNET) is False
    assert w._format_network_status(ChiaNetwork.MAINNET) == ""

    w._network_telemetry = {
        ChiaNetwork.MAINNET: NetworkTelemetry(
            network=ChiaNetwork.MAINNET,
            last_farmed_height="123",
            total_plot_count=456,
            total_plot_size="7 TiB",
            estimated_network_space="42 EiB",
            expected_time_to_win="1 month",
        )
    }
    html_text = w._format_network_status(ChiaNetwork.MAINNET)
    assert "span" in html_text
    assert "height" in html_text
    assert "1 month" in html_text


def test_main_window_construct() -> None:
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    w = MainWindow.__new__(MainWindow)
    assert w is not None
    app.quit()


def test_log_panel_splits_multiline_entries() -> None:
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.gui.widgets.log_panel import LogPanel

    app = QApplication.instance() or QApplication([])
    panel = LogPanel()
    panel.append_line("kinnakeet", "line one\nline two")

    text = panel._text.toPlainText()
    assert "kinnakeet | line one" in text
    assert "kinnakeet | line two" in text
    assert text.count("kinnakeet |") == 2
    app.quit()


def test_node_card_marks_unhealthy_on_health_failure() -> None:
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.domain.models import Harvester
    from harvester_deploy.gui.widgets.node_card import NodeCard

    app = QApplication.instance() or QApplication([])
    card = NodeCard(Harvester(id="tarkin", display_name="Tarkin", host="tarkin"))
    card.apply_status(
        {
            "install_mode": "unknown",
            "version": "—",
            "commits_behind": "—",
            "ip_address": None,
            "summary": "",
            "error": "SSH failed: timeout",
            "health_summary": "PING failed; SSH failed",
        }
    )

    assert card.property("unhealthy") is True
    assert "PING failed" in card._status_value.text()
    app.quit()


def test_settings_dialog_round_trip_value() -> None:
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.gui.widgets.settings_dialog import SettingsDialog

    app = QApplication.instance() or QApplication([])
    dlg = SettingsDialog(refresh_interval_seconds=180)

    assert dlg.refresh_interval_seconds() == 180
    dlg._refresh_interval.setValue(300)
    assert dlg.refresh_interval_seconds() == 300
    app.quit()


def test_fleet_summary_formatter_highlights_values() -> None:
    from harvester_deploy.gui.styles import ThemeMode
    from harvester_deploy.gui.widgets.fleet_summary_panel import _format_summary_line

    label_line = _format_summary_line(
        "Expected time to win: 1 month",
        theme=ThemeMode.LIGHT,
    )
    detail_line = _format_summary_line(
        "   165 plots of size: 32.471 TiB",
        theme=ThemeMode.LIGHT,
    )
    remote_line = _format_summary_line(
        "Remote Harvester for IP: 192.168.1.10",
        theme=ThemeMode.LIGHT,
    )

    assert "Expected time to win:" in label_line
    assert "1 month" in label_line
    assert "165" in detail_line
    assert "32.471 TiB" in detail_line
    assert "192.168.1.10" in remote_line
    assert "span" in label_line


def test_log_panel_clear_visible_honors_filter() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.gui.widgets.log_panel import LogPanel

    app = QApplication.instance() or QApplication([])
    panel = LogPanel()
    panel.set_nodes(["alpha", "beta"])
    panel.append_line("alpha", "alpha line")
    panel.append_line("beta", "beta line")

    idx = panel._filter.findData("alpha", Qt.ItemDataRole.UserRole)
    panel._filter.setCurrentIndex(idx)
    panel.clear_visible()

    visible = panel._visible_text()
    assert "alpha | alpha line" not in visible
    assert "beta | beta line" not in visible
    assert all(entry[1] != "alpha" for entry in panel._lines)
    assert any(entry[1] == "beta" for entry in panel._lines)
    app.quit()


def test_log_panel_save_visible_honors_filter(tmp_path: Path) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.gui.widgets.log_panel import LogPanel

    app = QApplication.instance() or QApplication([])
    panel = LogPanel()
    panel.set_nodes(["alpha", "beta"])
    panel.append_line("alpha", "alpha line")
    panel.append_line("beta", "beta line")

    idx = panel._filter.findData("beta", Qt.ItemDataRole.UserRole)
    panel._filter.setCurrentIndex(idx)
    out = tmp_path / "filtered-log.txt"
    panel.save_visible_to(str(out))

    text = out.read_text(encoding="utf-8")
    assert "beta | beta line" in text
    assert "alpha | alpha line" not in text
    app.quit()
