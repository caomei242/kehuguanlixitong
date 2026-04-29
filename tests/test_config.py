from __future__ import annotations

from strawberry_customer_management.config import default_config, normalize_option_list


def test_default_config_contains_minimax_settings_without_secret():
    config = default_config()

    assert config["ai_provider"] == "minimax"
    assert config["minimax_model"] == "MiniMax-M2.7"
    assert config["minimax_base_url"] == "https://api.minimaxi.com/v1"
    assert config["minimax_api_key"] == ""
    assert config["customer_root"].endswith("项目管理/草莓客户管理系统--主业/客户数据")
    assert config["project_root"].endswith("项目管理/草莓客户管理系统--主业/项目数据")
    assert config["approval_inbox_root"].endswith("主业/钉钉审批导入")
    assert config["customer_types"] == ["品牌客户", "网店KA客户", "网店店群客户", "博主"]
    assert config["secondary_tags"][:4] == ["小时达", "微信", "AI商品图", "AI详情页"]


def test_normalize_option_list_splits_combined_channel_tags():
    assert normalize_option_list(["小时达/微信", "AI商品图", "AI商品图"], ["兜底"]) == ["小时达", "微信", "AI商品图"]
