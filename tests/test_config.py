from __future__ import annotations

from strawberry_customer_management.config import default_config


def test_default_config_contains_minimax_settings_without_secret():
    config = default_config()

    assert config["ai_provider"] == "minimax"
    assert config["minimax_model"] == "MiniMax-M2.7-highspeed"
    assert config["minimax_base_url"] == "https://api.minimax.io/v1"
    assert config["minimax_api_key"] == ""
