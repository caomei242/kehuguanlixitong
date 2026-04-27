from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QLineEdit, QPushButton, QSizePolicy

from strawberry_customer_management.ui.pages.settings_page import SettingsPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _settings_panel(page: SettingsPage, role: str) -> QFrame:
    panels = [panel for panel in page.findChildren(QFrame) if panel.property("settingsRole") == role]
    assert len(panels) == 1
    return panels[0]


def test_settings_page_keeps_scroll_area_and_workspace_cards() -> None:
    _app()
    page = SettingsPage()

    assert page.scroll_area.widgetResizable()
    assert page.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff

    path_panel = _settings_panel(page, "paths")
    ai_panel = _settings_panel(page, "ai")
    status_panel = _settings_panel(page, "status")

    assert path_panel.objectName() == "WorkspacePanel"
    assert ai_panel.objectName() == "WorkspacePanel"
    assert status_panel.objectName() == "WorkspacePanel"
    assert path_panel.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert ai_panel.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding


def test_settings_fields_expand_inside_their_cards() -> None:
    _app()
    page = SettingsPage()

    path_panel = _settings_panel(page, "paths")
    ai_panel = _settings_panel(page, "ai")

    path_fields = path_panel.findChildren(QLineEdit)
    ai_fields = ai_panel.findChildren(QLineEdit)
    assert page.customer_root_edit in path_fields
    assert page.project_root_edit in path_fields
    assert page.main_work_root_edit in path_fields
    assert page.approval_inbox_root_edit in path_fields
    assert page.minimax_api_key_edit not in path_fields
    assert page.minimax_api_key_edit in ai_fields
    assert page.minimax_model_edit in ai_fields
    assert page.minimax_base_url_edit in ai_fields
    assert page.customer_root_edit not in ai_fields

    for editor in page.findChildren(QLineEdit):
        assert editor.minimumWidth() >= 280
        assert editor.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert editor.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed


def test_settings_save_payload_stays_compatible() -> None:
    _app()
    page = SettingsPage()
    page.set_values(
        customer_root=" /customers ",
        project_root="/projects",
        main_work_root="/main-work",
        approval_inbox_root="/inbox",
        minimax_api_key=" sk-cp-test ",
        minimax_model="MiniMax-M2.7",
        minimax_base_url="https://api.minimax.chat/v1",
    )

    emitted: list[object] = []
    page.save_requested.connect(emitted.append)
    page._emit_save()

    assert emitted == [
        {
            "customer_root": "/customers",
            "project_root": "/projects",
            "main_work_root": "/main-work",
            "approval_inbox_root": "/inbox",
            "ai_provider": "minimax",
            "minimax_api_key": "sk-cp-test",
            "minimax_model": "MiniMax-M2.7",
            "minimax_base_url": "https://api.minimax.chat/v1",
        }
    ]


def test_settings_actions_are_visible_in_short_window() -> None:
    app = _app()
    page = SettingsPage()
    page.resize(1200, 760)
    page.show()
    app.processEvents()

    action_buttons = {
        button.text(): button
        for button in page.findChildren(QPushButton)
        if button.text() in {"保存设置", "刷新数据", "校验路径"}
    }

    assert set(action_buttons) == {"保存设置", "刷新数据", "校验路径"}
    for button in action_buttons.values():
        mapped_top_left = button.mapTo(page, button.rect().topLeft())
        assert mapped_top_left.y() < 180

    page.close()
    app.processEvents()
