"""Lightweight GUI smoke tests (no display required)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_filter_options_cover_network() -> None:
    from harvester_deploy.gui.main_window import _FILTER_OPTIONS, _TAB_LOGS, _TAB_NODES

    keys = {k for _, k in _FILTER_OPTIONS}
    assert "mainnet" in keys
    assert "testnet" in keys
    assert _TAB_NODES == 0
    assert _TAB_LOGS == 2


def test_main_window_construct() -> None:
    from PySide6.QtWidgets import QApplication

    from harvester_deploy.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    w = MainWindow.__new__(MainWindow)
    assert w is not None
    app.quit()
