"""Application-wide Qt theming."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


class ThemeMode(str, Enum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ThemeColors:
    window: str
    surface: str
    surface_alt: str
    text_primary: str
    text_muted: str
    border: str
    accent: str
    accent_hover: str
    accent_pressed: str
    button_bg: str
    button_hover: str
    button_pressed: str
    button_disabled_bg: str
    button_disabled_text: str
    input_bg: str
    input_text: str
    input_selection_bg: str
    input_selection_text: str
    danger: str
    warning: str
    success: str
    log_bg: str
    log_text: str
    log_border: str


_LIGHT = ThemeColors(
    window="#f0f2f5",
    surface="#ffffff",
    surface_alt="#e9ecef",
    text_primary="#1a1a1a",
    text_muted="#6c757d",
    border="#c8cdd3",
    accent="#4a6fa5",
    accent_hover="#3d5f94",
    accent_pressed="#35527f",
    button_bg="#e9ecef",
    button_hover="#dee2e6",
    button_pressed="#ced4da",
    button_disabled_bg="#f1f3f5",
    button_disabled_text="#868e96",
    input_bg="#ffffff",
    input_text="#1a1a1a",
    input_selection_bg="#4a6fa5",
    input_selection_text="#ffffff",
    danger="#c0392b",
    warning="#8a6d3b",
    success="#2d5a2d",
    log_bg="#ffffff",
    log_text="#1f2933",
    log_border="#c8cdd3",
)

_DARK = ThemeColors(
    window="#1b1f24",
    surface="#232a31",
    surface_alt="#2d3640",
    text_primary="#e6edf3",
    text_muted="#9aa6b2",
    border="#3b4652",
    accent="#6ea8fe",
    accent_hover="#8bb9ff",
    accent_pressed="#5c93eb",
    button_bg="#2d3640",
    button_hover="#37424d",
    button_pressed="#44515e",
    button_disabled_bg="#242c34",
    button_disabled_text="#72808d",
    input_bg="#1f252c",
    input_text="#e6edf3",
    input_selection_bg="#6ea8fe",
    input_selection_text="#0d1117",
    danger="#ff7b72",
    warning="#d29922",
    success="#7ee787",
    log_bg="#11161c",
    log_text="#dce6f2",
    log_border="#3b4652",
)


def parse_theme(value: str | None) -> ThemeMode:
    if str(value or "").strip().lower() == ThemeMode.DARK.value:
        return ThemeMode.DARK
    return ThemeMode.LIGHT


def current_theme_mode(app: QApplication | None = None) -> ThemeMode:
    app = app or QApplication.instance()
    if app is None:
        return ThemeMode.LIGHT
    return parse_theme(app.property("hdm_theme"))


def theme_colors(theme: ThemeMode) -> ThemeColors:
    return _DARK if theme == ThemeMode.DARK else _LIGHT


def build_palette(theme: ThemeMode) -> QPalette:
    colors = theme_colors(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors.window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors.input_bg))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors.surface))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors.input_text))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors.button_bg))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors.input_selection_bg))
    palette.setColor(
        QPalette.ColorRole.HighlightedText,
        QColor(colors.input_selection_text),
    )
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors.surface))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors.text_primary))
    return palette


def build_stylesheet(theme: ThemeMode) -> str:
    c = theme_colors(theme)
    return f"""
QMainWindow, QWidget {{
    background-color: {c.window};
    color: {c.text_primary};
}}
QLabel {{
    color: {c.text_primary};
}}
QMenuBar {{
    background-color: {c.surface};
    color: {c.text_primary};
    border-bottom: 1px solid {c.border};
    padding: 2px;
}}
QMenuBar::item:selected {{
    background-color: {c.surface_alt};
}}
QMenu {{
    background-color: {c.surface};
    color: {c.text_primary};
    border: 1px solid {c.border};
}}
QStatusBar {{
    background-color: {c.surface};
    color: {c.text_primary};
    border-top: 1px solid {c.border};
}}
QFrame#actionBar {{
    background-color: {c.surface};
    border: 1px solid {c.border};
    border-radius: 6px;
}}
QLabel#inlineCaption {{
    background: transparent;
    border: none;
    padding: 0 6px 0 0;
    color: {c.text_primary};
    font-weight: 600;
}}
QFrame#nodeCard {{
    background-color: {c.surface};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 8px;
}}
QFrame#nodeCard[failed="true"] {{
    border: 2px solid {c.danger};
}}
QFrame#nodeCard[unhealthy="true"] {{
    border: 4px solid {c.danger};
}}
QFrame#nodeCard[busy="true"] {{
    border: 2px solid {c.accent};
}}
QPushButton {{
    background-color: {c.button_bg};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 4px;
    padding: 6px 14px;
    min-height: 28px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {c.button_hover};
}}
QPushButton:pressed {{
    background-color: {c.button_pressed};
}}
QPushButton:disabled {{
    color: {c.button_disabled_text};
    background-color: {c.button_disabled_bg};
}}
QPushButton#themeToggleButton {{
    padding: 3px 7px;
    min-height: 14px;
    font-size: 14px;
    font-weight: 600;
}}
QComboBox, QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c.input_bg};
    color: {c.input_text};
    border: 1px solid {c.border};
    border-radius: 4px;
}}
QComboBox {{
    padding: 4px 8px;
    min-height: 28px;
}}
QComboBox QAbstractItemView {{
    background-color: {c.surface};
    color: {c.text_primary};
    selection-background-color: {c.input_selection_bg};
    selection-color: {c.input_selection_text};
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QFrame#logPanelContainer {{
    border-top: 1px solid {c.border};
    background-color: {c.window};
}}
QProgressBar {{
    border: 1px solid {c.border};
    border-radius: 4px;
    background-color: {c.surface};
    text-align: center;
    color: {c.text_primary};
}}
QProgressBar::chunk {{
    background-color: {c.accent};
}}
"""


def apply_app_theme(app: QApplication, theme: ThemeMode) -> None:
    app.setStyle("Fusion")
    app.setProperty("hdm_theme", theme.value)
    app.setPalette(build_palette(theme))
    app.setStyleSheet(build_stylesheet(theme))
