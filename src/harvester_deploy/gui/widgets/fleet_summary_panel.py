"""Farmer fleet summary (chia farm summary) from refresh."""

from __future__ import annotations

import html
import re

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import Harvester, NodeRole
from harvester_deploy.gui.styles import ThemeMode, current_theme_mode, theme_colors

_DETAIL_RE = re.compile(
    r"^(?P<indent>\s+)(?P<count>[\d,]+)\s+plots?\s+of\s+size:\s*(?P<size>.+)$"
)
_LABEL_VALUE_RE = re.compile(r"^(?P<label>[^:]+:)(?P<value>\s*.*)$")
_REMOTE_RE = re.compile(r"^(Remote Harvester for IP:)(\s*)(.+)$")
_SECTION_TITLE_RE = re.compile(r"^(Local Harvester|Remote Harvester.*)$")


def _format_summary_html(
    title: str,
    body: str,
    *,
    theme: ThemeMode,
    is_error: bool = False,
) -> str:
    colors = theme_colors(theme)
    title_color = colors.danger if is_error else colors.text_primary
    title_bg = colors.surface_alt if not is_error else colors.danger
    title_fg = colors.text_primary if not is_error else colors.input_selection_text
    lines = [_format_summary_line(line, theme=theme, is_error=is_error) for line in body.splitlines()] or [
        _format_summary_line("", theme=theme, is_error=is_error)
    ]
    return (
        f"<div style='margin-bottom:18px;'>"
        f"<div style='font-weight:700; color:{title_fg}; background-color:{title_bg}; "
        f"border:1px solid {colors.border}; border-radius:6px; padding:6px 10px; margin-bottom:8px;'>"
        f"{html.escape(title)}</div>"
        f"<div style='font-family:Consolas, \"Courier New\", monospace; white-space:pre-wrap;'>"
        + "<br>".join(lines)
        + "</div><br></div>"
    )


def _format_summary_line(line: str, *, theme: ThemeMode, is_error: bool = False) -> str:
    colors = theme_colors(theme)
    value_color = colors.accent_pressed if theme == ThemeMode.LIGHT else colors.accent_hover
    escaped = html.escape(line)
    if not line:
        return ""
    if is_error or line.startswith("Error:"):
        return f"<span style='color:{colors.danger};'>{escaped}</span>"

    remote = _REMOTE_RE.match(line)
    if remote:
        return (
            f"<span style='color:{colors.text_primary}; font-weight:600;'>{html.escape(remote.group(1))}</span>"
            f"{_spaces_html(remote.group(2))}"
            f"<span style='color:{value_color}; font-weight:600;'>{html.escape(remote.group(3))}</span>"
        )

    if _SECTION_TITLE_RE.match(line):
        return f"<span style='color:{value_color}; font-weight:600;'>{escaped}</span>"

    detail = _DETAIL_RE.match(line)
    if detail:
        return (
            f"{_spaces_html(detail.group('indent'))}"
            f"<span style='color:{value_color}; font-weight:600;'>{html.escape(detail.group('count'))}</span>"
            f"<span style='color:{colors.text_primary};'> plots of size: </span>"
            f"<span style='color:{colors.success}; font-weight:600;'>{html.escape(detail.group('size'))}</span>"
        )

    label_value = _LABEL_VALUE_RE.match(line)
    if label_value:
        return (
            f"<span style='color:{colors.text_muted}; font-weight:600;'>{html.escape(label_value.group('label'))}</span>"
            f"<span style='color:{value_color};'>{html.escape(label_value.group('value'))}</span>"
        )

    return f"<span style='color:{colors.text_primary};'>{escaped}</span>"


def _spaces_html(text: str) -> str:
    return text.replace(" ", "&nbsp;").replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")


class FleetSummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = current_theme_mode()
        self._last_harvesters: list[Harvester] = []
        self._last_results: list[dict | BaseException] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        action_bar = QFrame()
        action_bar.setObjectName("actionBar")
        header = QHBoxLayout(action_bar)
        header.setContentsMargins(12, 10, 12, 10)
        header.setSpacing(12)
        self._title = QLabel(
            "<b>Farmer fleet summary</b> — from <code>chia farm summary</code> "
            "on farmer node(s). Use <b>Refresh fleet</b> on the Nodes tab."
        )
        self._title.setWordWrap(True)
        header.addWidget(self._title, stretch=1)
        layout.addWidget(action_bar)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlaceholderText(
            "Refresh fleet to load chia farm summary from farmer node(s)."
        )
        self._text.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._text, stretch=1)
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeMode) -> None:
        self._theme = theme
        colors = theme_colors(theme)
        self._title.setStyleSheet(f"color: {colors.text_primary}; background: transparent;")
        self._text.setStyleSheet(
            f"background-color: {colors.input_bg}; color: {colors.input_text}; "
            f"border: 1px solid {colors.border}; border-radius: 4px;"
        )
        self._render_summary()

    def update_from_status(
        self,
        harvesters: list[Harvester],
        results: list[dict | BaseException],
    ) -> None:
        self._last_harvesters = list(harvesters)
        self._last_results = list(results)
        self._render_summary()

    def _render_summary(self) -> None:
        blocks: list[str] = []
        for harvester, result in zip(
            self._last_harvesters,
            self._last_results,
            strict=True,
        ):
            if harvester.role != NodeRole.FARMER:
                continue
            if isinstance(result, BaseException):
                blocks.append(
                    _format_summary_html(
                        f"{harvester.display_name} ({harvester.network_label})",
                        f"Error: {result}",
                        theme=self._theme,
                        is_error=True,
                    )
                )
                continue
            error = str(result.get("error") or "").strip()
            if error:
                blocks.append(
                    _format_summary_html(
                        f"{harvester.display_name} ({harvester.network_label})",
                        f"Error: {error}",
                        theme=self._theme,
                        is_error=True,
                    )
                )
                continue
            summary = (result.get("summary") or "").strip()
            if not summary:
                summary = "(no farm summary — package node or command unavailable)"
            blocks.append(
                _format_summary_html(
                    f"{harvester.display_name} ({harvester.network_label})",
                    summary,
                    theme=self._theme,
                )
            )

        if blocks:
            self._text.setHtml("".join(blocks))
        else:
            self._text.setHtml(
                _format_summary_html(
                    "Fleet summary",
                    "No farmer nodes in fleet, or refresh has not completed yet.",
                    theme=self._theme,
                )
            )
