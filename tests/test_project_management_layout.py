from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QTextEdit

from strawberry_customer_management.markdown_store import sort_project_records
from strawberry_customer_management.models import ApprovalEntry, PartyAInfo, ProjectDetail, ProjectProgressNode, ProjectRecord, ProjectRole
from strawberry_customer_management.ui.pages.project_management_page import (
    ApprovalInboxDropZone,
    ProjectManagementPage,
)
from strawberry_customer_management.ui.widgets.screenshot_input_widget import ScreenshotInputWidget


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _sample_record() -> ProjectRecord:
    record = ProjectRecord(
        brand_customer_name="爱慕儿童",
        project_name="2026-04 爱慕儿童春夏短视频拍摄制作服务合同",
        stage="推进中",
        year="2026",
        project_type="合同项目",
        current_focus="确认拍摄排期和确认单信息",
        next_action="补齐寄送资料后推进盖章",
        latest_approval_status="审批中 · 业务Owner / tiger",
    )
    object.__setattr__(record, "next_follow_up_date", "2026-05-08")
    return record


def _sample_detail() -> ProjectDetail:
    record = _sample_record()
    detail = ProjectDetail(
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
        participant_roles=[
            ProjectRole(name="李岩", role="品牌方 / 甲方", responsibility="负责合同回寄和品牌方向确认。"),
            ProjectRole(name="小苏", role="实施商", responsibility="负责达人收货、拍摄准备与执行。", note="今天先催达人收货截图。"),
        ],
        progress_nodes=[
            ProjectProgressNode(
                node_name="合同回寄与盖章",
                status="进行中",
                owner="李岩",
                collaborators="草莓 / tiger",
                planned_date="2026-04-30",
                risk="到件后需及时盖章留底。",
                next_action="确认合同到件并补盖章闭环。",
            ),
            ProjectProgressNode(
                node_name="达人收货与拍摄准备",
                status="卡住",
                owner="小苏",
                planned_date="2026-04-29",
                risk="回执未齐，影响拍摄排期。",
                next_action="先催达人收货截图，再安排拍摄档期。",
            ),
        ],
        progress_markdown="- 熊伟预计 2026-05-10 给到小苏，后续单独留意。",
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
    object.__setattr__(detail, "next_follow_up_date", "2026-05-08")
    return detail


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
    assert page.toolbox_content.isHidden()
    assert page.toolbox_toggle_button.text() == "展开审批导入"


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
        "participant_roles_markdown_edit",
        "progress_markdown_edit",
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


def test_project_management_expanded_form_emits_next_follow_up_date() -> None:
    _app()
    page = ProjectManagementPage()

    record = _sample_record()
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))
    page.set_project_detail(_sample_detail())
    next_follow_up_date_edit = page._active_widgets["next_follow_up_date_edit"]
    assert isinstance(next_follow_up_date_edit, QLineEdit)
    assert next_follow_up_date_edit.text() == "2026-05-08"
    next_follow_up_date_edit.setText("2026-05-15")

    emitted = []
    page.save_requested.connect(emitted.append)
    page._emit_save_requested()

    assert len(emitted) == 1
    assert getattr(emitted[0], "next_follow_up_date") == "2026-05-15"
    page.close()


def test_project_management_detail_drawer_exposes_case_board_sections() -> None:
    _app()
    page = ProjectManagementPage()

    record = _sample_record()
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))
    page.set_project_detail(_sample_detail())

    label_texts = {label.text() for label in page.findChildren(type(page.meta_label))}

    assert "Case 概览" in label_texts
    assert "流程节点" in label_texts
    assert "参与角色" in label_texts
    assert "快速补充" in label_texts
    assert "项目详情" in label_texts
    assert "小苏" in label_texts
    assert "达人收货与拍摄准备" in label_texts
    page.close()


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
