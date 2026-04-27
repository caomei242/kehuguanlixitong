from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from strawberry_customer_management.ai_capture import MINIMAX_BASE_URL, MINIMAX_DEFAULT_MODEL

from strawberry_customer_management.paths import default_approval_inbox_root, default_customer_root, default_main_work_root, default_project_root


class ConfigStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return default_config()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return default_config()
        if not isinstance(payload, dict):
            return default_config()
        merged = default_config()
        merged.update(payload)
        return merged

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def default_config() -> dict[str, Any]:
    return {
        "customer_root": str(default_customer_root()),
        "project_root": str(default_project_root()),
        "main_work_root": str(default_main_work_root()),
        "approval_inbox_root": str(default_approval_inbox_root()),
        "ai_provider": "minimax",
        "minimax_api_key": "",
        "minimax_model": MINIMAX_DEFAULT_MODEL,
        "minimax_base_url": MINIMAX_BASE_URL,
    }


def default_config_path() -> Path:
    return Path.home() / ".config" / "strawberry-customer-management" / "config.json"


def resolved_minimax_api_key(config: dict[str, Any]) -> str:
    return os.environ.get("MINIMAX_API_KEY", "").strip() or str(config.get("minimax_api_key", "")).strip()
