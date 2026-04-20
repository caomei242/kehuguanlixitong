from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SettingsPage(QWidget):
    save_requested = Signal(object)
    refresh_requested = Signal()
    validate_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

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

        header = QLabel("设置")
        header.setObjectName("SectionTitle")
        hint = QLabel("这里主要确认 Obsidian 客户管理路径和主业文件根路径是否正确。")
        hint.setObjectName("SectionHint")

        card = QFrame()
        card.setObjectName("SettingsCard")
        form = QFormLayout(card)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)

        self.customer_root_edit = QLineEdit()
        self.main_work_root_edit = QLineEdit()
        self.minimax_api_key_edit = QLineEdit()
        self.minimax_api_key_edit.setEchoMode(QLineEdit.Password)
        self.minimax_model_edit = QLineEdit()
        self.minimax_base_url_edit = QLineEdit()
        form.addRow("客户管理根路径", self.customer_root_edit)
        form.addRow("主业文件根路径", self.main_work_root_edit)
        form.addRow("MiniMax API Key", self.minimax_api_key_edit)
        form.addRow("MiniMax 模型", self.minimax_model_edit)
        form.addRow("MiniMax Base URL", self.minimax_base_url_edit)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self._emit_save)
        refresh_button = QPushButton("刷新数据")
        refresh_button.setObjectName("SecondaryActionButton")
        refresh_button.clicked.connect(self.refresh_requested.emit)
        validate_button = QPushButton("校验路径")
        validate_button.setObjectName("SecondaryActionButton")
        validate_button.clicked.connect(self.validate_requested.emit)
        actions.addWidget(save_button)
        actions.addWidget(refresh_button)
        actions.addWidget(validate_button)
        actions.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionHint")

        root.addWidget(header)
        root.addWidget(hint)
        root.addWidget(card)
        root.addLayout(actions)
        root.addWidget(self.status_label)
        root.addStretch(1)

    def set_values(
        self,
        customer_root: str,
        main_work_root: str,
        minimax_api_key: str = "",
        minimax_model: str = "",
        minimax_base_url: str = "",
    ) -> None:
        self.customer_root_edit.setText(customer_root)
        self.main_work_root_edit.setText(main_work_root)
        self.minimax_api_key_edit.setText(minimax_api_key)
        self.minimax_model_edit.setText(minimax_model)
        self.minimax_base_url_edit.setText(minimax_base_url)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _emit_save(self) -> None:
        self.save_requested.emit(
            {
                "customer_root": self.customer_root_edit.text().strip(),
                "main_work_root": self.main_work_root_edit.text().strip(),
                "ai_provider": "minimax",
                "minimax_api_key": self.minimax_api_key_edit.text().strip(),
                "minimax_model": self.minimax_model_edit.text().strip(),
                "minimax_base_url": self.minimax_base_url_edit.text().strip(),
            }
        )
