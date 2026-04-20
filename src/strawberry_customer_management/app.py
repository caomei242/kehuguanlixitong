from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from strawberry_customer_management.config import ConfigStore, default_config_path
from strawberry_customer_management.ui.app_icon import load_app_icon
from strawberry_customer_management.ui.main_window import MainWindow
from strawberry_customer_management.ui.theme import apply_theme


APP_NAME = "草莓客户管理系统"


def build_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(load_app_icon())
    apply_theme(app)
    return app


def build_main_window(config_path: Path | None = None) -> MainWindow:
    config_store = ConfigStore(config_path or default_config_path())
    return MainWindow(config_store=config_store)


def main() -> int:
    app = build_app()
    window = build_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
