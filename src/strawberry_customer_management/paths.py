from __future__ import annotations

from pathlib import Path


OBSIDIAN_CUSTOMER_ROOT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "iCloud~md~obsidian"
    / "Documents"
    / "项目管理"
    / "草莓客户管理系统--主业"
    / "客户数据"
)

OBSIDIAN_PROJECT_ROOT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "iCloud~md~obsidian"
    / "Documents"
    / "项目管理"
    / "草莓客户管理系统--主业"
    / "项目数据"
)

OBSIDIAN_PERSON_ROOT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "iCloud~md~obsidian"
    / "Documents"
    / "项目管理"
    / "草莓客户管理系统--主业"
    / "人员数据"
)

OBSIDIAN_DEVELOPMENT_LOG_ROOT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "iCloud~md~obsidian"
    / "Documents"
    / "项目管理"
    / "草莓客户管理系统--主业"
    / "开发"
)

MAIN_WORK_ROOT = Path.home() / "Desktop" / "主业"
APPROVAL_INBOX_ROOT = MAIN_WORK_ROOT / "钉钉审批导入"


def default_customer_root() -> Path:
    return OBSIDIAN_CUSTOMER_ROOT


def default_main_work_root() -> Path:
    return MAIN_WORK_ROOT


def default_project_root() -> Path:
    return OBSIDIAN_PROJECT_ROOT


def default_person_root() -> Path:
    return OBSIDIAN_PERSON_ROOT


def default_development_log_root() -> Path:
    return OBSIDIAN_DEVELOPMENT_LOG_ROOT


def default_approval_inbox_root() -> Path:
    return APPROVAL_INBOX_ROOT
