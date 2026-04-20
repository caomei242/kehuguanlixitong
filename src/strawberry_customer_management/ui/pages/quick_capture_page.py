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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import CommunicationEntry, CustomerDraft, CUSTOMER_STAGES, CUSTOMER_TYPES


class QuickCapturePage(QWidget):
    save_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        header = QLabel("快速录入")
        header.setObjectName("SectionTitle")
        hint = QLabel("把新客户或最新沟通快速结构化，保存后自动更新客户页和总表。")
        hint.setObjectName("SectionHint")

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
        root.addWidget(card, 1)
        root.addLayout(actions)
        root.addWidget(self.status_label)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def clear_form(self) -> None:
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

