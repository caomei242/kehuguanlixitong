from __future__ import annotations

import json

import pytest

from strawberry_customer_management.ai_capture import (
    AICaptureError,
    MINIMAX_BASE_URL,
    MINIMAX_GLOBAL_BASE_URL,
    MiniMaxCaptureClient,
)


class FakeMiniMaxTransport:
    def __init__(self, payload: dict):
        self.payload = payload
        self.requests: list[dict] = []

    def post_json(self, url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        self.requests.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        return self.payload


def minimax_response(content: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                }
            }
        ]
    }


def test_minimax_extracts_customer_draft_from_json_response():
    transport = FakeMiniMaxTransport(
        minimax_response(
            json.dumps(
                {
                    "客户名称": "云舟店群",
                    "客户类型": "网店店群客户",
                    "阶段": "沟通中",
                    "业务方向": "集采点数 / 店铺软件批量采购",
                    "联系人": "王五",
                    "手机号": "13812345678",
                    "微信号": "wangwu_88",
                    "所属主体": "云舟电商",
                    "店铺规模": "50家店",
                    "当前需求": "想确认 50 家店批量购买店铺软件是否有阶梯折扣",
                    "最近推进": "客户询问批量折扣",
                    "下次动作": "确认采购软件、点数数量和期望折扣",
                    "下次跟进日期": "明天",
                    "沟通日期": "2026-04-20",
                    "沟通结论": "店群客户有 50 家店，正在询价批量采购折扣",
                    "新增信息": "关注店铺软件和集采点数",
                    "风险顾虑": "暂未确认采购时间",
                    "下一步": "补齐采购数量后报价",
                },
                ensure_ascii=False,
            )
        )
    )
    client = MiniMaxCaptureClient(api_key="test-key", transport=transport)

    draft = client.extract_draft(
        "王五说云舟店群 50 家店，想问店铺软件批量采购有没有阶梯折扣",
        existing_customers=["爱慕"],
        today="2026-04-20",
    )

    assert draft.name == "云舟店群"
    assert draft.customer_type == "网店店群客户"
    assert draft.stage == "沟通中"
    assert draft.business_direction == "集采点数 / 店铺软件批量采购"
    assert draft.contact == "王五"
    assert draft.phone == "13812345678"
    assert draft.wechat_id == "wangwu_88"
    assert draft.company == "云舟电商"
    assert draft.shop_scale == "50家店"
    assert draft.current_need == "想确认 50 家店批量购买店铺软件是否有阶梯折扣"
    assert draft.recent_progress == "客户询问批量折扣"
    assert draft.next_action == "确认采购软件、点数数量和期望折扣"
    assert draft.next_follow_up_date == "2026-04-21"
    assert draft.communication is not None
    assert draft.communication.entry_date == "2026-04-20"
    assert draft.communication.summary == "店群客户有 50 家店，正在询价批量采购折扣"
    assert transport.requests[0]["url"] == "https://api.minimaxi.com/v1/chat/completions"
    assert transport.requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert transport.requests[0]["payload"]["model"] == "MiniMax-M2.7"
    user_prompt = transport.requests[0]["payload"]["messages"][1]["content"]
    assert "下次跟进日期" in user_prompt
    assert "相对日期" in user_prompt


def test_minimax_extracts_json_from_markdown_code_fence():
    transport = FakeMiniMaxTransport(
        minimax_response(
            """```json
{
  "客户名称": "爱慕",
  "客户类型": "品牌客户",
  "阶段": "沟通中",
  "当前需求": "补充品牌推广视频拍摄需求",
  "沟通日期": "2026-04-20",
  "沟通结论": "客户补充了品牌推广方向"
}
```"""
        )
    )
    client = MiniMaxCaptureClient(api_key="test-key", transport=transport)

    draft = client.extract_draft("爱慕补充品牌推广视频拍摄需求", existing_customers=["爱慕"], today="2026-04-20")

    assert draft.name == "爱慕"
    assert draft.customer_type == "品牌客户"
    assert draft.stage == "沟通中"
    assert draft.communication is not None
    assert draft.communication.new_info == ""


def test_minimax_target_customer_name_is_prompted_and_forced():
    transport = FakeMiniMaxTransport(
        minimax_response(
            json.dumps(
                {
                    "客户名称": "爱慕客户",
                    "客户类型": "品牌客户",
                    "阶段": "沟通中",
                    "当前需求": "补充品牌推广需求",
                    "沟通日期": "2026-04-20",
                    "沟通结论": "客户补充了推广方向",
                },
                ensure_ascii=False,
            )
        )
    )
    client = MiniMaxCaptureClient(api_key="test-key", transport=transport)

    draft = client.extract_draft(
        "这个是爱慕的老客户更新，补充品牌推广需求",
        existing_customers=["爱慕"],
        today="2026-04-20",
        target_customer_name="爱慕",
    )

    user_prompt = transport.requests[0]["payload"]["messages"][1]["content"]
    assert "当前正在更新的老客户：爱慕" in user_prompt
    assert draft.name == "爱慕"


def test_minimax_falls_back_to_structured_contact_fields_from_raw_text():
    transport = FakeMiniMaxTransport(
        minimax_response(
            json.dumps(
                {
                    "客户名称": "L·",
                    "客户类型": "网店店群客户",
                    "阶段": "沟通中",
                    "业务方向": "集采点数",
                    "联系人": "L·",
                    "当前需求": "希望获得更多店铺的优惠政策",
                    "沟通日期": "2026-04-20",
                    "沟通结论": "需要电话沟通价格",
                },
                ensure_ascii=False,
            )
        )
    )
    client = MiniMaxCaptureClient(api_key="test-key", transport=transport)

    draft = client.extract_draft(
        "L·说现在有10个抖店，后面每天加5-10个店铺，电话 13776288616，微信号 lshop_2026，想申请优惠价格。",
        existing_customers=[],
        today="2026-04-20",
    )

    assert draft.name == "新客户-抖店店群"
    assert draft.contact == "L·"
    assert draft.phone == "13776288616"
    assert draft.wechat_id == "lshop_2026"


def test_minimax_falls_back_to_shop_ka_store_name_from_raw_text():
    transport = FakeMiniMaxTransport(
        minimax_response(
            json.dumps(
                {
                    "客户名称": "李岩",
                    "客户类型": "网店KA客户",
                    "阶段": "已合作",
                    "业务方向": "KA版 / AI裂变 / AI详情页",
                    "联系人": "李岩",
                    "店铺规模": "抖店 · 已订购 KA版",
                    "当前需求": "已使用 AI裂变，并对 AI详情页功能有明确兴趣",
                    "沟通日期": "2026-04-23",
                    "沟通结论": "客户是已付费网店 KA 客户，不应归为店群客户",
                },
                ensure_ascii=False,
            )
        )
    )
    client = MiniMaxCaptureClient(api_key="test-key", transport=transport)

    draft = client.extract_draft(
        "青竹画材官方旗舰店，平台是抖店，已经订购 KA版，当前主要使用 AI裂变，也对新的 AI详情页功能有兴趣。",
        existing_customers=[],
        today="2026-04-23",
    )

    assert draft.name == "青竹画材官方旗舰店"
    assert draft.customer_type == "网店KA客户"
    assert draft.business_direction == "KA版 / AI裂变 / AI详情页"
    assert draft.shop_scale == "抖店 · 已订购 KA版"
    assert draft.current_need == "已使用 AI裂变，并对 AI详情页功能有明确兴趣"


def test_minimax_recognizes_blogger_with_overlapping_user_identity():
    transport = FakeMiniMaxTransport(
        minimax_response(
            json.dumps(
                {
                    "客户名称": "孙总",
                    "客户类型": "博主 / 网店店群客户",
                    "二级标签": "小时达 / 微信 / AI商品图 / AI详情页",
                    "阶段": "沟通中",
                    "业务方向": "新功能推广 / AI商品图 / AI详情页",
                    "联系人": "孙总",
                    "店铺规模": "博主推广者，同时也是小时达/微信场景使用者",
                    "当前需求": "评估是否合作推广 AI 商品图/详情页新功能",
                    "最近推进": "已发功能说明和示例图，博主表示这两天没在",
                    "下次动作": "等待回去后确认推广合作意向和报价/排期",
                    "沟通日期": "2026-04-27",
                    "沟通结论": "该对象是博主推广线索，同时可能也是软件使用者",
                },
                ensure_ascii=False,
            )
        )
    )
    client = MiniMaxCaptureClient(api_key="test-key", transport=transport)

    draft = client.extract_draft(
        "孙总X稳定电商（小时达/微信）群里，@那山那水那人，想看是否合作推广 AI 商品图/详情页新功能。孙总说这两天没在，回去和你说。",
        existing_customers=[],
        today="2026-04-27",
    )

    assert draft.name == "那山那水那人"
    assert draft.customer_type == "博主 / 网店店群客户"
    assert draft.secondary_tags == "小时达 / 微信 / AI商品图 / AI详情页"
    assert draft.business_direction == "新功能推广 / AI商品图 / AI详情页"
    assert draft.shop_scale == "博主推广者，同时也是小时达/微信场景使用者"
    assert draft.current_need == "评估是否合作推广 AI 商品图/详情页新功能"


def test_minimax_requires_api_key_before_requesting():
    client = MiniMaxCaptureClient(api_key="", transport=FakeMiniMaxTransport(minimax_response("{}")))

    with pytest.raises(AICaptureError, match="MiniMax API Key"):
        client.extract_draft("云舟店群想问批量折扣", existing_customers=[], today="2026-04-20")


class RetryOnOfficialBaseUrlTransport:
    def __init__(self, success_payload: dict):
        self.success_payload = success_payload
        self.requests: list[dict] = []

    def post_json(self, url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        self.requests.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        if url.startswith(MINIMAX_GLOBAL_BASE_URL):
            raise AICaptureError(
                'MiniMax 请求失败：HTTP 401 {"type":"error","error":{"type":"authorized_error","message":"invalid api key"}}'
            )
        return self.success_payload


def test_minimax_retries_official_alternate_base_url_after_invalid_api_key():
    transport = RetryOnOfficialBaseUrlTransport(
        minimax_response(
            json.dumps(
                {
                    "客户名称": "爱慕",
                    "客户类型": "品牌客户",
                    "阶段": "沟通中",
                    "当前需求": "补充品牌推广需求",
                    "沟通日期": "2026-04-20",
                    "沟通结论": "客户补充了推广方向",
                },
                ensure_ascii=False,
            )
        )
    )
    client = MiniMaxCaptureClient(
        api_key="test-key",
        base_url=MINIMAX_GLOBAL_BASE_URL,
        transport=transport,
    )

    draft = client.extract_draft("爱慕补充品牌推广需求", existing_customers=["爱慕"], today="2026-04-20")

    assert draft.name == "爱慕"
    assert [request["url"] for request in transport.requests] == [
        f"{MINIMAX_GLOBAL_BASE_URL}/chat/completions",
        f"{MINIMAX_BASE_URL}/chat/completions",
    ]


def test_minimax_invalid_api_key_error_mentions_both_official_base_urls():
    transport = RetryOnOfficialBaseUrlTransport(
        success_payload=minimax_response("{}")
    )

    def always_fail(url: str, headers: dict[str, str], payload: dict, timeout: float) -> dict:
        transport.requests.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout": timeout,
            }
        )
        raise AICaptureError(
            'MiniMax 请求失败：HTTP 401 {"type":"error","error":{"type":"authorized_error","message":"invalid api key"}}'
        )

    transport.post_json = always_fail  # type: ignore[method-assign]
    client = MiniMaxCaptureClient(api_key="test-key", base_url=MINIMAX_GLOBAL_BASE_URL, transport=transport)

    with pytest.raises(AICaptureError) as exc_info:
        client.extract_draft("爱慕补充品牌推广需求", existing_customers=["爱慕"], today="2026-04-20")

    message = str(exc_info.value)
    assert MINIMAX_BASE_URL in message
    assert MINIMAX_GLOBAL_BASE_URL in message
