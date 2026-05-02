from __future__ import annotations

import os
import re

from PySide6.QtGui import QColor, QPalette


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _brightness(color: QColor) -> float:
    return (0.299 * color.red()) + (0.587 * color.green()) + (0.114 * color.blue())


def _selector_block(stylesheet: str, selector: str) -> str:
    for match in re.finditer(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", stylesheet):
        selectors = [item.strip() for item in match.group("selectors").split(",")]
        if selector in selectors:
            return match.group("body")
    raise AssertionError(f"missing stylesheet selector: {selector}")


def test_app_module_imports():
    import strawberry_customer_management.app as app

    assert app.APP_NAME == "草莓客户管理系统"


def test_build_app_uses_light_global_palette_under_offscreen_qt():
    from strawberry_customer_management.app import build_app

    app = build_app()
    palette = app.palette()

    light_background_roles = {
        "Window": QPalette.ColorRole.Window,
        "Base": QPalette.ColorRole.Base,
        "AlternateBase": QPalette.ColorRole.AlternateBase,
        "Button": QPalette.ColorRole.Button,
        "ToolTipBase": QPalette.ColorRole.ToolTipBase,
    }
    dark_text_roles = {
        "Text": QPalette.ColorRole.Text,
        "ButtonText": QPalette.ColorRole.ButtonText,
        "ToolTipText": QPalette.ColorRole.ToolTipText,
    }

    for name, role in light_background_roles.items():
        color = palette.color(role)
        assert _brightness(color) >= 220, f"{name} should stay light, got {color.name()}"

    for name, role in dark_text_roles.items():
        color = palette.color(role)
        assert _brightness(color) <= 100, f"{name} should stay dark, got {color.name()}"

    highlight = palette.color(QPalette.ColorRole.Highlight)
    highlighted_text = palette.color(QPalette.ColorRole.HighlightedText)
    assert 70 <= _brightness(highlight) <= 190, f"Highlight should be a mid-tone accent, got {highlight.name()}"
    assert _brightness(highlighted_text) >= 220, f"HighlightedText should be light, got {highlighted_text.name()}"

    contrast_pairs = (
        (QPalette.ColorRole.Base, QPalette.ColorRole.Text),
        (QPalette.ColorRole.Button, QPalette.ColorRole.ButtonText),
        (QPalette.ColorRole.ToolTipBase, QPalette.ColorRole.ToolTipText),
        (QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Highlight),
    )
    for light_role, dark_role in contrast_pairs:
        assert _brightness(palette.color(light_role)) - _brightness(palette.color(dark_role)) >= 100


def test_build_app_stylesheet_contains_dark_mode_leak_guards():
    from strawberry_customer_management.app import build_app

    stylesheet = build_app().styleSheet()

    selector_expectations = {
        "QToolTip": ("background:", "color:"),
        "QAbstractScrollArea::viewport": ("background:",),
        "QTabWidget::pane": ("background:",),
        "QTabBar": ("background:",),
        "QSplitter::handle": ("background:",),
        "QComboBox QAbstractItemView": ("background:", "color:", "selection-background-color:"),
    }
    for selector, fragments in selector_expectations.items():
        block = _selector_block(stylesheet, selector)
        for fragment in fragments:
            assert fragment in block, f"{selector} should include {fragment}"
