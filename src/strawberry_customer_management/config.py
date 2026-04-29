from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from strawberry_customer_management.ai_capture import MINIMAX_BASE_URL, MINIMAX_DEFAULT_MODEL
from strawberry_customer_management.models import CUSTOMER_TYPES, SECONDARY_TAGS

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
        merged["customer_types"] = normalize_option_list(merged.get("customer_types"), CUSTOMER_TYPES)
        merged["secondary_tags"] = normalize_option_list(merged.get("secondary_tags"), SECONDARY_TAGS)
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
        "customer_types": list(CUSTOMER_TYPES),
        "secondary_tags": list(SECONDARY_TAGS),
    }


def default_config_path() -> Path:
    return Path.home() / ".config" / "strawberry-customer-management" / "config.json"


def resolved_minimax_api_key(config: dict[str, Any]) -> str:
    return os.environ.get("MINIMAX_API_KEY", "").strip() or str(config.get("minimax_api_key", "")).strip()


def normalize_option_list(value: Any, fallback: tuple[str, ...] | list[str]) -> list[str]:
    raw_items: list[str] = []
    if isinstance(value, str):
        raw_items = value.splitlines()
    elif isinstance(value, (list, tuple)):
        raw_items = [str(item) for item in value]
    else:
        raw_items = list(fallback)

    options: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        for item in _split_option_item(raw_item):
            if item in seen:
                continue
            options.append(item)
            seen.add(item)
    if not options:
        return list(fallback)
    return options


def _split_option_item(value: str) -> list[str]:
    cleaned = value.strip().lstrip("-*•").strip()
    if not cleaned:
        return []
    return [part.strip() for part in cleaned.replace("，", "/").replace(",", "/").replace("、", "/").split("/") if part.strip()]
