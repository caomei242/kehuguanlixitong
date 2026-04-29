from __future__ import annotations

from datetime import date, timedelta
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QPushButton, QLabel, QSizePolicy

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


def test_overview_timeline_card_uses_compact_actions() -> None:
    _app()
    page = OverviewPage()
    today = date.today().isoformat()
    page.set_customers(
        [
            CustomerRecord(
                name="爱慕",
                customer_type="品牌客户",
                stage="已合作",
                business_direction="视频拍摄",
                current_need="确认夏季拍摄安排",
                next_action="今天补齐拍摄时间和寄样计划",
                next_follow_up_date=today,
                updated_at="2026-04-26",
            )
        ]
    )

    timeline_cards = [widget for widget in page.findChildren(QFrame) if widget.objectName() == "TimelineCardSelected"]

    assert timeline_cards
    due_chip = [button for button in timeline_cards[0].findChildren(QPushButton) if button.objectName() == "TimelineDueChipButton"][0]
    assert due_chip.text() == "今天"
    assert [button.text() for button in timeline_cards[0].findChildren(QPushButton)] == ["今天", "›"]
    assert len(timeline_cards[0].findChildren(QComboBox)) == 1


def test_overview_timeline_due_chip_uses_relative_text_for_tomorrow() -> None:
    _app()
    page = OverviewPage()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    page.set_customers(
        [
            CustomerRecord(
                name="孙总",
                customer_type="博主 / 网店店群客户",
                stage="沟通中",
                business_direction="AI商品图 / AI详情页推广",
                current_need="确认推广合作",
                next_action="明天回来确认推广坑位、报价和排期",
                next_follow_up_date=tomorrow,
                updated_at="2026-04-27",
            )
        ]
    )

    timeline_cards = [widget for widget in page.findChildren(QFrame) if widget.objectName() == "TimelineCardSelected"]

    assert timeline_cards
    due_chip = [button for button in timeline_cards[0].findChildren(QPushButton) if button.objectName() == "TimelineDueChipButton"][0]
    assert due_chip.text() == "明天"


def test_overview_due_chip_click_emits_customer_reschedule_action() -> None:
    _app()
    page = OverviewPage()
    captured: list[tuple[str, str]] = []
    page.customer_follow_up_action_requested.connect(lambda name, action: captured.append((name, action)))
    page.set_customers(
        [
            CustomerRecord(
                name="孤帆远影",
                customer_type="网店店群客户",
                stage="沟通中",
                next_action="下午主动联系",
                next_follow_up_date="2026-04-28",
                updated_at="2026-04-28",
            )
        ]
    )

    timeline_card = [widget for widget in page.findChildren(QFrame) if widget.objectName() == "TimelineCardSelected"][0]
    due_chip = [button for button in timeline_card.findChildren(QPushButton) if button.objectName() == "TimelineDueChipButton"][0]
    with patch("strawberry_customer_management.ui.pages.overview_page.QInputDialog.getText", return_value=("2026-05-03", True)):
        due_chip.click()

    assert captured == [("孤帆远影", "reschedule:2026-05-03")]


def test_overview_timeline_action_combo_can_open_reschedule_prompt_for_project() -> None:
    _app()
    page = OverviewPage()
    captured: list[tuple[str, str, str]] = []
    page.project_follow_up_action_requested.connect(
        lambda customer_name, project_name, action: captured.append((customer_name, project_name, action))
    )
    page.set_follow_up_projects(
        [
            ProjectRecord(
                brand_customer_name="孙总",
                project_name="2026-04 孙总AI商品图推广合作跟进",
                stage="推进中",
                year="2026",
                project_type="博主推广",
                next_action="明天确认推广报价",
                next_follow_up_date="2026-04-28",
                updated_at="2026-04-27",
            )
        ]
    )

    timeline_card = [widget for widget in page.findChildren(QFrame) if widget.objectName() == "TimelineCard"][0]
    action_combo = timeline_card.findChildren(QComboBox)[0]
    with patch("strawberry_customer_management.ui.pages.overview_page.QInputDialog.getText", return_value=("", True)):
        action_combo.activated.emit(2)

    assert captured == [("孙总", "2026-04 孙总AI商品图推广合作跟进", "unschedule")]
    assert action_combo.currentIndex() == 0


def test_overview_timeline_action_combo_keeps_customer_follow_up_actions() -> None:
    _app()
    page = OverviewPage()
    captured: list[tuple[str, str]] = []
    page.customer_follow_up_action_requested.connect(lambda name, action: captured.append((name, action)))
    page.set_customers(
        [
            CustomerRecord(
                name="爱慕",
                customer_type="品牌客户",
                stage="已合作",
                business_direction="视频拍摄",
                next_action="今天确认拍摄时间",
                next_follow_up_date="2026-04-27",
                updated_at="2026-04-26",
            )
        ]
    )

    timeline_card = [widget for widget in page.findChildren(QFrame) if widget.objectName() == "TimelineCardSelected"][0]
    action_combo = timeline_card.findChildren(QComboBox)[0]
    action_combo.activated.emit(1)

    assert captured == [("爱慕", "complete")]
    assert action_combo.currentIndex() == 0


def test_overview_timeline_action_combo_keeps_project_follow_up_actions() -> None:
    _app()
    page = OverviewPage()
    captured: list[tuple[str, str, str]] = []
    page.project_follow_up_action_requested.connect(
        lambda customer_name, project_name, action: captured.append((customer_name, project_name, action))
    )
    page.set_follow_up_projects(
        [
            ProjectRecord(
                brand_customer_name="孙总",
                project_name="2026-04 孙总AI商品图推广合作跟进",
                stage="推进中",
                year="2026",
                project_type="博主推广",
                next_action="明天确认推广报价",
                next_follow_up_date="2026-04-28",
                updated_at="2026-04-27",
            )
        ]
    )

    timeline_card = [widget for widget in page.findChildren(QFrame) if widget.objectName() == "TimelineCard"][0]
    action_combo = timeline_card.findChildren(QComboBox)[0]
    action_combo.activated.emit(3)

    assert captured == [("孙总", "2026-04 孙总AI商品图推广合作跟进", "tomorrow")]
    assert action_combo.currentIndex() == 0
