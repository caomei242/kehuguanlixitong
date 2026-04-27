from __future__ import annotations

from datetime import date
import os
import time

from strawberry_customer_management.app import build_app
from strawberry_customer_management.config import ConfigStore
from strawberry_customer_management.models import ApprovalEntry, CommunicationEntry, CustomerDraft, PartyAInfo, ProjectDetail, ProjectDraft, ProjectRecord
from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.models import CustomerDetail
from strawberry_customer_management.models import CustomerRecord
from strawberry_customer_management.project_store import MarkdownProjectStore
from strawberry_customer_management.ui.pages.overview_page import OverviewPage
from strawberry_customer_management.ui.pages.project_management_page import ProjectManagementPage
from strawberry_customer_management.ui.pages.quick_capture_page import QuickCapturePage
from strawberry_customer_management.ui.pages.settings_page import SettingsPage
from strawberry_customer_management.ui.main_window import MainWindow
from strawberry_customer_management.ui.widgets.screenshot_input_widget import ScreenshotInputWidget

from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QSizePolicy


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
    assert window.nav.count() == 4
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


def test_quick_capture_field_lock_keeps_manual_value_when_ai_applies_draft():
    app = build_app()
    page = QuickCapturePage()
    page.name_edit.setText("抖店店群-L")
    page.phone_edit.setText("13776288616")

    page.set_field_locked("name", True)
    page.set_field_locked("phone", True)
    page.apply_draft(
        CustomerDraft(
            name="L·",
            customer_type="网店店群客户",
            stage="沟通中",
            business_direction="集采点数",
            contact="L·",
            phone="19999999999",
            current_need="继续询价",
        )
    )

    assert page.name_edit.text() == "抖店店群-L"
    assert page.phone_edit.text() == "13776288616"
    assert page.contact_edit.text() == "L·"
    assert page.need_edit.toPlainText() == "继续询价"
    page.close()
    app.processEvents()


def test_quick_capture_clear_form_resets_field_locks():
    app = build_app()
    page = QuickCapturePage()
    page.name_edit.setText("抖店店群-L")
    page.set_field_locked("name", True)

    page.clear_form()
    page.apply_draft(CustomerDraft(name="新客户-抖店店群", customer_type="网店店群客户", stage="沟通中"))

    assert page.name_edit.text() == "新客户-抖店店群"
    assert not page.is_field_locked("name")
    page.close()
    app.processEvents()


def test_quick_capture_existing_customer_save_keeps_original_name_for_safe_rename():
    app = build_app()
    page = QuickCapturePage()
    captured: list[CustomerDraft] = []
    page.save_requested.connect(captured.append)

    page.set_target_customer("新客户-抖店店群", mode_label="手动编辑老客户")
    assert not page.name_edit.isReadOnly()
    page.name_edit.setText("抖店店群-L")
    page.contact_edit.setText("L·")
    page._emit_save_requested()

    assert captured
    assert captured[0].name == "抖店店群-L"
    assert captured[0].original_name == "新客户-抖店店群"
    page.close()
    app.processEvents()


def test_quick_capture_raw_input_uses_wide_workbench_layout():
    app = build_app()
    page = QuickCapturePage()

    assert page.raw_text_edit.minimumHeight() >= 156
    assert page.raw_text_edit.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert page.ai_extract_button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Fixed
    page.close()
    app.processEvents()


def test_pages_have_outer_scroll_area():
    app = build_app()
    pages = [OverviewPage(), QuickCapturePage(), ProjectManagementPage(), SettingsPage()]

    for page in pages:
        assert page.findChild(QScrollArea) is not None
        page.close()
    app.processEvents()


def test_project_management_page_uses_single_expand_panel_and_year_shortcuts():
    app = build_app()
    page = ProjectManagementPage()
    captured: list[ProjectDraft] = []
    page.save_requested.connect(captured.append)

    record = ProjectRecord(
        brand_customer_name="MW1",
        project_name="MW1短视频拍摄合同",
        stage="待确认",
        project_type="视频项目",
        current_focus="补充项目当前重点",
        next_action="确认年份和联系人",
        updated_at="2026-04-21",
        latest_approval_status="暂无审批记录",
    )
    detail = ProjectDetail(
        brand_customer_name="MW1",
        project_name="MW1短视频拍摄合同",
        stage="待确认",
        project_type="视频项目",
        current_focus="补充项目当前重点",
        next_action="确认年份和联系人",
        default_party_a_info=PartyAInfo(),
        approval_entries=[
            ApprovalEntry(
                entry_date="2026-04-21",
                title_or_usage="MW1短视频拍摄合同确认",
                approval_status="审批中",
                current_node="业务Owner / tiger",
            )
        ],
    )

    page.set_projects([record])
    page.set_project_detail(detail)

    year_buttons = [button for button in page.findChildren(QPushButton) if button.text() == "去年"]
    assert year_buttons
    year_buttons[0].click()
    save_buttons = [button for button in page.findChildren(QPushButton) if button.text() == "保存项目补充"]
    assert len(save_buttons) == 1
    save_buttons[0].click()

    assert captured
    assert captured[0].year == str(date.today().year - 1)
    labels = [label.text() for label in page.findChildren(QLabel)]
    assert any("MW1短视频拍摄合同" in text for text in labels)
    assert any("审批中" in text for text in labels)
    assert len([button for button in page.findChildren(QPushButton) if button.text() == "收起详情"]) >= 2
    page.close()
    app.processEvents()


def test_project_management_page_emits_approval_import_actions():
    app = build_app()
    page = ProjectManagementPage()
    preview_requests: list[str] = []
    apply_requests: list[str] = []
    ocr_requests: list[tuple[bytes, str]] = []
    page.approval_import_preview_requested.connect(preview_requests.append)
    page.approval_import_apply_requested.connect(apply_requests.append)
    page.approval_import_ocr_requested.connect(lambda image_bytes, source: ocr_requests.append((image_bytes, source)))

    page.approval_import_text_edit.setPlainText("草莓提交的用印申请\n审批通过")
    page.approval_import_preview_button.click()
    page.approval_import_apply_button.click()
    page.set_approval_import_preview(["1. 2026-04-21 · 审批通过 -> 项目：爱慕儿童 / 春夏短视频项目"])
    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff4b6e"))
    QGuiApplication.clipboard().setImage(image)
    page.approval_import_screenshot_widget.paste_button.click()

    assert preview_requests == ["草莓提交的用印申请\n审批通过"]
    assert apply_requests == ["草莓提交的用印申请\n审批通过"]
    assert "项目：爱慕儿童" in page.approval_import_preview_label.text()
    assert ocr_requests
    assert ocr_requests[0][0].startswith(b"\x89PNG")
    page.close()
    app.processEvents()


def test_main_window_imports_dingtalk_approval_into_project(tmp_path):
    customer_root = tmp_path / "客户数据"
    project_root = tmp_path / "项目数据"
    customer_root.mkdir()
    customer_store = MarkdownCustomerStore(customer_root)
    customer_store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            company="爱慕股份有限公司",
            contact="李岩",
            current_need="推进春夏短视频项目",
            next_action="补充审批记录",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            party_a_contact="李岩",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有客户"),
        )
    )
    project_store = MarkdownProjectStore(project_root)
    project_store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="补录审批",
            next_action="确认用印状态",
            customer_page_link="[[客户/客户--爱慕儿童]]",
            main_work_path="/tmp/fake-aimer-project",
            path_status="主业路径失效",
            default_party_a_info=PartyAInfo(brand="爱慕儿童", company="爱慕股份有限公司", contact="李岩"),
        )
    )
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "project_root": str(project_root),
            "main_work_root": str(tmp_path / "主业"),
        }
    )
    app = build_app()
    window = MainWindow(config_store=config_store)
    raw_text = """草莓提交的用印申请
用印文件名称及用途说明：供应商：厦门市邱熊网络科技有限公司 品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同
发起时间：2026-04-21
完成时间：2026-04-21
审批通过"""

    window._handle_approval_import_preview(raw_text)
    assert "项目：爱慕儿童 / 2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同" in window.project_management_page.approval_import_preview_label.text()

    window._handle_approval_import_apply(raw_text)

    detail = window._project_store.get_project("爱慕儿童", "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同")
    assert detail.approval_entries[0].approval_status == "审批通过"
    assert detail.approval_entries[0].counterparty == "爱慕股份有限公司"
    assert "项目 1 条" in window.project_management_page.status_label.text()
    window.close()
    app.processEvents()


def test_main_window_scans_approval_inbox_and_moves_imported_file(tmp_path):
    customer_root = tmp_path / "客户数据"
    project_root = tmp_path / "项目数据"
    approval_inbox_root = tmp_path / "钉钉审批导入"
    customer_root.mkdir()
    customer_store = MarkdownCustomerStore(customer_root)
    customer_store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            company="爱慕股份有限公司",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有客户"),
        )
    )
    project_store = MarkdownProjectStore(project_root)
    project_store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="补录审批",
            next_action="确认用印状态",
            default_party_a_info=PartyAInfo(brand="爱慕儿童", company="爱慕股份有限公司"),
        )
    )
    pending_dir = approval_inbox_root / "待处理"
    pending_dir.mkdir(parents=True)
    csv_path = pending_dir / "审批导出.csv"
    csv_path.write_text(
        "标题,用印文件名称及用途说明,发起时间,审批状态\n"
        "草莓提交的用印申请,品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同,2026-04-21,审批通过\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "project_root": str(project_root),
            "main_work_root": str(tmp_path / "主业"),
            "approval_inbox_root": str(approval_inbox_root),
        }
    )
    app = build_app()
    window = MainWindow(config_store=config_store)

    window._handle_approval_inbox_scan()
    assert "审批导出.csv" in window.project_management_page.approval_import_text_edit.toPlainText()
    assert "项目：爱慕儿童 / 2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同" in window.project_management_page.approval_import_preview_label.text()

    window._handle_approval_import_apply(window.project_management_page.approval_import_text_edit.toPlainText())

    assert (approval_inbox_root / "已导入" / "审批导出.csv").exists()
    assert not csv_path.exists()
    detail = window._project_store.get_project("爱慕儿童", "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同")
    assert detail.approval_entries[0].approval_status == "审批通过"
    window.close()
    app.processEvents()


def test_main_window_imports_dropped_approval_file_then_scans(tmp_path):
    customer_root = tmp_path / "客户数据"
    project_root = tmp_path / "项目数据"
    approval_inbox_root = tmp_path / "钉钉审批导入"
    download_dir = tmp_path / "下载"
    customer_root.mkdir()
    download_dir.mkdir()
    customer_store = MarkdownCustomerStore(customer_root)
    customer_store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            company="爱慕股份有限公司",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有客户"),
        )
    )
    project_store = MarkdownProjectStore(project_root)
    project_store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="补录审批",
            next_action="确认用印状态",
            default_party_a_info=PartyAInfo(brand="爱慕儿童", company="爱慕股份有限公司"),
        )
    )
    dropped_csv = download_dir / "审批导出.csv"
    dropped_csv.write_text(
        "标题,用印文件名称及用途说明,发起时间,审批状态\n"
        "草莓提交的用印申请,品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同,2026-04-21,审批通过\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "project_root": str(project_root),
            "main_work_root": str(tmp_path / "主业"),
            "approval_inbox_root": str(approval_inbox_root),
        }
    )
    app = build_app()
    window = MainWindow(config_store=config_store)

    window._handle_approval_inbox_files_dropped([dropped_csv])

    copied_csv = approval_inbox_root / "待处理" / "审批导出.csv"
    assert copied_csv.exists()
    assert dropped_csv.exists()
    assert "审批导出.csv" in window.project_management_page.approval_import_text_edit.toPlainText()
    assert "项目：爱慕儿童 / 2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同" in window.project_management_page.approval_import_preview_label.text()
    assert "已投递 1 个文件" in window.project_management_page.status_label.text()

    window._handle_approval_import_apply(window.project_management_page.approval_import_text_edit.toPlainText())

    assert (approval_inbox_root / "已导入" / "审批导出.csv").exists()
    assert dropped_csv.exists()
    window.close()
    app.processEvents()


def test_main_window_recognizes_pasted_approval_image_reference_before_preview(tmp_path, monkeypatch):
    class FakeOCRClient:
        def __init__(self, **_kwargs):
            pass

        def extract_text(self, _image_bytes):
            return """草莓提交的用印申请
用印文件名称及用途说明：供应商：厦门市邱熊网络科技有限公司 品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同
发起时间：2026-04-21
审批通过"""

    monkeypatch.setattr("strawberry_customer_management.ui.main_window.McpOCRClient", FakeOCRClient)

    customer_root = tmp_path / "客户数据"
    project_root = tmp_path / "项目数据"
    customer_root.mkdir()
    customer_store = MarkdownCustomerStore(customer_root)
    customer_store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            company="爱慕股份有限公司",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有客户"),
        )
    )
    project_store = MarkdownProjectStore(project_root)
    project_store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="补录审批",
            next_action="确认用印状态",
            customer_page_link="[[客户/客户--爱慕儿童]]",
            default_party_a_info=PartyAInfo(brand="爱慕儿童", company="爱慕股份有限公司"),
        )
    )
    image_path = tmp_path / "dingtalk-approval.png"
    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff4b6e"))
    image.save(str(image_path), "PNG")
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "project_root": str(project_root),
            "main_work_root": str(tmp_path / "主业"),
            "minimax_api_key": "test-key",
        }
    )
    app = build_app()
    window = MainWindow(config_store=config_store)

    window._handle_approval_import_preview(f"file://{image_path}")

    deadline = time.time() + 2
    while time.time() < deadline and "项目：爱慕儿童" not in window.project_management_page.approval_import_preview_label.text():
        app.processEvents()
        time.sleep(0.01)

    assert "26年春夏短视频拍摄制作服务合同" in window.project_management_page.approval_import_text_edit.toPlainText()
    assert "项目：爱慕儿童 / 2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同" in window.project_management_page.approval_import_preview_label.text()
    window.close()
    app.processEvents()


def test_screenshot_input_widget_reads_image_from_clipboard():
    app = build_app()
    widget = ScreenshotInputWidget()
    emitted: list[tuple[bytes, str]] = []
    widget.image_ready.connect(lambda image_bytes, source: emitted.append((image_bytes, source)))

    image = QImage(12, 12, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff4b6e"))
    QGuiApplication.clipboard().setImage(image)

    widget.paste_button.click()

    assert emitted
    assert emitted[0][0].startswith(b"\x89PNG")
    assert emitted[0][1] == "剪贴板截图"
    widget.close()
    app.processEvents()


def test_settings_page_shows_minimax_route_hint():
    app = build_app()
    page = SettingsPage()

    labels = [label.text() for label in page.findChildren(type(page.status_label))]

    assert any("中国大陆" in text and "Global" in text for text in labels)
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


def test_overview_page_filters_customer_type_and_updates_metrics():
    app = build_app()
    page = OverviewPage()
    page.set_customers(
        [
            CustomerRecord(
                name="爱慕",
                customer_type="品牌客户",
                stage="已合作",
                business_direction="视频拍摄",
                current_need="补充新业务需求",
                next_action="确认预算",
                updated_at="2026-04-20",
            ),
            CustomerRecord(
                name="青竹画材官方旗舰店",
                customer_type="网店KA客户",
                stage="已合作",
                business_direction="KA版 / AI裂变 / AI详情页",
                current_need="关注 AI详情页功能",
                next_action="跟进功能试用",
                updated_at="2026-04-23",
                shop_scale="抖店 · 已订购 KA版",
            ),
            CustomerRecord(
                name="新客户-抖店群",
                customer_type="网店店群客户",
                stage="沟通中",
                business_direction="集采点数",
                current_need="咨询批量优惠",
                next_action="电话沟通",
                updated_at="2026-04-20",
            ),
        ]
    )

    page.type_filter_combo.setCurrentText("网店KA客户")

    assert page.displayed_customer_names() == ["青竹画材官方旗舰店"]
    assert page.metric_value_labels["已合作"].text() == "1"
    assert "网店KA客户" in page.meta_label.text()
    page.close()
    app.processEvents()


def test_overview_page_orders_customers_by_latest_update_first():
    app = build_app()
    page = OverviewPage()
    page.set_customers(
        [
            CustomerRecord(
                name="MW1",
                customer_type="品牌客户",
                stage="已合作",
                business_direction="短视频拍摄",
                current_need="年份待确认",
                next_action="补齐联系人",
                updated_at="2026-04-20",
            ),
            CustomerRecord(
                name="爱慕儿童",
                customer_type="品牌客户",
                stage="已合作",
                business_direction="视频拍摄 / 品牌合作",
                current_need="合同已收到，待拍摄产品寄出",
                next_action="跟进物流",
                updated_at="2026-04-23",
            ),
            CustomerRecord(
                name="blackhead",
                customer_type="品牌客户",
                stage="已合作",
                business_direction="小红书营销",
                current_need="年份待确认",
                next_action="补齐当前需求",
                updated_at="2026-04-20",
            ),
        ]
    )

    assert page.displayed_customer_names() == ["爱慕儿童", "MW1", "blackhead"]
    page.close()
    app.processEvents()


def test_overview_page_emits_manual_edit_for_current_customer():
    app = build_app()
    page = OverviewPage()
    captured: list[str] = []
    page.edit_customer_requested.connect(captured.append)

    page.show_customer_detail(
        CustomerDetail(
            name="爱慕",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌推广",
        )
    )
    page.manual_edit_button.click()

    assert captured == ["爱慕"]
    page.close()
    app.processEvents()


def test_overview_quick_capture_button_switches_to_capture_page(tmp_path):
    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save({"customer_root": str(customer_root), "main_work_root": str(tmp_path / "主业")})
    app = build_app()
    window = MainWindow(config_store=config_store)

    window.overview_page.quick_capture_button.click()

    assert window.nav.currentRow() == 1
    window.close()
    app.processEvents()


def test_main_window_prepares_existing_customer_for_manual_edit(tmp_path):
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

    window._prepare_existing_customer_edit("爱慕")

    assert window.nav.currentRow() == 1
    assert window.quick_capture_page.name_edit.text() == "爱慕"
    assert window.quick_capture_page.target_customer_name == "爱慕"
    assert "手动编辑" in window.quick_capture_page.target_context_label.text()
    window.close()
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


def test_screenshot_ocr_populates_raw_text_and_ai_form(tmp_path, monkeypatch):
    class FakeOCRClient:
        def __init__(self, **_kwargs):
            pass

        def extract_text(self, _image_bytes):
            return "爱慕补充品牌推广需求，联系人张三，继续推进视频拍摄。"

    class FakeAIClient:
        def __init__(self, **_kwargs):
            pass

        def extract_draft(self, *_args, **_kwargs):
            return CustomerDraft(
                name="爱慕",
                customer_type="品牌客户",
                stage="沟通中",
                business_direction="视频拍摄 / 品牌推广",
                contact="张三",
                current_need="补充品牌推广视频拍摄需求",
                next_action="确认预算和排期",
                communication=CommunicationEntry(entry_date="2026-04-20", summary="继续推进品牌推广需求"),
            )

    monkeypatch.setattr("strawberry_customer_management.ui.main_window.McpOCRClient", FakeOCRClient)
    monkeypatch.setattr("strawberry_customer_management.ui.main_window.MiniMaxCaptureClient", FakeAIClient)

    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "main_work_root": str(tmp_path / "主业"),
            "minimax_api_key": "test-key",
            "minimax_base_url": "https://api.minimaxi.com/v1",
        }
    )
    app = build_app()
    window = MainWindow(config_store=config_store)

    window._handle_screenshot_ocr(b"fake-image", "剪贴板截图", "")

    deadline = time.time() + 2
    while time.time() < deadline and window.quick_capture_page.name_edit.text() != "爱慕":
        app.processEvents()
        time.sleep(0.01)

    assert window.quick_capture_page.raw_text_edit.toPlainText() == "爱慕补充品牌推广需求，联系人张三，继续推进视频拍摄。"
    assert window.quick_capture_page.name_edit.text() == "爱慕"
    assert window.quick_capture_page.contact_edit.text() == "张三"
    assert window.quick_capture_page.need_edit.toPlainText() == "补充品牌推广视频拍摄需求"
    window.close()
    app.processEvents()


def test_settings_validate_describes_minimax_route(tmp_path):
    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    main_work_root = tmp_path / "主业"
    main_work_root.mkdir()
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "main_work_root": str(main_work_root),
            "minimax_api_key": "test-key",
            "minimax_base_url": "https://api.minimaxi.com/v1",
        }
    )

    app = build_app()
    window = MainWindow(config_store=config_store)

    window._handle_settings_validate()

    status = window.settings_page.status_label.text()
    assert "MiniMax 口径：中国大陆" in status
    assert "MiniMax Base URL：https://api.minimaxi.com/v1" in status
    window.close()
    app.processEvents()


def test_main_window_sync_projects_creates_project_pages_and_repairs_customer_path(tmp_path):
    customer_root = tmp_path / "客户数据"
    customer_root.mkdir()
    main_work_root = tmp_path / "主业"
    project_dir = main_work_root / "品牌项目" / "品牌--爱慕儿童" / "2026" / "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同"
    project_dir.mkdir(parents=True)
    (project_dir / "合同模板.docx").write_text("stub", encoding="utf-8")
    store = MarkdownCustomerStore(customer_root)
    store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            contact="李岩",
            company="爱慕股份有限公司",
            current_need="推进春夏短视频项目",
            next_action="继续补充后续项目需求",
            main_work_path=str(main_work_root / "品牌项目" / "品牌--爱慕") + "/",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            party_a_contact="李岩",
            party_a_phone="17778019272",
            party_a_email="rellaliyan@aimer.com.cn",
            party_a_address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有客户"),
        )
    )
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "project_root": str(tmp_path / "项目数据"),
            "main_work_root": str(main_work_root),
        }
    )

    app = build_app()
    window = MainWindow(config_store=config_store)

    window._handle_project_sync()

    repaired_detail = store.get_customer("爱慕儿童")
    assert repaired_detail.main_work_path.endswith("品牌--爱慕儿童/")
    assert (tmp_path / "项目数据" / "00 品牌项目总表.md").exists()
    assert window.project_management_page.project_count_label.text() == "当前 1 个项目"
    assert any(
        "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同" in label.text()
        for label in window.project_management_page.findChildren(QLabel)
    )
    window.close()
    app.processEvents()


def test_overview_project_button_switches_to_project_management_page(tmp_path):
    customer_root = tmp_path / "客户数据"
    customer_root.mkdir()
    project_root = tmp_path / "项目数据"
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save({"customer_root": str(customer_root), "project_root": str(project_root), "main_work_root": str(tmp_path / "主业")})
    customer_store = MarkdownCustomerStore(customer_root)
    customer_store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄",
            contact="李岩",
            current_need="推进新项目",
            next_action="查看全部项目",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有客户"),
        )
    )
    app = build_app()
    window = MainWindow(config_store=config_store)

    window.overview_page.show_customer_detail(
        CustomerDetail(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄",
        )
    )
    window.overview_page.view_projects_button.click()

    assert window.nav.currentRow() == 2
    window.close()
    app.processEvents()


def test_overview_project_button_supports_shop_ka_customer(tmp_path):
    customer_root = tmp_path / "客户数据"
    customer_root.mkdir()
    project_root = tmp_path / "项目数据"
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save({"customer_root": str(customer_root), "project_root": str(project_root), "main_work_root": str(tmp_path / "主业")})
    app = build_app()
    window = MainWindow(config_store=config_store)

    window.overview_page.show_customer_detail(
        CustomerDetail(
            name="青竹画材官方旗舰店",
            customer_type="网店KA客户",
            stage="已合作",
            business_direction="KA版 / AI裂变 / AI详情页",
        )
    )
    assert window.overview_page.view_projects_button.isEnabled()
    window.overview_page.view_projects_button.click()

    assert window.nav.currentRow() == 2
    window.close()
    app.processEvents()
