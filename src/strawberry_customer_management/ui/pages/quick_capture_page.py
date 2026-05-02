from __future__ import annotations

from datetime import date

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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

from strawberry_customer_management.models import (
    CaptureDraft,
    CommunicationEntry,
    CustomerDetail,
    CustomerDraft,
    CUSTOMER_STAGES,
    CUSTOMER_TYPES,
    INTERNAL_MAIN_WORK_NAME,
    normalize_internal_project_name,
    PROJECT_STAGES,
    PROJECT_TYPES,
    ProjectDraft,
    SECONDARY_TAGS,
)
from strawberry_customer_management.ui.widgets.screenshot_input_widget import ScreenshotInputWidget


class MultiSelectComboBox(QComboBox):
    def __init__(self, options: tuple[str, ...], placeholder: str = "") -> None:
        super().__init__()
        self._placeholder = placeholder
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText(placeholder)
        self.set_options(options)
        self.view().pressed.connect(self._toggle_index)

    def set_options(self, options: tuple[str, ...] | list[str]) -> None:
        current_selection = set(self.selected_values()) if self.count() else set()
        self.clear()
        model = self.model()
        for option in options:
            self.addItem(option)
            index = model.index(self.count() - 1, 0)
            state = Qt.CheckState.Checked if option in current_selection else Qt.CheckState.Unchecked
            model.setData(index, state, Qt.ItemDataRole.CheckStateRole)
        self.lineEdit().setPlaceholderText(self._placeholder)
        self._refresh_text()

    def selected_values(self) -> list[str]:
        values: list[str] = []
        model = self.model()
        for index in range(self.count()):
            model_index = model.index(index, 0)
            if model.data(model_index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked:
                values.append(self.itemText(index))
        return values

    def currentText(self) -> str:  # type: ignore[override]
        return " / ".join(self.selected_values())

    def setCurrentText(self, text: str) -> None:  # type: ignore[override]
        selected = set(_split_multi_value(text))
        model = self.model()
        for index in range(self.count()):
            state = Qt.CheckState.Checked if self.itemText(index) in selected else Qt.CheckState.Unchecked
            model.setData(model.index(index, 0), state, Qt.ItemDataRole.CheckStateRole)
        self._refresh_text()

    def clear_selection(self) -> None:
        self.setCurrentText("")

    def _toggle_index(self, index) -> None:
        model = self.model()
        current = model.data(index, Qt.ItemDataRole.CheckStateRole)
        next_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
        model.setData(index, next_state, Qt.ItemDataRole.CheckStateRole)
        self._refresh_text()

    def _refresh_text(self) -> None:
        self.lineEdit().setText(self.currentText())


def _split_multi_value(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*/\s*|[，,、]", value) if part.strip()]


class QuickCapturePage(QWidget):
    save_requested = Signal(object)
    ai_extract_requested = Signal(str, str)
    screenshot_ocr_requested = Signal(object, str, str)

    def __init__(self) -> None:
        super().__init__()

        self.target_customer_name = ""
        self._locked_fields: set[str] = set()
        self.lock_buttons: dict[str, QPushButton] = {}
        self._customer_types = tuple(CUSTOMER_TYPES)
        self._draft_mode = "customer"
        self._project_brand_name = INTERNAL_MAIN_WORK_NAME
        self._original_project_name = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PageScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

        root = QVBoxLayout(content)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        header = QLabel("快速录入")
        header.setObjectName("SectionTitle")
        hint = QLabel("客户更新、客户项目和内部主业事项都可以粘贴原文，AI 整理到表单后，你确认再保存。")
        hint.setObjectName("SectionHint")
        self.target_context_label = QLabel("当前模式：通用录入")
        self.target_context_label.setObjectName("SectionHint")

        raw_card = QFrame()
        raw_card.setObjectName("CardFrame")
        raw_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        raw_layout = QVBoxLayout(raw_card)
        raw_layout.setContentsMargins(18, 18, 18, 18)
        raw_layout.setSpacing(12)

        raw_header = QHBoxLayout()
        raw_title_box = QVBoxLayout()
        raw_title_box.setSpacing(4)
        raw_label = QLabel("录入原文")
        raw_label.setObjectName("PanelTitle")
        raw_hint = QLabel("可以直接粘贴客户名、聊天记录、需求描述、项目推进或内部主业事项。")
        raw_hint.setObjectName("SectionHint")
        raw_title_box.addWidget(raw_label)
        raw_title_box.addWidget(raw_hint)
        raw_header.addLayout(raw_title_box, 1)

        self.raw_text_edit = QTextEdit()
        self.raw_text_edit.setPlaceholderText("直接粘贴客户名、聊天记录、需求描述、项目推进或内部主业事项，AI 会帮你整理成下面的字段。")
        self.raw_text_edit.setMinimumHeight(156)
        self.raw_text_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.screenshot_input_widget = ScreenshotInputWidget()
        self.ai_extract_button = QPushButton("AI 整理到表单")
        self.ai_extract_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.ai_extract_button.clicked.connect(self._emit_ai_extract_requested)
        self.screenshot_input_widget.image_ready.connect(self._emit_screenshot_ocr_requested)

        raw_actions = QHBoxLayout()
        raw_actions.setSpacing(12)
        raw_actions.addWidget(self.screenshot_input_widget, 1)
        raw_actions.addWidget(self.ai_extract_button, 0, Qt.AlignmentFlag.AlignBottom)

        raw_layout.addLayout(raw_header)
        raw_layout.addWidget(self.raw_text_edit)
        raw_layout.addLayout(raw_actions)

        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.name_edit = QLineEdit()
        self.type_combo = MultiSelectComboBox(CUSTOMER_TYPES, "可多选客户类型")
        self.secondary_tags_combo = MultiSelectComboBox(SECONDARY_TAGS, "可多选二级标签")
        self.stage_combo = QComboBox()
        self.stage_combo.addItems(CUSTOMER_STAGES)
        self.business_edit = QLineEdit()
        self.contact_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.wechat_edit = QLineEdit()
        self.company_edit = QLineEdit()
        self.party_a_brand_edit = QLineEdit()
        self.party_a_company_edit = QLineEdit()
        self.party_a_contact_edit = QLineEdit()
        self.party_a_phone_edit = QLineEdit()
        self.party_a_email_edit = QLineEdit()
        self.party_a_address_edit = QTextEdit()
        self.party_a_address_edit.setFixedHeight(64)
        self.shop_scale_edit = QLineEdit()
        self.need_edit = QTextEdit()
        self.need_edit.setFixedHeight(74)
        self.progress_edit = QLineEdit()
        self.next_action_edit = QLineEdit()
        self.next_follow_up_date_edit = QLineEdit()
        self.next_follow_up_date_edit.setPlaceholderText("YYYY-MM-DD")
        self.communication_date_edit = QLineEdit(date.today().isoformat())
        self.summary_edit = QTextEdit()
        self.summary_edit.setFixedHeight(64)
        self.new_info_edit = QTextEdit()
        self.new_info_edit.setFixedHeight(64)
        self.risk_edit = QTextEdit()
        self.risk_edit.setFixedHeight(64)
        self.next_step_edit = QTextEdit()
        self.next_step_edit.setFixedHeight(64)

        self._add_lockable_row(form, "对象/事项名称", "name", self.name_edit)
        self._add_lockable_row(form, "类型", "customer_type", self.type_combo)
        self._add_lockable_row(form, "二级标签", "secondary_tags", self.secondary_tags_combo)
        self._add_lockable_row(form, "阶段", "stage", self.stage_combo)
        self._add_lockable_row(form, "业务方向", "business_direction", self.business_edit)
        self._add_lockable_row(form, "联系人", "contact", self.contact_edit)
        self._add_lockable_row(form, "联系电话", "phone", self.phone_edit)
        self._add_lockable_row(form, "微信号", "wechat_id", self.wechat_edit)
        self._add_lockable_row(form, "所属主体", "company", self.company_edit)
        self._add_lockable_row(form, "甲方品牌", "party_a_brand", self.party_a_brand_edit)
        self._add_lockable_row(form, "甲方公司/主体", "party_a_company", self.party_a_company_edit)
        self._add_lockable_row(form, "收件联系人", "party_a_contact", self.party_a_contact_edit)
        self._add_lockable_row(form, "甲方联系电话", "party_a_phone", self.party_a_phone_edit)
        self._add_lockable_row(form, "甲方电子邮箱", "party_a_email", self.party_a_email_edit)
        self._add_lockable_row(form, "甲方通讯地址", "party_a_address", self.party_a_address_edit)
        self._add_lockable_row(form, "店铺规模", "shop_scale", self.shop_scale_edit)
        self._add_lockable_row(form, "当前需求", "current_need", self.need_edit)
        self._add_lockable_row(form, "最近推进", "recent_progress", self.progress_edit)
        self._add_lockable_row(form, "下次动作", "next_action", self.next_action_edit)
        self._add_lockable_row(form, "下次跟进日期", "next_follow_up_date", self.next_follow_up_date_edit)
        self._add_lockable_row(form, "沟通日期", "communication_date", self.communication_date_edit)
        self._add_lockable_row(form, "沟通结论", "communication_summary", self.summary_edit)
        self._add_lockable_row(form, "新增信息", "communication_new_info", self.new_info_edit)
        self._add_lockable_row(form, "风险/顾虑", "communication_risk", self.risk_edit)
        self._add_lockable_row(form, "下一步", "communication_next_step", self.next_step_edit)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.save_button = QPushButton("保存录入")
        self.save_button.clicked.connect(self._emit_save_requested)
        clear_button = QPushButton("清空")
        clear_button.setObjectName("SecondaryActionButton")
        clear_button.clicked.connect(self.clear_form)
        actions.addWidget(self.save_button)
        actions.addWidget(clear_button)
        actions.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")

        helper_card = QFrame()
        helper_card.setObjectName("CardFrame")
        helper_card.setMinimumWidth(300)
        helper_card.setMaximumWidth(360)
        helper_card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        helper_layout = QVBoxLayout(helper_card)
        helper_layout.setContentsMargins(18, 18, 18, 18)
        helper_layout.setSpacing(12)
        helper_title = QLabel("录入提示")
        helper_title.setObjectName("SectionTitle")
        helper_layout.addWidget(helper_title)
        for title, body in (
            ("适合粘贴什么", "客户名、聊天记录、需求描述、项目推进、内部系统或流程事项都可以；AI 只帮你整理，保存前仍由你确认。"),
            ("老客户更新", "从客户总览点 AI 更新此客户进入时，会锁定为当前客户，避免误建重复客户。"),
            ("主业事项", f"非客户事项会固定落到「{INTERNAL_MAIN_WORK_NAME}」下面，不需要创建伪客户。"),
            ("保存前检查", "重点看对象/事项名称、类型、当前需求/重点和下一步。确认过的字段可以点锁定，避免后续 AI 覆盖。"),
            ("身份线索", "客户类型可多选：博主和网店店群客户可以同时勾选；小时达、微信这类渠道写到二级标签。"),
        ):
            helper_item = QFrame()
            helper_item.setObjectName("SideItem")
            item_layout = QVBoxLayout(helper_item)
            item_layout.setContentsMargins(12, 12, 12, 12)
            item_layout.setSpacing(6)
            title_label = QLabel(title)
            title_label.setObjectName("SideItemTitle")
            body_label = QLabel(body)
            body_label.setObjectName("PanelHint")
            body_label.setWordWrap(True)
            item_layout.addWidget(title_label)
            item_layout.addWidget(body_label)
            helper_layout.addWidget(helper_item)
        helper_layout.addStretch(1)
        self.helper_card = helper_card

        main_workspace = QHBoxLayout()
        main_workspace.setSpacing(14)
        left_column = QVBoxLayout()
        left_column.setSpacing(16)
        left_column.addWidget(raw_card)
        left_column.addWidget(card)
        left_column.addLayout(actions)
        left_column.addWidget(self.status_label)
        left_column.addStretch(1)
        main_workspace.addLayout(left_column, 1)
        main_workspace.addWidget(helper_card)

        root.addWidget(header)
        root.addWidget(hint)
        root.addWidget(self.target_context_label)
        root.addLayout(main_workspace)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_option_lists(self, customer_types: list[str] | tuple[str, ...], secondary_tags: list[str] | tuple[str, ...]) -> None:
        self._customer_types = tuple(customer_types) or tuple(CUSTOMER_TYPES)
        if self._draft_mode == "customer":
            self.type_combo.set_options(self._customer_types)
        self.secondary_tags_combo.set_options(tuple(secondary_tags) or tuple(SECONDARY_TAGS))

    def set_raw_text(self, text: str) -> None:
        self.raw_text_edit.setPlainText(text)

    def clear_form(self) -> None:
        self.clear_field_locks()
        self.clear_target_customer()
        self._set_customer_mode()
        self.raw_text_edit.clear()
        self.name_edit.clear()
        self.type_combo.clear_selection()
        self.secondary_tags_combo.clear_selection()
        self.business_edit.clear()
        self.contact_edit.clear()
        self.phone_edit.clear()
        self.wechat_edit.clear()
        self.company_edit.clear()
        self.party_a_brand_edit.clear()
        self.party_a_company_edit.clear()
        self.party_a_contact_edit.clear()
        self.party_a_phone_edit.clear()
        self.party_a_email_edit.clear()
        self.party_a_address_edit.clear()
        self.shop_scale_edit.clear()
        self.need_edit.clear()
        self.progress_edit.clear()
        self.next_action_edit.clear()
        self.next_follow_up_date_edit.clear()
        self.communication_date_edit.setText(date.today().isoformat())
        self.summary_edit.clear()
        self.new_info_edit.clear()
        self.risk_edit.clear()
        self.next_step_edit.clear()

    def apply_draft(self, draft: CustomerDraft | ProjectDraft | CaptureDraft) -> None:
        if isinstance(draft, CaptureDraft):
            if draft.project_draft is not None:
                self.apply_draft(draft.project_draft)
            elif draft.customer_draft is not None:
                self.apply_draft(draft.customer_draft)
            return
        if isinstance(draft, ProjectDraft):
            self._apply_project_draft(draft)
            return
        self._set_customer_mode()
        self._set_line_value("name", self.name_edit, draft.name)
        self._set_combo_value("customer_type", self.type_combo, draft.customer_type)
        self._set_combo_value("secondary_tags", self.secondary_tags_combo, draft.secondary_tags)
        self._set_combo_value("stage", self.stage_combo, draft.stage)
        self._set_line_value("business_direction", self.business_edit, draft.business_direction)
        self._set_line_value("contact", self.contact_edit, draft.contact)
        self._set_line_value("phone", self.phone_edit, draft.phone)
        self._set_line_value("wechat_id", self.wechat_edit, draft.wechat_id)
        self._set_line_value("company", self.company_edit, draft.company)
        self._set_line_value("party_a_brand", self.party_a_brand_edit, draft.party_a_brand)
        self._set_line_value("party_a_company", self.party_a_company_edit, draft.party_a_company)
        self._set_line_value("party_a_contact", self.party_a_contact_edit, draft.party_a_contact)
        self._set_line_value("party_a_phone", self.party_a_phone_edit, draft.party_a_phone)
        self._set_line_value("party_a_email", self.party_a_email_edit, draft.party_a_email)
        self._set_text_value("party_a_address", self.party_a_address_edit, draft.party_a_address)
        self._set_line_value("shop_scale", self.shop_scale_edit, draft.shop_scale)
        self._set_text_value("current_need", self.need_edit, draft.current_need)
        self._set_line_value("recent_progress", self.progress_edit, draft.recent_progress)
        self._set_line_value("next_action", self.next_action_edit, draft.next_action)
        self._set_line_value("next_follow_up_date", self.next_follow_up_date_edit, draft.next_follow_up_date)
        if draft.communication:
            self._set_line_value("communication_date", self.communication_date_edit, draft.communication.entry_date)
            self._set_text_value("communication_summary", self.summary_edit, draft.communication.summary)
            self._set_text_value("communication_new_info", self.new_info_edit, draft.communication.new_info)
            self._set_text_value("communication_risk", self.risk_edit, draft.communication.risk)
            self._set_text_value("communication_next_step", self.next_step_edit, draft.communication.next_step)

    def prepare_existing_customer_update(self, detail: CustomerDetail) -> None:
        self.clear_field_locks()
        self.set_target_customer(detail.name)
        self.apply_draft(
            CustomerDraft(
                name=detail.name,
                customer_type=detail.customer_type or self._customer_types[0],
                stage=detail.stage or CUSTOMER_STAGES[0],
                secondary_tags=detail.secondary_tags,
                business_direction=detail.business_direction,
                contact=detail.contact,
                phone=detail.phone,
                wechat_id=detail.wechat_id,
                company=detail.company,
                party_a_brand=detail.party_a_brand,
                party_a_company=detail.party_a_company,
                party_a_contact=detail.party_a_contact,
                party_a_phone=detail.party_a_phone,
                party_a_email=detail.party_a_email,
                party_a_address=detail.party_a_address,
                shop_scale=detail.shop_scale,
                current_need=detail.current_need,
                recent_progress=detail.recent_progress,
                next_action=detail.next_action,
                next_follow_up_date=detail.next_follow_up_date,
                communication=CommunicationEntry(entry_date=date.today().isoformat()),
            )
        )
        self.set_status(f"正在更新老客户「{detail.name}」。粘贴最新聊天后点 AI 整理到表单。")

    def prepare_manual_customer_edit(self, detail: CustomerDetail) -> None:
        self.clear_field_locks()
        self.raw_text_edit.clear()
        self.set_target_customer(detail.name, mode_label="手动编辑老客户")
        self.apply_draft(
            CustomerDraft(
                name=detail.name,
                customer_type=detail.customer_type or self._customer_types[0],
                stage=detail.stage or CUSTOMER_STAGES[0],
                secondary_tags=detail.secondary_tags,
                business_direction=detail.business_direction,
                contact=detail.contact,
                phone=detail.phone,
                wechat_id=detail.wechat_id,
                company=detail.company,
                party_a_brand=detail.party_a_brand,
                party_a_company=detail.party_a_company,
                party_a_contact=detail.party_a_contact,
                party_a_phone=detail.party_a_phone,
                party_a_email=detail.party_a_email,
                party_a_address=detail.party_a_address,
                shop_scale=detail.shop_scale,
                current_need=detail.current_need,
                recent_progress=detail.recent_progress,
                next_action=detail.next_action,
                next_follow_up_date=detail.next_follow_up_date,
                communication=CommunicationEntry(entry_date=date.today().isoformat()),
            )
        )
        self.set_status(f"已载入「{detail.name}」当前信息。直接修改字段后点保存并更新客户。")

    def set_target_customer(self, name: str, mode_label: str = "更新老客户") -> None:
        self.target_customer_name = name.strip()
        if self.target_customer_name:
            self.target_context_label.setText(f"当前模式：{mode_label}「{self.target_customer_name}」")
            self.raw_text_edit.setPlaceholderText(f"粘贴「{self.target_customer_name}」的最新聊天、需求或推进情况。")
            self.name_edit.setText(self.target_customer_name)
            self.name_edit.setReadOnly(False)
        else:
            self.clear_target_customer()

    def clear_target_customer(self) -> None:
        self.target_customer_name = ""
        self.target_context_label.setText("当前模式：通用录入")
        self.raw_text_edit.setPlaceholderText("直接粘贴客户名、聊天记录、需求描述、项目推进或内部主业事项，AI 会帮你整理成下面的字段。")
        self.name_edit.setReadOnly(False)

    def set_ai_busy(self, busy: bool) -> None:
        self.ai_extract_button.setEnabled(not busy)
        self.ai_extract_button.setText("AI 整理中..." if busy else "AI 整理到表单")

    def set_screenshot_busy(self, busy: bool, text: str = "") -> None:
        self.screenshot_input_widget.set_busy(busy, text)

    def set_field_locked(self, field_key: str, locked: bool) -> None:
        if locked:
            self._locked_fields.add(field_key)
        else:
            self._locked_fields.discard(field_key)
        button = self.lock_buttons.get(field_key)
        if button is not None:
            button.blockSignals(True)
            button.setChecked(locked)
            button.setText("已锁" if locked else "锁定")
            button.blockSignals(False)

    def is_field_locked(self, field_key: str) -> bool:
        return field_key in self._locked_fields

    def clear_field_locks(self) -> None:
        for field_key in list(self._locked_fields):
            self.set_field_locked(field_key, False)

    def _add_lockable_row(self, form: QFormLayout, label: str, field_key: str, editor: QWidget) -> None:
        row = QWidget()
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, editor.sizePolicy().verticalPolicy())
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        lock_button = QPushButton("锁定")
        lock_button.setObjectName("FieldLockButton")
        lock_button.setCheckable(True)
        lock_button.clicked.connect(lambda checked, key=field_key: self.set_field_locked(key, checked))
        self.lock_buttons[field_key] = lock_button
        row_layout.addWidget(editor, 1)
        row_layout.addWidget(lock_button)
        form.addRow(label, row)

    def _set_line_value(self, field_key: str, editor: QLineEdit, value: str) -> None:
        if not self.is_field_locked(field_key):
            editor.setText(value)

    def _set_text_value(self, field_key: str, editor: QTextEdit, value: str) -> None:
        if not self.is_field_locked(field_key):
            editor.setPlainText(value)

    def _set_combo_value(self, field_key: str, editor: QComboBox, value: str) -> None:
        if not self.is_field_locked(field_key):
            editor.setCurrentText(value)

    def _emit_ai_extract_requested(self) -> None:
        self.ai_extract_requested.emit(self.raw_text_edit.toPlainText().strip(), self.target_customer_name)

    def _emit_screenshot_ocr_requested(self, image_bytes: bytes, source_label: str) -> None:
        self.screenshot_ocr_requested.emit(image_bytes, source_label, self.target_customer_name)

    def _emit_save_requested(self) -> None:
        if self._draft_mode == "project":
            project_name = self.name_edit.text().strip()
            if (self._project_brand_name or INTERNAL_MAIN_WORK_NAME) == INTERNAL_MAIN_WORK_NAME:
                project_name = normalize_internal_project_name(
                    project_name,
                    self.communication_date_edit.text().strip() or date.today().isoformat(),
                )
            draft = ProjectDraft(
                brand_customer_name=self._project_brand_name or INTERNAL_MAIN_WORK_NAME,
                project_name=project_name,
                stage=self.stage_combo.currentText().strip() or "推进中",
                original_project_name=self._original_project_name,
                project_type=self.type_combo.currentText().strip(),
                current_focus=self.need_edit.toPlainText().strip() or self.summary_edit.toPlainText().strip(),
                next_action=self.next_action_edit.text().strip() or self.next_step_edit.toPlainText().strip(),
                next_follow_up_date=self.next_follow_up_date_edit.text().strip(),
                risk=self.risk_edit.toPlainText().strip(),
                notes_markdown=self.new_info_edit.toPlainText().strip(),
                updated_at=self.communication_date_edit.text().strip() or date.today().isoformat(),
            )
            self.save_requested.emit(draft)
            return
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
            original_name=self.target_customer_name,
            secondary_tags=self.secondary_tags_combo.currentText().strip(),
            business_direction=self.business_edit.text().strip(),
            contact=self.contact_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            wechat_id=self.wechat_edit.text().strip(),
            company=self.company_edit.text().strip(),
            party_a_brand=self.party_a_brand_edit.text().strip(),
            party_a_company=self.party_a_company_edit.text().strip(),
            party_a_contact=self.party_a_contact_edit.text().strip(),
            party_a_phone=self.party_a_phone_edit.text().strip(),
            party_a_email=self.party_a_email_edit.text().strip(),
            party_a_address=self.party_a_address_edit.toPlainText().strip(),
            shop_scale=self.shop_scale_edit.text().strip(),
            current_need=self.need_edit.toPlainText().strip(),
            recent_progress=self.progress_edit.text().strip(),
            next_action=self.next_action_edit.text().strip(),
            next_follow_up_date=self.next_follow_up_date_edit.text().strip(),
            communication=communication,
        )
        self.save_requested.emit(draft)

    def _set_customer_mode(self) -> None:
        self._draft_mode = "customer"
        self._project_brand_name = INTERNAL_MAIN_WORK_NAME
        self._original_project_name = ""
        self.type_combo.set_options(self._customer_types)
        self.stage_combo.blockSignals(True)
        self.stage_combo.clear()
        self.stage_combo.addItems(CUSTOMER_STAGES)
        self.stage_combo.blockSignals(False)
        self.save_button.setText("保存录入")

    def _set_project_mode(self, brand_customer_name: str, original_project_name: str = "") -> None:
        self._draft_mode = "project"
        self._project_brand_name = brand_customer_name.strip() or INTERNAL_MAIN_WORK_NAME
        self._original_project_name = original_project_name.strip()
        self.type_combo.set_options(PROJECT_TYPES)
        self.secondary_tags_combo.clear_selection()
        self.stage_combo.blockSignals(True)
        self.stage_combo.clear()
        self.stage_combo.addItems(PROJECT_STAGES)
        self.stage_combo.blockSignals(False)
        self.target_context_label.setText(f"当前模式：项目/事项「{self._project_brand_name}」")
        self.save_button.setText("保存项目/事项")

    def _apply_project_draft(self, draft: ProjectDraft) -> None:
        self._set_project_mode(draft.brand_customer_name, draft.original_project_name)
        self._set_line_value("name", self.name_edit, draft.project_name)
        self._set_combo_value("customer_type", self.type_combo, draft.project_type)
        self._set_combo_value("stage", self.stage_combo, draft.stage or "推进中")
        self._set_text_value("current_need", self.need_edit, draft.current_focus)
        self._set_line_value("next_action", self.next_action_edit, draft.next_action)
        self._set_line_value("next_follow_up_date", self.next_follow_up_date_edit, draft.next_follow_up_date)
        self._set_text_value("communication_risk", self.risk_edit, draft.risk)
        self._set_line_value("communication_date", self.communication_date_edit, draft.updated_at or date.today().isoformat())
