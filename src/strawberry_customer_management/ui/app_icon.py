from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

from PySide6.QtGui import QIcon


def app_icon_path() -> str:
    return str(files("strawberry_customer_management.assets").joinpath("app_icon.png"))


@lru_cache(maxsize=1)
def load_app_icon() -> QIcon:
    return QIcon(app_icon_path())

