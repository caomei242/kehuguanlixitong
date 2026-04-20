from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import CustomerDetail, CustomerRecord


class OverviewPage(QWidget):
    customer_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        focus_card = QFrame()
        focus_card.setObjectName("FocusCard")
        focus_layout = QVBoxLayout(focus_card)
        focus_layout.setContentsMargins(18, 18, 18, 18)
        focus_layout.setSpacing(10)

        focus_title = QLabel("本周重点跟进")
        focus_title.setObjectName("SectionTitle")
        focus_hint = QLabel("优先看清谁在推进、目前卡在哪里、下一步做什么。")
        focus_hint.setObjectName("SectionHint")
        self.focus_items_layout = QHBoxLayout()
        self.focus_items_layout.setSpacing(10)
        self.focus_items_layout.addStretch(1)

        focus_layout.addWidget(focus_title)
        focus_layout.addWidget(focus_hint)
        focus_layout.addLayout(self.focus_items_layout)

        body = QHBoxLayout()
        body.setSpacing(16)

        list_card = QFrame()
        list_card.setObjectName("CardFrame")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(18, 18, 18, 18)
        list_layout.setSpacing(10)
        list_title = QLabel("客户列表")
        list_title.setObjectName("SectionTitle")
        self.customer_list = QListWidget()
        self.customer_list.currentItemChanged.connect(self._handle_item_change)
        list_layout.addWidget(list_title)
        list_layout.addWidget(self.customer_list, 1)

        detail_card = QFrame()
        detail_card.setObjectName("DetailCard")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(10)
        detail_title = QLabel("客户详情")
        detail_title.setObjectName("SectionTitle")
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(False)
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_browser, 1)

        body.addWidget(list_card, 1)
        body.addWidget(detail_card, 2)

        root.addWidget(focus_card)
        root.addLayout(body, 1)

        self._records: list[CustomerRecord] = []

    def set_focus_customers(self, records: list[CustomerRecord]) -> None:
        while self.focus_items_layout.count():
            item = self.focus_items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not records:
            label = QLabel("暂无重点客户")
            label.setObjectName("FocusItem")
            self.focus_items_layout.addWidget(label)
            self.focus_items_layout.addStretch(1)
            return
        for record in records:
            label = QLabel(f"{record.name} · {record.stage} · {record.next_action or '待补下一步'}")
            label.setObjectName("FocusItem")
            label.setWordWrap(True)
            self.focus_items_layout.addWidget(label)
        self.focus_items_layout.addStretch(1)

    def set_customers(self, records: list[CustomerRecord], selected_name: str | None = None) -> None:
        self._records = list(records)
        self.customer_list.clear()
        selected_row = 0
        for index, record in enumerate(records):
            item = QListWidgetItem(f"{record.name}\n{record.customer_type} · {record.stage}")
            item.setData(Qt.ItemDataRole.UserRole, record.name)
            self.customer_list.addItem(item)
            if selected_name and record.name == selected_name:
                selected_row = index
        if records:
            self.customer_list.setCurrentRow(selected_row)
        else:
            self.detail_browser.setHtml("<p>暂无客户数据。</p>")

    def show_customer_detail(self, detail: CustomerDetail | None) -> None:
        if detail is None:
            self.detail_browser.setHtml("<p>请选择客户。</p>")
            return
        communication_html = "".join(
            (
                f"<h4>{escape(entry.entry_date)}</h4>"
                f"<p><b>结论：</b>{escape(entry.summary or '待补充')}</p>"
                f"<p><b>新增：</b>{escape(entry.new_info or '待补充')}</p>"
                f"<p><b>风险：</b>{escape(entry.risk or '待补充')}</p>"
                f"<p><b>下一步：</b>{escape(entry.next_step or '待补充')}</p>"
            )
            for entry in detail.communication_entries
        ) or "<p>暂无沟通沉淀。</p>"
        html = f"""
        <h2>{escape(detail.name)}</h2>
        <p>{escape(detail.customer_type)} · {escape(detail.stage)} · {escape(detail.business_direction or '待补业务方向')}</p>
        <h3>当前需求</h3>
        <p>{escape(detail.current_need or '待补充')}</p>
        <h3>当前判断</h3>
        <p><b>当前重点：</b>{escape(detail.current_focus or '待补充')}</p>
        <p><b>下次动作：</b>{escape(detail.next_action or '待补充')}</p>
        <p><b>联系人：</b>{escape(detail.contact or '待补充')}</p>
        <p><b>主业文件路径：</b>{escape(detail.main_work_path or '待补充')}</p>
        <h3>沟通沉淀</h3>
        {communication_html}
        <h3>补充信息</h3>
        <p><b>所属主体：</b>{escape(detail.company or '待补充')}</p>
        <p><b>关键规模：</b>{escape(detail.shop_scale or '待补充')}</p>
        <p><b>预算线索：</b>{escape(detail.budget_clue or '待补充')}</p>
        """
        self.detail_browser.setHtml(html)

    def _handle_item_change(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        if name:
            self.customer_selected.emit(str(name))

