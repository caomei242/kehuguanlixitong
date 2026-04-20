from __future__ import annotations

import os

from strawberry_customer_management.app import build_app
from strawberry_customer_management.config import ConfigStore
from strawberry_customer_management.models import CommunicationEntry, CustomerDraft
from strawberry_customer_management.ui.pages.quick_capture_page import QuickCapturePage
from strawberry_customer_management.ui.main_window import MainWindow


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_instantiates_with_empty_customer_root(tmp_path):
    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "main_work_root": str(tmp_path / "主业"),
        }
    )

    app = build_app()
    window = MainWindow(config_store=config_store)

    assert window.windowTitle() == "草莓客户管理系统"
    assert window.nav.count() == 3
    window.close()
    app.processEvents()


def test_quick_capture_page_applies_ai_draft_to_form():
    app = build_app()
    page = QuickCapturePage()

    page.apply_draft(
        CustomerDraft(
            name="云舟店群",
            customer_type="网店店群客户",
            stage="沟通中",
            business_direction="集采点数 / 店铺软件批量采购",
            contact="王五",
            company="云舟电商",
            shop_scale="50家店",
            current_need="想确认批量购买是否有阶梯折扣",
            recent_progress="客户询价批量折扣",
            next_action="确认采购数量后报价",
            communication=CommunicationEntry(
                entry_date="2026-04-20",
                summary="店群客户询价批量采购折扣",
                new_info="关注店铺软件和集采点数",
                risk="采购时间未定",
                next_step="补齐采购数量",
            ),
        )
    )

    assert page.name_edit.text() == "云舟店群"
    assert page.type_combo.currentText() == "网店店群客户"
    assert page.stage_combo.currentText() == "沟通中"
    assert page.need_edit.toPlainText() == "想确认批量购买是否有阶梯折扣"
    assert page.summary_edit.toPlainText() == "店群客户询价批量采购折扣"
    page.close()
    app.processEvents()
