from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QTextEdit

from strawberry_customer_management.markdown_store import sort_project_records
from strawberry_customer_management.models import (
    ApprovalEntry,
    DidaDiaryEntry,
    INTERNAL_MAIN_WORK_NAME,
    PartyAInfo,
    ProjectDetail,
    ProjectProgressNode,
    ProjectRecord,
    ProjectRole,
)
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
        latest_approval_status="审批中 · 业务Owner / 内部负责人B",
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
        default_party_a_info=PartyAInfo(contact="甲方联系人A", phone="13800000000", email="contact@example.com"),
        participant_roles=[
            ProjectRole(name="甲方联系人A", role="品牌方 / 甲方", responsibility="负责合同回寄和品牌方向确认。"),
            ProjectRole(name="实施方A", role="实施商", responsibility="负责达人收货、拍摄准备与执行。", note="今天先催达人收货截图。"),
        ],
        progress_nodes=[
            ProjectProgressNode(
                node_name="合同回寄与盖章",
                status="进行中",
                owner="甲方联系人A",
                collaborators="草莓 / 内部负责人B",
                planned_date="2026-04-30",
                risk="到件后需及时盖章留底。",
                next_action="确认合同到件并补盖章闭环。",
            ),
            ProjectProgressNode(
                node_name="达人收货与拍摄准备",
                status="卡住",
                owner="实施方A",
                planned_date="2026-04-29",
                risk="回执未齐，影响拍摄排期。",
                next_action="先催达人收货截图，再安排拍摄档期。",
            ),
        ],
        progress_markdown="- 垫资方A预计 2026-05-10 给到实施方A，后续单独留意。",
        materials_markdown="- 合同模板.docx\n- 授权委托书.docx\n- 项目确认单.docx",
        notes_markdown="- 已从桌面项目同步资料。\n- 等待审批通过后补齐归档状态。",
        approval_entries=[
            ApprovalEntry(
                entry_date="2026-04-21",
                title_or_usage="爱慕春夏项目确认单",
                counterparty="爱慕股份有限公司",
                approval_status="审批中",
                current_node="业务Owner / 内部负责人B",
            )
        ],
    )
    object.__setattr__(detail, "next_follow_up_date", "2026-05-08")
    return detail


def test_project_management_page_keeps_import_area_compact() -> None:
    _app()
    page = ProjectManagementPage()
    record = _sample_record()
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))
    page.set_project_detail(_sample_detail())

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


def test_project_management_inline_detail_exposes_case_board_sections() -> None:
    _app()
    page = ProjectManagementPage()

    record = _sample_record()
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))
    page.set_project_detail(_sample_detail())

    label_texts = {label.text() for label in page.findChildren(type(page.meta_label))}
    button_texts = {button.text() for button in page.findChildren(QPushButton)}

    assert "Case 概览" in label_texts
    assert "流程节点" in label_texts
    assert "参与人" in label_texts
    assert "快速补充" in label_texts
    assert "审批导入工具" in label_texts
    assert "实施方A" in button_texts
    assert "达人收货与拍摄准备" in label_texts
    page.close()


def test_project_management_page_handles_single_participant_role_detail() -> None:
    _app()
    page = ProjectManagementPage()

    record = _sample_record()
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))

    detail = _sample_detail()
    object.__setattr__(
        detail,
        "participant_roles",
        [ProjectRole(name="甲方联系人A", role="品牌方 / 甲方", responsibility="负责合同回寄和品牌方向确认。")],
    )
    page.set_project_detail(detail)

    label_texts = {label.text() for label in page.findChildren(QLabel)}
    assert "客户方 / 品牌方 / 甲方：甲方联系人A。 · 补齐寄送资料后推进盖章 · 跟进 2026-05-08 · 最新审批：审批中 · 业务Owner / 内部负责人B" in label_texts
    page.close()


def test_project_management_card_shows_dida_diary_status() -> None:
    _app()
    page = ProjectManagementPage()
    record = _sample_record()
    object.__setattr__(record, "dida_diary_status", "待建滴答")
    page.set_projects([record])

    label_texts = {label.text() for label in page.findChildren(QLabel)}
    assert "滴答：待建" in label_texts


def test_project_management_uses_internal_workflow_without_contract_words() -> None:
    _app()
    page = ProjectManagementPage()
    detail = ProjectDetail(
        brand_customer_name=INTERNAL_MAIN_WORK_NAME,
        project_name="2026-05 录入助手优化",
        stage="推进中",
        year="2026",
        project_type="主业系统建设",
        current_focus="验证内部事项能否稳定回写",
        next_action="继续测试验证",
    )

    titles = [node["title"] for node in page._workflow_nodes_for_detail(detail)]
    role_titles = [row[0] for row in page._role_rows(detail)]

    assert titles == ["事项建档", "方案确认", "执行推进", "测试验证", "复盘沉淀", "归档"]
    assert all("审批" not in title and "合同" not in title for title in titles)
    assert role_titles[:2] == ["内部负责人", "协作人"]
    assert all("审批" not in title and "合同" not in title for title in role_titles)
    page.close()


def test_project_management_uses_ka_workflow_without_contract_words() -> None:
    _app()
    page = ProjectManagementPage()
    detail = ProjectDetail(
        brand_customer_name="青竹画材官方旗舰店",
        project_name="2026-04 青竹画材KA版与AI详情页跟进",
        stage="推进中",
        year="2026",
        project_type="KA客户运营",
        current_focus="客户试用 AI 详情页，确认开通配置",
        next_action="跟进使用反馈和增购可能",
        latest_approval_status="暂无审批记录",
    )

    titles = [node["title"] for node in page._workflow_nodes_for_detail(detail)]
    role_titles = [row[0] for row in page._role_rows(detail)]

    assert titles == ["需求确认", "方案试用", "配置开通", "使用跟进", "增购转化", "归档"]
    assert all("审批" not in title and "合同" not in title for title in titles)
    assert role_titles[:3] == ["客户对接", "开通配置", "使用反馈"]
    page.close()


def test_project_management_uses_shop_group_workflow() -> None:
    _app()
    page = ProjectManagementPage()
    detail = ProjectDetail(
        brand_customer_name="云舟店群",
        project_name="2026-05 云舟店群点数方案",
        stage="推进中",
        year="2026",
        project_type="店群客户运营",
        current_focus="确认店铺规模和点数折扣",
        next_action="给出批量开通方案",
    )

    titles = [node["title"] for node in page._workflow_nodes_for_detail(detail)]

    assert titles == ["需求确认", "点数方案", "批量开通", "使用反馈", "续费增购", "归档"]
    assert all("审批" not in title and "合同" not in title for title in titles)
    page.close()


def test_project_management_keeps_contract_workflow_for_contract_projects() -> None:
    _app()
    page = ProjectManagementPage()
    detail = _sample_detail()
    object.__setattr__(detail, "progress_nodes", [])

    titles = [node["title"] for node in page._workflow_nodes_for_detail(detail)]

    assert "审批合同" in titles
    page.close()


def test_project_management_detail_shows_dida_diary_status() -> None:
    _app()
    page = ProjectManagementPage()
    record = _sample_record()
    detail = _sample_detail()
    object.__setattr__(
        detail,
        "dida_diary_entries",
        [
            DidaDiaryEntry(
                scheduled_at="2026-05-08 10:00",
                status="待办",
                title="提醒甲方联系人A确认合同回寄",
                parent="主业客户跟进",
            )
        ],
    )
    page.set_projects([record], selected_project=(record.brand_customer_name, record.project_name))
    page.set_project_detail(detail)

    label_texts = {label.text() for label in page.findChildren(QLabel)}
    assert "滴答：已关联 2026-05-08 10:00 提醒甲方联系人A确认合同回寄" in label_texts
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
    assert page.selected_project_key() is None
    page.close()


def test_project_management_switching_selected_project_keeps_cards_and_toolbox() -> None:
    _app()
    page = ProjectManagementPage()
    first = _sample_record()
    second = ProjectRecord(
        brand_customer_name="MM官方旗舰店",
        project_name="2026-04 MM官方旗舰店店铺粉丝活动沟通",
        stage="推进中",
        year="2026",
        project_type="KA客户运营",
        current_focus="确认活动交付口径",
        next_action="补齐后续排期",
        updated_at="2026-04-29",
    )
    page.set_projects([first, second], selected_project=(first.brand_customer_name, first.project_name))
    page.set_project_detail(_sample_detail())

    second_detail = ProjectDetail(
        brand_customer_name=second.brand_customer_name,
        project_name=second.project_name,
        stage=second.stage,
        year=second.year,
        project_type=second.project_type,
        current_focus=second.current_focus,
        next_action=second.next_action,
        default_party_a_info=PartyAInfo(contact="MM"),
    )

    page._toggle_project(second.brand_customer_name, second.project_name)
    page.set_project_detail(second_detail)

    assert len(page.displayed_project_names()) == 2
    assert page.findChild(ApprovalInboxDropZone) is not None
    assert page.approval_import_text_edit is not None
    page.close()


def test_project_management_toggle_keeps_cards_visible_before_detail_arrives() -> None:
    _app()
    page = ProjectManagementPage()
    first = _sample_record()
    second = ProjectRecord(
        brand_customer_name="MM官方旗舰店",
        project_name="2026-04 MM官方旗舰店店铺粉丝活动沟通",
        stage="推进中",
        year="2026",
        project_type="KA客户运营",
        current_focus="确认活动交付口径",
        next_action="补齐后续排期",
        updated_at="2026-04-29",
    )
    page.set_projects([first, second], selected_project=(first.brand_customer_name, first.project_name))
    page.set_project_detail(_sample_detail())

    page._toggle_project(second.brand_customer_name, second.project_name)

    labels = {label.text() for label in page.findChildren(QLabel)}
    assert first.project_name in labels
    assert second.project_name in labels
    assert "项目详情加载中..." in labels
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
    assert page.selected_project_key() is None
    page.close()


def test_project_management_page_demotes_archived_projects_in_default_board() -> None:
    _app()
    page = ProjectManagementPage()

    page.set_projects(
        [
            ProjectRecord(
                brand_customer_name="blackhead",
                project_name="blackhead小红书营销合同",
                stage="已归档",
                year="2026",
                project_type="小红书项目",
                current_focus="资料已收档",
                next_action="不进入日常跟进",
                updated_at="2026-05-01",
            ),
            ProjectRecord(
                brand_customer_name="MM官方旗舰店",
                project_name="2026-04 MM官方旗舰店店铺粉丝活动沟通",
                stage="推进中",
                year="2026",
                project_type="KA客户运营",
                current_focus="确认活动交付口径",
                next_action="补齐后续排期",
                updated_at="2026-04-29",
            ),
            ProjectRecord(
                brand_customer_name="曼妮芬棉质生活",
                project_name="2026-03 曼妮芬棉质生活达人种草视频项目",
                stage="收尾中",
                year="2026",
                project_type="视频项目",
                current_focus="继续跟进走款和退款对账",
                next_action="确认最后 1 个达人走款",
                updated_at="2026-04-30",
            ),
        ]
    )

    assert page.displayed_project_names() == [
        "2026-03 曼妮芬棉质生活达人种草视频项目",
        "2026-04 MM官方旗舰店店铺粉丝活动沟通",
        "blackhead小红书营销合同",
    ]
    assert page.selected_project_key() is None

    page.stage_filter_combo.setCurrentText("已归档")

    assert page.displayed_project_names() == ["blackhead小红书营销合同"]
    page.close()
