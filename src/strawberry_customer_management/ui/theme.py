from __future__ import annotations

from PySide6.QtWidgets import QApplication


APP_STYLESHEET = """
QWidget {
    color: #20304a;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "Segoe UI", sans-serif;
    font-size: 14px;
}

QMainWindow {
    background: #eff3f8;
}

QFrame#WindowShell {
    background: #f7f9fc;
    border: 1px solid #dde5f0;
    border-radius: 30px;
}

QFrame#WindowSidebar {
    background: #fcfdff;
    border: 1px solid #e3eaf3;
    border-radius: 24px;
}

QFrame#SidebarBrandCard,
QFrame#SidebarNavCard {
    background: #ffffff;
    border: 1px solid #e4ebf4;
    border-radius: 22px;
}

QFrame#SidebarBrandCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fffaf7, stop:1 #fff3f6);
}

QFrame#WindowContentShell,
QFrame#CardFrame,
QFrame#FocusCard,
QFrame#DetailCard,
QFrame#SettingsCard,
QFrame#TopbarPanel,
QFrame#WorkspacePanel {
    background: rgba(255, 255, 255, 0.99);
    border: 1px solid #e4ebf4;
    border-radius: 24px;
}

QFrame#WindowContentShell {
    background: #fbfcfe;
    border-radius: 26px;
}

QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #e7edf6;
    border-radius: 20px;
}

QFrame#SideItem {
    background: #ffffff;
    border: 1px solid #e8eef7;
    border-radius: 16px;
}

QFrame#SidebarProfileCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff8f4, stop:1 #fff1f4);
    border: 1px solid #ffd7df;
    border-radius: 22px;
}

QLabel#SidebarEyebrow {
    color: #bc6d4f;
    background: #fff3e7;
    border: 1px solid #ffd8bc;
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 800;
}

QLabel#SidebarSectionTitle {
    color: #20304a;
    font-size: 13px;
    font-weight: 800;
}

QLabel#SidebarSectionHint {
    color: #7c879d;
    font-size: 12px;
    line-height: 1.35;
}

QLabel#SidebarAvatar {
    background: #ff5c78;
    color: #ffffff;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    font-size: 16px;
    font-weight: 900;
    qproperty-alignment: AlignCenter;
}

QLabel#SidebarProfileName {
    color: #20304a;
    font-size: 14px;
    font-weight: 800;
}

QLabel#SidebarProfileRole {
    color: #8a6172;
    font-size: 11px;
    font-weight: 700;
}

QLabel#SidebarProfileBadge {
    background: rgba(255, 255, 255, 0.78);
    color: #b64e68;
    border: 1px solid #ffc0cd;
    border-radius: 11px;
    padding: 5px 9px;
    font-size: 11px;
    font-weight: 800;
}

QLabel#SidebarProfileMeta {
    color: #7b6670;
    font-size: 12px;
    line-height: 1.4;
}

QLabel#BrandTitle {
    color: #ff5675;
    font-size: 30px;
    font-weight: 900;
}

QLabel#BrandSubtitle {
    color: #6f7f97;
    font-size: 12px;
    font-weight: 700;
}

QLabel#SectionTitle {
    color: #20304a;
    font-size: 20px;
    font-weight: 700;
}

QLabel#PanelTitle {
    color: #244ebd;
    background: #f2f6ff;
    border: 1px solid #dce6ff;
    border-radius: 11px;
    padding: 6px 10px;
    font-size: 13px;
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
    border-radius: 18px;
    padding: 11px 16px;
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
    background: transparent;
    border: none;
    border-radius: 18px;
    padding: 0;
    outline: none;
}

QListWidget#WorkbenchNav::item {
    background: transparent;
    border: none;
    padding: 0;
    margin: 0 0 8px 0;
}

QListWidget#WorkbenchNav::item:selected {
    background: transparent;
}

QFrame#NavCard {
    background: #f7f9fc;
    border: 1px solid #e3eaf3;
    border-radius: 18px;
}

QFrame#NavCard[current="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fff1f4, stop:1 #fff7f7);
    border: 1px solid #ffc4d0;
}

QLabel#NavCardIndex {
    background: #ffffff;
    color: #8fa0bc;
    border: 1px solid #dbe4f1;
    border-radius: 11px;
    min-width: 28px;
    max-width: 28px;
    min-height: 22px;
    max-height: 22px;
    font-size: 11px;
    font-weight: 800;
    qproperty-alignment: AlignCenter;
}

QFrame#NavCard[current="true"] QLabel#NavCardIndex {
    background: #ff647f;
    color: #ffffff;
    border: 1px solid #ff647f;
}

QLabel#NavCardTitle {
    color: #22324d;
    font-size: 13px;
    font-weight: 800;
}

QLabel#NavCardSubtitle {
    color: #7c889f;
    font-size: 11px;
    font-weight: 600;
}

QFrame#NavCard[current="true"] QLabel#NavCardTitle {
    color: #7f2340;
}

QFrame#NavCard[current="true"] QLabel#NavCardSubtitle {
    color: #b26a81;
}

QPushButton {
    background: #4a7cff;
    color: white;
    border: none;
    border-radius: 14px;
    padding: 9px 14px;
    font-weight: 700;
}

QPushButton:hover {
    background: #3d70f0;
}

QPushButton#SecondaryActionButton {
    background: #f3f7ff;
    color: #3f67d9;
    border: 1px solid #d7e2ff;
}

QPushButton#SecondaryActionButton:hover {
    background: #e8f0ff;
}

QFrame#CustomerTile,
QFrame#CustomerTileSelected {
    background: #ffffff;
    border: 1px solid #e5ebf6;
    border-radius: 18px;
    min-height: 112px;
}

QFrame#CustomerTileSelected {
    background: #f3f7ff;
    border-color: #9fbcff;
}

QFrame#FollowUpCard {
    background: #ffffff;
    border: 1px solid #e4ebf6;
    border-radius: 18px;
}

QFrame#FollowUpCardSelected {
    background: #f4f7ff;
    border: 1px solid #a9c1ff;
    border-radius: 18px;
}

QLabel#TimelineGroupLabel {
    color: #5b73d8;
    background: #eef3ff;
    border: 1px solid #d6e0ff;
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 800;
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
    background: #f3f7ff;
    color: #244ebd;
    border: 1px solid #d8e2ff;
    border-radius: 10px;
    padding: 5px 9px;
    font-size: 12px;
    font-weight: 700;
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
