from __future__ import annotations

from html import escape

from PySide6.QtCore import QUrl, Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import CUSTOMER_STAGES, CUSTOMER_TYPES, CustomerDetail, CustomerRecord, PersonRecord


ALL_FILTER = "全部"


class CustomerLibraryPage(QWidget):
    customer_selected = Signal(str)
    person_selected = Signal(str)
    update_customer_requested = Signal(str)
    edit_customer_requested = Signal(str)
    archive_customer_requested = Signal(str)
    view_customer_projects_requested = Signal(str)
    overview_requested = Signal()
    quick_capture_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("CustomerLibraryPage")
        self._records: list[CustomerRecord] = []
        self._displayed_records: list[CustomerRecord] = []
        self._current_customer_name = ""
        self.setStyleSheet(
            """
            QWidget#CustomerLibraryPage QLabel#WorkspaceEyebrow {
                color: #4363d8;
                background: #eef3ff;
                border: 1px solid #d5e0ff;
                border-radius: 10px;
                padding: 4px 9px;
                font-size: 11px;
                font-weight: 800;
            }
            QWidget#CustomerLibraryPage QFrame#CustomerLibrarySearchWell,
            QWidget#CustomerLibraryPage QFrame#FilterChip,
            QWidget#CustomerLibraryPage QFrame#DetailMiniCard,
            QWidget#CustomerLibraryPage QFrame#ReminderCard,
            QWidget#CustomerLibraryPage QFrame#ArchiveSectionCard {
                background: #f8fbff;
                border: 1px solid #dde6f5;
                border-radius: 18px;
            }
            QWidget#CustomerLibraryPage QLabel#FilterChipTitle,
            QWidget#CustomerLibraryPage QLabel#DetailMiniTitle,
            QWidget#CustomerLibraryPage QLabel#ReminderTitle,
            QWidget#CustomerLibraryPage QLabel#ArchiveSectionTitle {
                color: #6b7892;
                font-size: 11px;
                font-weight: 800;
            }
            QWidget#CustomerLibraryPage QLabel#ArchiveFieldLabel {
                color: #71809a;
                font-size: 11px;
                font-weight: 700;
            }
            QWidget#CustomerLibraryPage QLabel#ArchiveFieldValue {
                color: #20304a;
                font-size: 13px;
                font-weight: 700;
            }
            QWidget#CustomerLibraryPage QLabel#DetailMiniValue {
                color: #1f314d;
                font-size: 16px;
                font-weight: 850;
            }
            QWidget#CustomerLibraryPage QLabel#DetailMiniHint {
                color: #73819d;
                font-size: 12px;
                font-weight: 650;
            }
            QWidget#CustomerLibraryPage QLabel#ReminderBody {
                color: #20304a;
                font-size: 13px;
                font-weight: 700;
            }
            QWidget#CustomerLibraryPage QFrame#ReminderActionWell {
                background: #fff7f8;
                border: 1px solid #ffd8df;
                border-radius: 16px;
            }
            QWidget#CustomerLibraryPage QLabel#ReminderActionHint {
                color: #8b6070;
                font-size: 12px;
                font-weight: 650;
            }
            """
        )

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

        topbar = QFrame()
        topbar.setObjectName("TopbarPanel")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 16, 18, 16)
        topbar_layout.setSpacing(16)
        topbar_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(3)
        heading_tag = QLabel("客户档案工作台")
        heading_tag.setObjectName("WorkspaceEyebrow")
        title = QLabel("客户库")
        title.setObjectName("SectionTitle")
        self.meta_label = QLabel("全部客户")
        self.meta_label.setObjectName("SectionHint")
        self.meta_label.setWordWrap(True)
        heading.addWidget(heading_tag, 0, Qt.AlignmentFlag.AlignLeft)
        heading.addWidget(title)
        heading.addWidget(self.meta_label)

        search_well = QFrame()
        search_well.setObjectName("CustomerLibrarySearchWell")
        search_layout = QHBoxLayout(search_well)
        search_layout.setContentsMargins(14, 10, 14, 10)
        search_layout.setSpacing(10)
        search_title = QLabel("搜索")
        search_title.setObjectName("FilterChipTitle")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索客户 / 联系人 / 手机号")
        self.search_edit.textChanged.connect(lambda _text: self._refresh())
        search_layout.addWidget(search_title)
        search_layout.addWidget(self.search_edit, 1)
        search_well.setMaximumWidth(330)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(10)
        self.overview_button = QPushButton("返回")
        self.overview_button.setObjectName("SecondaryActionButton")
        self.overview_button.clicked.connect(lambda _checked=False: self.overview_requested.emit())
        self.quick_capture_button = QPushButton("新建客户")
        self.quick_capture_button.clicked.connect(lambda _checked=False: self.quick_capture_requested.emit())
        action_row.addWidget(search_well, 1)
        action_row.addWidget(self.quick_capture_button)
        action_row.addWidget(self.overview_button)

        topbar_layout.addLayout(heading, 4)
        topbar_layout.addLayout(action_row, 5)

        filters = QFrame()
        filters.setObjectName("WorkspacePanel")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(14, 12, 14, 12)
        filters_layout.setSpacing(12)
        filter_intro = QVBoxLayout()
        filter_intro.setContentsMargins(0, 0, 0, 0)
        filter_intro.setSpacing(3)
        filter_tag = QLabel("筛选标签条")
        filter_tag.setObjectName("WorkspaceEyebrow")
        filter_intro.addWidget(filter_tag, 0, Qt.AlignmentFlag.AlignLeft)
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems([ALL_FILTER, *CUSTOMER_TYPES])
        self.type_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        self.stage_filter_combo = QComboBox()
        self.stage_filter_combo.addItems([ALL_FILTER, *CUSTOMER_STAGES])
        self.stage_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        self.tag_filter_edit = QLineEdit()
        self.tag_filter_edit.setPlaceholderText("二级标签筛选，例如 小时达")
        self.tag_filter_edit.textChanged.connect(lambda _text: self._refresh())
        filters_layout.addLayout(filter_intro, 3)
        filters_layout.addWidget(self._build_filter_chip("客户类型", self.type_filter_combo), 2)
        filters_layout.addWidget(self._build_filter_chip("当前阶段", self.stage_filter_combo), 2)
        filters_layout.addWidget(self._build_filter_chip("二级标签", self.tag_filter_edit), 3)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)

        list_panel = QFrame()
        list_panel.setObjectName("WorkspacePanel")
        list_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(10)
        list_tag = QLabel("客户列表")
        list_tag.setObjectName("WorkspaceEyebrow")
        list_header = QHBoxLayout()
        list_title_column = QVBoxLayout()
        list_title_column.setContentsMargins(0, 0, 0, 0)
        list_title_column.setSpacing(3)
        list_title = QLabel("全部客户")
        list_title.setObjectName("SectionTitle")
        self.selection_label = QLabel("")
        self.selection_label.setObjectName("SectionHint")
        self.selection_label.setWordWrap(True)
        list_title_column.addWidget(list_title)
        list_title_column.addWidget(self.selection_label)
        self.count_label = QLabel("当前 0 个客户")
        self.count_label.setObjectName("SoftBadge")
        list_header.addLayout(list_title_column, 1)
        list_header.addStretch(1)
        list_header.addWidget(self.count_label)
        self.customer_grid = QGridLayout()
        self.customer_grid.setContentsMargins(0, 0, 0, 0)
        self.customer_grid.setSpacing(10)
        list_layout.addWidget(list_tag, 0, Qt.AlignmentFlag.AlignLeft)
        list_layout.addLayout(list_header)
        list_layout.addLayout(self.customer_grid)

        detail_panel = QFrame()
        detail_panel.setObjectName("DetailCard")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(12)
        detail_tag = QLabel("档案工作台")
        detail_tag.setObjectName("WorkspaceEyebrow")
        detail_heading = QVBoxLayout()
        detail_heading.setContentsMargins(0, 0, 0, 0)
        detail_heading.setSpacing(10)
        detail_header = QHBoxLayout()
        detail_title_column = QVBoxLayout()
        detail_title_column.setContentsMargins(0, 0, 0, 0)
        detail_title_column.setSpacing(3)
        detail_title = QLabel("客户档案")
        detail_title.setObjectName("SectionTitle")
        self.detail_meta_label = QLabel("")
        self.detail_meta_label.setObjectName("SectionHint")
        self.detail_meta_label.setWordWrap(True)
        detail_title_column.addWidget(detail_title)
        detail_title_column.addWidget(self.detail_meta_label)
        self.edit_button = QPushButton("编辑")
        self.edit_button.setObjectName("InlineActionButton")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._emit_edit)
        self.ai_button = QPushButton("AI更新")
        self.ai_button.setObjectName("InlineActionButton")
        self.ai_button.setEnabled(False)
        self.ai_button.clicked.connect(self._emit_ai_update)
        self.projects_button = QPushButton("看项目")
        self.projects_button.setObjectName("SecondaryActionButton")
        self.projects_button.setEnabled(False)
        self.projects_button.clicked.connect(self._emit_projects)
        self.archive_button = QPushButton("收档")
        self.archive_button.setObjectName("SecondaryActionButton")
        self.archive_button.setEnabled(False)
        self.archive_button.clicked.connect(self._emit_archive)
        detail_header.addLayout(detail_title_column, 1)
        detail_header.addStretch(1)
        detail_header.addWidget(self.edit_button)
        detail_header.addWidget(self.ai_button)
        detail_heading.addLayout(detail_header)
        detail_snapshot = QGridLayout()
        detail_snapshot.setContentsMargins(0, 0, 0, 0)
        detail_snapshot.setHorizontalSpacing(10)
        detail_snapshot.setVerticalSpacing(10)
        stage_card, self.stage_value_label, self.stage_hint_label = self._build_detail_mini_card("当前阶段")
        need_card, self.next_move_value_label, self.next_move_hint_label = self._build_detail_mini_card("最近推进")
        follow_card, self.follow_up_value_label, self.follow_up_hint_label = self._build_detail_mini_card("下次跟进")
        detail_snapshot.addWidget(stage_card, 0, 0)
        detail_snapshot.addWidget(follow_card, 0, 1)
        detail_snapshot.addWidget(need_card, 1, 0, 1, 2)
        detail_snapshot.setColumnStretch(0, 1)
        detail_snapshot.setColumnStretch(1, 1)
        detail_heading.addLayout(detail_snapshot)
        self.basic_info_card = self._build_archive_section_card("基本信息")
        self.basic_info_type_value = self._build_archive_field(self.basic_info_card[1], "客户类型")
        self.basic_info_tags_value = self._build_archive_field(self.basic_info_card[1], "二级标签")
        self.basic_info_contact_value = self._build_archive_field(self.basic_info_card[1], "联系人")
        self.basic_info_phone_value = self._build_archive_field(self.basic_info_card[1], "联系电话")
        self.basic_info_wechat_value = self._build_archive_field(self.basic_info_card[1], "微信号")
        self.basic_info_company_value = self._build_archive_field(self.basic_info_card[1], "所属主体")

        self.judgement_card = self._build_archive_section_card("当前判断")
        self.judgement_need_value = self._build_archive_field(self.judgement_card[1], "当前需求")
        self.judgement_progress_value = self._build_archive_field(self.judgement_card[1], "最近推进")
        self.judgement_action_value = self._build_archive_field(self.judgement_card[1], "下次动作")
        self.judgement_follow_up_value = self._build_archive_field(self.judgement_card[1], "下次跟进")

        self.party_card = self._build_archive_section_card("默认甲方信息")
        self.party_brand_value = self._build_archive_field(self.party_card[1], "品牌")
        self.party_contact_value = self._build_archive_field(self.party_card[1], "收件联系人")
        self.party_phone_value = self._build_archive_field(self.party_card[1], "联系电话")
        self.party_email_value = self._build_archive_field(self.party_card[1], "电子邮箱")
        self.party_address_value = self._build_archive_field(self.party_card[1], "通讯地址")

        self.people_card = self._build_archive_section_card("关系人")
        self.people_browser = QTextBrowser()
        self.people_browser.setOpenExternalLinks(False)
        self.people_browser.anchorClicked.connect(self._emit_person_link)
        self.people_browser.setMinimumHeight(90)
        self.people_browser.setMaximumHeight(150)
        self.people_card[1].addWidget(self.people_browser)

        self.communication_card = self._build_archive_section_card("最近沟通")
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(False)
        self.detail_browser.setMinimumHeight(120)
        self.detail_browser.setMaximumHeight(220)
        self.detail_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.communication_card[1].addWidget(self.detail_browser)

        section_grid = QGridLayout()
        section_grid.setContentsMargins(0, 0, 0, 0)
        section_grid.setHorizontalSpacing(10)
        section_grid.setVerticalSpacing(10)
        section_grid.addWidget(self.basic_info_card[0], 0, 0)
        section_grid.addWidget(self.judgement_card[0], 0, 1)
        section_grid.addWidget(self.party_card[0], 1, 0)
        section_grid.addWidget(self.communication_card[0], 1, 1)
        section_grid.addWidget(self.people_card[0], 2, 0, 1, 2)
        section_grid.setColumnStretch(0, 1)
        section_grid.setColumnStretch(1, 1)
        detail_layout.addWidget(detail_tag, 0, Qt.AlignmentFlag.AlignLeft)
        detail_layout.addLayout(detail_heading)
        detail_layout.addLayout(section_grid)

        reminder_panel = QFrame()
        reminder_panel.setObjectName("WorkspacePanel")
        reminder_layout = QVBoxLayout(reminder_panel)
        reminder_layout.setContentsMargins(16, 16, 16, 16)
        reminder_layout.setSpacing(10)
        reminder_tag = QLabel("推进提醒")
        reminder_tag.setObjectName("WorkspaceEyebrow")
        reminder_header = QVBoxLayout()
        reminder_header.setContentsMargins(0, 0, 0, 0)
        reminder_header.setSpacing(3)
        reminder_title = QLabel("操作与提醒")
        reminder_title.setObjectName("SectionTitle")
        self.reminder_meta_label = QLabel("")
        self.reminder_meta_label.setObjectName("SectionHint")
        self.reminder_meta_label.setWordWrap(True)
        reminder_header.addWidget(reminder_title)
        reminder_header.addWidget(self.reminder_meta_label)
        reminder_action_well = QFrame()
        reminder_action_well.setObjectName("ReminderActionWell")
        reminder_action_layout = QVBoxLayout(reminder_action_well)
        reminder_action_layout.setContentsMargins(12, 12, 12, 12)
        reminder_action_layout.setSpacing(8)
        reminder_action_title = QLabel("快捷动作")
        reminder_action_title.setObjectName("ReminderTitle")
        reminder_action_buttons = QVBoxLayout()
        reminder_action_buttons.setContentsMargins(0, 0, 0, 0)
        reminder_action_buttons.setSpacing(6)
        reminder_action_buttons.addWidget(self.projects_button)
        reminder_action_buttons.addWidget(self.archive_button)
        reminder_action_layout.addWidget(reminder_action_title)
        reminder_action_layout.addLayout(reminder_action_buttons)
        next_step_card, self.next_step_body_label, self.next_step_hint_label = self._build_reminder_card("下一步动作")
        recent_card, self.recent_comm_body_label, self.recent_comm_hint_label = self._build_reminder_card("最近沟通")
        admin_card, self.admin_watch_body_label, self.admin_watch_hint_label = self._build_reminder_card("收档 / 审批")
        reminder_layout.addWidget(reminder_tag, 0, Qt.AlignmentFlag.AlignLeft)
        reminder_layout.addLayout(reminder_header)
        reminder_layout.addWidget(reminder_action_well)
        reminder_layout.addWidget(next_step_card)
        reminder_layout.addWidget(recent_card)
        reminder_layout.addWidget(admin_card)
        reminder_layout.addStretch(1)

        workspace.addWidget(list_panel, 8)
        workspace.addWidget(detail_panel, 12)
        workspace.addWidget(reminder_panel, 8)

        root.addWidget(topbar)
        root.addWidget(filters)
        root.addLayout(workspace)
        root.addStretch(1)

    def set_customer_type_options(self, customer_types: list[str] | tuple[str, ...]) -> None:
        current = self.type_filter_combo.currentText()
        self.type_filter_combo.blockSignals(True)
        self.type_filter_combo.clear()
        self.type_filter_combo.addItems([ALL_FILTER, *(tuple(customer_types) or CUSTOMER_TYPES)])
        index = self.type_filter_combo.findText(current)
        self.type_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.type_filter_combo.blockSignals(False)
        self._refresh()

    def set_customers(self, records: list[CustomerRecord], selected_name: str | None = None) -> None:
        self._records = _sort_library_records(records)
        if selected_name:
            self._current_customer_name = selected_name
        elif self._current_customer_name and any(record.name == self._current_customer_name for record in self._records):
            pass
        elif self._records:
            self._current_customer_name = self._records[0].name
        else:
            self._current_customer_name = ""
        self._refresh()
        if self._current_customer_name:
            self.customer_selected.emit(self._current_customer_name)
        else:
            self.show_customer_detail(None)

    def displayed_customer_names(self) -> list[str]:
        return [record.name for record in self._displayed_records]

    def show_customer_detail(self, detail: CustomerDetail | None) -> None:
        if detail is None:
            self._current_customer_name = ""
            self.edit_button.setEnabled(False)
            self.ai_button.setEnabled(False)
            self.projects_button.setEnabled(False)
            self.archive_button.setEnabled(False)
            self.detail_meta_label.setText("")
            self._set_detail_snapshot("待选择", "", "待排期", "")
            self._set_reminder_content(
                "",
                "",
                "",
                "",
                "",
                "",
            )
            self._set_archive_fields(
                customer_type="待补充",
                secondary_tags="待补充",
                contact="待补充",
                phone="待补充",
                wechat="待补充",
                company="待补充",
                current_need="待补充",
                recent_progress="待补充",
                next_action="待补充",
                next_follow_up="待排期",
                party_brand="待补充",
                party_contact="待补充",
                party_phone="待补充",
                party_email="待补充",
                party_address="待补充",
            )
            self.detail_browser.setHtml("")
            self.set_related_people([])
            return

        self._current_customer_name = detail.name
        self.edit_button.setEnabled(True)
        self.ai_button.setEnabled(True)
        self.projects_button.setEnabled(True)
        self.archive_button.setEnabled(detail.stage != "已归档")
        self.detail_meta_label.setText(
            f"{detail.customer_type} · {detail.stage} · {detail.business_direction or '待补业务方向'}"
        )
        progress_value = detail.recent_progress or detail.current_need or "待补最近推进"
        next_action_value = _visible_next_action(detail.next_action)
        self._set_detail_snapshot(detail.stage or "待补阶段", progress_value, detail.next_follow_up_date or "待排期", "")
        self._set_archive_fields(
            customer_type=detail.customer_type or "待补充",
            secondary_tags=detail.secondary_tags or "待补充",
            contact=detail.contact or "待补充",
            phone=detail.phone or "待补充",
            wechat=detail.wechat_id or "待补充",
            company=detail.company or "待补充",
            current_need=detail.current_need or "待补充",
            recent_progress=detail.recent_progress or "待补充",
            next_action=next_action_value or "—",
            next_follow_up=detail.next_follow_up_date or "待排期",
            party_brand=detail.party_a_brand or "待补充",
            party_contact=detail.party_a_contact or "待补充",
            party_phone=detail.party_a_phone or "待补充",
            party_email=detail.party_a_email or "待补充",
            party_address=detail.party_a_address or "待补充",
        )
        latest_entry = detail.communication_entries[0] if detail.communication_entries else None
        if detail.pending_approval_count > 0:
            admin_body = f"待归属审批 {detail.pending_approval_count} 条"
            admin_hint = ""
        elif detail.stage == "已归档":
            admin_body = "已归档"
            admin_hint = ""
        else:
            admin_body = "—"
            admin_hint = ""
        self._set_reminder_content(
            next_action_value or "—",
            detail.next_follow_up_date or "待排期",
            latest_entry.summary if latest_entry and latest_entry.summary else "—",
            latest_entry.entry_date if latest_entry and latest_entry.entry_date else "",
            admin_body,
            admin_hint,
        )

        communication_html = "".join(
            (
                "<div style='margin:0 0 14px 0; padding:12px 14px; background:#f8fbff; "
                "border:1px solid #e2eaf6; border-radius:14px;'>"
                f"<div style='font-size:12px; font-weight:700; color:#6b7892; margin-bottom:6px;'>{escape(entry.entry_date)}</div>"
                f"<div style='font-size:13px; font-weight:700; color:#20304a; margin-bottom:4px;'>{escape(entry.summary or '待补充')}</div>"
                f"<div style='font-size:12px; color:#596883;'>下一步：{escape(entry.next_step or '待补充')}</div>"
                "</div>"
            )
            for entry in detail.communication_entries[:4]
        ) or ""
        self.detail_browser.setHtml(
            f"""
            <div style="font-family:'PingFang SC','Microsoft YaHei','Noto Sans SC','Segoe UI',sans-serif; color:#20304a; line-height:1.6;">
                <div style='margin:0 0 12px 0; padding:10px 12px; background:#ffffff; border:1px solid #e2eaf6; border-radius:12px;'>
                    <div style='font-size:12px; font-weight:700; color:#6b7892; margin-bottom:4px;'>推进摘要</div>
                    <div style='font-size:13px; font-weight:700; color:#20304a;'>下次动作：{escape(next_action_value or '—')}</div>
                </div>
                {communication_html}
            </div>
            """
        )

    def set_related_people(self, people: list[PersonRecord]) -> None:
        if not people:
            self.people_browser.setHtml(
                "<div style=\"font-family:'PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif; color:#73819d;\">暂无关系人。</div>"
            )
            return
        grouped: dict[str, list[PersonRecord]] = {}
        for person in people:
            grouped.setdefault(person.side or "待补所属方", []).append(person)
        blocks: list[str] = []
        for side, persons in grouped.items():
            items = "；".join(
                f"<a href='person:{escape(person.name)}' style='color:#4a7cff; text-decoration:none; font-weight:800;'>"
                f"{escape(person.name)}</a>：{escape(person.common_relation or person.organization or '待补关系')}"
                for person in persons
            )
            blocks.append(
                f"<div style='margin-bottom:8px;'><span style='color:#6b7892;font-weight:800;'>{escape(side)}</span>　{items}</div>"
            )
        self.people_browser.setHtml(
            "<div style=\"font-family:'PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif; color:#20304a; line-height:1.65;\">"
            + "".join(blocks)
            + "</div>"
        )

    def _emit_person_link(self, url: QUrl) -> None:
        value = url.toString()
        if not value.startswith("person:"):
            return
        name = value.removeprefix("person:").strip()
        if name:
            self.person_selected.emit(name)

    def _refresh(self) -> None:
        records = list(self._records)
        selected_type = self.type_filter_combo.currentText()
        selected_stage = self.stage_filter_combo.currentText()
        tag = self.tag_filter_edit.text().strip()
        keyword = self.search_edit.text().strip().lower()
        if selected_type and selected_type != ALL_FILTER:
            records = [record for record in records if _has_multi_value(record.customer_type, selected_type)]
        if selected_stage and selected_stage != ALL_FILTER:
            records = [record for record in records if record.stage == selected_stage]
        if tag:
            records = [record for record in records if tag in record.secondary_tags]
        if keyword:
            records = [record for record in records if keyword in _search_blob(record)]
        self._displayed_records = _sort_library_records(records)
        self.count_label.setText(f"当前 {len(self._displayed_records)} 个客户")
        self.meta_label.setText(f"当前筛选 {len(self._displayed_records)} / 全部 {len(self._records)}")
        if self._displayed_records and self._current_customer_name:
            self.selection_label.setText(f"当前查看：{self._current_customer_name}")
        elif self._displayed_records:
            self.selection_label.setText("")
        else:
            self.selection_label.setText("")
        if self._current_customer_name and not any(record.name == self._current_customer_name for record in self._displayed_records):
            self._current_customer_name = self._displayed_records[0].name if self._displayed_records else ""
            if self._current_customer_name:
                self.customer_selected.emit(self._current_customer_name)
            else:
                self.show_customer_detail(None)
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        _clear_layout(self.customer_grid)
        if not self._displayed_records:
            empty = QLabel("暂无客户。")
            empty.setObjectName("EmptyState")
            self.customer_grid.addWidget(empty, 0, 0)
            return
        for index, record in enumerate(self._displayed_records):
            self.customer_grid.addWidget(self._build_customer_card(record), index, 0)

    def _build_customer_card(self, record: CustomerRecord) -> QFrame:
        card = QFrame()
        card.setObjectName("CustomerTileSelected" if record.name == self._current_customer_name else "CustomerTile")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 12, 13, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        name = QLabel(record.name)
        name.setObjectName("CustomerTileName")
        stage = QLabel(record.stage or "待补阶段")
        stage.setObjectName("SoftBadge")
        header.addWidget(name, 1)
        header.addWidget(stage)
        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)
        customer_type = QLabel(record.customer_type or "待补客户类型")
        customer_type.setObjectName("SoftBadge")
        chips.addWidget(customer_type, 0, Qt.AlignmentFlag.AlignLeft)
        if record.secondary_tags:
            tags = QLabel(record.secondary_tags)
            tags.setObjectName("SoftBadge")
            chips.addWidget(tags, 0, Qt.AlignmentFlag.AlignLeft)
        chips.addStretch(1)
        meta = QLabel(record.business_direction or "待补业务方向")
        meta.setObjectName("CustomerTileMeta")
        meta.setWordWrap(True)
        progress = QLabel(record.recent_progress or record.current_need or "待补最近推进")
        progress.setObjectName("CustomerTileNeed")
        progress.setWordWrap(True)
        next_action_text = _visible_next_action(record.next_action)
        footer = QHBoxLayout()
        follow = QLabel(f"跟进日期：{record.next_follow_up_date or '待排期'}")
        follow.setObjectName("CustomerTileMeta")
        updated = QLabel(f"更新：{record.updated_at or '待补充'}")
        updated.setObjectName("CustomerTileMeta")
        view = QPushButton("查看档案")
        view.setObjectName("InlineActionButton")
        view.clicked.connect(lambda _checked=False, name=record.name: self._select_customer(name))
        footer.addWidget(follow)
        footer.addStretch(1)
        footer.addWidget(updated)
        footer.addStretch(1)
        footer.addWidget(view)
        layout.addLayout(header)
        layout.addLayout(chips)
        layout.addWidget(meta)
        layout.addWidget(progress)
        if next_action_text:
            next_action = QLabel(f"下一步：{next_action_text}")
            next_action.setObjectName("CustomerTileMeta")
            next_action.setWordWrap(True)
            layout.addWidget(next_action)
        layout.addLayout(footer)
        return card

    def _select_customer(self, name: str) -> None:
        self._current_customer_name = name
        self.selection_label.setText(f"当前查看：{name}")
        self._refresh_cards()
        self.customer_selected.emit(name)

    def _emit_edit(self) -> None:
        if self._current_customer_name:
            self.edit_customer_requested.emit(self._current_customer_name)

    def _emit_ai_update(self) -> None:
        if self._current_customer_name:
            self.update_customer_requested.emit(self._current_customer_name)

    def _emit_archive(self) -> None:
        if self._current_customer_name:
            self.archive_customer_requested.emit(self._current_customer_name)

    def _emit_projects(self) -> None:
        if self._current_customer_name:
            self.view_customer_projects_requested.emit(self._current_customer_name)

    def _build_filter_chip(self, title: str, control: QWidget) -> QFrame:
        card = QFrame()
        card.setObjectName("FilterChip")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setObjectName("FilterChipTitle")
        layout.addWidget(title_label)
        layout.addWidget(control)
        return card

    def _build_detail_mini_card(self, title: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName("DetailMiniCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("DetailMiniTitle")
        value_label = QLabel("待补充")
        value_label.setObjectName("DetailMiniValue")
        value_label.setWordWrap(True)
        hint_label = QLabel("")
        hint_label.setObjectName("DetailMiniHint")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)
        return card, value_label, hint_label

    def _build_reminder_card(self, title: str) -> tuple[QFrame, QLabel, QLabel]:
        card = QFrame()
        card.setObjectName("ReminderCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName("ReminderTitle")
        body_label = QLabel("待补充")
        body_label.setObjectName("ReminderBody")
        body_label.setWordWrap(True)
        hint_label = QLabel("")
        hint_label.setObjectName("SectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(body_label)
        layout.addWidget(hint_label)
        return card, body_label, hint_label

    def _build_archive_section_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("ArchiveSectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("ArchiveSectionTitle")
        layout.addWidget(title_label)
        return card, layout

    def _build_archive_field(self, parent_layout: QVBoxLayout, title: str) -> QLabel:
        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("ArchiveFieldLabel")
        value = QLabel("待补充")
        value.setObjectName("ArchiveFieldValue")
        value.setWordWrap(True)
        wrapper.addWidget(label)
        wrapper.addWidget(value)
        parent_layout.addLayout(wrapper)
        return value

    def _set_detail_snapshot(self, stage: str, progress: str, follow_up: str, follow_up_hint: str) -> None:
        self.stage_value_label.setText(stage)
        self.stage_hint_label.setText("")
        self.next_move_value_label.setText(progress)
        self.next_move_hint_label.setText("")
        self.follow_up_value_label.setText(follow_up)
        self.follow_up_hint_label.setText(follow_up_hint)

    def _set_reminder_content(
        self,
        next_step_body: str,
        next_step_hint: str,
        recent_body: str,
        recent_hint: str,
        admin_body: str,
        admin_hint: str,
    ) -> None:
        self.next_step_body_label.setText(next_step_body)
        self.next_step_hint_label.setText(next_step_hint)
        self.recent_comm_body_label.setText(recent_body)
        self.recent_comm_hint_label.setText(recent_hint)
        self.admin_watch_body_label.setText(admin_body)
        self.admin_watch_hint_label.setText(admin_hint)

    def _set_archive_fields(
        self,
        *,
        customer_type: str,
        secondary_tags: str,
        contact: str,
        phone: str,
        wechat: str,
        company: str,
        current_need: str,
        recent_progress: str,
        next_action: str,
        next_follow_up: str,
        party_brand: str,
        party_contact: str,
        party_phone: str,
        party_email: str,
        party_address: str,
    ) -> None:
        self.basic_info_type_value.setText(customer_type)
        self.basic_info_tags_value.setText(secondary_tags)
        self.basic_info_contact_value.setText(contact)
        self.basic_info_phone_value.setText(phone)
        self.basic_info_wechat_value.setText(wechat)
        self.basic_info_company_value.setText(company)
        self.judgement_need_value.setText(current_need)
        self.judgement_progress_value.setText(recent_progress)
        self.judgement_action_value.setText(next_action)
        self.judgement_follow_up_value.setText(next_follow_up)
        self.party_brand_value.setText(party_brand)
        self.party_contact_value.setText(party_contact)
        self.party_phone_value.setText(party_phone)
        self.party_email_value.setText(party_email)
        self.party_address_value.setText(party_address)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def _sort_library_records(records: list[CustomerRecord]) -> list[CustomerRecord]:
    return sorted(records, key=lambda record: (_stage_rank(record.stage), record.updated_at or "", record.name), reverse=True)


def _stage_rank(stage: str) -> int:
    if stage == "已归档":
        return 0
    if stage == "暂缓":
        return 1
    return 2


def _has_multi_value(value: str, target: str) -> bool:
    return target in [part.strip() for part in value.replace("，", "/").replace(",", "/").replace("、", "/").split("/") if part.strip()]


def _search_blob(record: CustomerRecord) -> str:
    return " ".join(
        [
            record.name,
            record.customer_type,
            record.secondary_tags,
            record.stage,
            record.business_direction,
            record.current_need,
            record.recent_progress,
            record.next_action,
            record.contact,
            record.shop_scale,
        ]
    ).lower()


def _visible_next_action(value: str) -> str:
    normalized = (value or "").strip()
    if normalized.startswith("已完成本次"):
        return ""
    return normalized
