from __future__ import annotations

import os
import time

from strawberry_customer_management.app import build_app
from strawberry_customer_management.config import ConfigStore
from strawberry_customer_management.models import CommunicationEntry, CustomerDraft
from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.models import CustomerDetail
from strawberry_customer_management.ui.pages.overview_page import OverviewPage
from strawberry_customer_management.ui.pages.quick_capture_page import QuickCapturePage
from strawberry_customer_management.ui.pages.settings_page import SettingsPage
from strawberry_customer_management.ui.main_window import MainWindow

from PySide6.QtWidgets import QScrollArea


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


def test_pages_have_outer_scroll_area():
    app = build_app()
    pages = [OverviewPage(), QuickCapturePage(), SettingsPage()]

    for page in pages:
        assert page.findChild(QScrollArea) is not None
        page.close()
    app.processEvents()


def test_overview_page_emits_ai_update_for_current_customer():
    app = build_app()
    page = OverviewPage()
    captured: list[str] = []
    page.update_customer_requested.connect(captured.append)

    page.show_customer_detail(
        CustomerDetail(
            name="爱慕",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌推广",
        )
    )
    page.ai_update_button.click()

    assert captured == ["爱慕"]
    page.close()
    app.processEvents()


def test_main_window_prepares_existing_customer_for_ai_update(tmp_path):
    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    store = MarkdownCustomerStore(customer_root)
    store.upsert_customer(
        CustomerDraft(
            name="爱慕",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌推广",
            contact="张三",
            company="爱慕股份有限公司",
            current_need="补充新业务需求",
            next_action="确认预算",
            communication=CommunicationEntry(entry_date="2026-04-20", summary="已有客户"),
        )
    )
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save({"customer_root": str(customer_root), "main_work_root": str(tmp_path / "主业")})
    app = build_app()
    window = MainWindow(config_store=config_store)

    window._prepare_existing_customer_update("爱慕")

    assert window.nav.currentRow() == 1
    assert window.quick_capture_page.name_edit.text() == "爱慕"
    assert window.quick_capture_page.type_combo.currentText() == "品牌客户"
    assert window.quick_capture_page.stage_combo.currentText() == "已合作"
    assert window.quick_capture_page.target_customer_name == "爱慕"
    window.close()
    app.processEvents()


def test_ai_extract_returns_immediately_while_worker_runs(tmp_path, monkeypatch):
    class SlowClient:
        def __init__(self, **_kwargs):
            pass

        def extract_draft(self, *_args, **_kwargs):
            time.sleep(0.2)
            return CustomerDraft(
                name="爱慕",
                customer_type="品牌客户",
                stage="沟通中",
                current_need="补充品牌推广需求",
                communication=CommunicationEntry(entry_date="2026-04-20", summary="补充品牌推广需求"),
            )

    monkeypatch.setattr("strawberry_customer_management.ui.main_window.MiniMaxCaptureClient", SlowClient)
    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "main_work_root": str(tmp_path / "主业"),
            "minimax_api_key": "test-key",
        }
    )
    app = build_app()
    window = MainWindow(config_store=config_store)

    started_at = time.perf_counter()
    window._handle_ai_extract("爱慕补充品牌推广需求", "")
    elapsed = time.perf_counter() - started_at

    assert elapsed < 0.1
    assert not window.quick_capture_page.ai_extract_button.isEnabled()

    deadline = time.time() + 2
    while time.time() < deadline and not window.quick_capture_page.ai_extract_button.isEnabled():
        app.processEvents()
        time.sleep(0.01)

    assert window.quick_capture_page.ai_extract_button.isEnabled()
    assert window.quick_capture_page.name_edit.text() == "爱慕"
    window.close()
    app.processEvents()
