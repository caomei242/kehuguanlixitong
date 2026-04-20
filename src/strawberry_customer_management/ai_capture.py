from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from strawberry_customer_management.models import (
    CommunicationEntry,
    CustomerDraft,
    CUSTOMER_STAGES,
    CUSTOMER_TYPES,
)


MINIMAX_BASE_URL = "https://api.minimax.io/v1"
MINIMAX_DEFAULT_MODEL = "MiniMax-M2.7-highspeed"


class AICaptureError(RuntimeError):
    pass


class JsonTransport(Protocol):
    def post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        ...


@dataclass
class UrllibJsonTransport:
    def post_json(self, url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AICaptureError(f"MiniMax 请求失败：HTTP {exc.code} {body[:240]}") from exc
        except urllib.error.URLError as exc:
            raise AICaptureError(f"MiniMax 请求失败：{exc.reason}") from exc
        except TimeoutError as exc:
            raise AICaptureError("MiniMax 请求超时，请稍后重试。") from exc
        except json.JSONDecodeError as exc:
            raise AICaptureError("MiniMax 返回内容不是合法 JSON。") from exc


class MiniMaxCaptureClient:
    def __init__(
        self,
        api_key: str,
        model: str = MINIMAX_DEFAULT_MODEL,
        base_url: str = MINIMAX_BASE_URL,
        timeout: float = 60,
        transport: JsonTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or MINIMAX_DEFAULT_MODEL
        self.base_url = base_url.rstrip("/") or MINIMAX_BASE_URL
        self.timeout = timeout
        self.transport = transport or UrllibJsonTransport()

    def extract_draft(
        self,
        raw_text: str,
        existing_customers: list[str],
        today: str | None = None,
        target_customer_name: str | None = None,
    ) -> CustomerDraft:
        if not self.api_key:
            raise AICaptureError("请先在设置里填写 MiniMax API Key。")
        if not raw_text.strip():
            raise AICaptureError("请先粘贴客户聊天或需求原文。")

        payload = self._build_payload(
            raw_text=raw_text,
            existing_customers=existing_customers,
            today=today or date.today().isoformat(),
            target_customer_name=target_customer_name,
        )
        response = self.transport.post_json(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            payload=payload,
            timeout=self.timeout,
        )
        content = _extract_message_content(response)
        return draft_from_ai_json(content, today=today or date.today().isoformat(), target_customer_name=target_customer_name)

    def _build_payload(
        self,
        raw_text: str,
        existing_customers: list[str],
        today: str,
        target_customer_name: str | None = None,
    ) -> dict[str, Any]:
        known_customers = "、".join(existing_customers[:80]) or "暂无"
        target_hint = f"当前正在更新的老客户：{target_customer_name.strip()}\n" if target_customer_name and target_customer_name.strip() else ""
        system_prompt = (
            "你是一个中文客户管理录入助手。你的任务是把用户粘贴的客户聊天、需求或推进情况，"
            "整理成草莓客户管理系统的表单字段。只输出一个 JSON 对象，不要输出解释。"
        )
        user_prompt = f"""今天日期：{today}
已存在客户：{known_customers}
{target_hint}

字段要求：
- 客户名称：必须尽量提取，老客户要使用已存在客户里的同名或最接近名称。
- 如果提供了“当前正在更新的老客户”，客户名称必须严格返回这个名称，不要改写或加后缀。
- 客户类型：只能是 品牌客户 或 网店店群客户。
- 阶段：只能是 潜客 / 沟通中 / 已合作 / 暂缓。
- 业务方向：品牌客户常见为 种草 / 视频拍摄 / 品牌推广 / 网店采买；网店店群客户常见为 集采点数 / 店铺软件批量采购。
- 没有提到的信息输出空字符串，不要编造。
- 同一天多轮聊天要合并成一句有效结论。

只返回这些键：
客户名称、客户类型、阶段、业务方向、联系人、所属主体、店铺规模、当前需求、最近推进、下次动作、沟通日期、沟通结论、新增信息、风险顾虑、下一步

客户原文：
{raw_text.strip()}"""
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "reasoning_split": True,
        }


def draft_from_ai_json(content: str, today: str | None = None, target_customer_name: str | None = None) -> CustomerDraft:
    payload = _load_json_object(content)
    current_date = today or date.today().isoformat()
    forced_name = target_customer_name.strip() if target_customer_name else ""
    communication = CommunicationEntry(
        entry_date=_value(payload, "沟通日期") or current_date,
        summary=_value(payload, "沟通结论"),
        new_info=_value(payload, "新增信息"),
        risk=_value(payload, "风险顾虑"),
        next_step=_value(payload, "下一步"),
    )
    return CustomerDraft(
        name=forced_name or _value(payload, "客户名称"),
        customer_type=_choice(_value(payload, "客户类型"), CUSTOMER_TYPES, "品牌客户"),
        stage=_choice(_value(payload, "阶段"), CUSTOMER_STAGES, "潜客"),
        business_direction=_value(payload, "业务方向"),
        contact=_value(payload, "联系人"),
        company=_value(payload, "所属主体"),
        shop_scale=_value(payload, "店铺规模"),
        current_need=_value(payload, "当前需求"),
        recent_progress=_value(payload, "最近推进"),
        next_action=_value(payload, "下次动作") or communication.next_step,
        communication=communication,
    )


def _extract_message_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AICaptureError("MiniMax 返回结构缺少 choices[0].message.content。") from exc
    if not isinstance(content, str) or not content.strip():
        raise AICaptureError("MiniMax 没有返回可解析内容。")
    return content


def _load_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(?P<body>\{.*?\})\s*```", text, flags=re.S)
    if fence:
        text = fence.group("body")
    elif "{" in text and "}" in text:
        text = text[text.find("{") : text.rfind("}") + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AICaptureError("AI 返回内容不是可解析的 JSON，请重试或手动填写。") from exc
    if not isinstance(payload, dict):
        raise AICaptureError("AI 返回内容不是 JSON 对象，请重试。")
    return payload


def _value(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _choice(value: str, choices: tuple[str, ...], fallback: str) -> str:
    return value if value in choices else fallback
