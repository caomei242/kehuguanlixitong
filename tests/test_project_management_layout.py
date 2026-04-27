from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTextEdit

from strawberry_customer_management.markdown_store import sort_project_records
from strawberry_customer_management.models import ApprovalEntry, PartyAInfo, ProjectDetail, ProjectRecord
from strawberry_customer_management.ui.pages.project_management_page import (
    ApprovalInboxDropZone,
    ProjectManagementPage,
)
from strawberry_customer_management.ui.widgets.screenshot_input_widget import ScreenshotInputWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _sample_record() -> ProjectRecord:
    return ProjectRecord(
        brand_customer_name="爱慕儿童",
        project_name="2026-04 爱慕儿童春夏短视频拍摄制作服务合同",
        stage="推进中",
        year="2026",
        project_type="合同项目",
        current_focus="确认拍摄排期和确认单信息",
        next_action="补齐寄送资料后推进盖章",
        latest_approval_status="审批中 · 业务Owner / tiger",
    )


def _sample_detail() -> ProjectDetail:
    record = _sample_record()
    return ProjectDetail(
        brand_customer_name=record.brand_customer_name,
        project_name=record.project_name,
        stage=record.stage,
        year=record.year,
        project_type=record.project_type,
        current_focus=record.current_focus,
        next_action=record.next_action,
        main_work_path="/tmp/品牌项目/品牌--爱慕儿童/2026/2026-04 爱慕儿童春夏短视频拍摄制作服务合同",
        path_status="主业路径有效",
        latest_approval_status=record.latest_approval_status,
        risk="纸质文件寄送和审批节点要继续盯住",
        default_party_a_info=PartyAInfo(contact="李岩", phone="17778019272", email="rellaliyan@aimer.com.cn"),
        materials_markdown="- 合同模板.docx\n- 授权委托书.docx\n- 项目确认单.docx",
        notes_markdown="- 已从桌面项目同步资料。\n- 等待审批通过后补齐归档状态。",
        approval_entries=[
            ApprovalEntry(
                entry_date="2026-04-21",
                title_or_usage="爱慕春夏项目确认单",
                counterparty="爱慕股份有限公司",
                approval_status="审批中",
                current_node="业务Owner / tiger",
            )
        ],
    )


def test_project_management_page_keeps_import_area_compact() -> None:
    _app()
    page = ProjectManagementPage()

    drop_zone = page.findChild(ApprovalInboxDropZone)
    screenshot_widget = page.findChild(ScreenshotInputWidget)

    assert page.scroll_area.widgetResizable()
    assert page.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.approval_import_text_edit.maximumHeight() <= 84
    assert drop_zone is not None
    assert drop_zone.maximumHeight() <= 76
    assert screenshot_widget is not None
    assert screenshot_widget.maximumHeight() <= 86


def test_project_management_expanded_detail_caps_long_text_fields() -> None:
    _app()
    page = ProjectManagementPage()

    record = _sample_record()
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))
    page.set_project_detail(_sample_detail())

    compact_field_names = (
        "current_focus_edit",
        "next_action_edit",
        "risk_edit",
        "party_a_address_edit",
        "materials_edit",
        "notes_edit",
        "approval_note_edit",
    )

    for name in compact_field_names:
        widget = page._active_widgets[name]
        assert isinstance(widget, QTextEdit)
        assert widget.minimumHeight() == widget.maximumHeight()
        assert widget.maximumHeight() <= 86


def test_project_management_sorts_latest_update_first_with_placeholder_dates_last() -> None:
    records = [
        ProjectRecord(brand_customer_name="爱慕儿童", project_name="待补日期项目", stage="推进中", updated_at="待补日期"),
        ProjectRecord(brand_customer_name="爱慕儿童", project_name="旧项目", stage="推进中", updated_at="2026-04-20"),
        ProjectRecord(brand_customer_name="爱慕儿童", project_name="新项目", stage="推进中", updated_at="2026-04-25"),
        ProjectRecord(brand_customer_name="爱慕儿童", project_name="同日后录入项目", stage="推进中", updated_at="2026-04-25"),
        ProjectRecord(brand_customer_name="爱慕儿童", project_name="空日期项目", stage="推进中", updated_at=""),
    ]

    sorted_names = [record.project_name for record in sort_project_records(records)]

    assert sorted_names == ["新项目", "同日后录入项目", "旧项目", "待补日期项目", "空日期项目"]


def test_project_management_page_orders_projects_by_latest_update_first() -> None:
    _app()
    page = ProjectManagementPage()
    page.set_projects(
        [
            ProjectRecord(
                brand_customer_name="MW1",
                project_name="MW1短视频拍摄合同",
                stage="待确认",
                year="2025",
                project_type="视频项目",
                current_focus="补齐当前重点",
                next_action="补齐联系人",
                updated_at="2026-04-21",
            ),
            ProjectRecord(
                brand_customer_name="青竹画材官方旗舰店",
                project_name="2026-04 青竹画材KA版与AI详情页跟进",
                stage="推进中",
                year="2026",
                project_type="KA客户运营",
                current_focus="确认13个点位主图和详情更新方案",
                next_action="跟进试用反馈",
                updated_at="2026-04-24",
            ),
            ProjectRecord(
                brand_customer_name="曼妮芬棉质生活",
                project_name="2026-03 曼妮芬棉质生活达人种草视频项目",
                stage="收尾中",
                year="2026",
                project_type="视频项目",
                current_focus="补齐审批归档",
                next_action="确认最后资料",
                updated_at="2026-04-23",
            ),
        ]
    )

    assert page.displayed_project_names() == [
        "2026-04 青竹画材KA版与AI详情页跟进",
        "2026-03 曼妮芬棉质生活达人种草视频项目",
        "MW1短视频拍摄合同",
    ]
    assert page.selected_project_key() == ("青竹画材官方旗舰店", "2026-04 青竹画材KA版与AI详情页跟进")
    page.close()


def test_project_management_page_keeps_same_day_order_and_placeholder_dates_last() -> None:
    _app()
    page = ProjectManagementPage()

    page.set_projects(
        [
            ProjectRecord(
                brand_customer_name="爱慕儿童",
                project_name="同日早录入项目",
                stage="推进中",
                year="2026",
                project_type="合同项目",
                current_focus="确认排期",
                next_action="推进盖章",
                updated_at="2026-04-25",
            ),
            ProjectRecord(
                brand_customer_name="爱慕儿童",
                project_name="待同步项目",
                stage="推进中",
                year="2026",
                project_type="合同项目",
                current_focus="确认排期",
                next_action="推进盖章",
                updated_at="待同步",
            ),
            ProjectRecord(
                brand_customer_name="爱慕儿童",
                project_name="空日期项目",
                stage="推进中",
                year="2026",
                project_type="合同项目",
                current_focus="确认排期",
                next_action="推进盖章",
                updated_at="",
            ),
            ProjectRecord(
                brand_customer_name="爱慕儿童",
                project_name="真实最新项目",
                stage="推进中",
                year="2026",
                project_type="合同项目",
                current_focus="确认排期",
                next_action="推进盖章",
                updated_at="2026-04-27",
            ),
            ProjectRecord(
                brand_customer_name="爱慕儿童",
                project_name="同日晚录入项目",
                stage="推进中",
                year="2026",
                project_type="合同项目",
                current_focus="确认排期",
                next_action="推进盖章",
                updated_at="2026-04-25",
            ),
            ProjectRecord(
                brand_customer_name="爱慕儿童",
                project_name="待确认项目",
                stage="推进中",
                year="2026",
                project_type="合同项目",
                current_focus="确认排期",
                next_action="推进盖章",
                updated_at="待确认",
            ),
        ]
    )

    assert page.displayed_project_names() == [
        "真实最新项目",
        "同日早录入项目",
        "同日晚录入项目",
        "待同步项目",
        "空日期项目",
        "待确认项目",
    ]
    assert page.selected_project_key() == ("爱慕儿童", "真实最新项目")
