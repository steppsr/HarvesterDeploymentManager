"""Live deploy log viewer."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

_FILTER_ROLE = Qt.ItemDataRole.UserRole


class LogPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("Deploy log")
        title.setStyleSheet("font-weight: 600; color: #1a1a1a;")
        header.addWidget(title)

        log_filter_label = QLabel("Show:")
        log_filter_label.setObjectName("inlineCaption")
        header.addWidget(log_filter_label)

        self._filter = QComboBox()
        self._filter.setMinimumWidth(160)
        self._filter.currentIndexChanged.connect(self._rebuild_view)
        header.addWidget(self._filter)
        header.addStretch()

        self._hint = QLabel("Click a node card to focus its log")
        self._hint.setStyleSheet("color: #6c757d; font-size: 11px;")
        header.addWidget(self._hint)
        layout.addLayout(header)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(5000)
        self._text.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px;"
            "background-color: #1e1e1e; color: #d4d4d4;"
            "border: 1px solid #3c3c3c; border-radius: 4px;"
        )
        layout.addWidget(self._text)

        self._lines: list[tuple[str, str]] = []
        self._node_colors: dict[str, QColor] = {}
        self._palette = [
            QColor("#4fc3f7"),
            QColor("#81c784"),
            QColor("#ffb74d"),
            QColor("#ce93d8"),
            QColor("#f06292"),
            QColor("#aed581"),
            QColor("#ff8a65"),
        ]

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

    def _color_for(self, node_id: str) -> QColor:
        if node_id not in self._node_colors:
            idx = len(self._node_colors) % len(self._palette)
            self._node_colors[node_id] = self._palette[idx]
        return self._node_colors[node_id]

    def _passes_filter(self, node_id: str) -> bool:
        selected = self._selected_node_id()
        return selected is None or selected == node_id

    def append_line(self, node_id: str, line: str) -> None:
        self._lines.append((node_id, line))
        if self._passes_filter(node_id):
            self._append_to_widget(node_id, line)

    def _append_to_widget(self, node_id: str, line: str) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        prefix_fmt = QTextCharFormat()
        prefix_fmt.setForeground(self._color_for(node_id))
        prefix_fmt.setFontWeight(700)
        cursor.insertText(f"{node_id} | ", prefix_fmt)

        body_fmt = QTextCharFormat()
        body_fmt.setForeground(QColor("#d4d4d4"))
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
        for node_id, line in self._lines:
            if self._passes_filter(node_id):
                self._append_to_widget(node_id, line)
