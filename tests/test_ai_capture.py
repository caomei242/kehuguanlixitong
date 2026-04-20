from __future__ import annotations

import json

import pytest

from strawberry_customer_management.ai_capture import AICaptureError, MiniMaxCaptureClient


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
                    "所属主体": "云舟电商",
                    "店铺规模": "50家店",
                    "当前需求": "想确认 50 家店批量购买店铺软件是否有阶梯折扣",
                    "最近推进": "客户询问批量折扣",
                    "下次动作": "确认采购软件、点数数量和期望折扣",
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
    assert draft.company == "云舟电商"
    assert draft.shop_scale == "50家店"
    assert draft.current_need == "想确认 50 家店批量购买店铺软件是否有阶梯折扣"
    assert draft.recent_progress == "客户询问批量折扣"
    assert draft.next_action == "确认采购软件、点数数量和期望折扣"
    assert draft.communication is not None
    assert draft.communication.entry_date == "2026-04-20"
    assert draft.communication.summary == "店群客户有 50 家店，正在询价批量采购折扣"
    assert transport.requests[0]["url"] == "https://api.minimax.io/v1/chat/completions"
    assert transport.requests[0]["headers"]["Authorization"] == "Bearer test-key"
    assert transport.requests[0]["payload"]["model"] == "MiniMax-M2.7-highspeed"


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


def test_minimax_requires_api_key_before_requesting():
    client = MiniMaxCaptureClient(api_key="", transport=FakeMiniMaxTransport(minimax_response("{}")))

    with pytest.raises(AICaptureError, match="MiniMax API Key"):
        client.extract_draft("云舟店群想问批量折扣", existing_customers=[], today="2026-04-20")

