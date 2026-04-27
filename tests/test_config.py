from __future__ import annotations

from strawberry_customer_management.config import default_config


def test_default_config_contains_minimax_settings_without_secret():
    config = default_config()

    assert config["ai_provider"] == "minimax"
    assert config["minimax_model"] == "MiniMax-M2.7"
    assert config["minimax_base_url"] == "https://api.minimaxi.com/v1"
    assert config["minimax_api_key"] == ""
    assert config["customer_root"].endswith("项目管理/草莓客户管理系统--主业/客户数据")
    assert config["project_root"].endswith("项目管理/草莓客户管理系统--主业/项目数据")
    assert config["approval_inbox_root"].endswith("主业/钉钉审批导入")
