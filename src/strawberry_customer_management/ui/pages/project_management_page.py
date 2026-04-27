from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from strawberry_customer_management.markdown_store import sort_approval_entries, sort_project_records, summarize_approval_entry
from strawberry_customer_management.models import (
    PROJECT_STAGES,
    PROJECT_TYPES,
    ApprovalEntry,
    PartyAInfo,
    ProjectDetail,
    ProjectDraft,
    ProjectRecord,
)
from strawberry_customer_management.ui.widgets.screenshot_input_widget import ScreenshotInputWidget


ALL_BRANDS_FILTER = "全部客户"
ALL_YEARS_FILTER = "全部年份"
ALL_STAGES_FILTER = "全部状态"


class ProjectManagementPage(QWidget):
    project_selected = Signal(str, str)
    sync_requested = Signal()
    save_requested = Signal(object)
    approval_import_preview_requested = Signal(str)
    approval_import_apply_requested = Signal(str)
    approval_import_ocr_requested = Signal(object, str)
    approval_inbox_scan_requested = Signal()
    approval_inbox_files_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._records: list[ProjectRecord] = []
        self._displayed_records: list[ProjectRecord] = []
        self._current_project_key: tuple[str, str] | None = None
        self._current_detail: ProjectDetail | None = None
        self._active_widgets: dict[str, object] = {}

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
        root.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("TopbarPanel")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 14, 16, 14)
        topbar_layout.setSpacing(12)

        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("项目管理")
        title.setObjectName("SectionTitle")
        self.meta_label = QLabel("当前筛选：全部客户 / 全部年份 / 全部状态")
        self.meta_label.setObjectName("SectionHint")
        self.meta_label.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(self.meta_label)

        self.brand_filter_combo = QComboBox()
        self.brand_filter_combo.addItem(ALL_BRANDS_FILTER)
        self.brand_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        self.year_filter_combo = QComboBox()
        self.year_filter_combo.addItem(ALL_YEARS_FILTER)
        self.year_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        self.stage_filter_combo = QComboBox()
        self.stage_filter_combo.addItems([ALL_STAGES_FILTER, *PROJECT_STAGES])
        self.stage_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        self.sync_button = QPushButton("同步桌面项目")
        self.sync_button.clicked.connect(self.sync_requested.emit)

        topbar_layout.addLayout(heading, 1)
        topbar_layout.addWidget(self.brand_filter_combo)
        topbar_layout.addWidget(self.year_filter_combo)
        topbar_layout.addWidget(self.stage_filter_combo)
        topbar_layout.addWidget(self.sync_button)

        banner = QLabel("项目以客户下的单次合作或运营事项为单位；品牌客户可同步桌面项目，网店KA客户可沉淀客户运营跟进。")
        banner.setObjectName("OverviewBanner")
        banner.setWordWrap(True)

        import_panel = QFrame()
        import_panel.setObjectName("WorkspacePanel")
        import_layout = QVBoxLayout(import_panel)
        import_layout.setContentsMargins(14, 12, 14, 12)
        import_layout.setSpacing(8)
        import_header = QHBoxLayout()
        import_title = QLabel("钉钉审批导入")
        import_title.setObjectName("SectionTitle")
        import_hint = QLabel("从钉钉审批列表或详情复制文本粘贴到这里，先预览归属，再写入项目/客户审批记录。")
        import_hint.setObjectName("SectionHint")
        import_hint.setWordWrap(True)
        self.approval_import_text_edit = QTextEdit()
        self.approval_import_text_edit.setPlaceholderText("粘贴钉钉审批列表、审批详情，或截图 OCR 后得到的文字。截图请用下面的“粘贴截图”。")
        self.approval_import_text_edit.setFixedHeight(78)
        self.approval_import_screenshot_widget = ScreenshotInputWidget(
            status_text="支持粘贴钉钉审批截图、拖拽图片或选择图片，识别后会放到上方文本框。",
            choose_dialog_title="选择钉钉审批截图",
        )
        self.approval_import_screenshot_widget.setMaximumHeight(84)
        self.approval_import_screenshot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.approval_import_screenshot_widget.image_ready.connect(self._emit_approval_import_ocr_requested)
        self.approval_import_preview_button = QPushButton("预览归属")
        self.approval_import_preview_button.setObjectName("SecondaryActionButton")
        self.approval_import_preview_button.clicked.connect(self._emit_approval_import_preview_requested)
        self.approval_import_apply_button = QPushButton("写入审批")
        self.approval_import_apply_button.clicked.connect(self._emit_approval_import_apply_requested)
        self.approval_inbox_scan_button = QPushButton("扫描导入箱")
        self.approval_inbox_scan_button.setObjectName("SecondaryActionButton")
        self.approval_inbox_scan_button.clicked.connect(self.approval_inbox_scan_requested.emit)
        self.approval_inbox_path_label = QLabel("")
        self.approval_inbox_path_label.setObjectName("SectionHint")
        self.approval_inbox_path_label.setWordWrap(True)
        self.approval_inbox_drop_zone = ApprovalInboxDropZone()
        self.approval_inbox_drop_zone.setMaximumHeight(72)
        self.approval_inbox_drop_zone.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.approval_inbox_drop_zone.files_dropped.connect(self.approval_inbox_files_dropped.emit)
        self.approval_import_preview_label = QLabel("尚未预览。")
        self.approval_import_preview_label.setObjectName("SectionHint")
        self.approval_import_preview_label.setWordWrap(True)
        import_header.addWidget(import_title)
        import_header.addStretch(1)
        import_header.addWidget(self.approval_inbox_scan_button)
        import_header.addWidget(self.approval_import_preview_button)
        import_header.addWidget(self.approval_import_apply_button)
        import_layout.addLayout(import_header)
        import_layout.addWidget(import_hint)
        import_layout.addWidget(self.approval_inbox_path_label)
        import_layout.addWidget(self.approval_inbox_drop_zone)
        import_layout.addWidget(self.approval_import_text_edit)
        import_layout.addWidget(self.approval_import_screenshot_widget)
        import_layout.addWidget(self.approval_import_preview_label)

        list_panel = QFrame()
        list_panel.setObjectName("WorkspacePanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(10)
        list_header = QHBoxLayout()
        list_title = QLabel("项目列表")
        list_title.setObjectName("SectionTitle")
        self.project_count_label = QLabel("当前 0 个项目")
        self.project_count_label.setObjectName("SoftBadge")
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        list_header.addWidget(self.project_count_label)
        self.project_cards_layout = QVBoxLayout()
        self.project_cards_layout.setSpacing(10)
        list_layout.addLayout(list_header)
        list_layout.addLayout(self.project_cards_layout)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")

        root.addWidget(topbar)
        root.addWidget(banner)
        root.addWidget(import_panel)
        root.addWidget(list_panel)
        root.addWidget(self.status_label)
        root.addStretch(1)

    def set_projects(
        self,
        records: list[ProjectRecord],
        selected_brand: str = "",
        selected_project: tuple[str, str] | None = None,
    ) -> None:
        self._records = sort_project_records(records)
        self._reset_filter_options(self._records)
        if selected_brand and selected_brand in [self.brand_filter_combo.itemText(index) for index in range(self.brand_filter_combo.count())]:
            self.brand_filter_combo.setCurrentText(selected_brand)
        if selected_project:
            self._current_project_key = selected_project
        elif self._records and self._current_project_key is None:
            first = self._records[0]
            self._current_project_key = (first.brand_customer_name, first.project_name)
        self._refresh()

    def selected_brand(self) -> str:
        current = self.brand_filter_combo.currentText().strip()
        return "" if current == ALL_BRANDS_FILTER else current

    def selected_project_key(self) -> tuple[str, str] | None:
        return self._current_project_key

    def displayed_project_names(self) -> list[str]:
        return [record.project_name for record in self._displayed_records]

    def focus_brand(self, brand_name: str) -> None:
        if brand_name and brand_name in [self.brand_filter_combo.itemText(index) for index in range(self.brand_filter_combo.count())]:
            self.brand_filter_combo.setCurrentText(brand_name)
        self._refresh()

    def set_project_detail(self, detail: ProjectDetail | None) -> None:
        self._current_detail = detail
        if detail is None:
            self._current_project_key = None
            self._active_widgets = {}
            self.status_label.setText("")
        else:
            self._current_project_key = (detail.brand_customer_name, detail.project_name)
            self.status_label.setText(f"当前项目：{detail.project_name} · {detail.path_status}")
        self._refresh_project_cards(self._displayed_records)

    def set_sync_busy(self, busy: bool) -> None:
        self.sync_button.setEnabled(not busy)
        self.sync_button.setText("同步中..." if busy else "同步桌面项目")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_approval_import_preview(self, lines: list[str]) -> None:
        if not lines:
            self.approval_import_preview_label.setText("没有解析到可导入的审批记录。")
            return
        self.approval_import_preview_label.setText("\n".join(lines))

    def set_approval_import_status(self, text: str) -> None:
        self.approval_import_preview_label.setText(text)

    def set_approval_import_text(self, text: str) -> None:
        self.approval_import_text_edit.setPlainText(text)

    def set_approval_inbox_path(self, path: str) -> None:
        self.approval_inbox_path_label.setText(f"导入箱：{path}/待处理")

    def set_approval_inbox_busy(self, busy: bool) -> None:
        self.approval_inbox_scan_button.setEnabled(not busy)
        self.approval_inbox_scan_button.setText("扫描中..." if busy else "扫描导入箱")

    def set_approval_import_ocr_busy(self, busy: bool, text: str = "") -> None:
        self.approval_import_preview_button.setEnabled(not busy)
        self.approval_import_apply_button.setEnabled(not busy)
        self.approval_import_screenshot_widget.set_busy(busy, text)

    def _reset_filter_options(self, records: list[ProjectRecord]) -> None:
        brand_names = [ALL_BRANDS_FILTER, *sorted({record.brand_customer_name for record in records})]
        current_brand = self.brand_filter_combo.currentText()
        self.brand_filter_combo.blockSignals(True)
        self.brand_filter_combo.clear()
        self.brand_filter_combo.addItems(brand_names)
        if current_brand in brand_names:
            self.brand_filter_combo.setCurrentText(current_brand)
        self.brand_filter_combo.blockSignals(False)

        year_values = [ALL_YEARS_FILTER, *sorted({record.year for record in records if record.year}, reverse=True)]
        current_year = self.year_filter_combo.currentText()
        self.year_filter_combo.blockSignals(True)
        self.year_filter_combo.clear()
        self.year_filter_combo.addItems(year_values)
        if current_year in year_values:
            self.year_filter_combo.setCurrentText(current_year)
        self.year_filter_combo.blockSignals(False)

    def _refresh(self) -> None:
        records = list(self._records)
        selected_brand = self.brand_filter_combo.currentText()
        if selected_brand and selected_brand != ALL_BRANDS_FILTER:
            records = [record for record in records if record.brand_customer_name == selected_brand]
        selected_year = self.year_filter_combo.currentText()
        if selected_year and selected_year != ALL_YEARS_FILTER:
            records = [record for record in records if record.year == selected_year]
        selected_stage = self.stage_filter_combo.currentText()
        if selected_stage and selected_stage != ALL_STAGES_FILTER:
            records = [record for record in records if record.stage == selected_stage]
        records = sort_project_records(records)
        self._displayed_records = records
        self.project_count_label.setText(f"当前 {len(records)} 个项目")
        self.meta_label.setText(
            f"当前筛选：{selected_brand or ALL_BRANDS_FILTER} / {selected_year or ALL_YEARS_FILTER} / {selected_stage or ALL_STAGES_FILTER}"
        )
        if self._current_project_key and not any(
            (record.brand_customer_name, record.project_name) == self._current_project_key for record in records
        ):
            self._current_project_key = None
            self._current_detail = None
        if self._current_project_key is None and records:
            first = records[0]
            self._current_project_key = (first.brand_customer_name, first.project_name)
        self._refresh_project_cards(records)
        if self._current_project_key:
            self.project_selected.emit(*self._current_project_key)

    def _refresh_project_cards(self, records: list[ProjectRecord]) -> None:
        _clear_layout(self.project_cards_layout)
        self._active_widgets = {}
        if not records:
            label = QLabel("当前筛选下暂无项目。先点右上角“同步桌面项目”。")
            label.setObjectName("EmptyState")
            label.setWordWrap(True)
            self.project_cards_layout.addWidget(label)
            return
        for record in records:
            self.project_cards_layout.addWidget(self._build_project_card(record))
        self.project_cards_layout.addStretch(1)

    def _build_project_card(self, record: ProjectRecord) -> QFrame:
        selected = (record.brand_customer_name, record.project_name) == self._current_project_key

        shell = QFrame()
        shell.setObjectName("DetailCard" if selected else "WorkspacePanel")
        shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(14, 14, 14, 14)
        shell_layout.setSpacing(10)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel(record.project_name)
        title.setObjectName("CustomerTileName")
        meta = QLabel(f"{record.brand_customer_name} · {record.year or '待确认年份'} · {record.project_type or '待补类型'}")
        meta.setObjectName("CustomerTileMeta")
        meta.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(meta)

        right_box = QVBoxLayout()
        right_box.setSpacing(6)
        tag = QLabel(record.stage or "待确认")
        tag.setObjectName("SoftBadge")
        toggle_button = QPushButton("收起详情" if selected else "展开详情")
        toggle_button.setObjectName("InlineActionButton")
        toggle_button.clicked.connect(
            lambda _checked=False, brand=record.brand_customer_name, project=record.project_name: self._toggle_project(brand, project)
        )
        right_box.addWidget(tag, 0, Qt.AlignmentFlag.AlignRight)
        right_box.addWidget(toggle_button, 0, Qt.AlignmentFlag.AlignRight)

        focus = QLabel(record.current_focus or "待补项目当前重点")
        focus.setObjectName("CustomerTileNeed")
        focus.setWordWrap(True)
        next_action = QLabel(f"下一步：{record.next_action or '待补下一步'}")
        next_action.setObjectName("CustomerTileMeta")
        next_action.setWordWrap(True)
        latest_approval = QLabel(f"最新审批：{record.latest_approval_status or '暂无审批记录'}")
        latest_approval.setObjectName("SectionHint")
        latest_approval.setWordWrap(True)
        footer = QHBoxLayout()
        updated_label = QLabel(record.updated_at or "待同步")
        updated_label.setObjectName("SectionHint")
        footer.addWidget(latest_approval, 1)
        footer.addWidget(updated_label)

        header.addLayout(title_box, 1)
        header.addLayout(right_box)
        shell_layout.addLayout(header)
        shell_layout.addWidget(focus)
        shell_layout.addWidget(next_action)
        shell_layout.addLayout(footer)

        if selected:
            if self._current_detail and (
                self._current_detail.brand_customer_name,
                self._current_detail.project_name,
            ) == self._current_project_key:
                shell_layout.addWidget(self._build_expanded_section(self._current_detail))
            else:
                loading_label = QLabel("项目详情加载中...")
                loading_label.setObjectName("SectionHint")
                shell_layout.addWidget(loading_label)

        return shell

    def _build_expanded_section(self, detail: ProjectDetail) -> QFrame:
        section = QFrame()
        section.setObjectName("CardFrame")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        compact_row = QHBoxLayout()
        compact_row.setSpacing(12)
        compact_row.addWidget(self._build_summary_panel(detail), 1)
        compact_row.addWidget(self._build_approval_panel(detail.approval_entries), 1)
        layout.addLayout(compact_row)

        form_wrap = QHBoxLayout()
        form_wrap.setSpacing(14)
        basic_card = QFrame()
        basic_card.setObjectName("WorkspacePanel")
        basic_layout = QVBoxLayout(basic_card)
        basic_layout.setContentsMargins(14, 14, 14, 14)
        basic_layout.setSpacing(10)
        basic_title = QLabel("项目基础信息")
        basic_title.setObjectName("PanelTitle")
        form = QFormLayout()
        _configure_form_layout(form)
        basic_layout.addWidget(basic_title)
        basic_layout.addLayout(form)

        party_card = QFrame()
        party_card.setObjectName("WorkspacePanel")
        party_layout = QVBoxLayout(party_card)
        party_layout.setContentsMargins(14, 14, 14, 14)
        party_layout.setSpacing(10)
        party_title = QLabel("甲方信息与资料")
        party_title.setObjectName("PanelTitle")
        party_form = QFormLayout()
        _configure_form_layout(party_form)
        party_layout.addWidget(party_title)
        party_layout.addLayout(party_form)

        brand_name_edit = QLineEdit(detail.brand_customer_name)
        brand_name_edit.setReadOnly(True)
        project_name_edit = QLineEdit(detail.project_name)

        detected_year = self._detect_year(detail.project_name, detail.main_work_path)
        initial_year = detail.year or detected_year or "待确认年份"
        year_panel = QWidget()
        year_panel_layout = QVBoxLayout(year_panel)
        year_panel_layout.setContentsMargins(0, 0, 0, 0)
        year_panel_layout.setSpacing(8)
        year_display = QLabel(initial_year)
        year_display.setObjectName("SoftBadge")
        year_detect_label = QLabel(
            f"自动识别：{detected_year}" if detected_year else "自动识别失败，可直接点快捷项，不需要手动敲。"
        )
        year_detect_label.setObjectName("SectionHint")
        year_edit = QLineEdit(initial_year)
        year_edit.setVisible(False)
        year_edit.textChanged.connect(lambda text: year_display.setText(text.strip() or "待确认年份"))
        year_shortcuts = QHBoxLayout()
        for label, value in (
            ("今年", str(date.today().year)),
            ("去年", str(date.today().year - 1)),
            ("待确认", "待确认年份"),
        ):
            button = QPushButton(label)
            button.setObjectName("InlineActionButton")
            button.clicked.connect(
                lambda _checked=False, year_value=value, edit=year_edit, display=year_display: self._apply_year_value(
                    edit, display, year_value, manual=False
                )
            )
            year_shortcuts.addWidget(button)
        manual_button = QPushButton("手动改")
        manual_button.setObjectName("InlineActionButton")
        manual_button.clicked.connect(lambda _checked=False, edit=year_edit: self._show_manual_year_editor(edit))
        year_shortcuts.addWidget(manual_button)
        year_shortcuts.addStretch(1)
        year_panel_layout.addWidget(year_display)
        year_panel_layout.addWidget(year_detect_label)
        year_panel_layout.addLayout(year_shortcuts)
        year_panel_layout.addWidget(year_edit)

        stage_combo = QComboBox()
        stage_combo.addItems(PROJECT_STAGES)
        stage_combo.setCurrentText(detail.stage or PROJECT_STAGES[0])
        project_type_combo = QComboBox()
        project_type_combo.setEditable(True)
        project_type_combo.addItems(PROJECT_TYPES)
        project_type_combo.setCurrentText(detail.project_type or PROJECT_TYPES[0])
        main_work_path_edit = QLineEdit(detail.main_work_path)
        main_work_path_edit.setReadOnly(True)
        current_focus_edit = QTextEdit(detail.current_focus)
        current_focus_edit.setFixedHeight(64)
        next_action_edit = QTextEdit(detail.next_action)
        next_action_edit.setFixedHeight(64)
        risk_edit = QTextEdit(detail.risk)
        risk_edit.setFixedHeight(64)
        default_party_label = QLabel(self._default_party_text(detail.default_party_a_info))
        default_party_label.setObjectName("SectionHint")
        default_party_label.setWordWrap(True)
        override_party_checkbox = QCheckBox("启用项目级甲方覆盖")
        party_a_brand_edit = QLineEdit(detail.party_a_info.brand if detail.party_a_source.startswith("项目覆盖") else "")
        party_a_company_edit = QLineEdit(detail.party_a_info.company if detail.party_a_source.startswith("项目覆盖") else "")
        party_a_contact_edit = QLineEdit(detail.party_a_info.contact if detail.party_a_source.startswith("项目覆盖") else "")
        party_a_phone_edit = QLineEdit(detail.party_a_info.phone if detail.party_a_source.startswith("项目覆盖") else "")
        party_a_email_edit = QLineEdit(detail.party_a_info.email if detail.party_a_source.startswith("项目覆盖") else "")
        party_a_address_edit = QTextEdit(detail.party_a_info.address if detail.party_a_source.startswith("项目覆盖") else "")
        party_a_address_edit.setFixedHeight(60)
        materials_edit = QTextEdit(detail.materials_markdown)
        materials_edit.setReadOnly(True)
        materials_edit.setFixedHeight(84)
        notes_edit = QTextEdit(detail.notes_markdown)
        notes_edit.setFixedHeight(84)

        override_party_checkbox.setChecked(detail.party_a_source.startswith("项目覆盖"))
        override_party_checkbox.toggled.connect(
            lambda checked, widgets=(
                party_a_brand_edit,
                party_a_company_edit,
                party_a_contact_edit,
                party_a_phone_edit,
                party_a_email_edit,
                party_a_address_edit,
            ): self._update_override_party_state(checked, widgets)
        )
        self._update_override_party_state(
            detail.party_a_source.startswith("项目覆盖"),
            (
                party_a_brand_edit,
                party_a_company_edit,
                party_a_contact_edit,
                party_a_phone_edit,
                party_a_email_edit,
                party_a_address_edit,
            ),
        )

        form.addRow("关联客户", brand_name_edit)
        form.addRow("项目名称", project_name_edit)
        form.addRow("所属年份", year_panel)
        form.addRow("项目状态", stage_combo)
        form.addRow("项目类型", project_type_combo)
        form.addRow("主业项目路径", main_work_path_edit)
        form.addRow("当前重点", current_focus_edit)
        form.addRow("下一步", next_action_edit)
        form.addRow("风险提醒", risk_edit)
        party_form.addRow("默认甲方信息", default_party_label)
        party_form.addRow("", override_party_checkbox)
        party_form.addRow("覆盖甲方品牌", party_a_brand_edit)
        party_form.addRow("覆盖公司/主体", party_a_company_edit)
        party_form.addRow("覆盖收件联系人", party_a_contact_edit)
        party_form.addRow("覆盖联系电话", party_a_phone_edit)
        party_form.addRow("覆盖电子邮箱", party_a_email_edit)
        party_form.addRow("覆盖通讯地址", party_a_address_edit)
        party_form.addRow("资料概览", materials_edit)
        party_form.addRow("项目沉淀", notes_edit)

        form_wrap.addWidget(basic_card, 1)
        form_wrap.addWidget(party_card, 1)

        approval_form_card = QFrame()
        approval_form_card.setObjectName("WorkspacePanel")
        approval_form = QFormLayout(approval_form_card)
        _configure_form_layout(approval_form)
        approval_hint = QLabel("新增审批记录只做轻量补录：填关键信息即可，保存时会直接追加到项目页审批记录。")
        approval_hint.setObjectName("SectionHint")
        approval_hint.setWordWrap(True)
        approval_date_edit = QLineEdit(date.today().isoformat())
        approval_type_edit = QLineEdit("其他证明&申请单")
        approval_title_edit = QLineEdit()
        approval_company_edit = QLineEdit()
        approval_status_edit = QLineEdit()
        approval_result_edit = QLineEdit()
        approval_node_edit = QLineEdit()
        approval_attachment_edit = QLineEdit()
        approval_note_edit = QTextEdit()
        approval_note_edit.setFixedHeight(64)
        _set_expanding_fields(
            (
                brand_name_edit,
                project_name_edit,
                year_panel,
                stage_combo,
                project_type_combo,
                main_work_path_edit,
                current_focus_edit,
                next_action_edit,
                risk_edit,
                default_party_label,
                party_a_brand_edit,
                party_a_company_edit,
                party_a_contact_edit,
                party_a_phone_edit,
                party_a_email_edit,
                party_a_address_edit,
                materials_edit,
                notes_edit,
                approval_hint,
                approval_date_edit,
                approval_type_edit,
                approval_title_edit,
                approval_company_edit,
                approval_status_edit,
                approval_result_edit,
                approval_node_edit,
                approval_attachment_edit,
                approval_note_edit,
            )
        )
        approval_form.addRow("", approval_hint)
        approval_form.addRow("审批日期", approval_date_edit)
        approval_form.addRow("审批类型", approval_type_edit)
        approval_form.addRow("标题/用途说明", approval_title_edit)
        approval_form.addRow("对应公司", approval_company_edit)
        approval_form.addRow("审批状态", approval_status_edit)
        approval_form.addRow("审批结果", approval_result_edit)
        approval_form.addRow("当前节点", approval_node_edit)
        approval_form.addRow("附件线索", approval_attachment_edit)
        approval_form.addRow("备注", approval_note_edit)

        action_row = QHBoxLayout()
        status_chip = QLabel(detail.stage or "待确认")
        status_chip.setObjectName("SoftBadge")
        save_button = QPushButton("保存项目补充")
        save_button.clicked.connect(self._emit_save_requested)
        collapse_button = QPushButton("收起详情")
        collapse_button.setObjectName("SecondaryActionButton")
        collapse_button.clicked.connect(
            lambda _checked=False, brand=detail.brand_customer_name, project=detail.project_name: self._toggle_project(brand, project)
        )
        bottom_hint = QLabel("滑到这里也可以快速收回当前详情")
        bottom_hint.setObjectName("SectionHint")
        action_row.addWidget(status_chip)
        action_row.addWidget(bottom_hint)
        action_row.addStretch(1)
        action_row.addWidget(save_button)
        action_row.addWidget(collapse_button)

        layout.addLayout(form_wrap)
        layout.addWidget(approval_form_card)
        layout.addLayout(action_row)

        self._active_widgets = {
            "detail": detail,
            "brand_name_edit": brand_name_edit,
            "project_name_edit": project_name_edit,
            "year_edit": year_edit,
            "year_display": year_display,
            "stage_combo": stage_combo,
            "project_type_combo": project_type_combo,
            "main_work_path_edit": main_work_path_edit,
            "current_focus_edit": current_focus_edit,
            "next_action_edit": next_action_edit,
            "risk_edit": risk_edit,
            "override_party_checkbox": override_party_checkbox,
            "party_a_brand_edit": party_a_brand_edit,
            "party_a_company_edit": party_a_company_edit,
            "party_a_contact_edit": party_a_contact_edit,
            "party_a_phone_edit": party_a_phone_edit,
            "party_a_email_edit": party_a_email_edit,
            "party_a_address_edit": party_a_address_edit,
            "materials_edit": materials_edit,
            "notes_edit": notes_edit,
            "approval_date_edit": approval_date_edit,
            "approval_type_edit": approval_type_edit,
            "approval_title_edit": approval_title_edit,
            "approval_company_edit": approval_company_edit,
            "approval_status_edit": approval_status_edit,
            "approval_result_edit": approval_result_edit,
            "approval_node_edit": approval_node_edit,
            "approval_attachment_edit": approval_attachment_edit,
            "approval_note_edit": approval_note_edit,
        }

        return section

    def _toggle_project(self, brand_customer_name: str, project_name: str) -> None:
        if self._current_project_key == (brand_customer_name, project_name):
            self._current_project_key = None
            self._current_detail = None
            self._refresh_project_cards(self._displayed_records)
            return
        self._current_project_key = (brand_customer_name, project_name)
        self._current_detail = None
        self._refresh_project_cards(self._displayed_records)
        self.project_selected.emit(brand_customer_name, project_name)

    def _emit_save_requested(self) -> None:
        if self._current_project_key is None or not self._active_widgets:
            return
        detail = self._active_widgets["detail"]
        assert isinstance(detail, ProjectDetail)

        approval_entries = list(detail.approval_entries)
        approval_title = self._line_edit_text("approval_title_edit")
        approval_company = self._line_edit_text("approval_company_edit")
        approval_status = self._line_edit_text("approval_status_edit")
        approval_note = self._text_edit_text("approval_note_edit")
        approval_attachment = self._line_edit_text("approval_attachment_edit")
        if any([approval_title, approval_company, approval_status, approval_note, approval_attachment]):
            approval_entries.insert(
                0,
                ApprovalEntry(
                    entry_date=self._line_edit_text("approval_date_edit") or date.today().isoformat(),
                    approval_type=self._line_edit_text("approval_type_edit"),
                    title_or_usage=approval_title or "审批记录",
                    counterparty=approval_company,
                    approval_status=approval_status,
                    approval_result=self._line_edit_text("approval_result_edit"),
                    current_node=self._line_edit_text("approval_node_edit"),
                    attachment_clue=approval_attachment,
                    note=approval_note,
                ),
            )

        draft = ProjectDraft(
            brand_customer_name=self._line_edit_text("brand_name_edit"),
            project_name=self._line_edit_text("project_name_edit"),
            original_project_name=self._current_project_key[1],
            stage=self._combo_text("stage_combo"),
            year=self._line_edit_text("year_edit") or self._label_text("year_display"),
            project_type=self._combo_text("project_type_combo"),
            current_focus=self._text_edit_text("current_focus_edit"),
            next_action=self._text_edit_text("next_action_edit"),
            risk=self._text_edit_text("risk_edit"),
            customer_page_link=f"[[客户/客户--{self._line_edit_text('brand_name_edit')}]]",
            main_work_path=self._line_edit_text("main_work_path_edit"),
            path_status="主业路径有效" if self._line_edit_text("main_work_path_edit") else "主业路径失效",
            party_a_source="项目覆盖甲方信息" if self._checkbox_value("override_party_checkbox") else "客户默认甲方信息",
            default_party_a_info=detail.default_party_a_info,
            party_a_info=PartyAInfo(
                brand=self._line_edit_text("party_a_brand_edit"),
                company=self._line_edit_text("party_a_company_edit"),
                contact=self._line_edit_text("party_a_contact_edit"),
                phone=self._line_edit_text("party_a_phone_edit"),
                email=self._line_edit_text("party_a_email_edit"),
                address=self._text_edit_text("party_a_address_edit"),
            ),
            override_party_a=self._checkbox_value("override_party_checkbox"),
            materials_markdown=self._text_edit_text("materials_edit"),
            notes_markdown=self._text_edit_text("notes_edit"),
            approval_entries=approval_entries,
            latest_approval_status=summarize_approval_entry(sort_approval_entries(approval_entries)[0] if approval_entries else None),
        )
        self.save_requested.emit(draft)

    def _emit_approval_import_preview_requested(self) -> None:
        self.approval_import_preview_requested.emit(self.approval_import_text_edit.toPlainText().strip())

    def _emit_approval_import_apply_requested(self) -> None:
        self.approval_import_apply_requested.emit(self.approval_import_text_edit.toPlainText().strip())

    def _emit_approval_import_ocr_requested(self, image_bytes: bytes, source_label: str) -> None:
        self.approval_import_ocr_requested.emit(image_bytes, source_label)

    def _apply_year_value(self, year_edit: QLineEdit, year_display: QLabel, year_value: str, manual: bool) -> None:
        year_edit.setText(year_value)
        year_display.setText(year_value or "待确认年份")
        year_edit.setVisible(manual)
        if manual:
            year_edit.setFocus()

    def _show_manual_year_editor(self, year_edit: QLineEdit) -> None:
        year_edit.setVisible(True)
        year_edit.setFocus()
        year_edit.selectAll()

    def _update_override_party_state(self, checked: bool, widgets: tuple[QWidget, ...]) -> None:
        for widget in widgets:
            widget.setEnabled(checked)

    def _default_party_text(self, party_a_info: PartyAInfo) -> str:
        return " / ".join(
            [
                party_a_info.contact or "待补联系人",
                party_a_info.phone or "待补电话",
                party_a_info.email or "待补邮箱",
            ]
        ) + ("\n" + (party_a_info.address or "待补通讯地址"))

    def _build_summary_panel(self, detail: ProjectDetail) -> QFrame:
        panel = QFrame()
        panel.setObjectName("WorkspacePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        header = QHBoxLayout()
        title = QLabel("详情速览")
        title.setObjectName("PanelTitle")
        status = QLabel(detail.stage or "待确认")
        status.setObjectName("SoftBadge")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(status)
        layout.addLayout(header)
        for label, value in (
            ("项目", detail.project_name),
            ("重点", detail.current_focus or "待补充"),
            ("下一步", detail.next_action or "待补充"),
            ("风险", detail.risk or "待补充"),
            ("审批", detail.latest_approval_status or "暂无审批记录"),
        ):
            layout.addWidget(self._compact_line(label, value))
        return panel

    def _build_approval_panel(self, entries: list[ApprovalEntry]) -> QFrame:
        panel = QFrame()
        panel.setObjectName("WorkspacePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(7)
        title = QLabel("审批记录")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)
        if not entries:
            empty = QLabel("暂无审批记录。")
            empty.setObjectName("SectionHint")
            layout.addWidget(empty)
            layout.addStretch(1)
            return panel
        for entry in entries[:2]:
            body = " / ".join(
                value
                for value in (
                    entry.counterparty,
                    entry.approval_status or entry.approval_result,
                    entry.current_node or entry.completed_at,
                )
                if value and value != "--"
            )
            layout.addWidget(self._compact_line(entry.entry_date, f"{entry.title_or_usage or '审批记录'} · {body or '待补充'}"))
        if len(entries) > 2:
            more = QLabel(f"还有 {len(entries) - 2} 条审批记录，已沉淀在项目页。")
            more.setObjectName("SectionHint")
            layout.addWidget(more)
        return panel

    def _compact_line(self, label: str, value: str) -> QLabel:
        widget = QLabel(f"<b>{escape(label)}：</b>{escape(value)}")
        widget.setObjectName("CustomerTileMeta")
        widget.setWordWrap(True)
        return widget

    def _detect_year(self, project_name: str, main_work_path: str) -> str:
        for candidate in (project_name, main_work_path):
            match = re.search(r"(20\d{2})", candidate or "")
            if match:
                return match.group(1)
        return ""

    def _line_edit_text(self, key: str) -> str:
        widget = self._active_widgets.get(key)
        return widget.text().strip() if isinstance(widget, QLineEdit) else ""

    def _text_edit_text(self, key: str) -> str:
        widget = self._active_widgets.get(key)
        return widget.toPlainText().strip() if isinstance(widget, QTextEdit) else ""

    def _combo_text(self, key: str) -> str:
        widget = self._active_widgets.get(key)
        return widget.currentText().strip() if isinstance(widget, QComboBox) else ""

    def _label_text(self, key: str) -> str:
        widget = self._active_widgets.get(key)
        return widget.text().strip() if isinstance(widget, QLabel) else ""

    def _checkbox_value(self, key: str) -> bool:
        widget = self._active_widgets.get(key)
        return bool(widget.isChecked()) if isinstance(widget, QCheckBox) else False


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()

class ApprovalInboxDropZone(QFrame):
    files_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ApprovalInboxDropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(74)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)

        title = QLabel("把钉钉导出的审批文件拖到这里")
        title.setObjectName("DropZoneTitle")
        hint = QLabel("支持 xlsx / csv / txt / md / pdf；拖入后自动复制到待处理并扫描预览。")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt event name.
        if self._paths_from_event(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt event name.
        if self._paths_from_event(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt event name.
        paths = self._paths_from_event(event)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.files_dropped.emit(paths)

    def _paths_from_event(self, event) -> list[Path]:
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return []
        paths: list[Path] = []
        for url in mime_data.urls():
            if url.isLocalFile():
                paths.append(Path(url.toLocalFile()))
        return paths


def _configure_form_layout(form: QFormLayout) -> None:
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(10)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)


def _set_expanding_fields(widgets: tuple[QWidget, ...]) -> None:
    for widget in widgets:
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, widget.sizePolicy().verticalPolicy())
