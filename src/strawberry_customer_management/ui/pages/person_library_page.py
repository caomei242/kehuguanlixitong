from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from strawberry_customer_management.models import PERSON_GENDERS, PERSON_SIDES, PersonDetail, PersonDraft, PersonRecord


ALL_FILTER = "全部"


class PersonLibraryPage(QWidget):
    person_selected = Signal(str)
    overview_requested = Signal()
    quick_capture_requested = Signal()
    save_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("PersonLibraryPage")
        self._records: list[PersonRecord] = []
        self._displayed_records: list[PersonRecord] = []
        self._current_person_name = ""
        self._current_detail: PersonDetail | None = None
        self._is_editing = False

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
        topbar_layout.setContentsMargins(18, 16, 18, 16)
        topbar_layout.setSpacing(14)

        heading = QVBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(3)
        title = QLabel("关系人库")
        title.setObjectName("SectionTitle")
        self.meta_label = QLabel("把主业里反复出现的人沉淀下来，项目页只放人名和关系。")
        self.meta_label.setObjectName("SectionHint")
        self.meta_label.setWordWrap(True)
        heading.addWidget(title)
        heading.addWidget(self.meta_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索人名 / 组织 / 品牌 / 关系")
        self.search_edit.textChanged.connect(lambda _text: self._refresh())
        self.side_combo = QComboBox()
        self.side_combo.addItems([ALL_FILTER, *PERSON_SIDES])
        self.side_combo.currentTextChanged.connect(lambda _text: self._refresh())
        self.quick_capture_button = QPushButton("快速录入")
        self.quick_capture_button.clicked.connect(lambda _checked=False: self.quick_capture_requested.emit())
        self.overview_button = QPushButton("返回总览")
        self.overview_button.setObjectName("SecondaryActionButton")
        self.overview_button.clicked.connect(lambda _checked=False: self.overview_requested.emit())

        topbar_layout.addLayout(heading, 1)
        topbar_layout.addWidget(self.search_edit, 1)
        topbar_layout.addWidget(self.side_combo)
        topbar_layout.addWidget(self.quick_capture_button)
        topbar_layout.addWidget(self.overview_button)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)

        list_panel = QFrame()
        list_panel.setObjectName("WorkspacePanel")
        list_panel.setMinimumWidth(360)
        list_panel.setMaximumWidth(460)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(10)
        list_header = QHBoxLayout()
        list_title = QLabel("人员列表")
        list_title.setObjectName("SectionTitle")
        self.count_label = QLabel("当前 0 个人")
        self.count_label.setObjectName("SoftBadge")
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        list_header.addWidget(self.count_label)
        list_body = QWidget()
        self.person_grid = QGridLayout(list_body)
        self.person_grid.setContentsMargins(0, 0, 0, 0)
        self.person_grid.setSpacing(10)
        self.person_list_scroll = QScrollArea()
        self.person_list_scroll.setObjectName("PersonListScroll")
        self.person_list_scroll.setWidgetResizable(True)
        self.person_list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.person_list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.person_list_scroll.setWidget(list_body)
        list_layout.addLayout(list_header)
        list_layout.addWidget(self.person_list_scroll, 1)

        detail_panel = QFrame()
        detail_panel.setObjectName("DetailCard")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(16, 16, 16, 16)
        detail_layout.setSpacing(12)
        detail_header = QHBoxLayout()
        detail_title_box = QVBoxLayout()
        detail_title_box.setContentsMargins(0, 0, 0, 0)
        detail_title_box.setSpacing(3)
        self.name_label = QLabel("人员档案")
        self.name_label.setObjectName("SectionTitle")
        self.detail_meta_label = QLabel("选择一个人查看")
        self.detail_meta_label.setObjectName("SectionHint")
        self.detail_meta_label.setWordWrap(True)
        detail_title_box.addWidget(self.name_label)
        detail_title_box.addWidget(self.detail_meta_label)
        detail_header.addLayout(detail_title_box, 1)
        self.edit_button = QPushButton("编辑")
        self.edit_button.setObjectName("InlineActionButton")
        self.edit_button.setEnabled(False)
        self.save_button = QPushButton("保存")
        self.save_button.setObjectName("InlineActionButton")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("SecondaryActionButton")
        self.edit_button.clicked.connect(lambda _checked=False: self._set_editing(True))
        self.save_button.clicked.connect(lambda _checked=False: self._emit_save_requested())
        self.cancel_button.clicked.connect(lambda _checked=False: self._cancel_editing())
        detail_header.addWidget(self.edit_button)
        detail_header.addWidget(self.save_button)
        detail_header.addWidget(self.cancel_button)
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(False)
        self.detail_browser.setMinimumHeight(380)
        self.edit_panel = self._build_edit_panel()
        detail_layout.addLayout(detail_header)
        detail_layout.addWidget(self.detail_browser)
        detail_layout.addWidget(self.edit_panel)
        self._set_editing(False)

        workspace.addWidget(list_panel, 4)
        workspace.addWidget(detail_panel, 9)

        root.addWidget(topbar)
        root.addLayout(workspace)
        root.addStretch(1)

    def set_people(self, records: list[PersonRecord], selected_name: str | None = None) -> None:
        self._records = sorted(records, key=lambda record: (record.updated_at or "", record.name), reverse=True)
        if selected_name:
            self._current_person_name = selected_name
        elif self._current_person_name and any(record.name == self._current_person_name for record in self._records):
            pass
        elif self._records:
            self._current_person_name = self._records[0].name
        else:
            self._current_person_name = ""
        self._refresh()
        if self._current_person_name:
            self.person_selected.emit(self._current_person_name)
        else:
            self.show_person_detail(None)

    def displayed_person_names(self) -> list[str]:
        return [record.name for record in self._displayed_records]

    def show_person_detail(self, detail: PersonDetail | None) -> None:
        self._current_detail = detail
        if detail is None:
            self.name_label.setText("人员档案")
            self.detail_meta_label.setText("选择一个人查看")
            self.detail_browser.setHtml("")
            self.edit_button.setEnabled(False)
            self._set_editing(False)
            return
        self._current_person_name = detail.name
        self.edit_button.setEnabled(True)
        self.name_label.setText(detail.name)
        self.detail_meta_label.setText(
            " · ".join(part for part in (detail.gender, detail.side, detail.organization, detail.common_relation) if part)
        )
        self._populate_edit_fields(detail)
        self._set_editing(False)
        project_rows = "".join(
            "<tr>"
            f"<td>{escape(link.side or '待补')}</td>"
            f"<td>{escape(link.relation or '待补')}</td>"
            f"<td>{escape(link.customer_name or '待补')}</td>"
            f"<td>{escape(link.project_name or '待补')}</td>"
            "</tr>"
            for link in detail.project_links
        ) or "<tr><td colspan='4'>暂无关联项目</td></tr>"
        customers = "、".join(escape(item) for item in detail.linked_customers) or "暂无关联客户"
        notes = escape(detail.relation_notes or "待补关系沉淀").replace("\n", "<br>")
        contact_rows = "".join(
            row
            for row in (
                _info_row("性别", detail.gender or "待判断"),
                _info_row("所属方", detail.side or "待补"),
                _info_row("所属组织", detail.organization or "待补"),
                _info_row("所属品牌", detail.brand or "待补"),
                _info_row("常见关系", detail.common_relation or "待补"),
                _info_row("联系方式", detail.contact or "待补"),
                _info_row("电话", detail.phone or "待补"),
                _info_row("微信", detail.wechat_id or "待补"),
            )
        )
        self.detail_browser.setHtml(
            f"""
            <div style="font-family:'PingFang SC','Microsoft YaHei','Noto Sans SC',sans-serif; color:#20304a; line-height:1.55;">
              <table width="100%" cellspacing="0" cellpadding="8" style="border-collapse:separate;">
                <tr>
                  <td width="48%" valign="top" style="background:#f8fbff;border:1px solid #e2eaf6;border-radius:16px;">
                    <div style="font-size:12px;color:#6b7892;font-weight:800;margin-bottom:6px;">基础档案</div>
                    <table width="100%" cellspacing="0" cellpadding="4">{contact_rows}</table>
                  </td>
                  <td width="52%" valign="top" style="background:#fff;border:1px solid #e2eaf6;border-radius:16px;">
                    <div style="font-size:12px;color:#6b7892;font-weight:800;margin-bottom:6px;">我对这个人的判断</div>
                    <div style="font-size:16px;font-weight:850;margin-bottom:8px;">{escape(detail.judgement or '待补充')}</div>
                    <div><b>适合：</b>{escape(detail.suitable_for or '待补充')}</div>
                    <div><b>不适合：</b>{escape(detail.not_suitable_for or '待补充')}</div>
                    <div><b>在意：</b>{escape(detail.likes or '待补充')}</div>
                    <div><b>雷区：</b>{escape(detail.dislikes or '待补充')}</div>
                  </td>
                </tr>
              </table>
              <section style="background:#ffffff;border:1px solid #e2eaf6;border-radius:16px;padding:12px;margin-top:10px;">
                <div style="font-size:12px;color:#6b7892;font-weight:800;margin-bottom:6px;">关联客户</div>
                <div>{customers}</div>
              </section>
              <section style="background:#ffffff;border:1px solid #e2eaf6;border-radius:16px;padding:12px;margin-top:10px;">
                <div style="font-size:12px;color:#6b7892;font-weight:800;margin-bottom:8px;">关联项目</div>
                <table width="100%" cellspacing="0" cellpadding="6" style="border-collapse:collapse;">
                  <tr style="color:#6b7892;font-weight:800;"><td>所属方</td><td>关系</td><td>客户</td><td>项目</td></tr>
                  {project_rows}
                </table>
              </section>
              <section style="background:#ffffff;border:1px solid #e2eaf6;border-radius:16px;padding:12px;margin-top:10px;">
                <div style="font-size:12px;color:#6b7892;font-weight:800;margin-bottom:6px;">关系沉淀</div>
                <div>{notes}</div>
              </section>
            </div>
            """
        )

    def _build_edit_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("WorkspacePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.gender_edit = QComboBox()
        self.gender_edit.addItems(PERSON_GENDERS)
        self.person_side_edit = QComboBox()
        self.person_side_edit.addItems(PERSON_SIDES)
        self.organization_edit = QLineEdit()
        self.brand_edit = QLineEdit()
        self.common_relation_edit = QLineEdit()
        self.contact_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.wechat_edit = QLineEdit()
        self.judgement_edit = _compact_text_edit()
        self.suitable_for_edit = _compact_text_edit()
        self.not_suitable_for_edit = _compact_text_edit()
        self.likes_edit = _compact_text_edit()
        self.dislikes_edit = _compact_text_edit()
        self.relation_notes_edit = _compact_text_edit(110)

        base_row = QHBoxLayout()
        base_row.setSpacing(14)
        left_form = _compact_form()
        right_form = _compact_form()
        left_form.addRow("性别", self.gender_edit)
        left_form.addRow("所属方", self.person_side_edit)
        left_form.addRow("所属组织", self.organization_edit)
        left_form.addRow("所属品牌", self.brand_edit)
        right_form.addRow("常见关系", self.common_relation_edit)
        right_form.addRow("联系方式", self.contact_edit)
        right_form.addRow("电话", self.phone_edit)
        right_form.addRow("微信", self.wechat_edit)
        base_row.addLayout(left_form, 1)
        base_row.addLayout(right_form, 1)

        text_row = QHBoxLayout()
        text_row.setSpacing(14)
        left_text_form = _compact_form()
        right_text_form = _compact_form()
        left_text_form.addRow("判断", self.judgement_edit)
        left_text_form.addRow("适合找他/她", self.suitable_for_edit)
        left_text_form.addRow("不适合找他/她", self.not_suitable_for_edit)
        right_text_form.addRow("喜欢/在意", self.likes_edit)
        right_text_form.addRow("不喜欢/雷区", self.dislikes_edit)
        right_text_form.addRow("关系沉淀", self.relation_notes_edit)
        text_row.addLayout(left_text_form, 1)
        text_row.addLayout(right_text_form, 1)

        layout.addLayout(base_row)
        layout.addLayout(text_row)
        return panel

    def _populate_edit_fields(self, detail: PersonDetail) -> None:
        self._set_combo_value(self.gender_edit, detail.gender or "待判断")
        self._set_combo_value(self.person_side_edit, detail.side or PERSON_SIDES[0])
        self.organization_edit.setText(detail.organization)
        self.brand_edit.setText(detail.brand)
        self.common_relation_edit.setText(detail.common_relation)
        self.contact_edit.setText(detail.contact)
        self.phone_edit.setText(detail.phone)
        self.wechat_edit.setText(detail.wechat_id)
        self.judgement_edit.setPlainText(detail.judgement)
        self.suitable_for_edit.setPlainText(detail.suitable_for)
        self.not_suitable_for_edit.setPlainText(detail.not_suitable_for)
        self.likes_edit.setPlainText(detail.likes)
        self.dislikes_edit.setPlainText(detail.dislikes)
        self.relation_notes_edit.setPlainText(detail.relation_notes)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        if value and combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    def _set_editing(self, editing: bool) -> None:
        self._is_editing = editing and self._current_detail is not None
        self.detail_browser.setVisible(not self._is_editing)
        self.edit_panel.setVisible(self._is_editing)
        self.edit_button.setVisible(not self._is_editing)
        self.save_button.setVisible(self._is_editing)
        self.cancel_button.setVisible(self._is_editing)

    def _cancel_editing(self) -> None:
        if self._current_detail is not None:
            self._populate_edit_fields(self._current_detail)
        self._set_editing(False)

    def _emit_save_requested(self) -> None:
        if self._current_detail is None:
            return
        draft = PersonDraft(
            name=self._current_detail.name,
            gender=self.gender_edit.currentText().strip() or "待判断",
            side=self.person_side_edit.currentText().strip(),
            organization=self.organization_edit.text().strip(),
            brand=self.brand_edit.text().strip(),
            common_relation=self.common_relation_edit.text().strip(),
            contact=self.contact_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            wechat_id=self.wechat_edit.text().strip(),
            linked_customers=list(self._current_detail.linked_customers),
            project_links=list(self._current_detail.project_links),
            judgement=self.judgement_edit.toPlainText().strip(),
            influence=self._current_detail.influence,
            suitable_for=self.suitable_for_edit.toPlainText().strip(),
            not_suitable_for=self.not_suitable_for_edit.toPlainText().strip(),
            likes=self.likes_edit.toPlainText().strip(),
            dislikes=self.dislikes_edit.toPlainText().strip(),
            relation_notes=self.relation_notes_edit.toPlainText().strip(),
        )
        self.save_requested.emit(draft)
        self._set_editing(False)

    def _refresh(self) -> None:
        keyword = self.search_edit.text().strip().lower()
        side = self.side_combo.currentText()
        records = list(self._records)
        if side and side != ALL_FILTER:
            records = [record for record in records if record.side == side]
        if keyword:
            records = [record for record in records if keyword in _search_blob(record)]
        self._displayed_records = records
        self.count_label.setText(f"当前 {len(records)} 个人")
        self.meta_label.setText(f"当前筛选 {len(records)} / 全部 {len(self._records)}")
        if self._current_person_name and not any(record.name == self._current_person_name for record in records):
            self._current_person_name = records[0].name if records else ""
            if self._current_person_name:
                self.person_selected.emit(self._current_person_name)
            else:
                self.show_person_detail(None)
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        _clear_layout(self.person_grid)
        if not self._displayed_records:
            empty = QLabel("暂无关系人。")
            empty.setObjectName("EmptyState")
            self.person_grid.addWidget(empty, 0, 0)
            return
        for index, record in enumerate(self._displayed_records):
            self.person_grid.addWidget(self._build_person_card(record), index, 0)

    def _build_person_card(self, record: PersonRecord) -> QFrame:
        card = QFrame()
        card.setObjectName("CustomerTileSelected" if record.name == self._current_person_name else "CustomerTile")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(13, 12, 13, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        name = QLabel(record.name)
        name.setObjectName("CustomerTileName")
        side = QLabel(record.side or "待补所属方")
        side.setObjectName("SoftBadge")
        header.addWidget(name, 1)
        header.addWidget(side)
        relation = QLabel(record.common_relation or record.organization or "待补关系")
        relation.setObjectName("CustomerTileNeed")
        relation.setWordWrap(True)
        meta = QLabel(" · ".join(part for part in (record.gender, record.brand, record.organization) if part))
        meta.setObjectName("CustomerTileMeta")
        meta.setWordWrap(True)
        linked = QLabel(f"客户：{'、'.join(record.linked_customers) or '待补'}")
        linked.setObjectName("CustomerTileMeta")
        linked.setWordWrap(True)
        view = QPushButton("查看")
        view.setObjectName("InlineActionButton")
        view.clicked.connect(lambda _checked=False, name=record.name: self._select_person(name))
        footer = QHBoxLayout()
        footer.addWidget(linked, 1)
        footer.addWidget(view)
        layout.addLayout(header)
        layout.addWidget(relation)
        layout.addWidget(meta)
        layout.addLayout(footer)
        return card

    def _select_person(self, name: str) -> None:
        self._current_person_name = name
        self._refresh_cards()
        self.person_selected.emit(name)


def _search_blob(record: PersonRecord) -> str:
    return " ".join(
        [
            record.name,
            record.gender,
            record.side,
            record.organization,
            record.brand,
            record.common_relation,
            " ".join(record.linked_customers),
            " ".join(record.linked_projects),
        ]
    ).lower()


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def _compact_form() -> QFormLayout:
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setSpacing(10)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return form


def _compact_text_edit(height: int = 76) -> QTextEdit:
    editor = QTextEdit()
    editor.setMinimumHeight(height)
    editor.setMaximumHeight(height)
    return editor


def _info_row(label: str, value: str) -> str:
    return (
        "<tr>"
        f"<td width='34%' style='color:#6b7892;font-weight:800;'>{escape(label)}</td>"
        f"<td style='font-weight:750;'>{escape(value)}</td>"
        "</tr>"
    )
