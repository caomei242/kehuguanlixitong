from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import (
    CUSTOMER_STAGES,
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

    def __init__(self) -> None:
        super().__init__()
        self._records: list[CustomerRecord] = []
        self._focus_records: list[CustomerRecord] = []
        self._displayed_records: list[CustomerRecord] = []
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
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("TopbarPanel")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 14, 16, 14)
        topbar_layout.setSpacing(12)

        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(3)
        title = QLabel("客户总览")
        title.setObjectName("SectionTitle")
        self.meta_label = QLabel("更新时间：待同步 · 当前筛选：全部客户 · 一期口径：使用客户页与客户总表字段")
        self.meta_label.setObjectName("SectionHint")
        self.meta_label.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(self.meta_label)

        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems([ALL_CUSTOMERS_FILTER, *CUSTOMER_TYPES])
        self.type_filter_combo.currentTextChanged.connect(lambda _text: self._refresh())
        export_button = QPushButton("导出示例")
        export_button.setObjectName("SecondaryActionButton")
        export_button.setEnabled(False)
        self.quick_capture_button = QPushButton("快速录入")
        self.quick_capture_button.clicked.connect(lambda _checked=False: self.quick_capture_requested.emit())

        topbar_layout.addLayout(heading, 1)
        topbar_layout.addWidget(self.type_filter_combo)
        topbar_layout.addWidget(export_button)
        topbar_layout.addWidget(self.quick_capture_button)

        banner = QLabel("客户工作台原型  ·  仅展示一期字段，报价、合同、交付、回款等二期字段暂不进入首页。")
        banner.setObjectName("OverviewBanner")
        banner.setWordWrap(True)

        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(12)
        self.metric_value_labels: dict[str, QLabel] = {}
        for label, note in (
            ("潜客", "当前仍有真实潜在事项"),
            ("沟通中", "正在推进中的客户"),
            ("已合作", "已有合作或合同沉淀"),
            ("本周待跟进", "仍可推进的动作"),
        ):
            self.metrics_layout.addWidget(self._build_metric_card(label, note), 1)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)

        self.overview_panel = QFrame()
        self.overview_panel.setObjectName("WorkspacePanel")
        self.overview_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        overview_layout = QVBoxLayout(self.overview_panel)
        overview_layout.setContentsMargins(16, 16, 16, 16)
        overview_layout.setSpacing(10)
        overview_header = QHBoxLayout()
        overview_title = QVBoxLayout()
        overview_title.setSpacing(3)
        title_label = QPushButton("客户推进概览")
        title_label.setObjectName("SecondaryActionButton")
        title_label.setCursor(Qt.CursorShape.ArrowCursor)
        title_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hint_label = QLabel("先看当前客户处于什么阶段、最需要补什么、下一步准备做什么。")
        hint_label.setObjectName("SectionHint")
        overview_title.addWidget(title_label)
        overview_title.addWidget(hint_label)
        self.customer_count_label = QLabel("当前 0 个客户")
        self.customer_count_label.setObjectName("SoftBadge")
        overview_header.addLayout(overview_title, 1)
        overview_header.addWidget(self.customer_count_label)
        self.customer_grid = QGridLayout()
        self.customer_grid.setSpacing(10)
        overview_layout.addLayout(overview_header)
        overview_layout.addLayout(self.customer_grid)

        side_column = QVBoxLayout()
        side_column.setSpacing(14)
        self.follow_panel, self.follow_layout = self._build_side_panel("待跟进客户", "先看谁最该继续推进，以及下一步具体是什么。")
        self.missing_panel, self.missing_layout = self._build_side_panel("待补资料", "这些缺口会直接影响推进效率，优先补联系人、需求和预算线索。")
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
        detail_title = QLabel("当前客户详情速览")
        detail_title.setObjectName("SectionTitle")
        self.manual_edit_button = QPushButton("手动编辑此客户")
        self.manual_edit_button.setObjectName("SecondaryActionButton")
        self.manual_edit_button.setEnabled(False)
        self.manual_edit_button.clicked.connect(self._emit_edit_current_customer)
        self.ai_update_button = QPushButton("AI 更新此客户")
        self.ai_update_button.setObjectName("SecondaryActionButton")
        self.ai_update_button.setEnabled(False)
        self.ai_update_button.clicked.connect(self._emit_update_current_customer)
        detail_header.addWidget(detail_title)
        detail_header.addStretch(1)
        detail_header.addWidget(self.manual_edit_button)
        detail_header.addWidget(self.ai_update_button)
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(False)
        self.detail_browser.setMinimumHeight(170)
        self.detail_browser.setMaximumHeight(280)
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
        root.addWidget(banner)
        root.addLayout(self.metrics_layout)
        root.addLayout(workspace)
        root.addWidget(detail_card)
        root.addStretch(1)

    def set_focus_customers(self, records: list[CustomerRecord]) -> None:
        self._focus_records = _sort_customer_records(records)
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

    def show_customer_detail(self, detail: CustomerDetail | None) -> None:
        if detail is None:
            self._current_customer_name = ""
            self.manual_edit_button.setEnabled(False)
            self.ai_update_button.setEnabled(False)
            self.view_projects_button.setEnabled(False)
            self.detail_browser.setHtml("<p>请选择客户。</p>")
            self.set_related_projects([], "")
            return

        self._current_customer_name = detail.name
        self.manual_edit_button.setEnabled(True)
        self.ai_update_button.setEnabled(True)
        self.view_projects_button.setEnabled(detail.customer_type in PROJECT_CUSTOMER_TYPES)
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
        <h2>{escape(detail.name)}</h2>
        <p>{escape(detail.customer_type)} · {escape(detail.stage)} · {escape(detail.business_direction or '待补业务方向')}</p>
        <h3>当前需求</h3>
        <p>{escape(detail.current_need or '待补充')}</p>
        <h3>当前判断</h3>
        <p><b>当前重点：</b>{escape(detail.current_focus or '待补充')}</p>
        <p><b>下次动作：</b>{escape(detail.next_action or '待补充')}</p>
        <p><b>联系人：</b>{escape(detail.contact or '待补充')}</p>
        <p><b>联系电话：</b>{escape(detail.phone or '待补充')}</p>
        <p><b>微信号：</b>{escape(detail.wechat_id or '待补充')}</p>
        <p><b>主业文件路径：</b>{escape(detail.main_work_path or '待补充')}</p>
        <h3>默认甲方信息</h3>
        <p><b>收件联系人：</b>{escape(detail.party_a_contact or '待补充')}</p>
        <p><b>联系电话：</b>{escape(detail.party_a_phone or '待补充')}</p>
        <p><b>电子邮箱：</b>{escape(detail.party_a_email or '待补充')}</p>
        <p><b>通讯地址：</b>{escape(detail.party_a_address or '待补充')}</p>
        <h3>待归属审批提醒</h3>
        <p><b>当前数量：</b>{detail.pending_approval_count}</p>
        <ul>{pending_approval_html}</ul>
        <h3>最近沟通沉淀</h3>
        {communication_html}
        """
        self.detail_browser.setHtml(html)

    def set_related_projects(self, projects: list[ProjectRecord], customer_type: str) -> None:
        self._related_projects = sort_project_records(projects)
        _clear_layout(self.related_projects_layout)
        if customer_type == "网店店群客户":
            self.related_projects_layout.addWidget(self._side_item("一期未启用", "网店店群客户暂不进入客户项目管理。", "空状态"))
            return
        if not self._related_projects:
            empty_text = "当前 KA 客户还没有客户运营项目。" if customer_type == "网店KA客户" else "当前品牌下还没有同步到项目资料。"
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
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        title = QLabel(label)
        title.setObjectName("MetricLabel")
        value = QLabel("0")
        value.setObjectName("MetricValue")
        note_label = QLabel(note)
        note_label.setObjectName("SectionHint")
        note_label.setWordWrap(True)
        self.metric_value_labels[label] = value
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(note_label)
        return card

    def _build_side_panel(self, title: str, hint: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("WorkspacePanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)
        title_label = QPushButton(title)
        title_label.setObjectName("SecondaryActionButton")
        title_label.setCursor(Qt.CursorShape.ArrowCursor)
        title_label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hint_label = QLabel(hint)
        hint_label.setObjectName("SectionHint")
        hint_label.setWordWrap(True)
        items = QVBoxLayout()
        items.setSpacing(8)
        layout.addWidget(title_label)
        layout.addWidget(hint_label)
        layout.addLayout(items)
        return panel, items

    def _refresh(self) -> None:
        selected_type = self.type_filter_combo.currentText() if hasattr(self, "type_filter_combo") else ALL_CUSTOMERS_FILTER
        if selected_type == ALL_CUSTOMERS_FILTER:
            records = list(self._records)
        else:
            records = [record for record in self._records if record.customer_type == selected_type]
        records = _sort_customer_records(records)
        self._displayed_records = records
        if self._current_customer_name and not any(record.name == self._current_customer_name for record in records):
            self._current_customer_name = records[0].name if records else ""
            if self._current_customer_name:
                self.customer_selected.emit(self._current_customer_name)
            else:
                self.show_customer_detail(None)

        self._refresh_meta(selected_type)
        self._refresh_metrics(records)
        self._refresh_customer_cards(records)
        self._refresh_sidebars(records)

    def _refresh_meta(self, selected_type: str) -> None:
        latest_update = max(
            (record.updated_at for record in self._records if _sortable_updated_at(record.updated_at)),
            default="待同步",
        )
        filter_label = selected_type
        self.meta_label.setText(f"更新时间：{latest_update} · 当前筛选：{filter_label} · 一期口径：使用客户页与客户总表字段")

    def _refresh_metrics(self, records: list[CustomerRecord]) -> None:
        counts = {stage: sum(1 for record in records if record.stage == stage) for stage in CUSTOMER_STAGES}
        follow_count = sum(1 for record in records if record.stage != "暂缓" and bool(record.next_action))
        self.metric_value_labels["潜客"].setText(str(counts.get("潜客", 0)))
        self.metric_value_labels["沟通中"].setText(str(counts.get("沟通中", 0)))
        self.metric_value_labels["已合作"].setText(str(counts.get("已合作", 0)))
        self.metric_value_labels["本周待跟进"].setText(str(follow_count))

    def _refresh_customer_cards(self, records: list[CustomerRecord]) -> None:
        _clear_layout(self.customer_grid)
        self.customer_count_label.setText(f"当前 {len(records)} 个真实客户")
        if not records:
            empty = QLabel("当前筛选下暂无客户。")
            empty.setObjectName("EmptyState")
            self.customer_grid.addWidget(empty, 0, 0)
            return
        for index, record in enumerate(records):
            card = self._build_customer_card(record)
            row = index // 2
            column = index % 2
            self.customer_grid.addWidget(card, row, column)
        self.customer_grid.setColumnStretch(0, 1)
        self.customer_grid.setColumnStretch(1, 1)

    def _refresh_sidebars(self, records: list[CustomerRecord]) -> None:
        _clear_layout(self.follow_layout)
        _clear_layout(self.missing_layout)
        follow_records = [record for record in records if record.stage != "暂缓" and record.next_action][:3]
        if not follow_records:
            self.follow_layout.addWidget(self._side_item("暂无待跟进", "当前筛选下没有明确下一步。", "看右栏"))
        for record in follow_records:
            self.follow_layout.addWidget(self._side_item(record.name, record.next_action, record.stage))

        missing_items = self._missing_items(records)[:4]
        if not missing_items:
            self.missing_layout.addWidget(self._side_item("资料完整度不错", "当前筛选下没有明显的一期字段缺口。", "完成"))
        for title, body, tag in missing_items:
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
            if record.customer_type == "网店店群客户" and (not record.shop_scale or record.shop_scale == "待补充"):
                missing.append("店铺规模")
            if record.customer_type == "网店KA客户" and (not record.shop_scale or record.shop_scale == "待补充"):
                missing.append("店铺/产品状态")
            if missing:
                items.append((f"{record.name} · {' / '.join(missing[:2])}", "这些信息会影响下一次推进和判断。", "待补"))
        return items

    def _side_item(self, title: str, body: str, tag: str) -> QFrame:
        item = QFrame()
        item.setObjectName("SideItem")
        layout = QVBoxLayout(item)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(5)
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("SideItemTitle")
        title_label.setWordWrap(True)
        tag_label = QLabel(tag)
        tag_label.setObjectName("SoftBadge")
        header.addWidget(title_label, 1)
        header.addWidget(tag_label)
        body_label = QLabel(body)
        body_label.setObjectName("SectionHint")
        body_label.setWordWrap(True)
        layout.addLayout(header)
        layout.addWidget(body_label)
        return item

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
        self._refresh_customer_cards(self._displayed_records)
        self.customer_selected.emit(name)

    def _emit_update_current_customer(self) -> None:
        if self._current_customer_name:
            self.update_customer_requested.emit(self._current_customer_name)

    def _emit_edit_current_customer(self) -> None:
        if self._current_customer_name:
            self.edit_customer_requested.emit(self._current_customer_name)

    def _emit_view_current_customer_projects(self) -> None:
        if self._current_customer_name:
            self.view_customer_projects_requested.emit(self._current_customer_name)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
        widget = item.widget()
        if widget is not None:
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


def _sortable_updated_at(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized or normalized in {"待同步", "待补充", "待确认", "待补日期"}:
        return ""
    return normalized
