"""Application-wide Qt styles (readable on Windows light/dark themes)."""

APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #f0f2f5;
    color: #1a1a1a;
}
QLabel {
    color: #1a1a1a;
}
QMenuBar {
    background-color: #ffffff;
    color: #1a1a1a;
    border-bottom: 1px solid #c8cdd3;
    padding: 2px;
}
QMenuBar::item:selected {
    background-color: #e2e6ea;
}
QMenu {
    background-color: #ffffff;
    color: #1a1a1a;
}
QStatusBar {
    background-color: #ffffff;
    color: #1a1a1a;
    border-top: 1px solid #c8cdd3;
}
QFrame#actionBar {
    background-color: #ffffff;
    border: 1px solid #c8cdd3;
    border-radius: 6px;
}
QLabel#inlineCaption {
    background: transparent;
    border: none;
    padding: 0 6px 0 0;
    color: #1a1a1a;
    font-weight: 600;
}
QFrame#nodeCard {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #c8cdd3;
    border-radius: 8px;
}
QFrame#nodeCard[failed="true"] {
    border: 2px solid #c0392b;
}
QFrame#nodeCard[busy="true"] {
    border: 2px solid #4a6fa5;
}
QPushButton {
    background-color: #e9ecef;
    color: #1a1a1a;
    border: 1px solid #adb5bd;
    border-radius: 4px;
    padding: 6px 14px;
    min-height: 28px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #dee2e6;
}
QPushButton:pressed {
    background-color: #ced4da;
}
QPushButton:disabled {
    color: #868e96;
    background-color: #f1f3f5;
}
QComboBox {
    background-color: #ffffff;
    color: #1a1a1a;
    border: 1px solid #adb5bd;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 28px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1a1a1a;
    selection-background-color: #4a6fa5;
    selection-color: #ffffff;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QSplitter#mainSplitter::handle:vertical {
    height: 2px;
    margin: 0;
    padding: 0;
    border: none;
    border-top: 2px solid #4a6fa5;
    background-color: #dee2e6;
    border-radius: 0;
}
QSplitter#mainSplitter::handle:vertical:hover {
    border-top: 2px solid #3d5f94;
    background-color: #ced4da;
}
QFrame#logPanelContainer {
    border-top: 1px solid #c8cdd3;
    background-color: #f0f2f5;
}
QProgressBar {
    border: 1px solid #adb5bd;
    border-radius: 4px;
    background-color: #ffffff;
    text-align: center;
    color: #1a1a1a;
}
QProgressBar::chunk {
    background-color: #4a6fa5;
}
"""
