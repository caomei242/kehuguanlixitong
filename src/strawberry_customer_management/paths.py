from __future__ import annotations

from pathlib import Path


OBSIDIAN_CUSTOMER_ROOT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "iCloud~md~obsidian"
    / "Documents"
    / "主业助手"
    / "客户管理"
)

MAIN_WORK_ROOT = Path.home() / "Desktop" / "主业"


def default_customer_root() -> Path:
    return OBSIDIAN_CUSTOMER_ROOT


def default_main_work_root() -> Path:
    return MAIN_WORK_ROOT

