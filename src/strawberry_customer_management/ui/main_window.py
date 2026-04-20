from __future__ import annotations

from pathlib import Path

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

from strawberry_customer_management.ai_capture import AICaptureError, MiniMaxCaptureClient
from strawberry_customer_management.config import ConfigStore
from strawberry_customer_management.config import resolved_minimax_api_key
from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.models import CustomerDraft
from strawberry_customer_management.ui.app_icon import load_app_icon
from strawberry_customer_management.ui.pages.overview_page import OverviewPage
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


class MainWindow(QMainWindow):
    def __init__(self, config_store: ConfigStore) -> None:
        super().__init__()
        self.setWindowTitle("草莓客户管理系统")
        self.setWindowIcon(load_app_icon())
        self.resize(1260, 820)

        self._config_store = config_store
        self._config = self._config_store.load()
        self._store = MarkdownCustomerStore(Path(self._config["customer_root"]))
        self._ai_thread: QThread | None = None
        self._ai_worker: AICaptureWorker | None = None

        self.nav = QListWidget()
        self.nav.addItems(["客户总览", "快速录入", "设置"])
        self.nav.setFixedWidth(148)

        self.stack = QStackedWidget()
        self.overview_page = OverviewPage()
        self.quick_capture_page = QuickCapturePage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.overview_page)
        self.stack.addWidget(self.quick_capture_page)
        self.stack.addWidget(self.settings_page)

        self.overview_page.customer_selected.connect(self._show_customer)
        self.overview_page.update_customer_requested.connect(self._prepare_existing_customer_update)
        self.quick_capture_page.ai_extract_requested.connect(self._handle_ai_extract)
        self.quick_capture_page.save_requested.connect(self._handle_capture_save)
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
            self._config["main_work_root"],
            self._config.get("minimax_api_key", ""),
            self._config.get("minimax_model", ""),
            self._config.get("minimax_base_url", ""),
        )
        self.nav.setCurrentRow(0)
        self._reload_customers()

    def _reload_customers(self, selected_name: str | None = None) -> None:
        records = self._store.list_customers()
        self.overview_page.set_focus_customers(self._store.list_focus_customers())
        self.overview_page.set_customers(records, selected_name=selected_name)
        self.quick_capture_page.set_status(f"当前共加载 {len(records)} 个客户。")

    def _show_customer(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            self.overview_page.show_customer_detail(None)
            return
        self.overview_page.show_customer_detail(detail)

    def _handle_capture_save(self, draft: CustomerDraft) -> None:
        if not draft.name:
            QMessageBox.warning(self, "缺少客户名", "请先填写客户名称。")
            return
        detail = self._store.upsert_customer(draft)
        self._reload_customers(selected_name=detail.name)
        self.quick_capture_page.set_status(f"{detail.name} 已写入 Obsidian 客户管理工作台。")
        self.nav.setCurrentRow(0)

    def _prepare_existing_customer_update(self, name: str) -> None:
        try:
            detail = self._store.get_customer(name)
        except KeyError:
            QMessageBox.warning(self, "客户不存在", f"没有找到客户「{name}」。")
            return
        self.quick_capture_page.prepare_existing_customer_update(detail)
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
            self.nav.setCurrentRow(2)
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

    def _handle_settings_save(self, payload: dict[str, str]) -> None:
        self._config.update(payload)
        self._config_store.save(self._config)
        self._store = MarkdownCustomerStore(Path(self._config["customer_root"]))
        self.settings_page.set_status("设置已保存。")
        self._reload_customers()

    def _handle_settings_refresh(self) -> None:
        self._reload_customers()
        self.settings_page.set_status("已按当前设置重新加载客户数据。")

    def _handle_settings_validate(self) -> None:
        customer_root = Path(self.settings_page.customer_root_edit.text().strip())
        main_work_root = Path(self.settings_page.main_work_root_edit.text().strip())
        current_minimax_key = self.settings_page.minimax_api_key_edit.text().strip() or resolved_minimax_api_key(self._config)
        messages = [
            f"客户管理路径：{'存在' if customer_root.exists() else '不存在'}",
            f"主业文件根路径：{'存在' if main_work_root.exists() else '不存在'}",
            f"MiniMax Key：{'已配置' if current_minimax_key else '未配置'}",
        ]
        self.settings_page.set_status("；".join(messages))
