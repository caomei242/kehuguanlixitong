from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
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
from strawberry_customer_management.models import CustomerDetail, CustomerDraft, PartyAInfo, ProjectDraft
from strawberry_customer_management.project_discovery import DesktopProjectDiscoveryService
from strawberry_customer_management.project_store import MarkdownProjectStore
from strawberry_customer_management.ui.app_icon import load_app_icon
from strawberry_customer_management.ui.pages.overview_page import OverviewPage
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
            draft = self.client.extract_draft(
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


class MainWindow(QMainWindow):
    def __init__(self, config_store: ConfigStore) -> None:
        super().__init__()
        self.setWindowTitle("草莓客户管理系统")
        self.setWindowIcon(load_app_icon())
        self.resize(1260, 820)

        self._config_store = config_store
        self._config = self._config_store.load()
        self._store = MarkdownCustomerStore(Path(self._config["customer_root"]))
        self._project_store = MarkdownProjectStore(Path(self._config["project_root"]))
        self._approval_inbox_scanner = ApprovalInboxScanner(Path(self._config["approval_inbox_root"]))
        self._approval_import_source_files: list[ApprovalInboxFile] = []
        self._ai_thread: QThread | None = None
        self._ai_worker: AICaptureWorker | None = None
        self._ocr_thread: QThread | None = None
        self._ocr_worker: ScreenshotOCRWorker | None = None
        self._approval_ocr_thread: QThread | None = None
        self._approval_ocr_worker: ScreenshotOCRWorker | None = None

        self.nav = QListWidget()
        self.nav.addItems(["客户总览", "快速录入", "项目管理", "设置"])
        self.nav.setFixedWidth(148)

        self.stack = QStackedWidget()
        self.overview_page = OverviewPage()
        self.quick_capture_page = QuickCapturePage()
        self.project_management_page = ProjectManagementPage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.quick_capture_page)
        self.stack.addWidget(self.project_management_page)
        self.stack.addWidget(self.settings_page)

        self.overview_page.customer_selected.connect(self._show_customer)
        self.overview_page.update_customer_requested.connect(self._prepare_existing_customer_update)
        self.overview_page.edit_customer_requested.connect(self._prepare_existing_customer_edit)
        self.overview_page.view_customer_projects_requested.connect(self._focus_customer_projects)
        self.overview_page.quick_capture_requested.connect(lambda: self.nav.setCurrentRow(1))
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
        self.settings_page.save_requested.connect(self._handle_settings_save)
        self.settings_page.refresh_requested.connect(self._handle_settings_refresh)
        self.settings_page.validate_requested.connect(self._handle_settings_validate)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        brand_title = QLabel("草莓")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("客户管理系统")
        brand_subtitle.setObjectName("BrandSubtitle")

        brand_box = QVBoxLayout()
        brand_box.setContentsMargins(0, 0, 0, 0)
        brand_box.setSpacing(2)
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_subtitle)

        sidebar = QFrame()
        sidebar.setObjectName("WindowSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(16)
        sidebar_layout.addLayout(brand_box)
        sidebar_layout.addWidget(self.nav)
        sidebar_layout.addStretch(1)

        content = QFrame()
        content.setObjectName("WindowContentShell")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(sidebar)
        body_layout.addWidget(content, 1)

        shell = QFrame()
        shell.setObjectName("WindowShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.addWidget(body)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.addWidget(shell)
        self.setCentralWidget(root)

        self.settings_page.set_values(
            self._config["customer_root"],
            self._config["project_root"],
            self._config["main_work_root"],
            str(self._config.get("approval_inbox_root", "")),
            self._config.get("minimax_api_key", ""),
            self._config.get("minimax_model", ""),
            self._config.get("minimax_base_url", ""),
        )
        self.project_management_page.set_approval_inbox_path(str(self._config.get("approval_inbox_root", "")))
        self.nav.setCurrentRow(0)
        self._reload_customers()
        self._reload_projects()

    def _reload_customers(self, selected_name: str | None = None) -> None:
        records = self._store.list_customers()
        self.overview_page.set_focus_customers(self._store.list_focus_customers())
        self.overview_page.set_customers(records, selected_name=selected_name)
        self.quick_capture_page.set_status(f"当前共加载 {len(records)} 个客户。")

    def _reload_projects(
        self,
        selected_brand: str = "",
        selected_project: tuple[str, str] | None = None,
    ) -> None:
        records = self._project_store.list_projects()
        self.project_management_page.set_projects(records, selected_brand=selected_brand, selected_project=selected_project)
        active_key = selected_project or self.project_management_page.selected_project_key()
        if active_key:
            self._show_project(*active_key)
        else:
            self.project_management_page.set_project_detail(None)

    def _show_customer(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            self.overview_page.show_customer_detail(None)
            self.overview_page.set_related_projects([], "")
            return
        self.overview_page.show_customer_detail(detail)
        self.overview_page.set_related_projects(self._project_store.list_projects_for_brand(detail.name), detail.customer_type)

    def _show_project(self, brand_customer_name: str, project_name: str) -> None:
        try:
            detail = self._project_store.get_project(brand_customer_name, project_name)
        except KeyError:
            self.project_management_page.set_project_detail(None)
            return
        self.project_management_page.set_project_detail(detail)

    def _focus_customer_projects(self, customer_name: str) -> None:
        self.nav.setCurrentRow(2)
        self.project_management_page.focus_brand(customer_name)
        active_key = self.project_management_page.selected_project_key()
        if active_key:
            self._show_project(*active_key)

    def _handle_capture_save(self, draft: CustomerDraft) -> None:
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
        self.nav.setCurrentRow(0)

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
            risk=draft.risk,
            customer_page_link=draft.customer_page_link or f"[[客户/客户--{draft.brand_customer_name}]]",
            main_work_path=draft.main_work_path,
            path_status="主业路径有效" if draft.main_work_path and Path(draft.main_work_path).exists() else "主业路径失效",
            party_a_source=draft.party_a_source,
            default_party_a_info=default_party_a if not default_party_a.is_empty() else (existing_detail.default_party_a_info if existing_detail else PartyAInfo()),
            party_a_info=draft.party_a_info,
            override_party_a=draft.override_party_a,
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
        if self.overview_page is not None and self.overview_page:
            self._show_customer(detail.brand_customer_name)
        self.project_management_page.set_status(f"项目「{detail.project_name}」已写入 Obsidian 项目工作台。")

    def _handle_project_sync(self) -> None:
        main_work_root = Path(self._config["main_work_root"])
        discovery = DesktopProjectDiscoveryService(main_work_root)
        self.project_management_page.set_sync_busy(True)
        synced_projects = 0
        repaired_customers = 0
        selected_customer = ""
        try:
            for record in self._store.list_customers():
                if record.customer_type != "品牌客户":
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
                        risk=project_draft.risk,
                        customer_page_link=project_draft.customer_page_link,
                        main_work_path=project_draft.main_work_path,
                        path_status=project_draft.path_status,
                        party_a_source=project_draft.party_a_source,
                        default_party_a_info=detail.party_a_info,
                        party_a_info=project_draft.party_a_info,
                        override_party_a=project_draft.override_party_a,
                        materials_markdown=project_draft.materials_markdown,
                        notes_markdown=project_draft.notes_markdown,
                        approval_entries=project_draft.approval_entries,
                        latest_approval_status=project_draft.latest_approval_status,
                        updated_at=project_draft.updated_at,
                    )
                    self._project_store.upsert_discovered_project(refreshed_draft)
                    synced_projects += 1
                    selected_customer = detail.name
        finally:
            self.project_management_page.set_sync_busy(False)
        self._reload_customers(selected_name=selected_customer or None)
        self._reload_projects(selected_brand=self.project_management_page.selected_brand() or selected_customer)
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
            self.nav.setCurrentRow(3)
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
        self.nav.setCurrentRow(1)

    def _prepare_existing_customer_edit(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            QMessageBox.warning(self, "客户不存在", f"没有找到客户「{name}」。")
            return
        self.quick_capture_page.prepare_manual_customer_edit(detail)
        self.nav.setCurrentRow(1)

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
            self.nav.setCurrentRow(3)
            return
        client = MiniMaxCaptureClient(
            api_key=api_key,
            model=str(self._config.get("minimax_model", "")),
            base_url=str(self._config.get("minimax_base_url", "")),
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
            self.nav.setCurrentRow(3)
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
    def _handle_ai_extract_success(self, draft: CustomerDraft) -> None:
        self.quick_capture_page.apply_draft(draft)
        self.quick_capture_page.set_status("AI 已整理到表单。请确认字段后，再保存并更新客户。")

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
        self._approval_inbox_scanner = ApprovalInboxScanner(Path(self._config["approval_inbox_root"]))
        self.project_management_page.set_approval_inbox_path(str(self._config["approval_inbox_root"]))
        route_label = self._describe_minimax_route(str(self._config.get("minimax_base_url", "")).strip())
        self.settings_page.set_status(f"设置已保存。当前 MiniMax 口径：{route_label}。")
        self._reload_customers()
        self._reload_projects()

    def _handle_settings_refresh(self) -> None:
        self._reload_customers()
        self._reload_projects()
        self.settings_page.set_status("已按当前设置重新加载客户和项目数据。")

    def _handle_settings_validate(self) -> None:
        customer_root = Path(self.settings_page.customer_root_edit.text().strip())
        project_root = Path(self.settings_page.project_root_edit.text().strip())
        main_work_root = Path(self.settings_page.main_work_root_edit.text().strip())
        approval_inbox_root = Path(self.settings_page.approval_inbox_root_edit.text().strip())
        current_minimax_key = self.settings_page.minimax_api_key_edit.text().strip() or resolved_minimax_api_key(self._config)
        current_minimax_base_url = self.settings_page.minimax_base_url_edit.text().strip() or str(self._config.get("minimax_base_url", "")).strip()
        messages = [
            f"客户管理路径：{'存在' if customer_root.exists() else '不存在'}",
            f"项目数据路径：{'存在' if project_root.exists() else '不存在'}",
            f"主业文件根路径：{'存在' if main_work_root.exists() else '不存在'}",
            f"钉钉审批导入箱：{'存在' if approval_inbox_root.exists() else '不存在'}",
            f"MiniMax Key：{'已配置' if current_minimax_key else '未配置'}",
            f"MiniMax 口径：{self._describe_minimax_route(current_minimax_base_url)}",
            f"MiniMax Base URL：{current_minimax_base_url or '未配置'}",
        ]
        self.settings_page.set_status("；".join(messages))

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
            "current_need": detail.current_need,
            "recent_progress": detail.recent_progress,
            "next_action": detail.next_action,
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


def _approval_inbox_file_text(file: ApprovalInboxFile) -> str:
    header = f"【导入文件：{file.path.name}】"
    if file.error:
        return f"{header}\n读取异常：{file.error}\n{file.extracted_text}"
    return f"{header}\n{file.extracted_text}"
