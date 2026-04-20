from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strawberry_customer_management.paths import default_customer_root, default_main_work_root


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
        "main_work_root": str(default_main_work_root()),
    }


def default_config_path() -> Path:
    return Path.home() / ".config" / "strawberry-customer-management" / "config.json"

