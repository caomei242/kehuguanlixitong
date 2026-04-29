from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from difflib import SequenceMatcher
from html import escape

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import (
    CUSTOMER_TYPES,
    PROJECT_CUSTOMER_TYPES,
    CustomerDetail,
    CustomerRecord,
    ProjectRecord,
)
from strawberry_customer_management.project_store import sort_project_records


ALL_CUSTOMERS_FILTER = "全部客户"


class OverviewPage(QWidget):
    customer_selected = Signal(str)
    update_customer_requested = Signal(str)
    edit_customer_requested = Signal(str)
    view_customer_projects_requested = Signal(str)
    quick_capture_requested = Signal()
    customer_library_requested = Signal()
    customer_follow_up_action_requested = Signal(str, str)
    project_follow_up_action_requested = Signal(str, str, str)
    undo_last_follow_up_action_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("OverviewPage")
        self._records: list[CustomerRecord] = []
        self._focus_records: list[CustomerRecord] = []
        self._project_records: list[ProjectRecord] = []
        self._displayed_records: list[CustomerRecord] = []
        self._displayed_nodes: list[FollowUpNode] = []
        self._current_customer_name = ""
        self._related_projects: list[ProjectRecord] = []

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
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        topbar = QFrame()
        topbar.setObjectName("TopbarPanel")
        topbar_layout = QVBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 16, 18, 16)
        topbar_layout.setSpacing(12)

        topbar_header = QHBoxLayout()
        topbar_header.setSpacing(12)
        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(3)
        title = QLabel("本周跟进")
        title.setObjectName("SectionTitle")
        self.meta_label = QLabel("今天：待同步")
        self.meta_label.setObjectName("SectionHint")
        self.meta_label.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(self.meta_label)

        self.type_filter_combo = QComboBox()
        self.type_filter_combo.setObjectName("OverviewFilterCombo")
        self.type_filter_combo.addItems([ALL_CUSTOMERS_FILTER, *CUSTOMER_TYPES])
        self.type_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        export_button = QPushButton("进入客户库")
        export_button.setObjectName("OverviewGhostButton")
        export_button.clicked.connect(lambda _checked=False: self.customer_library_requested.emit())
        self.quick_capture_button = QPushButton("快速录入")
        self.quick_capture_button.setObjectName("OverviewPrimaryButton")
        self.quick_capture_button.clicked.connect(lambda _checked=False: self.quick_capture_requested.emit())
        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addWidget(self.type_filter_combo)
        controls.addWidget(export_button)
        controls.addWidget(self.quick_capture_button)

        topbar_header.addLayout(heading, 1)
        topbar_header.addLayout(controls)

        topbar_footer = QHBoxLayout()
        topbar_footer.setSpacing(8)
        self.filter_badge_label = QLabel("筛选：全部客户")
        self.filter_badge_label.setObjectName("TopbarBadge")
        self.priority_badge_label = QLabel("本周 0 项")
        self.priority_badge_label.setObjectName("PriorityBadge")
        topbar_footer.addStretch(1)
        topbar_footer.addWidget(self.filter_badge_label)
        topbar_footer.addWidget(self.priority_badge_label)
        topbar_layout.addLayout(topbar_header)
        topbar_layout.addLayout(topbar_footer)

        self.undo_bar = QFrame()
        self.undo_bar.setObjectName("OverviewUndoBar")
        undo_layout = QHBoxLayout(self.undo_bar)
        undo_layout.setContentsMargins(12, 10, 12, 10)
        undo_layout.setSpacing(10)
        self.undo_label = QLabel("刚刚更新了跟进状态。")
        self.undo_label.setObjectName("OverviewUndoText")
        self.undo_button = QPushButton("撤销")
        self.undo_button.setObjectName("OverviewUndoButton")
        self.undo_button.clicked.connect(lambda _checked=False: self.undo_last_follow_up_action_requested.emit())
        self.undo_bar.setVisible(False)
        undo_layout.addWidget(self.undo_label, 1)
        undo_layout.addWidget(self.undo_button)

        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(10)
        self.metric_value_labels: dict[str, QLabel] = {}
        for label, note in (
            ("逾期", "已经该跟但还没处理"),
            ("今天", "今天需要确认"),
            ("明天", "提前看明天节点"),
            ("待排期", "有下一步但没日期"),
        ):
            self.metrics_layout.addWidget(self._build_metric_card(label, note), 1)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)

        self.overview_panel = QFrame()
        self.overview_panel.setObjectName("OverviewTimelinePanel")
        self.overview_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        overview_layout = QVBoxLayout(self.overview_panel)
        overview_layout.setContentsMargins(16, 16, 16, 16)
        overview_layout.setSpacing(10)
        overview_header = QHBoxLayout()
        overview_title = QVBoxLayout()
        overview_title.setSpacing(3)
        title_label = QLabel("本周跟进清单")
        title_label.setObjectName("SectionTitle")
        overview_title.addWidget(title_label)
        self.customer_count_label = QLabel("本周 0 个事项")
        self.customer_count_label.setObjectName("SoftBadge")
        overview_header.addLayout(overview_title, 1)
        overview_header.addStretch(1)
        overview_header.addWidget(self.customer_count_label)
        self.customer_grid = QVBoxLayout()
        self.customer_grid.setSpacing(10)
        overview_layout.addLayout(overview_header)
        overview_layout.addWidget(self.undo_bar)
        overview_layout.addLayout(self.customer_grid)

        side_column = QVBoxLayout()
        side_column.setSpacing(14)
        self.follow_panel, self.follow_layout = self._build_side_panel("快速提醒")
        self.missing_panel, self.missing_layout = self._build_side_panel("收档建议")
        side_column.addWidget(self.follow_panel)
        side_column.addWidget(self.missing_panel)
        side_column.addStretch(1)

        workspace.addWidget(self.overview_panel, 5)
        workspace.addLayout(side_column, 2)

        detail_card = QFrame()
        detail_card.setObjectName("DetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(10)
        detail_header = QHBoxLayout()
        detail_title = QLabel("客户库")
        detail_title.setObjectName("SectionTitle")
        detail_title_column = QVBoxLayout()
        detail_title_column.setContentsMargins(0, 0, 0, 0)
        detail_title_column.setSpacing(2)
        detail_title_column.addWidget(detail_title)
        self.customer_library_button = QPushButton("进入客户库")
        self.customer_library_button.setObjectName("SecondaryActionButton")
        self.customer_library_button.clicked.connect(lambda _checked=False: self.customer_library_requested.emit())
        self.manual_edit_button = QPushButton("手动编辑此客户")
        self.manual_edit_button.setObjectName("SecondaryActionButton")
        self.manual_edit_button.setEnabled(False)
        self.manual_edit_button.clicked.connect(self._emit_edit_current_customer)
        self.ai_update_button = QPushButton("AI 更新此客户")
        self.ai_update_button.setObjectName("SecondaryActionButton")
        self.ai_update_button.setEnabled(False)
        self.ai_update_button.clicked.connect(self._emit_update_current_customer)
        detail_header.addLayout(detail_title_column, 1)
        detail_header.addStretch(1)
        detail_header.addWidget(self.customer_library_button)
        detail_header.addWidget(self.manual_edit_button)
        detail_header.addWidget(self.ai_update_button)
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(False)
        self.detail_browser.setMinimumHeight(88)
        self.detail_browser.setMaximumHeight(120)
        self.detail_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        related_title_row = QHBoxLayout()
        related_title = QLabel("相关项目")
        related_title.setObjectName("SectionTitle")
        self.view_projects_button = QPushButton("查看全部项目")
        self.view_projects_button.setObjectName("SecondaryActionButton")
        self.view_projects_button.setEnabled(False)
        self.view_projects_button.clicked.connect(self._emit_view_current_customer_projects)
        related_title_row.addWidget(related_title)
        related_title_row.addStretch(1)
        related_title_row.addWidget(self.view_projects_button)
        self.related_projects_layout = QVBoxLayout()
        self.related_projects_layout.setSpacing(8)
        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.detail_browser)
        detail_layout.addLayout(related_title_row)
        detail_layout.addLayout(self.related_projects_layout)

        root.addWidget(topbar)
        root.addLayout(self.metrics_layout)
        root.addLayout(workspace)
        root.addWidget(detail_card)
        root.addStretch(1)
        self._apply_page_styles()

    def set_focus_customers(self, records: list[CustomerRecord]) -> None:
        self._focus_records = _sort_customer_records(records)
        self._refresh()

    def set_follow_up_projects(self, records: list[ProjectRecord]) -> None:
        self._project_records = list(records)
        self._refresh()

    def set_customer_type_options(self, customer_types: list[str] | tuple[str, ...]) -> None:
        current = self.type_filter_combo.currentText()
        self.type_filter_combo.blockSignals(True)
        self.type_filter_combo.clear()
        self.type_filter_combo.addItems([ALL_CUSTOMERS_FILTER, *(tuple(customer_types) or CUSTOMER_TYPES)])
        if current:
            index = self.type_filter_combo.findText(current)
            self.type_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.type_filter_combo.blockSignals(False)
        self._refresh()

    def set_customers(self, records: list[CustomerRecord], selected_name: str | None = None) -> None:
        self._records = _sort_customer_records(records)
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

    def displayed_follow_up_titles(self) -> list[str]:
        return [node.title for node in self._displayed_nodes]

    def show_customer_detail(self, detail: CustomerDetail | None) -> None:
        if detail is None:
            self._current_customer_name = ""
            self.manual_edit_button.setEnabled(False)
            self.ai_update_button.setEnabled(False)
            self.view_projects_button.setEnabled(False)
            self.detail_browser.setHtml("")
            self.set_related_projects([], "")
            return

        self._current_customer_name = detail.name
        self.manual_edit_button.setEnabled(True)
        self.ai_update_button.setEnabled(True)
        self.view_projects_button.setEnabled(any(_has_customer_type(detail.customer_type, item) for item in PROJECT_CUSTOMER_TYPES))
        communication_html = "".join(
            (
                f"<h4>{escape(entry.entry_date)}</h4>"
                f"<p><b>结论：</b>{escape(entry.summary or '待补充')}</p>"
                f"<p><b>新增：</b>{escape(entry.new_info or '待补充')}</p>"
                f"<p><b>风险：</b>{escape(entry.risk or '待补充')}</p>"
                f"<p><b>下一步：</b>{escape(entry.next_step or '待补充')}</p>"
            )
            for entry in detail.communication_entries[:2]
        ) or "<p>暂无沟通沉淀。</p>"
        pending_approval_html = (
            "".join(
                f"<li>{escape(entry.entry_date)} · {escape(entry.title_or_usage or '待归属审批')} · {escape(entry.approval_status or '待补状态')}</li>"
                for entry in detail.pending_approval_entries[:3]
            )
            if detail.pending_approval_entries
            else "<li>暂无待归属审批。</li>"
        )
        html = f"""
        <div style="font-family:'PingFang SC','Microsoft YaHei','Noto Sans SC','Segoe UI',sans-serif; color:#20304a; line-height:1.6;">
            <div style="font-size:16px; font-weight:800; margin-bottom:4px;">{escape(detail.name)}</div>
            <div style="font-size:12px; color:#6f7f98; margin-bottom:6px;">{escape(detail.customer_type)} · {escape(detail.stage)} · {escape(detail.business_direction or '待补业务方向')}</div>
            <div style="font-size:13px; color:#20304a;"><b>下次跟进：</b>{escape(detail.next_follow_up_date or '待排期')}<br><b>下次动作：</b>{escape(_visible_next_action(detail.next_action) or '—')}</div>
        </div>
        """
        self.detail_browser.setHtml(html)

    def set_related_projects(self, projects: list[ProjectRecord], customer_type: str) -> None:
        self._related_projects = sort_project_records(projects)
        _clear_layout(self.related_projects_layout)
        if _has_customer_type(customer_type, "网店店群客户") and not (
            _has_customer_type(customer_type, "博主") or _has_customer_type(customer_type, "网店KA客户")
        ):
            self.related_projects_layout.addWidget(self._side_item("一期未启用", "", "空状态"))
            return
        if not self._related_projects:
            if _has_customer_type(customer_type, "网店KA客户"):
                empty_text = ""
            elif _has_customer_type(customer_type, "博主"):
                empty_text = ""
            else:
                empty_text = ""
            self.related_projects_layout.addWidget(self._side_item("暂无项目", empty_text, "待同步"))
            return
        for record in self._related_projects[:3]:
            self.related_projects_layout.addWidget(
                self._side_item(
                    record.project_name,
                    f"{record.project_type or '待补类型'} · {record.current_focus or '待补项目重点'}\n最新审批：{record.latest_approval_status or '暂无审批记录'}",
                    record.year or "待确认年份",
                )
            )

    def displayed_related_project_names(self) -> list[str]:
        return [record.project_name for record in self._related_projects]

    def _build_metric_card(self, label: str, note: str) -> QFrame:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)
        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)
        title = QLabel(label)
        title.setObjectName("MetricLabel")
        value = QLabel("0")
        value.setObjectName("MetricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        note_label = QLabel(note)
        note_label.setObjectName("MetricNote")
        note_label.setWordWrap(True)
        text_column.addWidget(title)
        text_column.addWidget(note_label)
        self.metric_value_labels[label] = value
        layout.addLayout(text_column, 1)
        layout.addWidget(value)
        return card

    def _build_side_panel(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("WorkbenchPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        items = QVBoxLayout()
        items.setSpacing(8)
        layout.addWidget(title_label)
        layout.addLayout(items)
        return panel, items

    def _refresh(self) -> None:
        selected_type = self.type_filter_combo.currentText() if hasattr(self, "type_filter_combo") else ALL_CUSTOMERS_FILTER
        source_records = self._focus_records or self._records
        if selected_type == ALL_CUSTOMERS_FILTER:
            filtered_records = list(source_records)
        else:
            filtered_records = [record for record in source_records if _has_customer_type(record.customer_type, selected_type)]
        records = _sort_follow_up_customers(filtered_records)
        display_records = [record for record in records if _visible_next_action(record.next_action) or record.next_follow_up_date]
        if selected_type == ALL_CUSTOMERS_FILTER:
            project_records = list(self._project_records)
        else:
            visible_customer_names = {record.name for record in filtered_records}
            project_records = [record for record in self._project_records if record.brand_customer_name in visible_customer_names]
        nodes = _sort_follow_up_nodes(_follow_up_nodes_for_customers(records) + _follow_up_nodes_for_projects(project_records))
        nodes = _collapse_overlapping_follow_up_nodes(nodes)
        self._displayed_records = display_records
        self._displayed_nodes = nodes
        if self._current_customer_name and not any(record.name == self._current_customer_name for record in records):
            self._current_customer_name = records[0].name if records else ""
            if self._current_customer_name:
                self.customer_selected.emit(self._current_customer_name)
            else:
                self.show_customer_detail(None)

        self._refresh_meta(selected_type)
        self._refresh_metrics(nodes)
        self._refresh_follow_up_cards(nodes)
        self._refresh_sidebars(filtered_records, nodes)

    def _refresh_meta(self, selected_type: str) -> None:
        latest_update = max(
            (record.updated_at for record in self._records if _sortable_updated_at(record.updated_at)),
            default="待同步",
        )
        today = date.today().isoformat()
        self.meta_label.setText(f"今天：{today} · 更新时间：{latest_update}")
        self.filter_badge_label.setText(f"筛选：{selected_type}")

    def _refresh_metrics(self, nodes: list["FollowUpNode"]) -> None:
        counts = {label: sum(1 for node in nodes if node.group == label) for label in ("逾期", "今天", "明天", "待排期")}
        self.metric_value_labels["逾期"].setText(str(counts.get("逾期", 0)))
        self.metric_value_labels["今天"].setText(str(counts.get("今天", 0)))
        self.metric_value_labels["明天"].setText(str(counts.get("明天", 0)))
        self.metric_value_labels["待排期"].setText(str(counts.get("待排期", 0)))
        priority_count = counts.get("逾期", 0) + counts.get("今天", 0) + counts.get("明天", 0)
        self.priority_badge_label.setText(f"优先 {priority_count} 项")

    def _refresh_follow_up_cards(self, nodes: list["FollowUpNode"]) -> None:
        _clear_layout(self.customer_grid)
        self.customer_count_label.setText(f"本周 {len(nodes)} 个事项")
        if not nodes:
            empty = QLabel("当前没有事项。")
            empty.setObjectName("EmptyState")
            empty.setWordWrap(True)
            self.customer_grid.addWidget(empty)
            return

        last_group = ""
        for node in nodes:
            if node.group != last_group:
                self.customer_grid.addWidget(self._build_group_marker(node.group))
                last_group = node.group
            self.customer_grid.addWidget(self._build_follow_up_card(node))
        self.customer_grid.addStretch(1)

    def _refresh_customer_cards(self, records: list[CustomerRecord]) -> None:
        _clear_layout(self.customer_grid)
        self.customer_count_label.setText(f"{len(records)} 个真实客户")
        if not records:
            empty = QLabel("暂无客户。")
            empty.setObjectName("EmptyState")
            self.customer_grid.addWidget(empty)
            return
        for record in records:
            self.customer_grid.addWidget(self._build_customer_card(record))
        self.customer_grid.addStretch(1)

    def _refresh_sidebars(self, filtered_records: list[CustomerRecord], nodes: list["FollowUpNode"]) -> None:
        _clear_layout(self.follow_layout)
        _clear_layout(self.missing_layout)
        priority_nodes = nodes[:4]
        if not priority_nodes:
            self.follow_layout.addWidget(self._side_item("暂无事项", "", ""))
        for index, node in enumerate(priority_nodes, start=1):
            self.follow_layout.addWidget(
                self._side_item(
                    _compact_sidebar_title(node),
                    _compact_sidebar_body(node),
                    node.group,
                    rank=index,
                )
            )

        workbench_items: list[tuple[str, str, str]] = []
        archived = [record for record in filtered_records if record.stage == "已归档"][:2]
        workbench_items.extend(
            (
                record.name,
                record.next_action,
                "已归档",
            )
            for record in archived
        )
        settled = [record for record in filtered_records if record.stage == "已合作" and not record.next_follow_up_date][:2]
        for record in settled:
            if len(workbench_items) >= 4:
                break
            workbench_items.append((record.name, record.next_action, "可检查"))
        for item in self._missing_items(filtered_records):
            if len(workbench_items) >= 4:
                break
            workbench_items.append(item)
        if not workbench_items:
            self.missing_layout.addWidget(self._side_item("暂无收档提醒", "", ""))
        for title, body, tag in workbench_items[:4]:
            self.missing_layout.addWidget(self._side_item(title, body, tag))

    def _missing_items(self, records: list[CustomerRecord]) -> list[tuple[str, str, str]]:
        items: list[tuple[str, str, str]] = []
        for record in records:
            missing: list[str] = []
            if not record.contact or record.contact == "待补充":
                missing.append("联系人")
            if not record.current_need or record.current_need == "待补充":
                missing.append("需求一句话")
            if not record.next_action or record.next_action == "待补充":
                missing.append("下一步")
            if _has_customer_type(record.customer_type, "网店店群客户") and (not record.shop_scale or record.shop_scale == "待补充"):
                missing.append("店铺规模")
            if _has_customer_type(record.customer_type, "网店KA客户") and (not record.shop_scale or record.shop_scale == "待补充"):
                missing.append("店铺/产品状态")
            if _has_customer_type(record.customer_type, "博主"):
                if not record.secondary_tags or record.secondary_tags == "待补充":
                    missing.append("二级标签")
            if missing:
                items.append((f"{record.name} · {' / '.join(missing[:2])}", "", "待补"))
        return items

    def _side_item(self, title: str, body: str, tag: str, rank: int | None = None) -> QFrame:
        item = QFrame()
        item.setObjectName("WorkbenchItem")
        layout = QVBoxLayout(item)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(5)
        header = QHBoxLayout()
        if rank is not None:
            rank_label = QLabel(str(rank))
            rank_label.setObjectName("WorkbenchRank")
            header.addWidget(rank_label)
        title_label = QLabel(title)
        title_label.setObjectName("SideItemTitle")
        title_label.setWordWrap(True)
        title_label.setToolTip(title)
        tag_label = QLabel(tag)
        tag_label.setObjectName("WorkbenchTag")
        header.addWidget(title_label, 1)
        header.addWidget(tag_label)
        layout.addLayout(header)
        if body:
            body_label = QLabel(body)
            body_label.setObjectName("SectionHint")
            body_label.setWordWrap(True)
            body_label.setToolTip(body)
            layout.addWidget(body_label)
        return item

    def _build_group_marker(self, group: str) -> QLabel:
        label = QLabel(_group_title(group))
        label.setObjectName("TimelineGroupChip")
        return label

    def _build_follow_up_card(self, node: "FollowUpNode") -> QFrame:
        card = QFrame()
        card.setObjectName("TimelineCardSelected" if node.customer_name == self._current_customer_name else "TimelineCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        shell = QHBoxLayout(card)
        shell.setContentsMargins(14, 12, 14, 12)
        shell.setSpacing(12)
        rail = QFrame()
        rail.setFixedWidth(6)
        rail.setStyleSheet(f"background-color: {_group_accent_color(node.group)}; border-radius: 3px;")
        shell.addWidget(rail)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        name_label = QLabel(node.title)
        name_label.setObjectName("CustomerTileName")
        name_label.setWordWrap(True)
        if node.kind == "project":
            badge_text = "项目节点"
        else:
            badge_text = node.tag
        tag_label = QLabel(badge_text)
        tag_label.setObjectName("TimelineStatusBadge")
        title_row.addWidget(name_label, 1)
        title_row.addWidget(tag_label)
        meta = QLabel(node.meta)
        meta.setObjectName("CustomerTileMeta")
        meta.setWordWrap(True)
        body = QLabel(node.body)
        body.setObjectName("CustomerTileNeed")
        body.setWordWrap(True)
        body.setMaximumHeight(42)
        body.setToolTip(node.body)
        footer = QHBoxLayout()
        date_button = QPushButton(_follow_up_chip_text(node.follow_up_date, node.group))
        date_button.setObjectName("TimelineDueChipButton")
        date_button.clicked.connect(lambda _checked=False, current_node=node: self._prompt_reschedule(current_node))
        footer.addWidget(date_button)
        footer.addStretch(1)
        view_button = QPushButton("›")
        view_button.setObjectName("TimelineOpenButton")
        view_button.clicked.connect(lambda _checked=False, name=node.customer_name: self._select_customer(name))
        action_combo = QComboBox()
        action_combo.setObjectName("TimelineActionCombo")
        action_combo.addItem("⋯", "")
        for action_label, action in (
            ("完成", "complete"),
            ("改排期", "reschedule_prompt"),
            ("改明天", "tomorrow"),
            ("暂缓", "suspend"),
            ("收档", "archive"),
        ):
            action_combo.addItem(action_label, action)
        action_combo.activated.connect(
            lambda index, combo=action_combo, current_node=node: self._handle_follow_up_action(current_node, combo, index)
        )
        footer.addWidget(view_button)
        footer.addWidget(action_combo)
        layout.addLayout(title_row)
        layout.addWidget(meta)
        layout.addWidget(body)
        layout.addLayout(footer)
        shell.addLayout(layout, 1)
        return card

    def _build_customer_card(self, record: CustomerRecord) -> QFrame:
        card = QFrame()
        card.setObjectName("CustomerTileSelected" if record.name == self._current_customer_name else "CustomerTile")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 12, 13, 12)
        layout.setSpacing(7)

        header = QHBoxLayout()
        name_label = QLabel(record.name)
        name_label.setObjectName("CustomerTileName")
        stage_label = QLabel(record.stage or "待补阶段")
        stage_label.setObjectName("SoftBadge")
        header.addWidget(name_label, 1)
        header.addWidget(stage_label)

        meta = QLabel(f"{record.customer_type} · {record.business_direction or '待补业务方向'}")
        meta.setObjectName("CustomerTileMeta")
        meta.setWordWrap(True)

        progress = QLabel(f"最新进度：{record.recent_progress or record.current_need or '待补最新进度'}")
        progress.setObjectName("CustomerTileNeed")
        progress.setWordWrap(True)
        progress.setMaximumHeight(44)

        need = QLabel(f"需求：{record.current_need or '待补当前需求'}")
        need.setObjectName("CustomerTileNeed")
        need.setWordWrap(True)
        need.setMaximumHeight(42)

        footer = QHBoxLayout()
        next_action = QLabel(f"下一步：{record.next_action or '待补下一步'}")
        next_action.setObjectName("CustomerTileMeta")
        next_action.setWordWrap(True)
        next_action.setMaximumHeight(36)
        date_label = QLabel(record.updated_at or "待同步")
        date_label.setObjectName("CustomerTileMeta")
        edit_button = QPushButton("编辑")
        edit_button.setObjectName("InlineActionButton")
        edit_button.clicked.connect(lambda _checked=False, name=record.name: self.edit_customer_requested.emit(name))
        view_button = QPushButton("查看")
        view_button.setObjectName("InlineActionButton")
        view_button.clicked.connect(lambda _checked=False, name=record.name: self._select_customer(name))
        footer.addWidget(next_action, 1)
        footer.addWidget(date_label)
        footer.addWidget(edit_button)
        footer.addWidget(view_button)

        layout.addLayout(header)
        layout.addWidget(meta)
        layout.addWidget(progress)
        layout.addWidget(need)
        layout.addLayout(footer)
        return card

    def _customer_card_text(self, record: CustomerRecord) -> str:
        need = record.current_need or "待补当前需求"
        next_action = record.next_action or "待补下一步"
        direction = record.business_direction or "待补业务方向"
        return (
            f"{record.name}    {record.stage}\n"
            f"{record.customer_type} · {direction}\n\n"
            f"{need}\n"
            f"下一步：{next_action}        {record.updated_at or '待同步'}"
        )

    def _select_customer(self, name: str) -> None:
        if not name:
            return
        self._current_customer_name = name
        self._refresh_follow_up_cards(self._displayed_nodes)
        self.customer_selected.emit(name)

    def _handle_follow_up_action(self, node: "FollowUpNode", combo: QComboBox, index: int) -> None:
        action = combo.itemData(index)
        if not action:
            return
        if action == "reschedule_prompt":
            self._prompt_reschedule(node)
        elif node.kind == "customer":
            self.customer_follow_up_action_requested.emit(node.customer_name, action)
        else:
            self.project_follow_up_action_requested.emit(node.customer_name, node.project_name, action)
        combo.blockSignals(True)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _prompt_reschedule(self, node: "FollowUpNode") -> None:
        current_text = node.follow_up_date if _is_editable_follow_up_date(node.follow_up_date) else ""
        value, accepted = QInputDialog.getText(
            self,
            "改排期",
            "下次跟进日期（YYYY-MM-DD，留空改为待排期）",
            text=current_text,
        )
        if not accepted:
            return
        normalized = value.strip()
        if normalized:
            try:
                parsed = date.fromisoformat(normalized)
            except ValueError:
                return
            action = f"reschedule:{parsed.isoformat()}"
        else:
            action = "unschedule"
        if node.kind == "customer":
            self.customer_follow_up_action_requested.emit(node.customer_name, action)
        else:
            self.project_follow_up_action_requested.emit(node.customer_name, node.project_name, action)

    def _emit_update_current_customer(self) -> None:
        if self._current_customer_name:
            self.update_customer_requested.emit(self._current_customer_name)

    def _emit_edit_current_customer(self) -> None:
        if self._current_customer_name:
            self.edit_customer_requested.emit(self._current_customer_name)

    def _emit_view_current_customer_projects(self) -> None:
        if self._current_customer_name:
            self.view_customer_projects_requested.emit(self._current_customer_name)

    def _apply_page_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#TopbarPanel {
                background: #ffffff;
                border: 1px solid #dfe8f4;
                border-radius: 24px;
            }
            QLabel#TopbarSummary {
                color: #6e7e99;
                font-size: 12px;
            }
            QLabel#TopbarBadge,
            QLabel#TimelineGroupChip,
            QLabel#TimelineDueChip {
                background: #eef4ff;
                color: #4b68c9;
                border: 1px solid #d7e2ff;
                border-radius: 11px;
                padding: 4px 10px;
                font-weight: 600;
            }
            QPushButton#TimelineDueChipButton {
                background: #eef4ff;
                color: #4b68c9;
                border: 1px solid #d7e2ff;
                border-radius: 11px;
                padding: 5px 12px;
                font-weight: 800;
            }
            QPushButton#TimelineDueChipButton:hover {
                background: #e7f0ff;
                border: 1px solid #c8d8ff;
            }
            QLabel#PriorityBadge {
                background: #f3f7ff;
                color: #335fd1;
                border: 1px solid #d8e2ff;
                border-radius: 11px;
                padding: 4px 10px;
                font-weight: 700;
            }
            QPushButton#OverviewPrimaryButton {
                background: #1f6feb;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 700;
            }
            QPushButton#OverviewPrimaryButton:hover {
                background: #185cc0;
            }
            QPushButton#OverviewGhostButton {
                background: white;
                color: #4a5b79;
                border: 1px solid #dce6f3;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton#OverviewGhostButton:hover {
                background: #f6f9fe;
            }
            QComboBox#OverviewFilterCombo,
            QComboBox#TimelineActionCombo {
                background: white;
                border: 1px solid #dce6f3;
                border-radius: 12px;
                padding: 6px 10px;
            }
            QLabel#OverviewBanner {
                color: #7a5a17;
                background: #fff8e7;
                border: 1px solid #f1d89b;
                border-radius: 14px;
                padding: 10px 12px;
            }
            QFrame#OverviewUndoBar {
                background: #eef6ff;
                border: 1px solid #cfe0ff;
                border-radius: 14px;
            }
            QLabel#OverviewUndoText {
                color: #31518f;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#OverviewUndoButton {
                background: white;
                color: #315fd4;
                border: 1px solid #cddcff;
                border-radius: 10px;
                padding: 6px 12px;
                font-weight: 700;
            }
            QPushButton#OverviewUndoButton:hover {
                background: #f8fbff;
            }
            QLabel#TimelineGroupChip {
                border-radius: 12px;
                padding: 6px 12px;
                font-weight: 800;
            }
            QLabel#TimelineDueChip {
                border-radius: 12px;
                padding: 5px 12px;
                font-weight: 800;
            }
            QFrame#MetricCard {
                background: white;
                border: 1px solid #e3ebf6;
                border-radius: 16px;
            }
            QLabel#MetricLabel {
                color: #7a89a6;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#MetricValue {
                color: #213250;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#MetricNote {
                color: #8a97af;
                font-size: 11px;
            }
            QFrame#OverviewTimelinePanel,
            QFrame#WorkbenchPanel,
            QFrame#DetailCard {
                background: white;
                border: 1px solid #e3ebf6;
                border-radius: 22px;
            }
            QFrame#TimelineCard,
            QFrame#TimelineCardSelected,
            QFrame#WorkbenchItem {
                background: #ffffff;
                border: 1px solid #e6edf7;
                border-radius: 18px;
            }
            QFrame#TimelineCardSelected {
                background: #f5f8ff;
                border: 1px solid #bfd2ff;
            }
            QLabel#TimelineStatusBadge,
            QLabel#WorkbenchTag,
            QLabel#WorkbenchRank {
                background: #f2f6ff;
                color: #4f6ed1;
                border: 1px solid #dde6ff;
                border-radius: 10px;
                padding: 4px 9px;
                font-weight: 700;
            }
            QLabel#WorkbenchRank {
                min-width: 22px;
                max-width: 22px;
                min-height: 22px;
                max-height: 22px;
                border-radius: 11px;
                padding: 0;
                qproperty-alignment: AlignCenter;
            }
            QLabel#CustomerTileName {
                color: #20304a;
                font-size: 17px;
                font-weight: 850;
            }
            QLabel#CustomerTileMeta {
                color: #7384a0;
                font-size: 12px;
                font-weight: 650;
            }
            QLabel#CustomerTileNeed {
                color: #20304a;
                font-size: 14px;
                font-weight: 720;
                line-height: 1.35;
            }
            QPushButton#TimelineOpenButton {
                background: transparent;
                color: #2d5ab0;
                border: 1px solid #cbdaff;
                border-radius: 10px;
                min-width: 34px;
                max-width: 34px;
                padding: 6px 0px;
                font-weight: 700;
            }
            QPushButton#TimelineOpenButton:hover {
                background: #eef3ff;
            }
            QComboBox#TimelineActionCombo {
                min-width: 66px;
                max-width: 66px;
            }
            QFrame#WorkbenchItem {
                border-radius: 18px;
            }
            """
        )

    def show_undo_action(self, message: str) -> None:
        self.undo_label.setText(message)
        self.undo_bar.setVisible(True)

    def clear_undo_action(self) -> None:
        self.undo_bar.setVisible(False)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def _sort_customer_records(records: list[CustomerRecord]) -> list[CustomerRecord]:
    return [
        record
        for _index, record in sorted(
            enumerate(records),
            key=lambda item: (_sortable_updated_at(item[1].updated_at), -item[0]),
            reverse=True,
        )
    ]


@dataclass(frozen=True)
class FollowUpNode:
    kind: str
    title: str
    customer_name: str
    project_name: str
    body: str
    meta: str
    tag: str
    follow_up_date: str
    group: str
    sort_key: tuple[int, str, str]


def _follow_up_nodes_for_customers(records: list[CustomerRecord]) -> list[FollowUpNode]:
    nodes: list[FollowUpNode] = []
    for record in records:
        next_action = _visible_next_action(record.next_action)
        if _is_inactive_stage(record.stage):
            continue
        if not next_action and not record.next_follow_up_date:
            continue
        group, sort_key = _follow_up_group(record.next_follow_up_date)
        nodes.append(
            FollowUpNode(
                kind="customer",
                title=record.name,
                customer_name=record.name,
                project_name="",
                body=next_action or record.current_need or "待补下一步",
                meta=f"{record.customer_type} · {record.stage or '待补阶段'} · {record.business_direction or '待补业务方向'}",
                tag=record.stage or "客户",
                follow_up_date=record.next_follow_up_date,
                group=group,
                sort_key=(sort_key, record.updated_at or "", record.name),
            )
        )
    return nodes


def _follow_up_nodes_for_projects(records: list[ProjectRecord]) -> list[FollowUpNode]:
    nodes: list[FollowUpNode] = []
    for record in records:
        next_action = _visible_next_action(record.next_action)
        if _is_inactive_stage(record.stage):
            continue
        if not next_action and not record.next_follow_up_date:
            continue
        group, sort_key = _follow_up_group(record.next_follow_up_date)
        nodes.append(
            FollowUpNode(
                kind="project",
                title=f"{record.brand_customer_name} · {record.project_name}",
                customer_name=record.brand_customer_name,
                project_name=record.project_name,
                body=next_action or record.current_focus or "待补项目下一步",
                meta=f"{record.project_type or '项目'} · {record.stage or '待补状态'} · 最新审批：{record.latest_approval_status or '暂无审批记录'}",
                tag="项目节点",
                follow_up_date=record.next_follow_up_date,
                group=group,
                sort_key=(sort_key, record.updated_at or "", record.project_name),
            )
        )
    return nodes


def _compact_sidebar_title(node: FollowUpNode) -> str:
    if node.kind == "project":
        return f"{node.customer_name} · 项目"
    return node.customer_name


def _compact_sidebar_body(node: FollowUpNode) -> str:
    prefix = node.follow_up_date or "待排期"
    body = node.body.strip() if node.body else "待补下一步"
    compact = body.replace("；", "，").replace("。", "，")
    first = compact.split("，")[0].strip() if compact else "待补下一步"
    if len(first) > 26:
        first = first[:26].rstrip() + "…"
    return f"{prefix} · {first}"


def _follow_up_chip_text(value: str, group: str) -> str:
    parsed = _parse_iso_date(value)
    today = date.today()
    if group == "待排期" or parsed is None:
        return "待排期"
    if parsed < today:
        days = max((today - parsed).days, 1)
        return f"逾期 {days}天"
    if parsed == today:
        return "今天"
    if parsed == today + timedelta(days=1):
        return "明天"
    return f"{parsed.month}-{parsed.day}"


def _is_editable_follow_up_date(value: str) -> bool:
    normalized = (value or "").strip()
    return bool(normalized and normalized not in {"待排期", "已归档"})


def _visible_next_action(value: str) -> str:
    normalized = (value or "").strip()
    if normalized.startswith("已完成本次"):
        return ""
    return normalized


def _sort_follow_up_customers(records: list[CustomerRecord]) -> list[CustomerRecord]:
    active = [record for record in records if not _is_inactive_stage(record.stage)]
    return [
        record
        for _index, record in sorted(
            enumerate(active),
            key=lambda item: (
                _follow_up_group(item[1].next_follow_up_date)[1],
                item[1].next_follow_up_date or "9999-99-99",
                _reverse_date_key(item[1].updated_at),
                item[0],
            ),
        )
    ]


def _sort_follow_up_nodes(nodes: list[FollowUpNode]) -> list[FollowUpNode]:
    return sorted(nodes, key=lambda node: (node.sort_key[0], node.follow_up_date or "9999-99-99", node.sort_key[2]))


def _collapse_overlapping_follow_up_nodes(nodes: list[FollowUpNode]) -> list[FollowUpNode]:
    project_nodes_by_key: dict[tuple[str, str, str], list[FollowUpNode]] = {}
    for node in nodes:
        if node.kind != "project":
            continue
        key = (node.customer_name, node.follow_up_date or "", node.group)
        project_nodes_by_key.setdefault(key, []).append(node)

    collapsed: list[FollowUpNode] = []
    for node in nodes:
        if node.kind != "customer":
            collapsed.append(node)
            continue
        key = (node.customer_name, node.follow_up_date or "", node.group)
        related_projects = project_nodes_by_key.get(key, [])
        if related_projects and any(_is_same_follow_up_moment(node, project_node) for project_node in related_projects):
            continue
        collapsed.append(node)
    return collapsed


def _is_same_follow_up_moment(customer_node: FollowUpNode, project_node: FollowUpNode) -> bool:
    left = _normalize_follow_up_text(customer_node.body)
    right = _normalize_follow_up_text(project_node.body)
    if not left or not right:
        return False
    if left in right or right in left:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.72


def _normalize_follow_up_text(value: str) -> str:
    return (
        value.replace("：", "")
        .replace("，", "")
        .replace("。", "")
        .replace("；", "")
        .replace(" ", "")
        .strip()
    )


def _follow_up_group(value: str) -> tuple[str, int]:
    parsed = _parse_iso_date(value)
    today = date.today()
    if parsed is None:
        return "待排期", 50
    if parsed < today:
        return "逾期", 0
    if parsed == today:
        return "今天", 10
    if parsed == today + timedelta(days=1):
        return "明天", 20
    end_of_week = today + timedelta(days=6 - today.weekday())
    if parsed <= end_of_week:
        return "本周稍后", 30
    return "待排期", 50


def _group_title(group: str) -> str:
    today = date.today()
    if group == "今天":
        return f"今天 {today.isoformat()}"
    if group == "明天":
        return f"明天 {(today + timedelta(days=1)).isoformat()}"
    return group


def _group_accent_color(group: str) -> str:
    if group == "逾期":
        return "#d9485f"
    if group == "今天":
        return "#f08c2e"
    if group == "明天":
        return "#2f6feb"
    if group == "本周稍后":
        return "#3f8f63"
    return "#9b8d7b"


def _parse_iso_date(value: str) -> date | None:
    normalized = (value or "").strip()
    if not normalized or normalized in {"待补充", "待确认", "待排期", "已归档"}:
        return None
    try:
        return date.fromisoformat(normalized[:10])
    except ValueError:
        return None


def _reverse_date_key(value: str) -> int:
    parsed = _parse_iso_date(value)
    if parsed is None:
        return 99999999
    return -parsed.toordinal()


def _is_inactive_stage(stage: str) -> bool:
    return stage in {"暂缓", "已归档"}


def _sortable_updated_at(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized or normalized in {"待同步", "待补充", "待确认", "待补日期"}:
        return ""
    return normalized


def _has_customer_type(value: str, customer_type: str) -> bool:
    return customer_type in [part.strip() for part in value.replace("，", "/").replace(",", "/").replace("、", "/").split("/") if part.strip()]
