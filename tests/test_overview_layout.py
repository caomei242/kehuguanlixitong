from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy

from strawberry_customer_management.models import CustomerRecord, ProjectRecord
from strawberry_customer_management.ui.pages.overview_page import OverviewPage, _sort_customer_records


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_customer_records_sort_latest_first_with_placeholder_dates_last() -> None:
    records = [
        CustomerRecord(name="空日期客户", customer_type="品牌客户", stage="潜客", updated_at=""),
        CustomerRecord(name="旧客户", customer_type="品牌客户", stage="沟通中", updated_at="2026-04-20"),
        CustomerRecord(name="待补日期客户", customer_type="品牌客户", stage="潜客", updated_at="待补日期"),
        CustomerRecord(name="新客户", customer_type="品牌客户", stage="已合作", updated_at="2026-04-25"),
        CustomerRecord(name="同日早录入", customer_type="品牌客户", stage="沟通中", updated_at="2026-04-25"),
    ]

    sorted_names = [record.name for record in _sort_customer_records(records)]

    assert sorted_names == ["新客户", "同日早录入", "旧客户", "空日期客户", "待补日期客户"]


def test_overview_workspace_keeps_primary_regions_compact() -> None:
    _app()
    page = OverviewPage()

    assert page.overview_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    assert page.follow_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    assert page.missing_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    assert page.detail_browser.maximumHeight() <= 300


def test_overview_meta_ignores_placeholder_dates_for_latest_update() -> None:
    _app()
    page = OverviewPage()

    page.set_customers(
        [
            CustomerRecord(name="待同步客户", customer_type="品牌客户", stage="潜客", updated_at="待同步"),
            CustomerRecord(name="真实日期客户", customer_type="品牌客户", stage="已合作", updated_at="2026-04-25"),
            CustomerRecord(name="待补日期客户", customer_type="品牌客户", stage="沟通中", updated_at="待补日期"),
        ]
    )

    assert "更新时间：2026-04-25" in page.meta_label.text()


def test_overview_related_projects_follow_latest_update_first() -> None:
    _app()
    page = OverviewPage()

    projects = [
        ProjectRecord(
            brand_customer_name="爱慕儿童",
            project_name="旧项目",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="旧项目重点",
            next_action="旧项目下一步",
            updated_at="2026-04-20",
            latest_approval_status="审批通过 · 旧节点",
        ),
        ProjectRecord(
            brand_customer_name="爱慕儿童",
            project_name="最新项目",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="最新项目重点",
            next_action="最新项目下一步",
            updated_at="2026-04-25",
            latest_approval_status="审批通过 · 最新节点",
        ),
        ProjectRecord(
            brand_customer_name="爱慕儿童",
            project_name="同日后录入项目",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="同日后录入重点",
            next_action="同日后录入下一步",
            updated_at="2026-04-25",
            latest_approval_status="审批通过 · 同日节点",
        ),
    ]

    page.set_related_projects(projects, "品牌客户")

    assert [record.project_name for record in page._related_projects] == [
        "最新项目",
        "同日后录入项目",
        "旧项目",
    ]

    def _side_item_title(index: int) -> str:
        widget = page.related_projects_layout.itemAt(index).widget()
        return widget.findChildren(QLabel)[0].text()

    assert _side_item_title(0) == "最新项目"
    assert _side_item_title(1) == "同日后录入项目"
    assert _side_item_title(2) == "旧项目"
