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
QFrame#SettingsCard,
QFrame#TopbarPanel,
QFrame#WorkspacePanel {
    background: rgba(255, 255, 255, 0.97);
    border: 1px solid #dbe4f2;
    border-radius: 22px;
}

QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #e3e9f4;
    border-radius: 18px;
}

QFrame#SideItem {
    background: #ffffff;
    border: 1px solid #e6edf7;
    border-radius: 14px;
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

QLabel#PanelTitle {
    color: #244ebd;
    background: #eef4ff;
    border: 1px solid #d5e1ff;
    border-radius: 10px;
    padding: 5px 9px;
    font-size: 14px;
    font-weight: 850;
}

QLabel#SectionHint {
    color: #7e8aa5;
    font-size: 12px;
}

QLabel#PanelHint {
    color: #74829a;
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}

QLabel#OverviewBanner {
    background: #fff6df;
    color: #684915;
    border: 1px solid #f2d79c;
    border-radius: 16px;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#MetricLabel {
    color: #7a89a6;
    font-size: 12px;
    font-weight: 700;
}

QLabel#MetricValue {
    color: #1b2a45;
    font-size: 25px;
    font-weight: 850;
}

QLabel#SoftBadge {
    background: #eef4ff;
    color: #3f67d9;
    border: 1px solid #d5e1ff;
    border-radius: 10px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 700;
}

QLabel#SideItemTitle {
    color: #20304a;
    font-size: 13px;
    font-weight: 800;
}

QLabel#EmptyState {
    background: #f8fafc;
    color: #7e8aa5;
    border: 1px dashed #dbe4f2;
    border-radius: 16px;
    padding: 28px;
}

QFrame#ApprovalInboxDropZone {
    background: #f8fbff;
    border: 1px dashed #a9c0ff;
    border-radius: 16px;
}

QFrame#ApprovalInboxDropZone:hover {
    background: #eef4ff;
    border-color: #4a7cff;
}

QLabel#DropZoneTitle {
    color: #244ebd;
    font-size: 14px;
    font-weight: 850;
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

QFrame#CustomerTile,
QFrame#CustomerTileSelected {
    background: #ffffff;
    border: 1px solid #e0e8f4;
    border-radius: 16px;
    min-height: 108px;
}

QFrame#CustomerTileSelected {
    background: #eef4ff;
    border-color: #9fbcff;
}

QLabel#CustomerTileName {
    color: #20304a;
    font-size: 15px;
    font-weight: 850;
}

QLabel#CustomerTileMeta {
    color: #53627d;
    font-size: 12px;
    font-weight: 650;
}

QLabel#CustomerTileNeed {
    color: #20304a;
    font-size: 13px;
    font-weight: 750;
}

QPushButton#InlineActionButton {
    background: #eef4ff;
    color: #244ebd;
    border: 1px solid #cddcff;
    border-radius: 10px;
    padding: 5px 9px;
    font-size: 12px;
}

QPushButton#FieldLockButton {
    background: #f8fafc;
    color: #53627d;
    border: 1px solid #d9e2f1;
    border-radius: 10px;
    padding: 6px 9px;
    font-size: 12px;
    min-width: 46px;
}

QPushButton#FieldLockButton:checked {
    background: #fff6df;
    color: #9d6d16;
    border: 1px solid #f1dca6;
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
