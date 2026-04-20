from __future__ import annotations

import os

from strawberry_customer_management.app import build_app
from strawberry_customer_management.config import ConfigStore
from strawberry_customer_management.ui.main_window import MainWindow


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_window_instantiates_with_empty_customer_root(tmp_path):
    customer_root = tmp_path / "客户管理"
    customer_root.mkdir()
    config_path = tmp_path / "config.json"
    config_store = ConfigStore(config_path)
    config_store.save(
        {
            "customer_root": str(customer_root),
            "main_work_root": str(tmp_path / "主业"),
        }
    )

    app = build_app()
    window = MainWindow(config_store=config_store)

    assert window.windowTitle() == "草莓客户管理系统"
    assert window.nav.count() == 3
    window.close()
    app.processEvents()
