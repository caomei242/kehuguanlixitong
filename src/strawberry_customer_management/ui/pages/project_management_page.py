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
    QGridLayout,
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
    INTERNAL_MAIN_WORK_NAME,
    INTERNAL_PROJECT_TYPES,
    PROJECT_STAGES,
    PROJECT_TYPES,
    ApprovalEntry,
    PartyAInfo,
    ProjectDetail,
    ProjectDraft,
    ProjectProgressNode,
    ProjectRecord,
    ProjectRole,
)
from strawberry_customer_management.ui.widgets.screenshot_input_widget import ScreenshotInputWidget


ALL_BRANDS_FILTER = "全部客户"
ALL_YEARS_FILTER = "全部年份"
ALL_STAGES_FILTER = "全部状态"
ARCHIVED_PROJECT_STAGES = {"已归档"}


def _next_follow_up_date(value: object) -> str:
    return str(getattr(value, "next_follow_up_date", "") or "").strip()


def _with_next_follow_up_date(value, next_follow_up_date: str):
    object.__setattr__(value, "next_follow_up_date", next_follow_up_date)
    return value


def _sort_project_board_records(records: list[ProjectRecord], selected_stage: str = ALL_STAGES_FILTER) -> list[ProjectRecord]:
    sorted_records = sort_project_records(records)
    if selected_stage and selected_stage != ALL_STAGES_FILTER:
        return sorted_records
    active_records = [record for record in sorted_records if record.stage not in ARCHIVED_PROJECT_STAGES]
    archived_records = [record for record in sorted_records if record.stage in ARCHIVED_PROJECT_STAGES]
    return [*active_records, *archived_records]


class ProjectManagementPage(QWidget):
    project_selected = Signal(str, str)
    person_selected = Signal(str)
    sync_requested = Signal()
    save_requested = Signal(object)
    approval_import_preview_requested = Signal(str)
    approval_import_apply_requested = Signal(str)
    approval_import_ocr_requested = Signal(object, str)
    approval_inbox_scan_requested = Signal()
    approval_inbox_files_dropped = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ProjectManagementPage")
        self._records: list[ProjectRecord] = []
        self._displayed_records: list[ProjectRecord] = []
        self._current_project_key: tuple[str, str] | None = None
        self._current_detail: ProjectDetail | None = None
        self._active_widgets: dict[str, object] = {}
        self._toolbox_collapsed = True
        self._install_page_styles()

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

        banner = QLabel("")
        banner.setObjectName("OverviewBanner")
        banner.setWordWrap(True)

        import_hint = QLabel("把审批导入、OCR 识别和写入操作收在这里，不再抢占项目看板首屏。")
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

        list_panel = QFrame()
        list_panel.setObjectName("WorkspacePanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(10)
        list_header = QHBoxLayout()
        list_title = QLabel("项目看板")
        list_title.setObjectName("SectionTitle")
        self.project_count_label = QLabel("当前 0 个项目")
        self.project_count_label.setObjectName("SoftBadge")
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        list_header.addWidget(self.project_count_label)
        self.project_cards_layout = QVBoxLayout()
        self.project_cards_layout.setSpacing(14)
        list_layout.addLayout(list_header)
        list_layout.addLayout(self.project_cards_layout)

        self.toolbox_toggle_button = QPushButton("展开审批导入")
        self.toolbox_toggle_button.setObjectName("SecondaryActionButton")
        self.toolbox_toggle_button.clicked.connect(self._toggle_toolbox)
        self.toolbox_hint_label = QLabel("审批导入、OCR 和归属写入都收在这里。")
        self.toolbox_hint_label.setObjectName("SectionHint")
        self.toolbox_hint_label.setWordWrap(True)
        self.toolbox_content = QWidget()
        toolbox_content_layout = QVBoxLayout(self.toolbox_content)
        toolbox_content_layout.setContentsMargins(0, 0, 0, 0)
        toolbox_content_layout.setSpacing(8)
        toolbox_actions = QHBoxLayout()
        toolbox_actions.setSpacing(8)
        toolbox_actions.addWidget(self.approval_inbox_scan_button)
        toolbox_actions.addWidget(self.approval_import_preview_button)
        toolbox_actions.addWidget(self.approval_import_apply_button)
        toolbox_actions.addStretch(1)
        toolbox_content_layout.addLayout(toolbox_actions)
        toolbox_content_layout.addWidget(import_hint)
        toolbox_content_layout.addWidget(self.approval_inbox_path_label)
        toolbox_content_layout.addWidget(self.approval_inbox_drop_zone)
        toolbox_content_layout.addWidget(self.approval_import_text_edit)
        toolbox_content_layout.addWidget(self.approval_import_screenshot_widget)
        toolbox_content_layout.addWidget(self.approval_import_preview_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")
        self.approval_toolbox_panel = self._build_approval_toolbox_panel()

        root.addWidget(topbar)
        root.addWidget(banner)
        root.addWidget(list_panel, 1)
        root.addWidget(self.approval_toolbox_panel)
        root.addWidget(self.status_label)
        root.addStretch(1)
        self._set_toolbox_collapsed(True)

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
        records = _sort_project_board_records(records, selected_stage)
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
        self._refresh_project_cards(records)
        if self._current_project_key:
            self.project_selected.emit(*self._current_project_key)

    def _refresh_project_cards(self, records: list[ProjectRecord]) -> None:
        _clear_layout(self.project_cards_layout)
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
        detail = None
        if selected and self._current_detail and (
            self._current_detail.brand_customer_name,
            self._current_detail.project_name,
        ) == self._current_project_key:
            detail = self._current_detail

        shell = QFrame()
        shell.setObjectName("ProjectBoardCard")
        shell.setProperty("selected", selected)
        shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(18, 18, 18, 18)
        shell_layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel(record.project_name)
        title.setObjectName("CustomerTileName")
        meta = QLabel(
            f"{record.brand_customer_name} · {record.year or '待确认年份'} · "
            f"{record.project_type or '待补类型'} · 更新 {record.updated_at or '待同步'}"
        )
        meta.setObjectName("BoardMetaLabel")
        meta.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(meta)

        right_box = QVBoxLayout()
        right_box.setSpacing(6)
        tag = QLabel(record.stage or "待确认")
        tag.setObjectName("BoardStageBadge")
        toggle_button = QPushButton("收起详情" if selected else "查看项目")
        toggle_button.setObjectName("InlineActionButton")
        toggle_button.clicked.connect(
            lambda _checked=False, brand=record.brand_customer_name, project=record.project_name: self._toggle_project(brand, project)
        )
        right_box.addWidget(tag, 0, Qt.AlignmentFlag.AlignRight)
        right_box.addWidget(toggle_button, 0, Qt.AlignmentFlag.AlignRight)

        header.addLayout(title_box, 1)
        header.addLayout(right_box)
        shell_layout.addLayout(header)
        shell_layout.addWidget(self._build_progress_track(self._workflow_nodes_for_record(record, detail)))

        summary_label = QLabel(detail.current_focus if detail else record.current_focus or "待补项目当前重点")
        summary_label.setObjectName("BoardFlowTitle")
        summary_label.setWordWrap(True)
        shell_layout.addWidget(summary_label)

        meta_label = QLabel(
            " · ".join(
                part
                for part in (
                    self._role_summary_text(detail, record.brand_customer_name),
                    self._next_step_summary(detail, record),
                    f"最新审批：{self._latest_approval_summary(detail) if detail else (record.latest_approval_status or '暂无审批记录')}",
                )
                if part
            )
        )
        meta_label.setObjectName("BoardBodyLabel")
        meta_label.setWordWrap(True)
        shell_layout.addWidget(meta_label)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        footer.addWidget(self._build_inline_pill(f"跟进：{_next_follow_up_date(detail if detail else record) or '待补日期'}"))
        footer.addWidget(self._build_inline_pill(self._dida_diary_pill_text(detail if detail else record)))
        footer.addWidget(self._build_inline_pill(f"当前负责人：{self._primary_owner_text(detail, record.brand_customer_name)}"))
        footer.addStretch(1)
        shell_layout.addLayout(footer)

        if selected:
            if detail:
                shell_layout.addWidget(self._build_detail_drawer(detail))
            else:
                loading_label = QLabel("项目详情加载中...")
                loading_label.setObjectName("SectionHint")
                shell_layout.addWidget(loading_label)

        return shell

    def _build_detail_drawer(self, detail: ProjectDetail) -> QFrame:
        section = QFrame()
        section.setObjectName("ProjectBoardExpanded")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        overview_row = QHBoxLayout()
        overview_row.setSpacing(14)
        overview_row.addWidget(self._build_case_overview_panel(detail), 3)
        overview_row.addWidget(self._build_roles_panel(detail), 2)
        layout.addLayout(overview_row)

        current_focus_edit = QTextEdit(detail.current_focus)
        current_focus_edit.setFixedHeight(64)
        next_action_edit = QTextEdit(detail.next_action)
        next_action_edit.setFixedHeight(64)
        next_follow_up_date_edit = QLineEdit(_next_follow_up_date(detail))
        risk_edit = QTextEdit(detail.risk)
        risk_edit.setFixedHeight(64)
        participant_roles_markdown_edit = QTextEdit(detail.participant_roles_markdown)
        participant_roles_markdown_edit.setFixedHeight(72)
        progress_markdown_edit = QTextEdit(detail.progress_markdown)
        progress_markdown_edit.setFixedHeight(72)
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

        board_row = QHBoxLayout()
        board_row.setSpacing(14)
        board_row.addWidget(self._build_flow_panel(detail), 3)
        board_row.addWidget(
            self._build_quick_supplement_panel(
                detail,
                current_focus_edit,
                next_action_edit,
                next_follow_up_date_edit,
                risk_edit,
                participant_roles_markdown_edit,
                progress_markdown_edit,
                approval_date_edit,
                approval_type_edit,
                approval_title_edit,
                approval_company_edit,
                approval_status_edit,
                approval_result_edit,
                approval_node_edit,
                approval_attachment_edit,
                approval_note_edit,
            ),
            2,
        )
        layout.addLayout(board_row)

        form_wrap = QHBoxLayout()
        form_wrap.setSpacing(14)
        basic_card = QFrame()
        basic_card.setObjectName("BoardPanel")
        basic_layout = QVBoxLayout(basic_card)
        basic_layout.setContentsMargins(14, 14, 14, 14)
        basic_layout.setSpacing(10)
        basic_title = QLabel("项目底稿")
        basic_title.setObjectName("BoardPanelTitle")
        basic_subtitle = QLabel("保留项目名称、年份、状态和路径这些底层字段。")
        basic_subtitle.setObjectName("BoardPanelSubtitle")
        basic_subtitle.setWordWrap(True)
        form = QFormLayout()
        _configure_form_layout(form)
        basic_layout.addWidget(basic_title)
        basic_layout.addWidget(basic_subtitle)
        basic_layout.addLayout(form)

        party_card = QFrame()
        party_card.setObjectName("BoardPanel")
        party_layout = QVBoxLayout(party_card)
        party_layout.setContentsMargins(14, 14, 14, 14)
        party_layout.setSpacing(10)
        party_title = QLabel("甲方与资料")
        party_title.setObjectName("BoardPanelTitle")
        party_subtitle = QLabel("这里继续维护对口信息、资料概览和项目沉淀。")
        party_subtitle.setObjectName("BoardPanelSubtitle")
        party_subtitle.setWordWrap(True)
        party_form = QFormLayout()
        _configure_form_layout(party_form)
        party_layout.addWidget(party_title)
        party_layout.addWidget(party_subtitle)
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
                next_follow_up_date_edit,
                risk_edit,
                participant_roles_markdown_edit,
                progress_markdown_edit,
                default_party_label,
                party_a_brand_edit,
                party_a_company_edit,
                party_a_contact_edit,
                party_a_phone_edit,
                party_a_email_edit,
                party_a_address_edit,
                materials_edit,
                notes_edit,
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
        bottom_hint = QLabel("")
        bottom_hint.setObjectName("SectionHint")
        action_row.addWidget(status_chip)
        action_row.addWidget(bottom_hint)
        action_row.addStretch(1)
        action_row.addWidget(save_button)
        action_row.addWidget(collapse_button)

        layout.addLayout(form_wrap)
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
            "next_follow_up_date_edit": next_follow_up_date_edit,
            "risk_edit": risk_edit,
            "participant_roles_markdown_edit": participant_roles_markdown_edit,
            "progress_markdown_edit": progress_markdown_edit,
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

        draft = _with_next_follow_up_date(
            ProjectDraft(
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
                participant_roles=detail.participant_roles,
                participant_roles_markdown=self._text_edit_text("participant_roles_markdown_edit"),
                progress_nodes=detail.progress_nodes,
                progress_markdown=self._text_edit_text("progress_markdown_edit"),
                materials_markdown=self._text_edit_text("materials_edit"),
                notes_markdown=self._text_edit_text("notes_edit"),
                approval_entries=approval_entries,
                latest_approval_status=summarize_approval_entry(sort_approval_entries(approval_entries)[0] if approval_entries else None),
            ),
            self._line_edit_text("next_follow_up_date_edit"),
        )
        self.save_requested.emit(draft)

    def _build_approval_toolbox_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("审批导入工具")
        title.setObjectName("BoardPanelTitle")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.toolbox_toggle_button)
        layout.addLayout(header)
        layout.addWidget(self.toolbox_hint_label)
        layout.addWidget(self.toolbox_content)
        return panel

    def _toggle_toolbox(self) -> None:
        self._set_toolbox_collapsed(not self.toolbox_content.isVisible())

    def _set_toolbox_collapsed(self, collapsed: bool) -> None:
        self._toolbox_collapsed = collapsed
        self.toolbox_content.setVisible(not collapsed)
        self.toolbox_toggle_button.setText("展开审批导入" if collapsed else "收起审批导入")
        self.toolbox_hint_label.setText(
            "审批导入、OCR 和归属写入都收在这里。"
            if collapsed
            else "先扫描导入箱或粘贴审批文字，再预览归属并写入当前项目。"
        )

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

    def _install_page_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#ProjectManagementPage QFrame#ProjectBoardCard {
                background: rgba(255, 255, 255, 0.98);
                border: 1px solid #dbe4f2;
                border-radius: 24px;
            }
            QWidget#ProjectManagementPage QFrame#ProjectBoardCard[selected="true"] {
                background: #fcfdff;
                border: 1px solid #cfdcf2;
            }
            QWidget#ProjectManagementPage QFrame#ProjectBoardExpanded {
                background: transparent;
                border: none;
            }
            QWidget#ProjectManagementPage QFrame#BoardPanel,
            QWidget#ProjectManagementPage QFrame#BoardMiniPanel,
            QWidget#ProjectManagementPage QFrame#BoardMetricCard,
            QWidget#ProjectManagementPage QFrame#BoardRoleItem,
            QWidget#ProjectManagementPage QFrame#BoardFlowNode,
            QWidget#ProjectManagementPage QFrame#BoardInlinePill {
                background: #ffffff;
                border: 1px solid #e0e8f5;
                border-radius: 18px;
            }
            QWidget#ProjectManagementPage QFrame#BoardMiniPanel {
                background: #f9fbff;
            }
            QWidget#ProjectManagementPage QLabel#BoardPanelTitle {
                color: #1f2d44;
                font-size: 16px;
                font-weight: 700;
            }
            QWidget#ProjectManagementPage QLabel#BoardPanelSubtitle,
            QWidget#ProjectManagementPage QLabel#BoardMetaLabel,
            QWidget#ProjectManagementPage QLabel#BoardBodyLabel {
                color: #6f7d95;
                font-size: 12px;
                line-height: 1.5;
            }
            QWidget#ProjectManagementPage QLabel#BoardHeroEyebrow {
                color: #d15572;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }
            QWidget#ProjectManagementPage QLabel#BoardHeroTitle {
                color: #18243a;
                font-size: 24px;
                font-weight: 800;
            }
            QWidget#ProjectManagementPage QLabel#BoardMetricValue {
                color: #1f2d44;
                font-size: 22px;
                font-weight: 800;
            }
            QWidget#ProjectManagementPage QLabel#BoardMetricLabel,
            QWidget#ProjectManagementPage QLabel#BoardFlowStatus,
            QWidget#ProjectManagementPage QLabel#BoardMiniTitle,
            QWidget#ProjectManagementPage QLabel#BoardRoleType,
            QWidget#ProjectManagementPage QLabel#BoardPillLabel {
                color: #7a879d;
                font-size: 11px;
                font-weight: 700;
            }
            QWidget#ProjectManagementPage QLabel#BoardFlowTitle,
            QWidget#ProjectManagementPage QLabel#BoardRoleName {
                color: #1f2d44;
                font-size: 14px;
                font-weight: 700;
            }
            QWidget#ProjectManagementPage QLabel#BoardStageBadge {
                padding: 6px 10px;
                color: #416ce3;
                background: #eef4ff;
                border: 1px solid #d8e4ff;
                border-radius: 999px;
                font-size: 11px;
                font-weight: 700;
            }
            QWidget#ProjectManagementPage QFrame#BoardTrackStep {
                min-height: 8px;
                max-height: 8px;
                border-radius: 4px;
                border: 1px solid #dce5f2;
                background: #eef3f9;
            }
            QWidget#ProjectManagementPage QFrame#BoardTrackStep[status="done"] {
                border-color: #b9e8d6;
                background: #25aa78;
            }
            QWidget#ProjectManagementPage QFrame#BoardTrackStep[status="active"] {
                border-color: #cddcff;
                background: #4a7cff;
            }
            QWidget#ProjectManagementPage QFrame#BoardTrackStep[status="risk"] {
                border-color: #ffd5db;
                background: #de5a6d;
            }
            QWidget#ProjectManagementPage QLabel#BoardPlaceholderLabel {
                color: #8a5a2c;
                background: #fff6ec;
                border: 1px solid #f2dcc0;
                border-radius: 12px;
                padding: 8px 10px;
            }
            """
        )

    def _default_party_text(self, party_a_info: PartyAInfo) -> str:
        return " / ".join(
            [
                party_a_info.contact or "待补联系人",
                party_a_info.phone or "待补电话",
                party_a_info.email or "待补邮箱",
            ]
        ) + ("\n" + (party_a_info.address or "待补通讯地址"))

    def _build_case_overview_panel(self, detail: ProjectDetail) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        eyebrow = QLabel("Case 概览")
        eyebrow.setObjectName("BoardHeroEyebrow")
        title = QLabel(detail.project_name)
        title.setObjectName("BoardHeroTitle")
        title.setWordWrap(True)
        role_count = len(detail.participant_roles) or len(self._role_rows(detail))
        workflow_nodes = self._workflow_nodes_for_detail(detail)
        done_count = sum(1 for node in workflow_nodes if node["status"] == "done")
        active_count = sum(1 for node in workflow_nodes if node["status"] in {"active", "risk"})
        pending_count = sum(1 for node in workflow_nodes if node["status"] == "todo")
        progress = int(((done_count + active_count * 0.45) / max(len(workflow_nodes), 1)) * 100)
        blockers = sum(1 for node in workflow_nodes if node["status"] == "risk")
        body = QLabel(
            f"{detail.brand_customer_name} 当前有 {role_count} 个有效角色、{len(workflow_nodes)} 个流程节点。"
            "先扫当前阶段、关键卡点和下一步，再决定要不要往下补底稿。"
        )
        body.setObjectName("BoardBodyLabel")
        body.setWordWrap(True)
        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(body)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(10)
        metrics.setVerticalSpacing(10)
        metrics.addWidget(self._build_metric_card("整体进度", f"{progress}%"), 0, 0)
        metrics.addWidget(self._build_metric_card("当前阶段", detail.stage or "待确认"), 0, 1)
        metrics.addWidget(self._build_metric_card("待开始节点", str(pending_count)), 1, 0)
        metrics.addWidget(self._build_metric_card("当前卡点", str(blockers or (1 if detail.risk.strip() else 0))), 1, 1)
        layout.addLayout(metrics)

        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        info_row.addWidget(self._build_inline_pill(f"最新审批：{self._latest_approval_summary(detail)}"))
        info_row.addWidget(self._build_inline_pill(f"下次跟进：{_next_follow_up_date(detail) or '待补'}"))
        info_row.addWidget(self._build_inline_pill(self._dida_diary_pill_text(detail)))
        info_row.addStretch(1)
        layout.addLayout(info_row)
        return panel

    def _build_roles_panel(self, detail: ProjectDetail) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title = QLabel("参与人")
        title.setObjectName("BoardPanelTitle")
        subtitle = QLabel("项目里只放所属方、关系和人名；人的细节沉淀到关系人库。")
        subtitle.setObjectName("BoardPanelSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        for role_title, role_name, role_note in self._role_rows(detail):
            item = QFrame()
            item.setObjectName("BoardRoleItem")
            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(12, 12, 12, 12)
            item_layout.setSpacing(8)
            role_type = QLabel(role_title)
            role_type.setObjectName("BoardRoleType")
            role_name_label = QPushButton(role_name)
            role_name_label.setObjectName("InlineActionButton")
            role_name_label.clicked.connect(lambda _checked=False, name=role_name: self.person_selected.emit(name))
            item_layout.addWidget(role_type)
            item_layout.addWidget(role_name_label, 1)
            if role_note:
                role_note_label = QLabel(role_note)
                role_note_label.setObjectName("BoardMetaLabel")
                role_note_label.setWordWrap(True)
                item_layout.addWidget(role_note_label, 2)
            layout.addWidget(item)
        extra_role_note = self._first_meaningful_line(detail.participant_roles_markdown)
        if extra_role_note:
            extra_label = QLabel(f"补充留痕：{extra_role_note}")
            extra_label.setObjectName("BoardMetaLabel")
            extra_label.setWordWrap(True)
            layout.addWidget(extra_label)
        layout.addStretch(1)
        return panel

    def _build_flow_panel(self, detail: ProjectDetail) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QLabel("流程节点")
        title.setObjectName("BoardPanelTitle")
        subtitle = QLabel("把 Case 流程页落回项目管理里，先看节点状态，再决定要不要改底稿。")
        subtitle.setObjectName("BoardPanelSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        workflow_nodes = self._workflow_nodes_for_detail(detail)
        layout.addWidget(self._build_progress_track(workflow_nodes))

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, node in enumerate(workflow_nodes):
            card = QFrame()
            card.setObjectName("BoardFlowNode")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(4)
            status = QLabel(node["status_label"])
            status.setObjectName("BoardFlowStatus")
            step_title = QLabel(node["title"])
            step_title.setObjectName("BoardFlowTitle")
            summary = QLabel(node["summary"])
            summary.setObjectName("BoardBodyLabel")
            summary.setWordWrap(True)
            card_layout.addWidget(status)
            card_layout.addWidget(step_title)
            card_layout.addWidget(summary)
            grid.addWidget(card, index // 2, index % 2)
        layout.addLayout(grid)
        extra_progress_note = self._first_meaningful_line(detail.progress_markdown)
        if extra_progress_note:
            extra_label = QLabel(f"补充留痕：{extra_progress_note}")
            extra_label.setObjectName("BoardMetaLabel")
            extra_label.setWordWrap(True)
            layout.addWidget(extra_label)
        return panel

    def _build_quick_supplement_panel(
        self,
        detail: ProjectDetail,
        current_focus_edit: QTextEdit,
        next_action_edit: QTextEdit,
        next_follow_up_date_edit: QLineEdit,
        risk_edit: QTextEdit,
        participant_roles_markdown_edit: QTextEdit,
        progress_markdown_edit: QTextEdit,
        approval_date_edit: QLineEdit,
        approval_type_edit: QLineEdit,
        approval_title_edit: QLineEdit,
        approval_company_edit: QLineEdit,
        approval_status_edit: QLineEdit,
        approval_result_edit: QLineEdit,
        approval_node_edit: QLineEdit,
        approval_attachment_edit: QLineEdit,
        approval_note_edit: QTextEdit,
    ) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title = QLabel("快速补充")
        title.setObjectName("BoardPanelTitle")
        subtitle = QLabel("先补今天最需要推进的重点、下一步和审批快照，完整资料仍然保留在下面。")
        subtitle.setObjectName("BoardPanelSubtitle")
        subtitle.setWordWrap(True)
        placeholder = QLabel("后续这里会继续接进展 OCR、角色候选和流程候选，当前先保留人工补录入口。")
        placeholder.setObjectName("BoardPlaceholderLabel")
        placeholder.setWordWrap(True)
        form = QFormLayout()
        _configure_form_layout(form)
        form.addRow("当前重点", current_focus_edit)
        form.addRow("下一步", next_action_edit)
        form.addRow("下次跟进日期", next_follow_up_date_edit)
        form.addRow("风险提醒", risk_edit)
        form.addRow("角色补充", participant_roles_markdown_edit)
        form.addRow("进度补充", progress_markdown_edit)
        form.addRow("审批日期", approval_date_edit)
        form.addRow("审批类型", approval_type_edit)
        form.addRow("标题/用途说明", approval_title_edit)
        form.addRow("对应公司", approval_company_edit)
        form.addRow("审批状态", approval_status_edit)
        form.addRow("审批结果", approval_result_edit)
        form.addRow("当前节点", approval_node_edit)
        form.addRow("附件线索", approval_attachment_edit)
        form.addRow("备注", approval_note_edit)

        latest = QLabel(f"最近审批：{self._latest_approval_summary(detail)}")
        latest.setObjectName("BoardMetaLabel")
        latest.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(placeholder)
        layout.addWidget(latest)
        layout.addLayout(form)
        return panel

    def _build_metric_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("BoardMetricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setObjectName("BoardMetricLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("BoardMetricValue")
        value_widget.setWordWrap(True)
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        return card

    def _build_inline_pill(self, text: str) -> QFrame:
        pill = QFrame()
        pill.setObjectName("BoardInlinePill")
        layout = QHBoxLayout(pill)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(0)
        label = QLabel(text)
        label.setObjectName("BoardPillLabel")
        label.setWordWrap(True)
        layout.addWidget(label)
        return pill

    def _build_mini_panel(self, title: str, body: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardMiniPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("BoardMiniTitle")
        body_label = QLabel(body)
        body_label.setObjectName("BoardBodyLabel")
        body_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        return panel

    def _build_progress_track(self, nodes: list[dict[str, str]]) -> QFrame:
        panel = QFrame()
        panel.setObjectName("BoardPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        for node in nodes:
            step = QFrame()
            step.setObjectName("BoardTrackStep")
            step.setProperty("status", node["status"])
            step.setToolTip(f"{node['title']} · {node['status_label']}")
            step.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            layout.addWidget(step)
        return panel

    def _workflow_nodes_for_record(self, record: ProjectRecord, detail: ProjectDetail | None = None) -> list[dict[str, str]]:
        if detail is not None:
            return self._workflow_nodes_for_detail(detail)
        proxy_detail = ProjectDetail(
            brand_customer_name=record.brand_customer_name,
            project_name=record.project_name,
            stage=record.stage,
            year=record.year,
            project_type=record.project_type,
            current_focus=record.current_focus,
            next_action=record.next_action,
            main_work_path=record.main_work_path,
            path_status=record.path_status,
            latest_approval_status=record.latest_approval_status,
        )
        object.__setattr__(proxy_detail, "next_follow_up_date", _next_follow_up_date(record))
        return self._workflow_nodes_for_detail(proxy_detail)

    def _workflow_nodes_for_detail(self, detail: ProjectDetail) -> list[dict[str, str]]:
        structured_nodes = self._structured_progress_nodes(detail.progress_nodes)
        if structured_nodes:
            return structured_nodes
        approval_text = detail.latest_approval_status or ""
        workflow_kind = self._workflow_kind_for_detail(detail)
        progress_text = " ".join([detail.current_focus, detail.next_action, detail.risk, approval_text, detail.project_type])
        active_index = self._active_workflow_index(workflow_kind, detail, progress_text)

        steps = self._workflow_steps_for_detail(workflow_kind, detail, approval_text)

        nodes: list[dict[str, str]] = []
        for index, (title, summary) in enumerate(steps):
            if detail.stage == "已归档":
                status = "done"
            elif index < active_index:
                status = "done"
            elif index == active_index:
                status = "risk" if detail.risk.strip() or detail.stage == "暂缓" else "active"
            else:
                status = "todo"
            nodes.append(
                {
                    "title": title,
                    "summary": summary,
                    "status": status,
                    "status_label": {
                        "done": "已完成",
                        "active": "当前推进",
                        "risk": "卡点关注",
                        "todo": "待开始",
                    }[status],
                }
            )
        return nodes

    def _workflow_kind_for_detail(self, detail: ProjectDetail) -> str:
        project_type = detail.project_type or ""
        text = " ".join([detail.brand_customer_name, detail.project_name, project_type])
        if detail.brand_customer_name == INTERNAL_MAIN_WORK_NAME or project_type in INTERNAL_PROJECT_TYPES:
            return "internal"
        if "店群" in project_type or "店群" in text:
            return "shop_group"
        if "KA" in project_type or "KA" in text:
            return "ka"
        if "博主" in project_type or "达人" in project_type:
            return "blogger"
        if project_type == "合同项目" or "合同" in detail.project_name:
            return "contract"
        return "default"

    def _active_workflow_index(self, workflow_kind: str, detail: ProjectDetail, progress_text: str) -> int:
        if detail.stage == "已归档":
            return 5
        if detail.stage == "待确认":
            return 0
        if workflow_kind == "contract":
            if any(keyword in progress_text for keyword in ("审批", "合同", "盖章", "法务")):
                return 1
            if any(keyword in progress_text for keyword in ("样品", "素材", "资料", "寄送", "确认单")):
                return 2
            if any(keyword in progress_text for keyword in ("验收", "交付", "回执", "收货")):
                return 4
            return 3
        if workflow_kind == "internal":
            if any(keyword in progress_text for keyword in ("方案", "边界", "确认", "梳理")):
                return 1
            if any(keyword in progress_text for keyword in ("测试", "验证", "验收", "bug", "Bug")):
                return 3
            if any(keyword in progress_text for keyword in ("复盘", "沉淀", "上线", "归档")):
                return 4
            return 2
        if workflow_kind == "ka":
            if any(keyword in progress_text for keyword in ("试用", "演示", "方案")):
                return 1
            if any(keyword in progress_text for keyword in ("配置", "开通", "账号", "权限")):
                return 2
            if any(keyword in progress_text for keyword in ("增购", "续费", "转化")):
                return 4
            return 3
        if workflow_kind == "shop_group":
            if any(keyword in progress_text for keyword in ("点数", "折扣", "报价", "方案")):
                return 1
            if any(keyword in progress_text for keyword in ("批量", "开通", "店铺")):
                return 2
            if any(keyword in progress_text for keyword in ("续费", "增购")):
                return 4
            return 3
        if workflow_kind == "blogger":
            if any(keyword in progress_text for keyword in ("报价", "坑位")):
                return 1
            if any(keyword in progress_text for keyword in ("排期", "脚本", "内容")):
                return 2
            if any(keyword in progress_text for keyword in ("发布", "反馈")):
                return 3
            if any(keyword in progress_text for keyword in ("结算", "复盘")):
                return 4
            return 2
        if any(keyword in progress_text for keyword in ("验收", "交付", "反馈", "收货")):
            return 4
        if any(keyword in progress_text for keyword in ("样品", "素材", "资料", "寄送", "确认单")):
            return 2
        return 3

    def _workflow_steps_for_detail(self, workflow_kind: str, detail: ProjectDetail, approval_text: str) -> list[tuple[str, str]]:
        path_line = f"年份 {detail.year or '待确认'} · {(detail.path_status or '路径待确认')}"
        materials_line = self._first_meaningful_line(detail.materials_markdown)
        notes_line = self._first_meaningful_line(detail.notes_markdown)
        current_line = self._first_meaningful_line(detail.current_focus) or "当前推进事项待补"
        next_line = self._first_meaningful_line(detail.next_action) or "下一步动作待补"
        if workflow_kind == "internal":
            return [
                ("事项建档", path_line),
                ("方案确认", current_line),
                ("执行推进", current_line),
                ("测试验证", next_line),
                ("复盘沉淀", notes_line or "阶段结论和可复用规则待沉淀"),
                ("归档", notes_line or "收尾归档待确认"),
            ]
        if workflow_kind == "ka":
            return [
                ("需求确认", current_line),
                ("方案试用", next_line),
                ("配置开通", materials_line or detail.path_status or "账号、权限和配置待补"),
                ("使用跟进", current_line),
                ("增购转化", next_line),
                ("归档", notes_line or "客户运营沉淀待补"),
            ]
        if workflow_kind == "shop_group":
            return [
                ("需求确认", current_line),
                ("点数方案", next_line),
                ("批量开通", materials_line or "店铺、账号和点数开通待补"),
                ("使用反馈", current_line),
                ("续费增购", next_line),
                ("归档", notes_line or "店群客户沉淀待补"),
            ]
        if workflow_kind == "blogger":
            return [
                ("合作意向", current_line),
                ("报价坑位", next_line),
                ("内容排期", materials_line or "脚本、素材和发布时间待补"),
                ("发布反馈", current_line),
                ("结算复盘", notes_line or "效果、结算和复盘待补"),
                ("归档", notes_line or "推广合作沉淀待补"),
            ]
        if workflow_kind == "contract":
            return [
                ("Case 建档", path_line),
                ("审批合同", approval_text or "审批状态和合同进展待补"),
                ("资料筹备", materials_line or "素材、样品和确认单待补"),
                ("执行推进", current_line),
                ("验收交付", next_line),
                ("归档沉淀", notes_line or "项目沉淀和归档状态待补"),
            ]
        return [
            ("项目建档", path_line),
            ("需求确认", current_line),
            ("资料筹备", materials_line or "资料和协作信息待补"),
            ("执行推进", current_line),
            ("交付反馈", next_line),
            ("归档沉淀", notes_line or "项目沉淀和归档状态待补"),
        ]

    def _role_rows(self, detail: ProjectDetail) -> list[tuple[str, str, str]]:
        if detail.participant_roles:
            rows: list[tuple[str, str, str]] = []
            for role in detail.participant_roles:
                rows.append(
                    (
                        " / ".join(part for part in (role.display_side, role.display_relation) if part) or "参与人",
                        role.name or "待补姓名",
                        "",
                    )
                )
            return rows
        workflow_kind = self._workflow_kind_for_detail(detail)
        party = detail.party_a_info.resolved_with(detail.default_party_a_info)
        latest_entry = sort_approval_entries(detail.approval_entries)[0] if detail.approval_entries else None
        if workflow_kind == "internal":
            return [
                ("内部负责人", detail.brand_customer_name if detail.brand_customer_name != INTERNAL_MAIN_WORK_NAME else "草莓", "主业事项默认先由自己推进。"),
                ("协作人", "待补", "需要外部协作时再补人名。"),
                ("当前推进", self._first_meaningful_line(detail.current_focus) or "待补推进重点", self._first_meaningful_line(detail.next_action) or "下一步待补。"),
                ("资料沉淀", detail.path_status or "主业路径待确认", self._first_meaningful_line(detail.materials_markdown) or "资料入口待补。"),
            ]
        if workflow_kind in {"ka", "shop_group"}:
            return [
                ("客户对接", party.contact or detail.brand_customer_name, party.company or "客户联系人待补。"),
                ("开通配置", self._first_meaningful_line(detail.materials_markdown) or "账号/软件配置待补", detail.path_status or "配置入口待补。"),
                ("使用反馈", self._first_meaningful_line(detail.current_focus) or "使用反馈待补", self._first_meaningful_line(detail.next_action) or "下一步待补。"),
                ("后续转化", self._first_meaningful_line(detail.next_action) or "续费/增购判断待补", "不默认走合同审批。"),
            ]
        if workflow_kind == "blogger":
            return [
                ("博主对接", party.contact or detail.brand_customer_name, party.company or "博主账号信息待补。"),
                ("合作排期", self._first_meaningful_line(detail.next_action) or "内容排期待补", "坑位、报价和发布时间待确认。"),
                ("内容反馈", self._first_meaningful_line(detail.current_focus) or "内容反馈待补", "发布效果和评论反馈待沉淀。"),
                ("结算复盘", self._first_meaningful_line(detail.notes_markdown) or "结算复盘待补", "合作结束后再收档。"),
            ]
        if workflow_kind != "contract":
            return [
                ("项目对口", party.contact or detail.brand_customer_name, party.company or "对接人待补。"),
                ("当前推进", self._first_meaningful_line(detail.current_focus) or "待补推进重点", self._first_meaningful_line(detail.next_action) or "下一步待补。"),
                ("资料协同", detail.path_status or "主业路径待确认", self._first_meaningful_line(detail.materials_markdown) or "资料入口待补。"),
                ("下次动作", getattr(detail, "next_follow_up_date", "") or "待排期", self._first_meaningful_line(detail.next_action) or "下一步待补。"),
            ]
        return [
            (
                "品牌对口",
                party.contact or party.company or detail.brand_customer_name,
                party.company or party.email or "甲方联系人和主体信息待补充完整。",
            ),
            (
                "审批链路",
                latest_entry.current_node if latest_entry and latest_entry.current_node else detail.latest_approval_status or "待补审批节点",
                latest_entry.title_or_usage if latest_entry and latest_entry.title_or_usage else "最近审批事项还没有补齐标题。",
            ),
            (
                "内部推进",
                self._first_meaningful_line(detail.current_focus) or "待补内部 Owner / 执行跟进人",
                self._first_meaningful_line(detail.next_action) or "下一步还没有拆到负责人。",
            ),
            (
                "资料协同",
                detail.path_status or "主业路径待确认",
                self._first_meaningful_line(detail.materials_markdown) or "资料、回执和收档说明待补。",
            ),
        ]

    def _role_summary_text(self, detail: ProjectDetail | None, brand_customer_name: str) -> str:
        if detail is None:
            return f"{brand_customer_name} 对口和当前推进待补齐。"
        role_rows = self._role_rows(detail)
        if not role_rows:
            return f"{brand_customer_name} 对口和当前推进待补齐。"
        if len(role_rows) == 1:
            first_role = role_rows[0]
            return f"{first_role[0]}：{first_role[1]}。"
        first_role = role_rows[0]
        second_role = role_rows[1]
        return f"{first_role[0]}：{first_role[1]}；{second_role[0]}：{second_role[1]}。"

    def _primary_owner_text(self, detail: ProjectDetail | None, brand_customer_name: str) -> str:
        if detail is not None:
            if detail.participant_roles:
                return detail.participant_roles[0].name or detail.participant_roles[0].role or brand_customer_name
            rows = self._role_rows(detail)
            if rows:
                return rows[0][1]
        return brand_customer_name or "待补负责人"

    def _latest_approval_summary(self, detail: ProjectDetail) -> str:
        if detail.latest_approval_status.strip():
            return detail.latest_approval_status
        sorted_entries = sort_approval_entries(detail.approval_entries)
        if sorted_entries:
            return summarize_approval_entry(sorted_entries[0])
        return "暂无审批记录"

    def _dida_diary_pill_text(self, project: ProjectRecord | ProjectDetail) -> str:
        entries = list(getattr(project, "dida_diary_entries", []) or [])
        if entries:
            latest = sorted(entries, key=lambda entry: getattr(entry, "scheduled_at", "") or "", reverse=True)[0]
            summary = " ".join(
                part
                for part in (
                    getattr(latest, "scheduled_at", ""),
                    getattr(latest, "title", "") or getattr(latest, "note", ""),
                )
                if part
            ).strip()
            return f"滴答：已关联 {summary}" if summary else "滴答：已关联"
        status = str(getattr(project, "dida_diary_status", "") or "").strip()
        latest_text = str(getattr(project, "latest_dida_diary", "") or "").strip()
        if status == "已关联滴答":
            return f"滴答：已关联 {latest_text}" if latest_text else "滴答：已关联"
        if status == "待建滴答" or self._has_schedulable_follow_up(project):
            return "滴答：待建"
        return "滴答：无排期"

    def _has_schedulable_follow_up(self, project: ProjectRecord | ProjectDetail) -> bool:
        follow_up = _next_follow_up_date(project)
        return bool(follow_up and follow_up not in {"待补日期", "待补", "待确认", "待排期", "已归档", "暂缓"})

    def _next_step_summary(self, detail: ProjectDetail | None, record: ProjectRecord) -> str:
        if detail is not None:
            follow_up = _next_follow_up_date(detail) or "待补日期"
            return f"{detail.next_action or '待补下一步'} · 跟进 {follow_up}"
        follow_up = _next_follow_up_date(record) or "待补日期"
        return f"{record.next_action or '待补下一步'} · 跟进 {follow_up}"

    def _structured_progress_nodes(self, nodes: list[ProjectProgressNode]) -> list[dict[str, str]]:
        structured: list[dict[str, str]] = []
        for node in nodes:
            status, status_label = self._normalized_progress_status(node.status, node)
            summary_parts = [
                node.note,
                node.next_action,
                f"负责人：{node.owner}" if node.owner else "",
                f"计划：{node.planned_date}" if node.planned_date else "",
                f"完成：{node.completed_date}" if node.completed_date else "",
                f"协作：{node.collaborators}" if node.collaborators else "",
                f"卡点：{node.risk}" if node.risk else "",
            ]
            structured.append(
                {
                    "title": node.node_name or "待补进度节点",
                    "summary": " · ".join(part for part in summary_parts if part).strip() or "待补节点说明",
                    "status": status,
                    "status_label": status_label,
                }
            )
        return structured

    def _normalized_progress_status(self, raw_status: str, node: ProjectProgressNode) -> tuple[str, str]:
        status = (raw_status or "").strip()
        if any(keyword in status for keyword in ("已完成", "完成", "归档")) or node.completed_date:
            return "done", "已完成"
        if any(keyword in status for keyword in ("卡", "风险", "阻塞", "延期")) or node.risk.strip():
            return "risk", "卡点关注"
        if any(keyword in status for keyword in ("待开始", "未开始", "待补", "待确认")):
            return "todo", "待开始"
        if status:
            return "active", "当前推进"
        if node.note.strip() or node.next_action.strip():
            return "active", "当前推进"
        return "todo", "待开始"

    def _first_meaningful_line(self, text: str) -> str:
        for line in (text or "").splitlines():
            cleaned = line.strip().lstrip("-").strip()
            if cleaned:
                return cleaned
        return ""

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


def _clear_layout(layout, preserve: tuple[QWidget, ...] = ()) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout, preserve)
        widget = item.widget()
        if widget is not None:
            if widget in preserve:
                widget.setParent(None)
                continue
            widget.setParent(None)
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
