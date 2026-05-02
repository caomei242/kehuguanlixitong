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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.ai_capture import MINIMAX_BASE_URL, MINIMAX_GLOBAL_BASE_URL
from strawberry_customer_management.models import CUSTOMER_TYPES, SECONDARY_TAGS


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
        hint = QLabel("")
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
        path_hint = QLabel("")
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
        ai_hint = QLabel("")
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
        self.person_root_edit = QLineEdit()
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
            self.person_root_edit,
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
        path_form.addRow("人员数据根路径", self.person_root_edit)
        path_form.addRow("主业文件根路径", self.main_work_root_edit)
        path_form.addRow("钉钉审批导入箱", self.approval_inbox_root_edit)
        path_layout.addLayout(path_form)
        path_layout.addStretch(1)

        ai_form.addRow("MiniMax API Key", self.minimax_api_key_edit)
        ai_form.addRow("MiniMax 模型", self.minimax_model_edit)
        ai_form.addRow("MiniMax Base URL（中国大陆 / Global）", self.minimax_base_url_edit)
        ai_layout.addLayout(ai_form)

        minimax_route_hint = QLabel("")
        minimax_route_hint.setObjectName("SectionHint")
        minimax_route_hint.setWordWrap(True)
        ai_layout.addWidget(minimax_route_hint)
        ai_layout.addStretch(1)

        taxonomy_card = QFrame()
        taxonomy_card.setObjectName("WorkspacePanel")
        taxonomy_card.setProperty("settingsRole", "taxonomy")
        taxonomy_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        taxonomy_layout = QVBoxLayout(taxonomy_card)
        taxonomy_layout.setContentsMargins(16, 16, 16, 16)
        taxonomy_layout.setSpacing(10)
        taxonomy_title = QLabel("分类选项配置")
        taxonomy_title.setObjectName("PanelTitle")
        taxonomy_hint = QLabel("")
        taxonomy_hint.setObjectName("SectionHint")
        taxonomy_hint.setWordWrap(True)
        taxonomy_layout.addWidget(taxonomy_title)
        taxonomy_layout.addWidget(taxonomy_hint)

        taxonomy_form = QFormLayout()
        taxonomy_form.setContentsMargins(0, 4, 0, 0)
        taxonomy_form.setSpacing(12)
        taxonomy_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        taxonomy_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        taxonomy_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.customer_types_edit = QTextEdit()
        self.secondary_tags_edit = QTextEdit()
        self.customer_types_edit.setPlaceholderText("品牌客户\n网店KA客户\n网店店群客户\n博主")
        self.secondary_tags_edit.setPlaceholderText("小时达\n微信\nAI商品图\nAI详情页")
        self.customer_types_edit.setPlainText("\n".join(CUSTOMER_TYPES))
        self.secondary_tags_edit.setPlainText("\n".join(SECONDARY_TAGS))
        for editor in (self.customer_types_edit, self.secondary_tags_edit):
            editor.setMinimumWidth(280)
            editor.setFixedHeight(132)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        taxonomy_form.addRow("客户类型选项", self.customer_types_edit)
        taxonomy_form.addRow("二级标签选项", self.secondary_tags_edit)
        taxonomy_layout.addLayout(taxonomy_form)

        status_card = QFrame()
        status_card.setObjectName("WorkspacePanel")
        status_card.setProperty("settingsRole", "status")
        status_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 16, 16, 16)
        status_layout.setSpacing(10)
        status_title = QLabel("状态检查")
        status_title.setObjectName("PanelTitle")
        status_hint = QLabel("")
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
        root.addWidget(taxonomy_card)
        root.addWidget(status_card)
        root.addStretch(1)

    def set_values(
        self,
        customer_root: str,
        project_root: str,
        person_root: str,
        main_work_root: str,
        approval_inbox_root: str = "",
        minimax_api_key: str = "",
        minimax_model: str = "",
        minimax_base_url: str = "",
        customer_types: list[str] | tuple[str, ...] | None = None,
        secondary_tags: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.customer_root_edit.setText(customer_root)
        self.project_root_edit.setText(project_root)
        self.person_root_edit.setText(person_root)
        self.main_work_root_edit.setText(main_work_root)
        self.approval_inbox_root_edit.setText(approval_inbox_root)
        self.minimax_api_key_edit.setText(minimax_api_key)
        self.minimax_model_edit.setText(minimax_model)
        self.minimax_base_url_edit.setText(minimax_base_url)
        self.customer_types_edit.setPlainText("\n".join(customer_types or CUSTOMER_TYPES))
        self.secondary_tags_edit.setPlainText("\n".join(secondary_tags or SECONDARY_TAGS))

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _emit_save(self) -> None:
        self.save_requested.emit(
            {
                "customer_root": self.customer_root_edit.text().strip(),
                "project_root": self.project_root_edit.text().strip(),
                "person_root": self.person_root_edit.text().strip(),
                "main_work_root": self.main_work_root_edit.text().strip(),
                "approval_inbox_root": self.approval_inbox_root_edit.text().strip(),
                "ai_provider": "minimax",
                "minimax_api_key": self.minimax_api_key_edit.text().strip(),
                "minimax_model": self.minimax_model_edit.text().strip(),
                "minimax_base_url": self.minimax_base_url_edit.text().strip(),
                "customer_types": _parse_options_text(self.customer_types_edit.toPlainText()),
                "secondary_tags": _parse_options_text(self.secondary_tags_edit.toPlainText()),
            }
        )


def _parse_options_text(text: str) -> list[str]:
    options: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        cleaned = raw_line.strip().lstrip("-*•").strip()
        if not cleaned:
            continue
        for part in cleaned.replace("，", "/").replace(",", "/").replace("、", "/").split("/"):
            option = part.strip()
            if not option or option in seen:
                continue
            options.append(option)
            seen.add(option)
    return options
