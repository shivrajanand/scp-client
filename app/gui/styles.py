"""
Qt stylesheets for the application's dark and light themes.

Kept intentionally simple (flat colors, generous padding) rather than
pulling in a third-party Qt theming library, to keep dependencies small
per spec section 40.
"""

DARK_STYLESHEET = """
QWidget {
    background-color: #1e1f22;
    color: #e6e6e6;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #1e1f22;
}
QLabel#SectionLabel {
    color: #9aa0a6;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #2b2d31;
    border: 1px solid #3c3f44;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e6e6e6;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #5b8def;
}
QPushButton {
    background-color: #3c3f44;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #e6e6e6;
}
QPushButton:hover {
    background-color: #4a4d53;
}
QPushButton:pressed {
    background-color: #33363b;
}
QPushButton:disabled {
    background-color: #2b2d31;
    color: #6b6f76;
}
QPushButton#PrimaryButton {
    background-color: #5b8def;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: #6f9bf2;
}
QPushButton#PrimaryButton:disabled {
    background-color: #33455f;
    color: #9aa5b5;
}
QPushButton#DirectionButton {
    padding: 12px;
    font-weight: 600;
    border-radius: 8px;
}
QPushButton#DirectionButton:checked {
    background-color: #5b8def;
    color: white;
}
QProgressBar {
    background-color: #2b2d31;
    border-radius: 6px;
    text-align: center;
    color: #e6e6e6;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #5b8def;
    border-radius: 6px;
}
QPlainTextEdit, QTextEdit {
    background-color: #17181a;
    border: 1px solid #3c3f44;
    border-radius: 6px;
    color: #c7c7c7;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QTreeWidget, QTableWidget, QListWidget {
    background-color: #2b2d31;
    border: 1px solid #3c3f44;
    border-radius: 6px;
    alternate-background-color: #26282c;
}
QHeaderView::section {
    background-color: #2b2d31;
    padding: 4px;
    border: none;
    border-bottom: 1px solid #3c3f44;
}
QStatusBar {
    background-color: #17181a;
    color: #9aa0a6;
}
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #fafafa;
    color: #1c1c1c;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #fafafa;
}
QLabel#SectionLabel {
    color: #5f6368;
    font-weight: 600;
    letter-spacing: 0.5px;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 6px 8px;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3568d4;
}
QPushButton {
    background-color: #eeeeee;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #1c1c1c;
}
QPushButton:hover {
    background-color: #e2e2e2;
}
QPushButton:pressed {
    background-color: #d6d6d6;
}
QPushButton:disabled {
    background-color: #f2f2f2;
    color: #a6a6a6;
}
QPushButton#PrimaryButton {
    background-color: #3568d4;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: #4778e0;
}
QPushButton#PrimaryButton:disabled {
    background-color: #b7c8ee;
    color: #eef2fb;
}
QPushButton#DirectionButton {
    padding: 12px;
    font-weight: 600;
    border-radius: 8px;
}
QPushButton#DirectionButton:checked {
    background-color: #3568d4;
    color: white;
}
QProgressBar {
    background-color: #e6e6e6;
    border-radius: 6px;
    text-align: center;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #3568d4;
    border-radius: 6px;
}
QPlainTextEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    font-family: Consolas, monospace;
    font-size: 12px;
}
QTreeWidget, QTableWidget, QListWidget {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    alternate-background-color: #f4f4f4;
}
QHeaderView::section {
    background-color: #f0f0f0;
    padding: 4px;
    border: none;
    border-bottom: 1px solid #d0d0d0;
}
QStatusBar {
    background-color: #f0f0f0;
    color: #5f6368;
}
"""


def stylesheet_for_theme(theme: str) -> str:
    return DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET
