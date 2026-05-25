"""Live deploy log viewer."""

from __future__ import annotations

from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.gui.styles import ThemeMode, current_theme_mode, theme_colors

_FILTER_ROLE = Qt.ItemDataRole.UserRole


class LogPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = current_theme_mode()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        action_bar = QFrame()
        action_bar.setObjectName("actionBar")
        header = QHBoxLayout(action_bar)
        header.setContentsMargins(12, 10, 12, 10)
        header.setSpacing(12)
        self._title = QLabel("Deploy log")
        header.addWidget(self._title)

        log_filter_label = QLabel("Show:")
        log_filter_label.setObjectName("inlineCaption")
        header.addWidget(log_filter_label)

        self._filter = QComboBox()
        self._filter.setMinimumWidth(160)
        self._filter.currentIndexChanged.connect(self._rebuild_view)
        header.addWidget(self._filter)

        self._btn_clear = QPushButton("Clear")
        self._btn_clear.clicked.connect(self.clear_visible)
        header.addWidget(self._btn_clear)

        self._btn_select_all = QPushButton("Select All")
        self._btn_select_all.clicked.connect(self.select_visible)
        header.addWidget(self._btn_select_all)

        self._btn_deselect_all = QPushButton("Deselect All")
        self._btn_deselect_all.clicked.connect(self.deselect_visible)
        header.addWidget(self._btn_deselect_all)

        self._btn_copy = QPushButton("Copy to Clipboard")
        self._btn_copy.clicked.connect(self.copy_visible)
        header.addWidget(self._btn_copy)

        self._btn_save = QPushButton("Save as")
        self._btn_save.clicked.connect(self.save_visible_as)
        header.addWidget(self._btn_save)

        header.addStretch()

        self._hint = QLabel("Use a node's Log button to focus its log")
        header.addWidget(self._hint)
        layout.addWidget(action_bar)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(5000)
        layout.addWidget(self._text)

        self._lines: list[tuple[str, str, str]] = []
        self._node_colors: dict[str, QColor] = {}
        self._palette: list[QColor] = []
        self._body_text_color = QColor("#1f2933")
        self._stamp_text_color = QColor("#808b96")
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemeMode) -> None:
        self._theme = theme
        colors = theme_colors(theme)
        self._title.setStyleSheet(
            f"font-weight: 600; color: {colors.text_primary}; background: transparent;"
        )
        self._hint.setStyleSheet(
            f"color: {colors.text_muted}; font-size: 11px; background: transparent;"
        )
        self._text.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px;"
            f"background-color: {colors.log_bg}; color: {colors.log_text};"
            f"border: 1px solid {colors.log_border}; border-radius: 4px;"
        )
        self._body_text_color = QColor(colors.log_text)
        self._stamp_text_color = QColor(colors.text_muted)
        if theme == ThemeMode.DARK:
            palette = [
                "#4fc3f7",
                "#81c784",
                "#ffb74d",
                "#ce93d8",
                "#f06292",
                "#aed581",
                "#ff8a65",
            ]
        else:
            palette = [
                "#005f99",
                "#2e7d32",
                "#b35400",
                "#7b1fa2",
                "#c2185b",
                "#558b2f",
                "#bf360c",
            ]
        self._palette = [QColor(value) for value in palette]
        self._node_colors.clear()
        self._rebuild_view()

    def _selected_node_id(self) -> str | None:
        """None means show all nodes."""
        node_id = self._filter.currentData(_FILTER_ROLE)
        if node_id is None:
            return None
        text = str(node_id).strip()
        return text if text else None

    def set_nodes(self, node_ids: list[str]) -> None:
        selected = self._selected_node_id()
        self._filter.blockSignals(True)
        self._filter.clear()
        self._filter.addItem("All nodes")
        self._filter.setItemData(0, "", _FILTER_ROLE)
        for i, nid in enumerate(sorted(node_ids), start=1):
            self._filter.addItem(nid)
            self._filter.setItemData(i, nid, _FILTER_ROLE)
        self._filter.blockSignals(False)
        if selected:
            idx = self._filter.findData(selected, _FILTER_ROLE)
            if idx >= 0:
                self._filter.setCurrentIndex(idx)
        self._rebuild_view()

    def focus_node(self, node_id: str) -> None:
        idx = self._filter.findData(node_id, _FILTER_ROLE)
        if idx >= 0:
            self._filter.setCurrentIndex(idx)
        self._hint.setText(f"Filtered to {node_id}")

    def clear(self) -> None:
        self._lines.clear()
        self._text.clear()
        self._node_colors.clear()

    def clear_visible(self) -> None:
        selected = self._selected_node_id()
        if selected is None:
            self.clear()
            return
        self._lines = [entry for entry in self._lines if entry[1] != selected]
        self._rebuild_view()

    def select_visible(self) -> None:
        self._text.selectAll()

    def deselect_visible(self) -> None:
        cursor = self._text.textCursor()
        cursor.clearSelection()
        self._text.setTextCursor(cursor)

    def copy_visible(self) -> None:
        text = self._visible_text()
        if text:
            QApplication.clipboard().setText(text)

    def save_visible_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save log view",
            "deploy-log.txt",
            "Text files (*.txt);;Log files (*.log);;All files (*.*)",
        )
        if not path:
            return
        self.save_visible_to(path)

    def save_visible_to(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self._visible_text())

    def _color_for(self, node_id: str) -> QColor:
        if node_id not in self._node_colors:
            idx = len(self._node_colors) % len(self._palette)
            self._node_colors[node_id] = self._palette[idx]
        return self._node_colors[node_id]

    def _passes_filter(self, node_id: str) -> bool:
        selected = self._selected_node_id()
        return selected is None or selected == node_id

    def _visible_entries(self) -> list[tuple[str, str, str]]:
        return [entry for entry in self._lines if self._passes_filter(entry[1])]

    def _format_entry(self, stamp: str, node_id: str, line: str) -> str:
        return f"{stamp} | {node_id} | {line}"

    def _visible_text(self) -> str:
        return "\n".join(
            self._format_entry(stamp, node_id, line)
            for stamp, node_id, line in self._visible_entries()
        )

    def append_line(self, node_id: str, line: str) -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = line.splitlines() or [""]
        for part in parts:
            self._lines.append((stamp, node_id, part))
            if self._passes_filter(node_id):
                self._append_to_widget(stamp, node_id, part)

    def _append_to_widget(self, stamp: str, node_id: str, line: str) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        stamp_fmt = QTextCharFormat()
        stamp_fmt.setForeground(self._stamp_text_color)
        cursor.insertText(f"{stamp} | ", stamp_fmt)

        prefix_fmt = QTextCharFormat()
        prefix_fmt.setForeground(self._color_for(node_id))
        prefix_fmt.setFontWeight(700)
        cursor.insertText(f"{node_id} | ", prefix_fmt)

        body_fmt = QTextCharFormat()
        body_fmt.setForeground(self._body_text_color)
        cursor.insertText(f"{line}\n", body_fmt)

        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def _rebuild_view(self) -> None:
        selected = self._selected_node_id()
        if selected is None:
            self._hint.setText("Showing all nodes — pick one to filter")
        else:
            self._hint.setText(f"Showing log for {selected}")

        self._text.clear()
        for stamp, node_id, line in self._visible_entries():
            self._append_to_widget(stamp, node_id, line)
