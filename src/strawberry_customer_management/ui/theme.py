from __future__ import annotations

from PySide6.QtWidgets import QApplication


APP_STYLESHEET = """
QWidget {
    color: #20304a;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background: #e9eef5;
}

QFrame#WindowShell {
    background: #f4f7fb;
    border: 1px solid #d8e1ef;
    border-radius: 16px;
}

QFrame#WindowSidebar {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
    border-bottom-left-radius: 16px;
}

QFrame#WindowContentShell,
QFrame#CardFrame,
QFrame#FocusCard,
QFrame#DetailCard,
QFrame#SettingsCard {
    background: rgba(255, 255, 255, 0.97);
    border: 1px solid #dbe4f2;
    border-radius: 22px;
}

QLabel#BrandTitle {
    color: #ff4b6e;
    font-size: 26px;
    font-weight: 800;
}

QLabel#BrandSubtitle {
    color: #7e8aa5;
    font-size: 12px;
}

QLabel#SectionTitle {
    color: #20304a;
    font-size: 18px;
    font-weight: 700;
}

QLabel#SectionHint {
    color: #7e8aa5;
    font-size: 12px;
}

QLabel#FocusItem {
    background: #eef4ff;
    color: #315ecf;
    border: 1px solid #cddcff;
    border-radius: 12px;
    padding: 8px 10px;
    font-weight: 600;
}

QListWidget {
    background: rgba(255, 255, 255, 0.98);
    border: 1px solid #dbe4f2;
    border-radius: 18px;
    padding: 6px;
    outline: none;
}

QListWidget::item {
    padding: 9px 11px;
    margin: 2px 0;
    border-radius: 12px;
}

QListWidget::item:selected {
    background: #4a7cff;
    color: #ffffff;
}

QPushButton {
    background: #4a7cff;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 8px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background: #3d70f0;
}

QPushButton#SecondaryActionButton {
    background: #eef4ff;
    color: #3f67d9;
    border: 1px solid #cddcff;
}

QPushButton#SecondaryActionButton:hover {
    background: #e3ecff;
}

QLineEdit, QTextEdit, QComboBox {
    background: #ffffff;
    border: 1px solid #d9e2f1;
    border-radius: 10px;
    padding: 7px 10px;
    color: #20304a;
}

QTextBrowser {
    background: transparent;
    border: none;
}

QScrollArea, QAbstractScrollArea {
    background: transparent;
    border: none;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(APP_STYLESHEET)

