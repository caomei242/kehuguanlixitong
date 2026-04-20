from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import CommunicationEntry, CustomerDetail, CustomerDraft, CUSTOMER_STAGES, CUSTOMER_TYPES


class QuickCapturePage(QWidget):
    save_requested = Signal(object)
    ai_extract_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()

        self.target_customer_name = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PageScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        header = QLabel("快速录入")
        header.setObjectName("SectionTitle")
        hint = QLabel("新客户和老客户更新都可以粘贴原文，AI 整理到表单后，你确认再保存。")
        hint.setObjectName("SectionHint")
        self.target_context_label = QLabel("当前模式：通用录入")
        self.target_context_label.setObjectName("SectionHint")

        raw_card = QFrame()
        raw_card.setObjectName("CardFrame")
        raw_layout = QVBoxLayout(raw_card)
        raw_layout.setContentsMargins(18, 18, 18, 18)
        raw_layout.setSpacing(10)
        raw_label = QLabel("客户原文")
        raw_label.setObjectName("SectionHint")
        self.raw_text_edit = QTextEdit()
        self.raw_text_edit.setPlaceholderText("直接粘贴客户名、聊天记录、需求描述或推进情况，AI 会帮你整理成下面的字段。")
        self.raw_text_edit.setFixedHeight(112)
        self.ai_extract_button = QPushButton("AI 整理到表单")
        self.ai_extract_button.clicked.connect(self._emit_ai_extract_requested)
        raw_layout.addWidget(raw_label)
        raw_layout.addWidget(self.raw_text_edit)
        raw_layout.addWidget(self.ai_extract_button)

        card = QFrame()
        card.setObjectName("CardFrame")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)

        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(CUSTOMER_TYPES)
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(CUSTOMER_STAGES)
        self.business_edit = QLineEdit()
        self.contact_edit = QLineEdit()
        self.company_edit = QLineEdit()
        self.shop_scale_edit = QLineEdit()
        self.need_edit = QTextEdit()
        self.need_edit.setFixedHeight(74)
        self.progress_edit = QLineEdit()
        self.next_action_edit = QLineEdit()
        self.communication_date_edit = QLineEdit(date.today().isoformat())
        self.summary_edit = QTextEdit()
        self.summary_edit.setFixedHeight(64)
        self.new_info_edit = QTextEdit()
        self.new_info_edit.setFixedHeight(64)
        self.risk_edit = QTextEdit()
        self.risk_edit.setFixedHeight(64)
        self.next_step_edit = QTextEdit()
        self.next_step_edit.setFixedHeight(64)

        form.addRow("客户名称", self.name_edit)
        form.addRow("客户类型", self.type_combo)
        form.addRow("阶段", self.stage_combo)
        form.addRow("业务方向", self.business_edit)
        form.addRow("联系人", self.contact_edit)
        form.addRow("所属主体", self.company_edit)
        form.addRow("店铺规模", self.shop_scale_edit)
        form.addRow("当前需求", self.need_edit)
        form.addRow("最近推进", self.progress_edit)
        form.addRow("下次动作", self.next_action_edit)
        form.addRow("沟通日期", self.communication_date_edit)
        form.addRow("沟通结论", self.summary_edit)
        form.addRow("新增信息", self.new_info_edit)
        form.addRow("风险/顾虑", self.risk_edit)
        form.addRow("下一步", self.next_step_edit)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        save_button = QPushButton("保存并更新客户")
        save_button.clicked.connect(self._emit_save_requested)
        clear_button = QPushButton("清空")
        clear_button.setObjectName("SecondaryActionButton")
        clear_button.clicked.connect(self.clear_form)
        actions.addWidget(save_button)
        actions.addWidget(clear_button)
        actions.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")

        root.addWidget(header)
        root.addWidget(hint)
        root.addWidget(self.target_context_label)
        root.addWidget(raw_card)
        root.addWidget(card, 1)
        root.addLayout(actions)
        root.addWidget(self.status_label)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def clear_form(self) -> None:
        self.clear_target_customer()
        self.raw_text_edit.clear()
        self.name_edit.clear()
        self.business_edit.clear()
        self.contact_edit.clear()
        self.company_edit.clear()
        self.shop_scale_edit.clear()
        self.need_edit.clear()
        self.progress_edit.clear()
        self.next_action_edit.clear()
        self.communication_date_edit.setText(date.today().isoformat())
        self.summary_edit.clear()
        self.new_info_edit.clear()
        self.risk_edit.clear()
        self.next_step_edit.clear()

    def apply_draft(self, draft: CustomerDraft) -> None:
        self.name_edit.setText(draft.name)
        self.type_combo.setCurrentText(draft.customer_type)
        self.stage_combo.setCurrentText(draft.stage)
        self.business_edit.setText(draft.business_direction)
        self.contact_edit.setText(draft.contact)
        self.company_edit.setText(draft.company)
        self.shop_scale_edit.setText(draft.shop_scale)
        self.need_edit.setPlainText(draft.current_need)
        self.progress_edit.setText(draft.recent_progress)
        self.next_action_edit.setText(draft.next_action)
        if draft.communication:
            self.communication_date_edit.setText(draft.communication.entry_date)
            self.summary_edit.setPlainText(draft.communication.summary)
            self.new_info_edit.setPlainText(draft.communication.new_info)
            self.risk_edit.setPlainText(draft.communication.risk)
            self.next_step_edit.setPlainText(draft.communication.next_step)

    def prepare_existing_customer_update(self, detail: CustomerDetail) -> None:
        self.set_target_customer(detail.name)
        self.apply_draft(
            CustomerDraft(
                name=detail.name,
                customer_type=detail.customer_type or CUSTOMER_TYPES[0],
                stage=detail.stage or CUSTOMER_STAGES[0],
                business_direction=detail.business_direction,
                contact=detail.contact,
                company=detail.company,
                shop_scale=detail.shop_scale,
                current_need=detail.current_need,
                recent_progress=detail.recent_progress,
                next_action=detail.next_action,
                communication=CommunicationEntry(entry_date=date.today().isoformat()),
            )
        )
        self.set_status(f"正在更新老客户「{detail.name}」。粘贴最新聊天后点 AI 整理到表单。")

    def set_target_customer(self, name: str) -> None:
        self.target_customer_name = name.strip()
        if self.target_customer_name:
            self.target_context_label.setText(f"当前模式：更新老客户「{self.target_customer_name}」")
            self.raw_text_edit.setPlaceholderText(f"粘贴「{self.target_customer_name}」的最新聊天、需求或推进情况。")
        else:
            self.clear_target_customer()

    def clear_target_customer(self) -> None:
        self.target_customer_name = ""
        self.target_context_label.setText("当前模式：通用录入")
        self.raw_text_edit.setPlaceholderText("直接粘贴客户名、聊天记录、需求描述或推进情况，AI 会帮你整理成下面的字段。")

    def set_ai_busy(self, busy: bool) -> None:
        self.ai_extract_button.setEnabled(not busy)
        self.ai_extract_button.setText("AI 整理中..." if busy else "AI 整理到表单")

    def _emit_ai_extract_requested(self) -> None:
        self.ai_extract_requested.emit(self.raw_text_edit.toPlainText().strip(), self.target_customer_name)

    def _emit_save_requested(self) -> None:
        communication = CommunicationEntry(
            entry_date=self.communication_date_edit.text().strip() or date.today().isoformat(),
            summary=self.summary_edit.toPlainText().strip(),
            new_info=self.new_info_edit.toPlainText().strip(),
            risk=self.risk_edit.toPlainText().strip(),
            next_step=self.next_step_edit.toPlainText().strip(),
        )
        draft = CustomerDraft(
            name=self.name_edit.text().strip(),
            customer_type=self.type_combo.currentText().strip(),
            stage=self.stage_combo.currentText().strip(),
            business_direction=self.business_edit.text().strip(),
            contact=self.contact_edit.text().strip(),
            company=self.company_edit.text().strip(),
            shop_scale=self.shop_scale_edit.text().strip(),
            current_need=self.need_edit.toPlainText().strip(),
            recent_progress=self.progress_edit.text().strip(),
            next_action=self.next_action_edit.text().strip(),
            communication=communication,
        )
        self.save_requested.emit(draft)
