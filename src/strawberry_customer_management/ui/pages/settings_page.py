from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.ai_capture import MINIMAX_BASE_URL, MINIMAX_GLOBAL_BASE_URL


class SettingsPage(QWidget):
    save_requested = Signal(object)
    refresh_requested = Signal()
    validate_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PageScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("TopbarPanel")
        topbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 14, 16, 14)
        topbar_layout.setSpacing(12)
        topbar_text = QVBoxLayout()
        topbar_text.setSpacing(4)
        header = QLabel("设置")
        header.setObjectName("SectionTitle")
        hint = QLabel("这里主要确认 Obsidian 客户数据路径、项目数据路径、主业文件根路径，以及 MiniMax 是走中国大陆还是 Global 接口。")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        topbar_text.addWidget(header)
        topbar_text.addWidget(hint)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self._emit_save)
        refresh_button = QPushButton("刷新数据")
        refresh_button.setObjectName("SecondaryActionButton")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        validate_button = QPushButton("校验路径")
        validate_button.setObjectName("SecondaryActionButton")
        validate_button.clicked.connect(self.validate_requested.emit)
        actions.addWidget(save_button)
        actions.addWidget(refresh_button)
        actions.addWidget(validate_button)

        topbar_layout.addLayout(topbar_text, 1)
        topbar_layout.addLayout(actions)

        path_card = QFrame()
        path_card.setObjectName("WorkspacePanel")
        path_card.setProperty("settingsRole", "paths")
        path_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(16, 16, 16, 16)
        path_layout.setSpacing(10)
        path_title = QLabel("路径配置")
        path_title.setObjectName("PanelTitle")
        path_hint = QLabel("这些目录决定客户资料、项目资料和审批导入箱的读写位置。")
        path_hint.setObjectName("SectionHint")
        path_hint.setWordWrap(True)
        path_layout.addWidget(path_title)
        path_layout.addWidget(path_hint)

        path_form = QFormLayout()
        path_form.setContentsMargins(0, 4, 0, 0)
        path_form.setSpacing(12)
        path_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        path_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        path_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        ai_card = QFrame()
        ai_card.setObjectName("WorkspacePanel")
        ai_card.setProperty("settingsRole", "ai")
        ai_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(16, 16, 16, 16)
        ai_layout.setSpacing(10)
        ai_title = QLabel("AI 配置")
        ai_title.setObjectName("PanelTitle")
        ai_hint = QLabel("MiniMax 配置会同时用于快速录入和截图识别。")
        ai_hint.setObjectName("SectionHint")
        ai_hint.setWordWrap(True)
        ai_layout.addWidget(ai_title)
        ai_layout.addWidget(ai_hint)

        ai_form = QFormLayout()
        ai_form.setContentsMargins(0, 4, 0, 0)
        ai_form.setSpacing(12)
        ai_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        ai_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        ai_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.customer_root_edit = QLineEdit()
        self.project_root_edit = QLineEdit()
        self.main_work_root_edit = QLineEdit()
        self.approval_inbox_root_edit = QLineEdit()
        self.minimax_api_key_edit = QLineEdit()
        self.minimax_api_key_edit.setEchoMode(QLineEdit.Password)
        self.minimax_model_edit = QLineEdit()
        self.minimax_base_url_edit = QLineEdit()
        self.minimax_model_edit.setPlaceholderText("MiniMax-M2.7")
        self.minimax_base_url_edit.setPlaceholderText(MINIMAX_BASE_URL)
        for editor in (
            self.customer_root_edit,
            self.project_root_edit,
            self.main_work_root_edit,
            self.approval_inbox_root_edit,
            self.minimax_api_key_edit,
            self.minimax_model_edit,
            self.minimax_base_url_edit,
        ):
            editor.setMinimumWidth(280)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        path_form.addRow("客户管理根路径", self.customer_root_edit)
        path_form.addRow("项目数据根路径", self.project_root_edit)
        path_form.addRow("主业文件根路径", self.main_work_root_edit)
        path_form.addRow("钉钉审批导入箱", self.approval_inbox_root_edit)
        path_layout.addLayout(path_form)
        path_layout.addStretch(1)

        ai_form.addRow("MiniMax API Key", self.minimax_api_key_edit)
        ai_form.addRow("MiniMax 模型", self.minimax_model_edit)
        ai_form.addRow("MiniMax Base URL（中国大陆 / Global）", self.minimax_base_url_edit)
        ai_layout.addLayout(ai_form)

        minimax_route_hint = QLabel(
            "推荐口径：\n"
            f"- 中国大陆：{MINIMAX_BASE_URL}\n"
            f"- Global：{MINIMAX_GLOBAL_BASE_URL}\n"
            "如果你使用 `sk-cp-...` 这类 MiniMax key，通常应优先使用中国大陆地址。\n"
            "快速录入里的截图识别也会复用这里的 MiniMax Key 和 Base URL。"
        )
        minimax_route_hint.setObjectName("SectionHint")
        minimax_route_hint.setWordWrap(True)
        ai_layout.addWidget(minimax_route_hint)
        ai_layout.addStretch(1)

        status_card = QFrame()
        status_card.setObjectName("WorkspacePanel")
        status_card.setProperty("settingsRole", "status")
        status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(10)
        status_title = QLabel("状态检查")
        status_title.setObjectName("PanelTitle")
        status_hint = QLabel("保存后可刷新数据，或先校验路径是否能被应用正常访问。")
        status_hint.setObjectName("SectionHint")
        status_hint.setWordWrap(True)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        status_layout.addWidget(status_title)
        status_layout.addWidget(status_hint)
        status_layout.addWidget(self.status_label)

        root.addWidget(topbar)
        root.addWidget(path_card)
        root.addWidget(ai_card)
        root.addWidget(status_card)
        root.addStretch(1)

    def set_values(
        self,
        customer_root: str,
        project_root: str,
        main_work_root: str,
        approval_inbox_root: str = "",
        minimax_api_key: str = "",
        minimax_model: str = "",
        minimax_base_url: str = "",
    ) -> None:
        self.customer_root_edit.setText(customer_root)
        self.project_root_edit.setText(project_root)
        self.main_work_root_edit.setText(main_work_root)
        self.approval_inbox_root_edit.setText(approval_inbox_root)
        self.minimax_api_key_edit.setText(minimax_api_key)
        self.minimax_model_edit.setText(minimax_model)
        self.minimax_base_url_edit.setText(minimax_base_url)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _emit_save(self) -> None:
        self.save_requested.emit(
            {
                "customer_root": self.customer_root_edit.text().strip(),
                "project_root": self.project_root_edit.text().strip(),
                "main_work_root": self.main_work_root_edit.text().strip(),
                "approval_inbox_root": self.approval_inbox_root_edit.text().strip(),
                "ai_provider": "minimax",
                "minimax_api_key": self.minimax_api_key_edit.text().strip(),
                "minimax_model": self.minimax_model_edit.text().strip(),
                "minimax_base_url": self.minimax_base_url_edit.text().strip(),
            }
        )
