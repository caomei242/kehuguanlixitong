from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, QSize, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QMainWindow,
)

from strawberry_customer_management.ai_capture import (
    AICaptureError,
    MINIMAX_BASE_URL,
    MINIMAX_GLOBAL_BASE_URL,
    MiniMaxCaptureClient,
)
from strawberry_customer_management.approval_inbox import ApprovalInboxFile, ApprovalInboxScanner
from strawberry_customer_management.approval_importer import (
    CUSTOMER_DESTINATION,
    PROJECT_DESTINATION,
    UNASSIGNED_DESTINATION,
    ApprovalImportCandidate,
    build_approval_import_candidates,
)
from strawberry_customer_management.config import ConfigStore
from strawberry_customer_management.config import resolved_minimax_api_key
from strawberry_customer_management.mcp_ocr_client import DEFAULT_MCP_COMMAND, McpOCRClient
from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.models import (
    CaptureDraft,
    CommunicationEntry,
    CustomerDetail,
    CustomerDraft,
    INTERNAL_MAIN_WORK_NAME,
    PartyAInfo,
    PersonDraft,
    PersonProjectLink,
    ProjectDetail,
    ProjectDraft,
    ProjectRole,
)
from strawberry_customer_management.person_store import MarkdownPersonStore
from strawberry_customer_management.project_discovery import DesktopProjectDiscoveryService
from strawberry_customer_management.project_store import MarkdownProjectStore
from strawberry_customer_management.ui.app_icon import load_app_icon
from strawberry_customer_management.ui.pages.overview_page import OverviewPage
from strawberry_customer_management.ui.pages.customer_library_page import CustomerLibraryPage
from strawberry_customer_management.ui.pages.person_library_page import PersonLibraryPage
from strawberry_customer_management.ui.pages.project_management_page import ProjectManagementPage
from strawberry_customer_management.ui.pages.quick_capture_page import QuickCapturePage
from strawberry_customer_management.ui.pages.settings_page import SettingsPage


class AICaptureWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        client: MiniMaxCaptureClient,
        raw_text: str,
        existing_customers: list[str],
        target_customer_name: str,
    ) -> None:
        super().__init__()
        self.client = client
        self.raw_text = raw_text
        self.existing_customers = existing_customers
        self.target_customer_name = target_customer_name

    @Slot()
    def run(self) -> None:
        try:
            draft = self.client.extract_capture(
                self.raw_text,
                existing_customers=self.existing_customers,
                target_customer_name=self.target_customer_name or None,
            )
        except AICaptureError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface unexpected worker errors to the UI.
            self.failed.emit(f"AI 整理失败：{exc}")
        else:
            self.succeeded.emit(draft)
        finally:
            self.finished.emit()


class ScreenshotOCRWorker(QObject):
    succeeded = Signal(str, str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, client: McpOCRClient, image_bytes: bytes, source_label: str) -> None:
        super().__init__()
        self.client = client
        self.image_bytes = image_bytes
        self.source_label = source_label

    @Slot()
    def run(self) -> None:
        try:
            raw_text = self.client.extract_text(self.image_bytes)
        except Exception as exc:  # noqa: BLE001 - surface OCR errors to the UI.
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(raw_text, self.source_label)
        finally:
            self.finished.emit()


@dataclass(frozen=True)
class FollowUpUndoState:
    kind: str
    message: str
    customer_name: str
    project_name: str = ""
    customer_before: CustomerDetail | None = None
    project_before: ProjectDetail | None = None


class MainWindow(QMainWindow):
    _NAV_ITEMS: tuple[tuple[str, str], ...] = (
        ("客户总览", "本周跟进"),
        ("项目管理", "项目与审批"),
        ("关系人库", "人员关系"),
        ("客户库", "全部客户"),
        ("快速录入", "新增与更新"),
        ("设置", "系统配置"),
    )
    OVERVIEW_ROW = 0
    PROJECTS_ROW = 1
    PERSON_LIBRARY_ROW = 2
    CUSTOMER_LIBRARY_ROW = 3
    QUICK_CAPTURE_ROW = 4
    SETTINGS_ROW = 5

    def __init__(self, config_store: ConfigStore) -> None:
        super().__init__()
        self.setWindowTitle("草莓客户管理系统")
        self.setWindowIcon(load_app_icon())
        self.resize(1260, 820)

        self._config_store = config_store
        self._config = self._config_store.load()
        self._store = MarkdownCustomerStore(Path(self._config["customer_root"]))
        self._project_store = MarkdownProjectStore(Path(self._config["project_root"]))
        self._person_store = MarkdownPersonStore(Path(self._config["person_root"]))
        self._approval_inbox_scanner = ApprovalInboxScanner(Path(self._config["approval_inbox_root"]))
        self._approval_import_source_files: list[ApprovalInboxFile] = []
        self._ai_thread: QThread | None = None
        self._ai_worker: AICaptureWorker | None = None
        self._ocr_thread: QThread | None = None
        self._ocr_worker: ScreenshotOCRWorker | None = None
        self._approval_ocr_thread: QThread | None = None
        self._approval_ocr_worker: ScreenshotOCRWorker | None = None
        self._nav_cards: list[QFrame] = []
        self._last_follow_up_undo: FollowUpUndoState | None = None

        self.nav = QListWidget()
        self.nav.setObjectName("WorkbenchNav")
        self.nav.setSpacing(8)
        self.nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._populate_navigation()

        self.stack = QStackedWidget()
        self.overview_page = OverviewPage()
        self.project_management_page = ProjectManagementPage()
        self.person_library_page = PersonLibraryPage()
        self.customer_library_page = CustomerLibraryPage()
        self.quick_capture_page = QuickCapturePage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.project_management_page)
        self.stack.addWidget(self.person_library_page)
        self.stack.addWidget(self.customer_library_page)
        self.stack.addWidget(self.quick_capture_page)
        self.stack.addWidget(self.settings_page)

        self.overview_page.customer_selected.connect(self._show_customer)
        self.overview_page.update_customer_requested.connect(self._prepare_existing_customer_update)
        self.overview_page.edit_customer_requested.connect(self._prepare_existing_customer_edit)
        self.overview_page.view_customer_projects_requested.connect(self._focus_customer_projects)
        self.overview_page.quick_capture_requested.connect(lambda: self.nav.setCurrentRow(self.QUICK_CAPTURE_ROW))
        self.overview_page.customer_library_requested.connect(lambda: self.nav.setCurrentRow(self.CUSTOMER_LIBRARY_ROW))
        self.overview_page.customer_follow_up_action_requested.connect(self._handle_customer_follow_up_action)
        self.overview_page.project_follow_up_action_requested.connect(self._handle_project_follow_up_action)
        self.overview_page.undo_last_follow_up_action_requested.connect(self._undo_last_follow_up_action)
        self.customer_library_page.customer_selected.connect(self._show_library_customer)
        self.customer_library_page.update_customer_requested.connect(self._prepare_existing_customer_update)
        self.customer_library_page.edit_customer_requested.connect(self._prepare_existing_customer_edit)
        self.customer_library_page.archive_customer_requested.connect(lambda name: self._handle_customer_follow_up_action(name, "archive"))
        self.customer_library_page.view_customer_projects_requested.connect(self._focus_customer_projects)
        self.customer_library_page.person_selected.connect(self._focus_person)
        self.customer_library_page.overview_requested.connect(lambda: self.nav.setCurrentRow(self.OVERVIEW_ROW))
        self.customer_library_page.quick_capture_requested.connect(lambda: self.nav.setCurrentRow(self.QUICK_CAPTURE_ROW))
        self.person_library_page.person_selected.connect(self._show_person)
        self.person_library_page.save_requested.connect(self._handle_person_save)
        self.person_library_page.overview_requested.connect(lambda: self.nav.setCurrentRow(self.OVERVIEW_ROW))
        self.person_library_page.quick_capture_requested.connect(lambda: self.nav.setCurrentRow(self.QUICK_CAPTURE_ROW))
        self.quick_capture_page.ai_extract_requested.connect(self._handle_ai_extract)
        self.quick_capture_page.screenshot_ocr_requested.connect(self._handle_screenshot_ocr)
        self.quick_capture_page.save_requested.connect(self._handle_capture_save)
        self.project_management_page.project_selected.connect(self._show_project)
        self.project_management_page.sync_requested.connect(self._handle_project_sync)
        self.project_management_page.save_requested.connect(self._handle_project_save)
        self.project_management_page.approval_import_preview_requested.connect(self._handle_approval_import_preview)
        self.project_management_page.approval_import_apply_requested.connect(self._handle_approval_import_apply)
        self.project_management_page.approval_import_ocr_requested.connect(self._handle_approval_import_ocr)
        self.project_management_page.approval_inbox_scan_requested.connect(self._handle_approval_inbox_scan)
        self.project_management_page.approval_inbox_files_dropped.connect(self._handle_approval_inbox_files_dropped)
        self.project_management_page.person_selected.connect(self._focus_person)
        self.settings_page.save_requested.connect(self._handle_settings_save)
        self.settings_page.refresh_requested.connect(self._handle_settings_refresh)
        self.settings_page.validate_requested.connect(self._handle_settings_validate)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(self._sync_navigation_state)

        brand_title = QLabel("草莓")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("客户管理系统")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_eyebrow = QLabel("STRAWBERRY WORKBENCH")
        brand_eyebrow.setObjectName("SidebarEyebrow")
        brand_hint = QLabel("")
        brand_hint.setWordWrap(True)
        brand_hint.setObjectName("SidebarSectionHint")

        brand_card = QFrame()
        brand_card.setObjectName("SidebarBrandCard")
        brand_layout = QVBoxLayout(brand_card)
        brand_layout.setContentsMargins(16, 16, 16, 16)
        brand_layout.setSpacing(8)
        brand_layout.addWidget(brand_eyebrow)
        brand_layout.addWidget(brand_title)
        brand_layout.addWidget(brand_subtitle)
        brand_layout.addWidget(brand_hint)

        nav_section_title = QLabel("工作台导航")
        nav_section_title.setObjectName("SidebarSectionTitle")
        nav_section_hint = QLabel("")
        nav_section_hint.setWordWrap(True)
        nav_section_hint.setObjectName("SidebarSectionHint")

        nav_card = QFrame()
        nav_card.setObjectName("SidebarNavCard")
        nav_card_layout = QVBoxLayout(nav_card)
        nav_card_layout.setContentsMargins(14, 14, 14, 14)
        nav_card_layout.setSpacing(12)
        nav_card_layout.addWidget(nav_section_title)
        nav_card_layout.addWidget(nav_section_hint)
        nav_card_layout.addWidget(self.nav)

        sidebar = QFrame()
        sidebar.setObjectName("WindowSidebar")
        sidebar.setFixedWidth(272)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(14)
        sidebar_layout.addWidget(brand_card)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(nav_card, 1)

        content = QFrame()
        content.setObjectName("WindowContentShell")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.addWidget(self.stack)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        body_layout.addWidget(sidebar)
        body_layout.addWidget(content, 1)

        shell = QFrame()
        shell.setObjectName("WindowShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(12, 12, 12, 12)
        shell_layout.addWidget(body)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.addWidget(shell)
        self.setCentralWidget(root)

        self.settings_page.set_values(
            self._config["customer_root"],
            self._config["project_root"],
            self._config["person_root"],
            self._config["main_work_root"],
            str(self._config.get("approval_inbox_root", "")),
            self._config.get("minimax_api_key", ""),
            self._config.get("minimax_model", ""),
            self._config.get("minimax_base_url", ""),
            self._config.get("customer_types", []),
            self._config.get("secondary_tags", []),
        )
        self._apply_option_config()
        self.project_management_page.set_approval_inbox_path(str(self._config.get("approval_inbox_root", "")))
        self.nav.setCurrentRow(self.OVERVIEW_ROW)
        self._reload_customers()
        self._reload_projects()
        self._reload_people()

    def _populate_navigation(self) -> None:
        for index, (title, subtitle) in enumerate(self._NAV_ITEMS, start=1):
            item = QListWidgetItem(title)
            item.setSizeHint(QSize(0, 60))
            self.nav.addItem(item)
            card = self._build_navigation_card(index, title, subtitle)
            self.nav.setItemWidget(item, card)
            self._nav_cards.append(card)

    def _build_navigation_card(self, index: int, title: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setObjectName("NavCard")
        card.setProperty("current", False)

        layout = QHBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        index_label = QLabel(f"{index:02d}")
        index_label.setObjectName("NavCardIndex")

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)
        title_label = QLabel(title)
        title_label.setObjectName("NavCardTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("NavCardSubtitle")
        subtitle_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(subtitle_label)

        layout.addWidget(index_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_layout, 1)
        return card

    def _sync_navigation_state(self, current_row: int) -> None:
        for index, card in enumerate(self._nav_cards):
            is_current = index == current_row
            if card.property("current") == is_current:
                continue
            card.setProperty("current", is_current)
            self._refresh_styles(card)

    def _refresh_styles(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        for child in widget.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
        widget.update()

    def _reload_customers(self, selected_name: str | None = None) -> None:
        records = self._store.list_customers()
        self.overview_page.set_focus_customers(records)
        self.overview_page.set_customers(records, selected_name=selected_name)
        self.customer_library_page.set_customers(records, selected_name=selected_name)
        self.quick_capture_page.set_status(f"当前共加载 {len(records)} 个客户。")

    def _reload_projects(
        self,
        selected_brand: str = "",
        selected_project: tuple[str, str] | None = None,
    ) -> None:
        records = self._project_store.list_projects()
        self.overview_page.set_follow_up_projects(records)
        self.project_management_page.set_projects(records, selected_brand=selected_brand, selected_project=selected_project)
        active_key = selected_project or self.project_management_page.selected_project_key()
        if active_key:
            self._show_project(*active_key)
        else:
            self.project_management_page.set_project_detail(None)

    def _reload_people(self, selected_name: str | None = None) -> None:
        records = self._person_store.list_people()
        self.person_library_page.set_people(records, selected_name=selected_name)

    def _show_customer(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            self.overview_page.show_customer_detail(None)
            self.overview_page.set_related_projects([], "")
            return
        self.overview_page.show_customer_detail(detail)
        self.overview_page.set_related_projects(self._project_store.list_projects_for_brand(detail.name), detail.customer_type)

    def _show_library_customer(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            self.customer_library_page.show_customer_detail(None)
            self.customer_library_page.set_related_people([])
            return
        self.customer_library_page.show_customer_detail(detail)
        self.customer_library_page.set_related_people(self._person_store.list_people_for_customer(detail.name))

    def _show_project(self, brand_customer_name: str, project_name: str) -> None:
        try:
            detail = self._project_store.get_project(brand_customer_name, project_name)
        except KeyError:
            self.project_management_page.set_project_detail(None)
            return
        self.project_management_page.set_project_detail(detail)

    def _show_person(self, name: str) -> None:
        try:
            detail = self._person_store.get_person(name)
        except KeyError:
            self.person_library_page.show_person_detail(None)
            return
        self.person_library_page.show_person_detail(detail)

    def _handle_person_save(self, draft: PersonDraft) -> None:
        if not draft.name:
            QMessageBox.warning(self, "缺少人名", "请先选择一个关系人。")
            return
        detail = self._person_store.upsert_person(draft)
        self._reload_people(selected_name=detail.name)
        selected_customer = getattr(self.customer_library_page, "_current_customer_name", "")
        if selected_customer:
            self.customer_library_page.set_related_people(self._person_store.list_people_for_customer(selected_customer))

    def _focus_person(self, name: str) -> None:
        self.nav.setCurrentRow(self.PERSON_LIBRARY_ROW)
        self._reload_people(selected_name=name)

    def _focus_customer_projects(self, customer_name: str) -> None:
        self.nav.setCurrentRow(self.PROJECTS_ROW)
        self.project_management_page.focus_brand(customer_name)
        active_key = self.project_management_page.selected_project_key()
        if active_key:
            self._show_project(*active_key)

    def _handle_customer_follow_up_action(self, name: str, action: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            QMessageBox.warning(self, "客户不存在", f"没有找到客户「{name}」。")
            return
        today = date.today().isoformat()
        next_follow_up_date = detail.next_follow_up_date
        next_action = detail.next_action
        stage = detail.stage
        summary = ""
        recent_progress = detail.recent_progress
        if action == "complete":
            next_follow_up_date = " "
            next_action = " "
            recent_progress = "已完成本次跟进"
            summary = "已完成本次跟进"
        elif action == "today":
            next_follow_up_date = date.today().isoformat()
            summary = f"已改期到 {next_follow_up_date}"
        elif action.startswith("reschedule:"):
            next_follow_up_date = action.split(":", 1)[1].strip()
            summary = f"已改期到 {next_follow_up_date}"
        elif action == "tomorrow":
            next_follow_up_date = (date.today() + timedelta(days=1)).isoformat()
            summary = f"已改期到 {next_follow_up_date}"
        elif action == "unschedule":
            next_follow_up_date = ""
            summary = "已改为待排期"
        elif action == "suspend":
            stage = "暂缓"
            next_follow_up_date = ""
            next_action = "已转暂缓，后续有新触发再推进"
            summary = "已转暂缓"
        elif action == "archive":
            stage = "已归档"
            next_follow_up_date = "已归档"
            next_action = "已结束并收档，后续仅做历史查询"
            summary = "已收档"
        else:
            return
        draft = self._customer_draft_from_detail(
            detail,
            stage=stage,
            recent_progress=recent_progress,
            next_action=next_action,
            next_follow_up_date=next_follow_up_date,
            communication=CommunicationEntry(entry_date=today, summary=summary, next_step=next_action),
            updated_at=today,
        )
        updated = self._store.upsert_customer(draft)
        self._set_last_follow_up_undo(
            FollowUpUndoState(
                kind="customer",
                message=f"{detail.name} · {summary}",
                customer_name=detail.name,
                customer_before=detail,
            )
        )
        self._reload_customers(selected_name=updated.name)
        self._reload_projects(selected_brand=updated.name)
        self.overview_page.show_customer_detail(updated)
        self.customer_library_page.show_customer_detail(updated)

    def _handle_project_follow_up_action(self, brand_customer_name: str, project_name: str, action: str) -> None:
        try:
            detail = self._project_store.get_project(brand_customer_name, project_name)
        except KeyError:
            QMessageBox.warning(self, "项目不存在", f"没有找到项目「{brand_customer_name}/{project_name}」。")
            return
        today = date.today().isoformat()
        next_follow_up_date = detail.next_follow_up_date
        next_action = detail.next_action
        stage = detail.stage
        notes = detail.notes_markdown
        action_label = "更新"
        if action == "complete":
            next_follow_up_date = " "
            next_action = " "
            notes = _append_note(notes, f"- {today}：已完成本次项目跟进。")
            action_label = "已完成本次项目跟进"
        elif action == "today":
            next_follow_up_date = date.today().isoformat()
            notes = _append_note(notes, f"- {today}：项目跟进已改期到 {next_follow_up_date}。")
            action_label = f"已改到 {next_follow_up_date}"
        elif action.startswith("reschedule:"):
            next_follow_up_date = action.split(":", 1)[1].strip()
            notes = _append_note(notes, f"- {today}：项目跟进已改期到 {next_follow_up_date}。")
            action_label = f"已改到 {next_follow_up_date}"
        elif action == "tomorrow":
            next_follow_up_date = (date.today() + timedelta(days=1)).isoformat()
            notes = _append_note(notes, f"- {today}：项目跟进已改期到 {next_follow_up_date}。")
            action_label = f"已改到 {next_follow_up_date}"
        elif action == "unschedule":
            next_follow_up_date = ""
            notes = _append_note(notes, f"- {today}：项目改为待排期。")
            action_label = "已改为待排期"
        elif action == "suspend":
            stage = "暂缓"
            next_follow_up_date = ""
            next_action = "已转暂缓，后续有新触发再推进"
            notes = _append_note(notes, f"- {today}：项目已转暂缓。")
            action_label = "已转暂缓"
        elif action == "archive":
            stage = "已归档"
            next_follow_up_date = "已归档"
            next_action = "已结束并收档，后续仅做历史查询"
            notes = _append_note(notes, f"- {today}：项目已收档。")
            action_label = "已收档"
        else:
            return
        draft = ProjectDraft(
            brand_customer_name=detail.brand_customer_name,
            project_name=detail.project_name,
            stage=stage,
            original_project_name=detail.project_name,
            year=detail.year,
            project_type=detail.project_type,
            current_focus=detail.current_focus,
            next_action=next_action,
            next_follow_up_date=next_follow_up_date,
            risk=detail.risk,
            customer_page_link=detail.customer_page_link,
            main_work_path=detail.main_work_path,
            path_status=detail.path_status,
            party_a_source=detail.party_a_source,
            default_party_a_info=detail.default_party_a_info,
            party_a_info=detail.party_a_info,
            override_party_a=detail.party_a_source.startswith("项目覆盖"),
            participant_roles=detail.participant_roles,
            participant_roles_markdown=detail.participant_roles_markdown,
            progress_nodes=detail.progress_nodes,
            progress_markdown=detail.progress_markdown,
            materials_markdown=detail.materials_markdown,
            notes_markdown=notes,
            approval_entries=detail.approval_entries,
            latest_approval_status=detail.latest_approval_status,
            updated_at=today,
        )
        updated = self._project_store.upsert_project(draft)
        self._set_last_follow_up_undo(
            FollowUpUndoState(
                kind="project",
                message=f"{detail.project_name} · {action_label}",
                customer_name=detail.brand_customer_name,
                project_name=detail.project_name,
                project_before=detail,
            )
        )
        self._reload_projects(selected_brand=updated.brand_customer_name, selected_project=(updated.brand_customer_name, updated.project_name))

    def _handle_capture_save(self, draft: object) -> None:
        if isinstance(draft, ProjectDraft):
            self._handle_project_save(draft)
            self.quick_capture_page.set_status(f"项目/事项「{draft.project_name}」已写入 Obsidian 项目工作台。")
            self.nav.setCurrentRow(self.PROJECTS_ROW)
            return
        if isinstance(draft, CaptureDraft):
            if draft.project_draft is not None:
                self._handle_capture_save(draft.project_draft)
                return
            if draft.customer_draft is not None:
                draft = draft.customer_draft
            else:
                QMessageBox.warning(self, "缺少录入内容", "AI 没有返回可保存的客户或项目草稿。")
                return
        if not isinstance(draft, CustomerDraft):
            QMessageBox.warning(self, "录入类型不支持", "当前录入内容不是可保存的客户或项目草稿。")
            return
        if not draft.name:
            QMessageBox.warning(self, "缺少客户名", "请先填写客户名称。")
            return
        try:
            detail = self._store.upsert_customer(draft)
        except ValueError as exc:
            QMessageBox.warning(self, "客户名称冲突", str(exc))
            return
        except KeyError as exc:
            QMessageBox.warning(self, "原客户不存在", f"没有找到原客户「{exc.args[0]}」，请刷新后重试。")
            return
        self._reload_customers(selected_name=detail.name)
        self._reload_projects(selected_brand=detail.name)
        self.quick_capture_page.set_status(f"{detail.name} 已写入 Obsidian 客户管理工作台。")
        self.nav.setCurrentRow(self.OVERVIEW_ROW)

    def _handle_project_save(self, draft: ProjectDraft) -> None:
        if not draft.brand_customer_name or not draft.project_name:
            QMessageBox.warning(self, "缺少项目信息", "请先确认关联客户和项目名称。")
            return
        default_party_a = PartyAInfo()
        try:
            customer_detail = self._store.get_customer(draft.brand_customer_name)
        except KeyError:
            customer_detail = None
        else:
            default_party_a = customer_detail.party_a_info
        try:
            existing_detail = self._project_store.get_project(
                draft.brand_customer_name,
                draft.original_project_name or draft.project_name,
            )
        except KeyError:
            existing_detail = None
        merged = ProjectDraft(
            brand_customer_name=draft.brand_customer_name,
            project_name=draft.project_name,
            stage=draft.stage,
            original_project_name=draft.original_project_name,
            year=draft.year,
            project_type=draft.project_type,
            current_focus=draft.current_focus,
            next_action=draft.next_action,
            next_follow_up_date=draft.next_follow_up_date,
            risk=draft.risk,
            customer_page_link=draft.customer_page_link or ("" if draft.brand_customer_name == INTERNAL_MAIN_WORK_NAME else f"[[客户/客户--{draft.brand_customer_name}]]"),
            main_work_path=draft.main_work_path,
            path_status="主业路径有效" if draft.main_work_path and Path(draft.main_work_path).exists() else "主业路径失效",
            party_a_source=draft.party_a_source,
            default_party_a_info=default_party_a if not default_party_a.is_empty() else (existing_detail.default_party_a_info if existing_detail else PartyAInfo()),
            party_a_info=draft.party_a_info,
            override_party_a=draft.override_party_a,
            participant_roles=draft.participant_roles or (existing_detail.participant_roles if existing_detail else []),
            participant_roles_markdown=draft.participant_roles_markdown or (existing_detail.participant_roles_markdown if existing_detail else ""),
            progress_nodes=draft.progress_nodes or (existing_detail.progress_nodes if existing_detail else []),
            progress_markdown=draft.progress_markdown or (existing_detail.progress_markdown if existing_detail else ""),
            materials_markdown=draft.materials_markdown or (existing_detail.materials_markdown if existing_detail else ""),
            notes_markdown=draft.notes_markdown,
            approval_entries=draft.approval_entries or (existing_detail.approval_entries if existing_detail else []),
            latest_approval_status=draft.latest_approval_status or (existing_detail.latest_approval_status if existing_detail else ""),
            updated_at=draft.updated_at,
        )
        try:
            detail = self._project_store.upsert_project(merged)
        except ValueError as exc:
            QMessageBox.warning(self, "项目名称冲突", str(exc))
            return
        except KeyError as exc:
            QMessageBox.warning(self, "原项目不存在", f"没有找到原项目「{exc.args[0]}」，请刷新后重试。")
            return
        self._reload_projects(selected_brand=detail.brand_customer_name, selected_project=(detail.brand_customer_name, detail.project_name))
        self._sync_people_from_project(detail)
        self._reload_people()
        if detail.brand_customer_name != INTERNAL_MAIN_WORK_NAME and self.overview_page is not None and self.overview_page:
            self._show_customer(detail.brand_customer_name)
        self.project_management_page.set_status(f"项目「{detail.project_name}」已写入 Obsidian 项目工作台。")

    def _set_last_follow_up_undo(self, state: FollowUpUndoState) -> None:
        self._last_follow_up_undo = state
        self.overview_page.show_undo_action(state.message)

    def _clear_last_follow_up_undo(self) -> None:
        self._last_follow_up_undo = None
        self.overview_page.clear_undo_action()

    def _undo_last_follow_up_action(self) -> None:
        state = self._last_follow_up_undo
        if state is None:
            self.overview_page.clear_undo_action()
            return
        if state.kind == "customer" and state.customer_before is not None:
            restored = self._store.upsert_customer(self._customer_draft_from_detail(state.customer_before))
            self._reload_customers(selected_name=restored.name)
            self._reload_projects(selected_brand=restored.name)
            self.overview_page.show_customer_detail(restored)
            self.customer_library_page.show_customer_detail(restored)
        elif state.kind == "project" and state.project_before is not None:
            restored = self._project_store.upsert_project(self._project_draft_from_detail(state.project_before))
            self._reload_projects(
                selected_brand=restored.brand_customer_name,
                selected_project=(restored.brand_customer_name, restored.project_name),
            )
            self._reload_customers(selected_name=restored.brand_customer_name)
            self._show_customer(restored.brand_customer_name)
        else:
            return
        self._clear_last_follow_up_undo()

    def _handle_project_sync(self) -> None:
        main_work_root = Path(self._config["main_work_root"])
        discovery = DesktopProjectDiscoveryService(main_work_root)
        self.project_management_page.set_sync_busy(True)
        synced_projects = 0
        repaired_customers = 0
        selected_customer = ""
        try:
            for record in self._store.list_customers():
                if not _has_customer_type(record.customer_type, "品牌客户"):
                    continue
                try:
                    detail = self._store.get_customer(record.name)
                except KeyError:
                    continue
                result = discovery.discover_for_customer(detail)
                if result.corrected_main_work_path and result.corrected_main_work_path != detail.main_work_path:
                    repaired_customers += 1
                    repaired_detail = self._store.upsert_customer(self._customer_draft_from_detail(detail, main_work_path=result.corrected_main_work_path))
                    detail = repaired_detail
                for project_draft in result.projects:
                    refreshed_draft = ProjectDraft(
                        brand_customer_name=project_draft.brand_customer_name,
                        project_name=project_draft.project_name,
                        stage=project_draft.stage,
                        year=project_draft.year,
                        project_type=project_draft.project_type,
                        current_focus=project_draft.current_focus,
                        next_action=project_draft.next_action,
                        next_follow_up_date=project_draft.next_follow_up_date,
                        risk=project_draft.risk,
                        customer_page_link=project_draft.customer_page_link,
                        main_work_path=project_draft.main_work_path,
                        path_status=project_draft.path_status,
                        party_a_source=project_draft.party_a_source,
                        default_party_a_info=detail.party_a_info,
                        party_a_info=project_draft.party_a_info,
                        override_party_a=project_draft.override_party_a,
                        participant_roles=project_draft.participant_roles,
                        participant_roles_markdown=project_draft.participant_roles_markdown,
                        progress_nodes=project_draft.progress_nodes,
                        progress_markdown=project_draft.progress_markdown,
                        materials_markdown=project_draft.materials_markdown,
                        notes_markdown=project_draft.notes_markdown,
                        approval_entries=project_draft.approval_entries,
                        latest_approval_status=project_draft.latest_approval_status,
                        updated_at=project_draft.updated_at,
                    )
                    synced_detail = self._project_store.upsert_discovered_project(refreshed_draft)
                    self._sync_people_from_project(synced_detail)
                    synced_projects += 1
                    selected_customer = detail.name
        finally:
            self.project_management_page.set_sync_busy(False)
        self._reload_customers(selected_name=selected_customer or None)
        self._reload_projects(selected_brand=self.project_management_page.selected_brand() or selected_customer)
        self._reload_people()
        self.project_management_page.set_status(f"已同步 {synced_projects} 个项目，修正 {repaired_customers} 个客户主业路径。")

    def _handle_approval_import_preview(self, raw_text: str) -> None:
        if not raw_text:
            self.project_management_page.set_approval_import_status("请先粘贴钉钉审批列表或审批详情文本。")
            return
        if self._start_approval_import_ocr_from_text(raw_text):
            return
        candidates = self._build_approval_import_candidates(raw_text)
        self.project_management_page.set_approval_import_preview(self._format_approval_import_preview(candidates))
        self.project_management_page.set_status(f"已解析 {len(candidates)} 条钉钉审批，请确认归属后再写入。")

    def _handle_approval_inbox_scan(self) -> None:
        self.project_management_page.set_approval_inbox_busy(True)
        try:
            files = self._approval_inbox_scanner.scan_pending()
        finally:
            self.project_management_page.set_approval_inbox_busy(False)
        if not files:
            self._approval_import_source_files = []
            self.project_management_page.set_approval_import_status(
                f"导入箱暂无待处理文件：{self._approval_inbox_scanner.pending_dir}"
            )
            return

        self._approval_import_source_files = files
        raw_text = "\n\n".join(_approval_inbox_file_text(file) for file in files)
        self.project_management_page.set_approval_import_text(raw_text)
        candidates = self._build_approval_import_candidates(raw_text)
        preview = [f"已读取 {len(files)} 个待处理文件。", *self._format_approval_import_preview(candidates)]
        unreadable = [file for file in files if file.error]
        if unreadable:
            preview.append(f"有 {len(unreadable)} 个文件读取不完整，写入后会进入需人工确认。")
        self.project_management_page.set_approval_import_preview(preview)
        self.project_management_page.set_status(
            f"已扫描钉钉审批导入箱：{len(files)} 个文件，解析出 {len(candidates)} 条审批线索。"
        )

    def _handle_approval_inbox_files_dropped(self, paths: object) -> None:
        source_paths = [Path(path) for path in paths] if isinstance(paths, list) else []
        copied_files, skipped_files = self._approval_inbox_scanner.import_files(source_paths)
        if not copied_files:
            skipped_text = f"；已跳过 {len(skipped_files)} 个不支持或无效文件" if skipped_files else ""
            self.project_management_page.set_approval_import_status(
                f"没有可导入的审批文件{skipped_text}。支持 xlsx / csv / txt / md / pdf。"
            )
            return

        self._handle_approval_inbox_scan()
        skipped_text = f"，跳过 {len(skipped_files)} 个不支持文件" if skipped_files else ""
        self.project_management_page.set_status(
            f"已投递 {len(copied_files)} 个文件到钉钉审批导入箱并完成扫描{skipped_text}。确认预览后点“写入审批”。"
        )

    def _handle_approval_import_apply(self, raw_text: str) -> None:
        if not raw_text:
            self.project_management_page.set_approval_import_status("请先粘贴钉钉审批列表或审批详情文本。")
            return
        if self._start_approval_import_ocr_from_text(raw_text):
            return
        candidates = self._build_approval_import_candidates(raw_text)
        if not candidates:
            self.project_management_page.set_approval_import_status("没有解析到可导入的审批记录。")
            return

        project_count = 0
        customer_count = 0
        unassigned_count = 0
        last_project_key: tuple[str, str] | None = None
        selected_customer = ""
        for candidate in candidates:
            if candidate.destination == PROJECT_DESTINATION and candidate.customer_name and candidate.project_name:
                try:
                    self._project_store.append_approval_entry(candidate.customer_name, candidate.project_name, candidate.entry)
                except KeyError:
                    self._project_store.append_unassigned_approval(candidate.entry)
                    unassigned_count += 1
                else:
                    project_count += 1
                    last_project_key = (candidate.customer_name, candidate.project_name)
                    selected_customer = candidate.customer_name
            elif candidate.destination == CUSTOMER_DESTINATION and candidate.customer_name:
                try:
                    self._store.append_pending_approval(candidate.customer_name, candidate.entry)
                except KeyError:
                    self._project_store.append_unassigned_approval(candidate.entry)
                    unassigned_count += 1
                else:
                    customer_count += 1
                    selected_customer = candidate.customer_name
            else:
                self._project_store.append_unassigned_approval(candidate.entry)
                unassigned_count += 1

        self._reload_customers(selected_name=selected_customer or None)
        self._reload_projects(selected_brand=selected_customer, selected_project=last_project_key)
        imported_files, review_files = self._settle_approval_import_source_files(needs_review=unassigned_count > 0 or not candidates)
        preview_lines = self._format_approval_import_preview(candidates)
        self.project_management_page.set_approval_import_preview(preview_lines)
        file_status = f"；文件归档：已导入 {imported_files} 个，需人工确认 {review_files} 个" if imported_files or review_files else ""
        self.project_management_page.set_status(
            f"已写入钉钉审批：项目 {project_count} 条，客户待归属 {customer_count} 条，兜底待归属 {unassigned_count} 条{file_status}。"
        )

    def _settle_approval_import_source_files(self, needs_review: bool) -> tuple[int, int]:
        if not self._approval_import_source_files:
            return 0, 0
        imported_files = 0
        review_files = 0
        for file in self._approval_import_source_files:
            if not file.path.exists():
                continue
            if needs_review or file.error:
                self._approval_inbox_scanner.move_needs_review(file.path)
                review_files += 1
            else:
                self._approval_inbox_scanner.move_imported(file.path)
                imported_files += 1
        self._approval_import_source_files = []
        return imported_files, review_files

    def _build_approval_import_candidates(self, raw_text: str) -> list[ApprovalImportCandidate]:
        customers = self._store.list_customers()
        projects = self._project_store.list_projects()
        customer_details: dict[str, CustomerDetail] = {}
        for customer in customers:
            try:
                customer_details[customer.name] = self._store.get_customer(customer.name)
            except KeyError:
                continue
        project_details = {}
        for project in projects:
            try:
                project_details[(project.brand_customer_name, project.project_name)] = self._project_store.get_project(
                    project.brand_customer_name,
                    project.project_name,
                )
            except KeyError:
                continue
        return build_approval_import_candidates(
            raw_text=raw_text,
            projects=projects,
            customers=customers,
            project_details=project_details,
            customer_details=customer_details,
        )

    def _format_approval_import_preview(self, candidates: list[ApprovalImportCandidate]) -> list[str]:
        lines: list[str] = []
        for index, candidate in enumerate(candidates, start=1):
            entry = candidate.entry
            status = entry.approval_status or entry.approval_result or "待补状态"
            title = entry.title_or_usage or "审批记录"
            lines.append(
                f"{index}. {entry.entry_date} · {status} · {title} -> {candidate.destination_label()}（{candidate.reason}）"
            )
        return lines

    def _start_approval_import_ocr_from_text(self, raw_text: str) -> bool:
        image_bytes = _image_bytes_from_text_reference(raw_text)
        if not image_bytes:
            return False
        self._handle_approval_import_ocr(image_bytes, "粘贴的图片路径")
        return True

    def _handle_approval_import_ocr(self, image_bytes: bytes, source_label: str) -> None:
        if not image_bytes:
            self.project_management_page.set_approval_import_status("没有拿到可识别的审批截图。")
            return
        if self._approval_ocr_thread is not None and self._approval_ocr_thread.isRunning():
            self.project_management_page.set_approval_import_status("上一张钉钉审批截图还在识别中，请稍等。")
            return
        api_key = resolved_minimax_api_key(self._config)
        if not api_key:
            QMessageBox.warning(self, "缺少 MiniMax Key", "请先在设置页填写 MiniMax API Key，或设置 MINIMAX_API_KEY 环境变量。")
            self.nav.setCurrentRow(self.SETTINGS_ROW)
            return

        client = McpOCRClient(
            command=DEFAULT_MCP_COMMAND,
            api_key=api_key,
            api_host=str(self._config.get("minimax_base_url", "")),
        )
        worker = ScreenshotOCRWorker(client=client, image_bytes=image_bytes, source_label=source_label)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._handle_approval_import_ocr_success)
        worker.failed.connect(self._handle_approval_import_ocr_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_approval_import_ocr_finished)
        self._approval_ocr_thread = thread
        self._approval_ocr_worker = worker
        self.project_management_page.set_approval_import_ocr_busy(True, f"正在识别{source_label}...")
        self.project_management_page.set_approval_import_status("正在把钉钉审批截图识别成文字，完成后会自动预览归属。")
        thread.start()

    @Slot(str, str)
    def _handle_approval_import_ocr_success(self, raw_text: str, source_label: str) -> None:
        self.project_management_page.set_approval_import_text(raw_text)
        self.project_management_page.set_approval_import_ocr_busy(False, f"已完成{source_label}识别")
        self.project_management_page.set_approval_import_status("截图已识别成文字，正在预览归属...")
        self._handle_approval_import_preview(raw_text)

    @Slot(str)
    def _handle_approval_import_ocr_failure(self, message: str) -> None:
        QMessageBox.warning(self, "钉钉审批截图识别失败", message)
        self.project_management_page.set_approval_import_ocr_busy(False, "截图识别失败，可改用复制审批文字。")
        self.project_management_page.set_approval_import_status("截图识别失败，可以复制钉钉审批列表文字，或换一张更清晰的截图。")

    @Slot()
    def _handle_approval_import_ocr_finished(self) -> None:
        self._approval_ocr_thread = None
        self._approval_ocr_worker = None

    def _prepare_existing_customer_update(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            QMessageBox.warning(self, "客户不存在", f"没有找到客户「{name}」。")
            return
        self.quick_capture_page.prepare_existing_customer_update(detail)
        self.nav.setCurrentRow(self.QUICK_CAPTURE_ROW)

    def _prepare_existing_customer_edit(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            QMessageBox.warning(self, "客户不存在", f"没有找到客户「{name}」。")
            return
        self.quick_capture_page.prepare_manual_customer_edit(detail)
        self.nav.setCurrentRow(self.QUICK_CAPTURE_ROW)

    def _handle_ai_extract(self, raw_text: str, target_customer_name: str = "") -> None:
        if not raw_text:
            QMessageBox.warning(self, "缺少客户原文", "请先粘贴客户聊天、需求或推进情况。")
            return
        if self._ai_thread is not None and self._ai_thread.isRunning():
            QMessageBox.information(self, "AI 正在整理", "上一条客户信息还在整理中，请稍等。")
            return
        api_key = resolved_minimax_api_key(self._config)
        if not api_key:
            QMessageBox.warning(self, "缺少 MiniMax Key", "请先在设置页填写 MiniMax API Key，或设置 MINIMAX_API_KEY 环境变量。")
            self.nav.setCurrentRow(self.SETTINGS_ROW)
            return
        client = MiniMaxCaptureClient(
            api_key=api_key,
            model=str(self._config.get("minimax_model", "")),
            base_url=str(self._config.get("minimax_base_url", "")),
            customer_types=list(self._config.get("customer_types", [])),
            secondary_tags=list(self._config.get("secondary_tags", [])),
        )
        existing_customers = [record.name for record in self._store.list_customers()]
        worker = AICaptureWorker(
            client=client,
            raw_text=raw_text,
            existing_customers=existing_customers,
            target_customer_name=target_customer_name,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._handle_ai_extract_success)
        worker.failed.connect(self._handle_ai_extract_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_ai_extract_finished)
        self._ai_thread = thread
        self._ai_worker = worker
        self.quick_capture_page.set_ai_busy(True)
        self.quick_capture_page.set_status("正在用 MiniMax 整理客户信息...")
        thread.start()

    def _handle_screenshot_ocr(self, image_bytes: bytes, source_label: str, target_customer_name: str = "") -> None:
        if not image_bytes:
            QMessageBox.warning(self, "缺少截图", "请先粘贴、拖拽或选择客户截图。")
            return
        if self._ocr_thread is not None and self._ocr_thread.isRunning():
            QMessageBox.information(self, "截图识别中", "上一张截图还在识别中，请稍等。")
            return
        if self._ai_thread is not None and self._ai_thread.isRunning():
            QMessageBox.information(self, "AI 正在整理", "当前正在整理上一条客户信息，请稍后再试截图识别。")
            return
        api_key = resolved_minimax_api_key(self._config)
        if not api_key:
            QMessageBox.warning(self, "缺少 MiniMax Key", "请先在设置页填写 MiniMax API Key，或设置 MINIMAX_API_KEY 环境变量。")
            self.nav.setCurrentRow(self.SETTINGS_ROW)
            return

        client = McpOCRClient(
            command=DEFAULT_MCP_COMMAND,
            api_key=api_key,
            api_host=str(self._config.get("minimax_base_url", "")),
        )
        worker = ScreenshotOCRWorker(client=client, image_bytes=image_bytes, source_label=source_label)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(lambda raw_text, label: self._handle_screenshot_ocr_success(raw_text, label, target_customer_name))
        worker.failed.connect(self._handle_screenshot_ocr_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._handle_screenshot_ocr_finished)
        self._ocr_thread = thread
        self._ocr_worker = worker
        self.quick_capture_page.set_screenshot_busy(True, f"正在识别{source_label}...")
        self.quick_capture_page.set_status("正在把截图识别成客户原文，识别后会自动继续整理表单。")
        thread.start()

    @Slot(object)
    def _handle_ai_extract_success(self, draft: object) -> None:
        if isinstance(draft, CaptureDraft):
            if draft.project_draft is not None:
                self.quick_capture_page.apply_draft(draft.project_draft)
                self.quick_capture_page.set_status("AI 已整理为项目/主业事项。请确认字段后，再保存项目/事项。")
                return
            if draft.customer_draft is not None:
                draft = draft.customer_draft
        self.quick_capture_page.apply_draft(draft)
        self.quick_capture_page.set_status("AI 已整理到表单。请确认字段后，再保存录入。")

    @Slot(str)
    def _handle_ai_extract_failure(self, message: str) -> None:
        QMessageBox.warning(self, "AI 整理失败", message)
        self.quick_capture_page.set_status("AI 整理失败，可以修改原文后重试，或继续手动填写。")

    @Slot()
    def _handle_ai_extract_finished(self) -> None:
        self.quick_capture_page.set_ai_busy(False)
        self._ai_thread = None
        self._ai_worker = None

    @Slot(str, str)
    def _handle_screenshot_ocr_success(self, raw_text: str, source_label: str, target_customer_name: str = "") -> None:
        self.quick_capture_page.set_raw_text(raw_text)
        self.quick_capture_page.set_screenshot_busy(False, f"已完成{source_label}识别")
        self.quick_capture_page.set_status("截图已识别为客户原文，正在自动整理到表单...")
        self._handle_ai_extract(raw_text, target_customer_name)

    @Slot(str)
    def _handle_screenshot_ocr_failure(self, message: str) -> None:
        QMessageBox.warning(self, "截图识别失败", message)
        self.quick_capture_page.set_screenshot_busy(False, "截图识别失败，可改用手动粘贴原文。")
        self.quick_capture_page.set_status("截图识别失败，可以换一张更清晰的截图，或继续手动填写。")

    @Slot()
    def _handle_screenshot_ocr_finished(self) -> None:
        self._ocr_thread = None
        self._ocr_worker = None

    def _handle_settings_save(self, payload: dict[str, str]) -> None:
        self._config.update(payload)
        self._config_store.save(self._config)
        self._store = MarkdownCustomerStore(Path(self._config["customer_root"]))
        self._project_store = MarkdownProjectStore(Path(self._config["project_root"]))
        self._person_store = MarkdownPersonStore(Path(self._config["person_root"]))
        self._approval_inbox_scanner = ApprovalInboxScanner(Path(self._config["approval_inbox_root"]))
        self.project_management_page.set_approval_inbox_path(str(self._config["approval_inbox_root"]))
        self._apply_option_config()
        route_label = self._describe_minimax_route(str(self._config.get("minimax_base_url", "")).strip())
        self.settings_page.set_status(f"设置已保存。当前 MiniMax 口径：{route_label}；分类选项已刷新。")
        self._reload_customers()
        self._reload_projects()
        self._reload_people()

    def _handle_settings_refresh(self) -> None:
        self._reload_customers()
        self._reload_projects()
        self._reload_people()
        self.settings_page.set_status("已按当前设置重新加载客户、项目和人员数据。")

    def _handle_settings_validate(self) -> None:
        customer_root = Path(self.settings_page.customer_root_edit.text().strip())
        project_root = Path(self.settings_page.project_root_edit.text().strip())
        person_root = Path(self.settings_page.person_root_edit.text().strip())
        main_work_root = Path(self.settings_page.main_work_root_edit.text().strip())
        approval_inbox_root = Path(self.settings_page.approval_inbox_root_edit.text().strip())
        current_minimax_key = self.settings_page.minimax_api_key_edit.text().strip() or resolved_minimax_api_key(self._config)
        current_minimax_base_url = self.settings_page.minimax_base_url_edit.text().strip() or str(self._config.get("minimax_base_url", "")).strip()
        customer_types = self.settings_page.customer_types_edit.toPlainText().splitlines()
        secondary_tags = self.settings_page.secondary_tags_edit.toPlainText().splitlines()
        messages = [
            f"客户管理路径：{'存在' if customer_root.exists() else '不存在'}",
            f"项目数据路径：{'存在' if project_root.exists() else '不存在'}",
            f"人员数据路径：{'存在' if person_root.exists() else '不存在'}",
            f"主业文件根路径：{'存在' if main_work_root.exists() else '不存在'}",
            f"钉钉审批导入箱：{'存在' if approval_inbox_root.exists() else '不存在'}",
            f"MiniMax Key：{'已配置' if current_minimax_key else '未配置'}",
            f"MiniMax 口径：{self._describe_minimax_route(current_minimax_base_url)}",
            f"MiniMax Base URL：{current_minimax_base_url or '未配置'}",
            f"客户类型选项：{len([item for item in customer_types if item.strip()])} 个",
            f"二级标签选项：{len([item for item in secondary_tags if item.strip()])} 个",
        ]
        self.settings_page.set_status("；".join(messages))

    def _apply_option_config(self) -> None:
        customer_types = list(self._config.get("customer_types", []))
        secondary_tags = list(self._config.get("secondary_tags", []))
        self.quick_capture_page.set_option_lists(customer_types, secondary_tags)
        self.overview_page.set_customer_type_options(customer_types)
        self.customer_library_page.set_customer_type_options(customer_types)

    def _sync_people_from_project(self, detail: ProjectDetail) -> None:
        if not detail.participant_roles:
            return
        synced_name = ""
        for role in detail.participant_roles:
            if not role.name.strip():
                continue
            person = self._person_store.upsert_person(
                PersonDraft(
                    name=role.name.strip(),
                    gender="待判断",
                    side=role.display_side,
                    brand="" if detail.brand_customer_name == INTERNAL_MAIN_WORK_NAME else detail.brand_customer_name,
                    common_relation=role.display_relation,
                    linked_customers=[] if detail.brand_customer_name == INTERNAL_MAIN_WORK_NAME else [detail.brand_customer_name],
                    project_links=[
                        PersonProjectLink(
                            customer_name=detail.brand_customer_name,
                            project_name=detail.project_name,
                            side=role.display_side,
                            relation=role.display_relation,
                            note=role.note,
                        )
                    ],
                    updated_at=detail.updated_at,
                )
            )
            synced_name = person.name
        if synced_name:
            self._reload_people(selected_name=synced_name)

    @staticmethod
    def _customer_draft_from_detail(detail: CustomerDetail, **overrides: str) -> CustomerDraft:
        values = {
            "name": detail.name,
            "customer_type": detail.customer_type,
            "stage": detail.stage,
            "business_direction": detail.business_direction,
            "contact": detail.contact,
            "phone": detail.phone,
            "wechat_id": detail.wechat_id,
            "company": detail.company,
            "source": detail.source,
            "main_work_path": detail.main_work_path,
            "external_material_path": detail.external_material_path,
            "shop_scale": detail.shop_scale,
            "secondary_tags": detail.secondary_tags,
            "current_need": detail.current_need,
            "recent_progress": detail.recent_progress,
            "next_action": detail.next_action,
            "next_follow_up_date": detail.next_follow_up_date,
            "party_a_brand": detail.party_a_brand,
            "party_a_company": detail.party_a_company,
            "party_a_contact": detail.party_a_contact,
            "party_a_phone": detail.party_a_phone,
            "party_a_email": detail.party_a_email,
            "party_a_address": detail.party_a_address,
            "pending_approval_entries": detail.pending_approval_entries,
            "pending_approval_count": detail.pending_approval_count,
            "updated_at": detail.updated_at,
        }
        values.update(overrides)
        return CustomerDraft(**values)

    @staticmethod
    def _project_draft_from_detail(project: ProjectDetail) -> ProjectDraft:
        return ProjectDraft(
            brand_customer_name=project.brand_customer_name,
            project_name=project.project_name,
            original_project_name=project.project_name,
            stage=project.stage,
            year=project.year,
            project_type=project.project_type,
            current_focus=project.current_focus,
            next_action=project.next_action,
            next_follow_up_date=project.next_follow_up_date,
            risk=project.risk,
            customer_page_link=project.customer_page_link,
            main_work_path=project.main_work_path,
            path_status=project.path_status,
            party_a_source=project.party_a_source,
            default_party_a_info=project.default_party_a_info,
            party_a_info=project.party_a_info,
            override_party_a=project.party_a_source.startswith("项目覆盖"),
            participant_roles=project.participant_roles,
            participant_roles_markdown=project.participant_roles_markdown,
            progress_nodes=project.progress_nodes,
            progress_markdown=project.progress_markdown,
            materials_markdown=project.materials_markdown,
            notes_markdown=project.notes_markdown,
            approval_entries=project.approval_entries,
            latest_approval_status=project.latest_approval_status,
            updated_at=project.updated_at,
        )

    @staticmethod
    def _describe_minimax_route(base_url: str) -> str:
        normalized = base_url.rstrip("/")
        if normalized == MINIMAX_BASE_URL:
            return "中国大陆"
        if normalized == MINIMAX_GLOBAL_BASE_URL:
            return "Global"
        if normalized:
            return "自定义"
        return "未配置"


IMAGE_REFERENCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _image_bytes_from_text_reference(raw_text: str) -> bytes:
    candidates = _image_reference_candidates(raw_text)
    for path in candidates:
        if path.suffix.lower() not in IMAGE_REFERENCE_SUFFIXES:
            continue
        try:
            if path.is_file():
                return path.read_bytes()
        except OSError:
            continue
    return b""


def _image_reference_candidates(raw_text: str) -> list[Path]:
    text = raw_text.strip()
    if not text:
        return []
    raw_candidates = [text, *[line.strip() for line in text.splitlines() if line.strip()]]
    raw_candidates.extend(re.findall(r"file://[^\s]+", text))
    raw_candidates.extend(token.strip() for token in re.split(r"\s+", text) if token.strip())

    paths: list[Path] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        path = _path_from_image_reference(candidate)
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        paths.append(path)
        seen.add(key)
    return paths


def _append_note(existing: str, line: str) -> str:
    text = (existing or "").strip()
    if not text or text == "- 待补项目沉淀":
        return line
    return f"{line}\n{text}"


def _path_from_image_reference(value: str) -> Path | None:
    cleaned = value.strip().strip("'\"<>，。；;")
    if not cleaned:
        return None
    if cleaned.startswith("file://"):
        parsed = urlparse(cleaned)
        if parsed.scheme != "file":
            return None
        return Path(unquote(parsed.path))
    if cleaned.startswith("~") or cleaned.startswith("/"):
        return Path(unquote(cleaned)).expanduser()
    return None


def _has_customer_type(value: str, customer_type: str) -> bool:
    return customer_type in [part.strip() for part in re.split(r"\s*/\s*|[，,、]", value) if part.strip()]


def _approval_inbox_file_text(file: ApprovalInboxFile) -> str:
    header = f"【导入文件：{file.path.name}】"
    if file.error:
        return f"{header}\n读取异常：{file.error}\n{file.extracted_text}"
    return f"{header}\n{file.extracted_text}"
