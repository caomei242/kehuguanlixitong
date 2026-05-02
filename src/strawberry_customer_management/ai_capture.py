from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Protocol

from strawberry_customer_management.models import (
    CaptureDraft,
    CommunicationEntry,
    CustomerDraft,
    CUSTOMER_STAGES,
    CUSTOMER_TYPES,
    INTERNAL_MAIN_WORK_NAME,
    INTERNAL_PROJECT_TYPES,
    normalize_internal_project_name,
    PROJECT_STAGES,
    PROJECT_TYPES,
    ProjectRole,
    ProjectDraft,
    SECONDARY_TAGS,
)


MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_GLOBAL_BASE_URL = "https://api.minimax.io/v1"
MINIMAX_OFFICIAL_BASE_URLS = (MINIMAX_BASE_URL, MINIMAX_GLOBAL_BASE_URL)
MINIMAX_DEFAULT_MODEL = "MiniMax-M2.7"


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
        customer_types: list[str] | tuple[str, ...] | None = None,
        secondary_tags: list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() or MINIMAX_DEFAULT_MODEL
        self.base_url = base_url.rstrip("/") or MINIMAX_BASE_URL
        self.timeout = timeout
        self.transport = transport or UrllibJsonTransport()
        self.customer_types = tuple(customer_types or CUSTOMER_TYPES)
        self.secondary_tags = tuple(secondary_tags or SECONDARY_TAGS)

    def extract_draft(
        self,
        raw_text: str,
        existing_customers: list[str],
        today: str | None = None,
        target_customer_name: str | None = None,
    ) -> CustomerDraft:
        capture = self.extract_capture(
            raw_text=raw_text,
            existing_customers=existing_customers,
            today=today,
            target_customer_name=target_customer_name,
        )
        if capture.customer_draft is not None:
            return capture.customer_draft
        raise AICaptureError(f"AI 识别为「{capture.kind}」，请用主业录入保存。")

    def extract_capture(
        self,
        raw_text: str,
        existing_customers: list[str],
        today: str | None = None,
        target_customer_name: str | None = None,
    ) -> CaptureDraft:
        if not self.api_key:
            raise AICaptureError("请先在设置里填写 MiniMax API Key。")
        if not raw_text.strip():
            raise AICaptureError("请先粘贴主业事项、客户聊天或需求原文。")

        payload = self._build_payload(
            raw_text=raw_text,
            existing_customers=existing_customers,
            today=today or date.today().isoformat(),
            target_customer_name=target_customer_name,
        )
        candidate_base_urls = _candidate_base_urls(self.base_url)
        attempted_base_urls: list[str] = []
        last_error: AICaptureError | None = None
        for base_url in candidate_base_urls:
            attempted_base_urls.append(base_url)
            try:
                response = self.transport.post_json(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    payload=payload,
                    timeout=self.timeout,
                )
            except AICaptureError as exc:
                last_error = exc
                if _is_retryable_invalid_api_key(exc) and len(attempted_base_urls) < len(candidate_base_urls):
                    continue
                raise _decorate_minimax_error(exc, attempted_base_urls) from exc
            self.base_url = base_url
            break
        else:
            assert last_error is not None
            raise _decorate_minimax_error(last_error, attempted_base_urls) from last_error
        content = _extract_message_content(response)
        draft = draft_from_ai_json(
            content,
            raw_text=raw_text,
            today=today or date.today().isoformat(),
            target_customer_name=target_customer_name,
            customer_types=self.customer_types,
            secondary_tags=self.secondary_tags,
        )
        if isinstance(draft, CaptureDraft):
            return draft
        return CaptureDraft(kind="客户更新", customer_draft=draft)

    def _build_payload(
        self,
        raw_text: str,
        existing_customers: list[str],
        today: str,
        target_customer_name: str | None = None,
    ) -> dict[str, Any]:
        known_customers = "、".join(existing_customers[:80]) or "暂无"
        target_hint = f"当前正在更新的老客户：{target_customer_name.strip()}\n" if target_customer_name and target_customer_name.strip() else ""
        customer_type_options = " / ".join(self.customer_types)
        secondary_tag_options = " / ".join(self.secondary_tags)
        system_prompt = (
            "你是一个中文主业管理录入助手。你的任务是把用户粘贴的内部主业事项、客户聊天、"
            "客户项目需求或推进情况，整理成草莓主业管理系统的表单字段。只输出一个 JSON 对象，不要输出解释。"
        )
        user_prompt = f"""今天日期：{today}
已存在客户：{known_customers}
{target_hint}

先判断录入类型：
- 录入类型只能是 客户更新 / 客户项目 / 主业事项。
- 非客户事项不要创建伪客户；例如系统建设、内部流程、资料整理、运营安排，都归为 主业事项。
- 主业事项固定关联对象为 {INTERNAL_MAIN_WORK_NAME}。

字段要求：
- 录入类型：必须返回。
- 客户名称：必须尽量提取，老客户要使用已存在客户里的同名或最接近名称。
- 如果提供了“当前正在更新的老客户”，客户名称必须严格返回这个名称，不要改写或加后缀。
- 不要把联系人姓名、微信昵称或缩写昵称直接当成客户名称。品牌客户优先用品牌名；网店KA客户优先用具体店铺/账号名；网店店群客户优先用店群主体、店铺类型或业务标识命名；博主优先用博主昵称、账号名或沟通群里的对外称呼。
- 客户类型：可以多选，选项只能来自 {customer_type_options}；用 “ / ” 分隔，例如：博主 / 网店店群客户。
- 阶段：只能是 潜客 / 沟通中 / 已合作 / 暂缓 / 已归档。
- 业务方向：品牌客户常见为 种草 / 视频拍摄 / 品牌推广 / 网店采买；网店KA客户常见为 KA版 / AI裂变 / AI详情页 / 功能跟进；网店店群客户常见为 集采点数 / 店铺软件批量采购；博主常见为 新功能推广 / 新产品推广 / 内容合作 / 小时达与微信生态推广。
- 二级标签：可以多选，选项优先来自 {secondary_tag_options}；用 “ / ” 分隔。
- 如果一个对象既是推广者又是软件使用者，不要二选一；客户类型直接多选，例如：博主 / 网店店群客户。小时达、微信这类渠道/场景只放二级标签。
- 手机号、联系电话、微信号尽量提取；没有提到的信息输出空字符串。
- 下次跟进日期：如有“明天、后天、下周一、3天后”等相对日期，必须结合今天日期转换成 YYYY-MM-DD 绝对日期；没有明确日期输出空字符串。
- 如果是客户项目，返回 项目名称、项目类型、当前重点、下次动作、下次跟进日期；客户名称仍然是关联客户。
- 如果是主业事项，返回 事项名称、项目类型、当前重点、下次动作、下次跟进日期。项目类型只能是 {' / '.join(INTERNAL_PROJECT_TYPES)}，阶段默认 推进中。
- 如果原文出现人名、对接人、负责人、供应商、垫资商、法务、达人、客户联系人等项目关系人，必须返回 项目参与人。
- 项目参与人只返回最小结构数组，每项包含 所属方、关系、人；例如 {{"所属方":"客户方","关系":"负责人","人":"张三"}}。
- 所属方优先使用 我方 / 客户方 / 供应商 / 垫资方 / 达人博主 / 内部支持；关系保留原文角色，例如 对接人 / 负责人 / 供应商 / 垫资商 / 法务。
- 没有提到的信息输出空字符串，不要编造。
- 同一天多轮聊天要合并成一句有效结论。

只返回这些键：
录入类型、客户名称、客户类型、二级标签、阶段、业务方向、联系人、手机号、微信号、所属主体、店铺规模、当前需求、最近推进、项目名称、事项名称、项目类型、当前重点、下次动作、下次跟进日期、项目参与人、沟通日期、沟通结论、新增信息、风险顾虑、下一步

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


def draft_from_ai_json(
    content: str,
    raw_text: str = "",
    today: str | None = None,
    target_customer_name: str | None = None,
    customer_types: list[str] | tuple[str, ...] | None = None,
    secondary_tags: list[str] | tuple[str, ...] | None = None,
) -> CustomerDraft | CaptureDraft:
    payload = _load_json_object(content)
    current_date = today or date.today().isoformat()
    forced_name = target_customer_name.strip() if target_customer_name else ""
    capture_kind = _normalize_capture_kind(_value(payload, "录入类型"), forced_name)
    if capture_kind == "主业事项":
        return CaptureDraft(
            kind="主业事项",
            project_draft=_internal_project_draft_from_payload(payload, raw_text=raw_text, today=current_date),
        )
    if capture_kind == "客户项目":
        return CaptureDraft(
            kind="客户项目",
            project_draft=_customer_project_draft_from_payload(payload, raw_text=raw_text, today=current_date, target_customer_name=forced_name),
        )
    allowed_customer_types = tuple(customer_types or CUSTOMER_TYPES)
    allowed_secondary_tags = tuple(secondary_tags or SECONDARY_TAGS)
    customer_type = _multi_choice(_value(payload, "客户类型"), allowed_customer_types, _first_or_default(allowed_customer_types, "品牌客户"))
    contact = _value(payload, "联系人")
    phone = _value(payload, "手机号") or _value(payload, "联系电话") or _extract_phone_number(raw_text)
    wechat_id = _value(payload, "微信号") or _extract_wechat_id(raw_text)
    resolved_name = _resolve_customer_name(
        forced_name or _value(payload, "客户名称"),
        customer_type=customer_type,
        contact=contact,
        raw_text=raw_text,
    )
    communication = CommunicationEntry(
        entry_date=_value(payload, "沟通日期") or current_date,
        summary=_value(payload, "沟通结论"),
        new_info=_value(payload, "新增信息"),
        risk=_value(payload, "风险顾虑"),
        next_step=_value(payload, "下一步"),
    )
    return CustomerDraft(
        name=resolved_name,
        customer_type=customer_type,
        stage=_choice(_value(payload, "阶段"), CUSTOMER_STAGES, "潜客"),
        secondary_tags=_multi_choice(_value(payload, "二级标签"), allowed_secondary_tags, ""),
        business_direction=_value(payload, "业务方向"),
        contact=contact,
        phone=phone,
        wechat_id=wechat_id,
        company=_value(payload, "所属主体"),
        shop_scale=_value(payload, "店铺规模"),
        current_need=_value(payload, "当前需求"),
        recent_progress=_value(payload, "最近推进"),
        next_action=_value(payload, "下次动作") or communication.next_step,
        next_follow_up_date=_normalize_follow_up_date(_value(payload, "下次跟进日期"), current_date),
        communication=communication,
    )


def _normalize_capture_kind(value: str, forced_customer_name: str = "") -> str:
    if forced_customer_name:
        return "客户更新"
    if value in {"客户更新", "客户项目", "主业事项"}:
        return value
    if "主业" in value or "内部" in value:
        return "主业事项"
    if "项目" in value:
        return "客户项目"
    return "客户更新"


def _internal_project_draft_from_payload(payload: dict[str, Any], raw_text: str, today: str) -> ProjectDraft:
    project_name = _value(payload, "事项名称") or _value(payload, "项目名称") or _infer_internal_project_name(raw_text)
    return ProjectDraft(
        brand_customer_name=INTERNAL_MAIN_WORK_NAME,
        project_name=normalize_internal_project_name(project_name, today),
        stage=_choice(_value(payload, "阶段"), PROJECT_STAGES, "推进中"),
        project_type=_internal_project_type(_value(payload, "项目类型"), raw_text),
        current_focus=_value(payload, "当前重点") or _value(payload, "当前需求") or raw_text.strip(),
        next_action=_value(payload, "下次动作") or _value(payload, "下一步"),
        next_follow_up_date=_normalize_follow_up_date(_value(payload, "下次跟进日期"), today),
        participant_roles=_project_roles_from_payload(payload),
        updated_at=today,
    )


def _customer_project_draft_from_payload(payload: dict[str, Any], raw_text: str, today: str, target_customer_name: str = "") -> ProjectDraft:
    brand_customer_name = target_customer_name or _value(payload, "客户名称") or "待确认客户"
    project_name = _value(payload, "项目名称") or _value(payload, "事项名称") or _infer_customer_project_name(raw_text, brand_customer_name)
    return ProjectDraft(
        brand_customer_name=brand_customer_name,
        project_name=project_name,
        stage=_choice(_value(payload, "阶段"), PROJECT_STAGES, "推进中"),
        project_type=_choice(_value(payload, "项目类型"), PROJECT_TYPES, "其他项目"),
        current_focus=_value(payload, "当前重点") or _value(payload, "当前需求") or raw_text.strip(),
        next_action=_value(payload, "下次动作") or _value(payload, "下一步"),
        next_follow_up_date=_normalize_follow_up_date(_value(payload, "下次跟进日期"), today),
        participant_roles=_project_roles_from_payload(payload),
        updated_at=today,
    )


def _project_roles_from_payload(payload: dict[str, Any]) -> list[ProjectRole]:
    raw_roles = payload.get("项目参与人") or payload.get("参与人") or payload.get("项目关系人") or []
    if isinstance(raw_roles, dict):
        raw_items: list[Any] = [raw_roles]
    elif isinstance(raw_roles, list):
        raw_items = raw_roles
    elif isinstance(raw_roles, str):
        raw_items = _parse_project_role_text(raw_roles)
    else:
        raw_items = []

    roles: list[ProjectRole] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        name = _role_item_value(item, "人", "姓名", "name", "person")
        relation = _role_item_value(item, "关系", "角色", "role", "relation")
        side = _role_item_value(item, "所属方", "所属", "side")
        if not name:
            continue
        key = (side, relation, name)
        if key in seen:
            continue
        seen.add(key)
        roles.append(ProjectRole(name=name, role=relation, side=side, relation=relation))
    return roles


def _role_item_value(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _parse_project_role_text(value: str) -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    for part in re.split(r"\n|；|;", value):
        text = part.strip(" -，,、")
        if not text:
            continue
        chunks = [chunk.strip() for chunk in re.split(r"\s*[-/｜|：:]\s*", text) if chunk.strip()]
        if len(chunks) >= 3:
            roles.append({"所属方": chunks[0], "关系": chunks[1], "人": chunks[2]})
        elif len(chunks) == 2:
            roles.append({"关系": chunks[0], "人": chunks[1]})
    return roles


def _internal_project_type(value: str, raw_text: str) -> str:
    if value in INTERNAL_PROJECT_TYPES:
        return value
    text = f"{value} {raw_text}"
    if any(keyword in text for keyword in ("系统", "工具", "平台", "管理系统")):
        return "主业系统建设"
    if any(keyword in text for keyword in ("流程", "SOP", "规范", "优化")):
        return "主业流程优化"
    if any(keyword in text for keyword in ("资料", "文档", "整理", "归档")):
        return "主业资料整理"
    if any(keyword in text for keyword in ("运营", "跟进", "日常")):
        return "主业运营事项"
    return "其他主业事项"


def _infer_internal_project_name(raw_text: str) -> str:
    text = raw_text.strip()
    for pattern in (
        r"(?:做|建设|搭建|整理|优化|推进)(?:一个|一套|新的)?(?P<name>[^，。,；;]+)",
        r"(?P<name>[^，。,；;]+?)(?:明天|后天|下周|继续|推进)",
    ):
        match = re.search(pattern, text)
        if match:
            name = match.group("name").strip(" ，。,；;")
            if name:
                return name
    return text[:30] or "待确认主业事项"


def _infer_customer_project_name(raw_text: str, brand_customer_name: str) -> str:
    text = raw_text.strip()
    if brand_customer_name and brand_customer_name in text:
        without_customer = text.replace(brand_customer_name, "").strip(" ，。,；;")
        if without_customer:
            return without_customer[:40]
    return text[:40] or "待确认客户项目"


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


def _split_multi_value(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*/\s*|[，,、]", value) if part.strip()]


def _multi_choice(value: str, choices: tuple[str, ...], fallback: str) -> str:
    selected: list[str] = []
    for part in _split_multi_value(value):
        if part in choices and part not in selected:
            selected.append(part)
    if not selected and fallback:
        selected.append(fallback)
    return " / ".join(selected)


def _first_or_default(values: tuple[str, ...], fallback: str) -> str:
    return values[0] if values else fallback


def _normalize_follow_up_date(value: str, today: str) -> str:
    raw_value = value.strip()
    if not raw_value:
        return ""
    iso_match = re.search(r"20\d{2}-\d{1,2}-\d{1,2}", raw_value)
    if iso_match:
        parts = [int(part) for part in iso_match.group(0).split("-")]
        return date(parts[0], parts[1], parts[2]).isoformat()
    try:
        base_date = date.fromisoformat(today)
    except ValueError:
        return raw_value

    relative_days = {
        "今天": 0,
        "明天": 1,
        "后天": 2,
        "大后天": 3,
    }
    if raw_value in relative_days:
        return (base_date + timedelta(days=relative_days[raw_value])).isoformat()

    days_later_match = re.search(r"(\d+)\s*天后", raw_value)
    if days_later_match:
        return (base_date + timedelta(days=int(days_later_match.group(1)))).isoformat()

    next_week_match = re.search(r"下周([一二三四五六日天])", raw_value)
    if next_week_match:
        weekday = _weekday_number(next_week_match.group(1))
        days_until_next_weekday = 7 - base_date.weekday() + weekday
        return (base_date + timedelta(days=days_until_next_weekday)).isoformat()

    return raw_value


def _weekday_number(value: str) -> int:
    return {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}[value]


def _extract_phone_number(raw_text: str) -> str:
    match = re.search(r"(?<!\d)(1[3-9]\d{9})(?!\d)", raw_text)
    return match.group(1) if match else ""


def _extract_wechat_id(raw_text: str) -> str:
    patterns = (
        r"(?:微信(?:号)?|vx|Vx|VX)[：:\s]*([a-zA-Z][-_a-zA-Z0-9]{5,19})",
        r"(?:加微|加v)[：:\s]*([a-zA-Z][-_a-zA-Z0-9]{5,19})",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return match.group(1)
    return ""


def _resolve_customer_name(candidate: str, customer_type: str, contact: str, raw_text: str) -> str:
    name = candidate.strip()
    if not name:
        return _fallback_customer_name(customer_type, raw_text)
    if any(_has_customer_type(customer_type, item) for item in ("网店KA客户", "网店店群客户", "博主")) and _looks_like_contact_name(name, contact):
        return _fallback_customer_name(customer_type, raw_text) or name
    return name


def _looks_like_contact_name(name: str, contact: str) -> bool:
    cleaned = name.strip()
    if not cleaned:
        return True
    if contact and cleaned == contact.strip():
        return True
    if len(cleaned) <= 3:
        return True
    if re.fullmatch(r"[A-Za-z][·•.]?", cleaned):
        return True
    return False


def _fallback_customer_name(customer_type: str, raw_text: str) -> str:
    if _has_customer_type(customer_type, "博主"):
        blogger_name = _extract_blogger_name(raw_text)
        if blogger_name:
            return blogger_name
        if "小时达" in raw_text or "微信" in raw_text:
            return "新博主-小时达-微信"
        return "新博主-待确认"
    if _has_customer_type(customer_type, "网店KA客户"):
        store_name = _extract_shop_store_name(raw_text)
        if store_name:
            return store_name
        if "抖店" in raw_text:
            return "新客户-抖店KA"
        return "新客户-网店KA"
    if _has_customer_type(customer_type, "网店店群客户"):
        if "抖店" in raw_text:
            return "新客户-抖店店群"
        if "店群" in raw_text:
            return "新客户-店群客户"
        return "新客户-网店店群"
    if "品牌" in raw_text:
        return "新客户-品牌合作"
    return "新客户-待确认"


def _has_customer_type(value: str, customer_type: str) -> bool:
    return customer_type in _split_multi_value(value)


def _extract_blogger_name(raw_text: str) -> str:
    patterns = (
        r"@([\u4e00-\u9fa5A-Za-z0-9·•._-]{2,30})",
        r"(?:博主|达人|推广者|账号)[：:\s]*([\u4e00-\u9fa5A-Za-z0-9·•._-]{2,30})",
        r"([\u4e00-\u9fa5A-Za-z0-9·•._-]{2,30})[（(](?:小时达|微信|小红书|抖音)[）)]",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return match.group(1).strip()
    return ""


def _extract_shop_store_name(raw_text: str) -> str:
    patterns = (
        r"([\u4e00-\u9fa5A-Za-z0-9·•._-]{2,30}官方旗舰店)",
        r"([\u4e00-\u9fa5A-Za-z0-9·•._-]{2,30}旗舰店)",
    )
    for pattern in patterns:
        match = re.search(pattern, raw_text)
        if match:
            return match.group(1)
    return ""


def _candidate_base_urls(base_url: str) -> list[str]:
    normalized = base_url.rstrip("/") or MINIMAX_BASE_URL
    candidates = [normalized]
    if normalized in MINIMAX_OFFICIAL_BASE_URLS:
        for official_url in MINIMAX_OFFICIAL_BASE_URLS:
            if official_url != normalized:
                candidates.append(official_url)
    return candidates


def _is_retryable_invalid_api_key(exc: AICaptureError) -> bool:
    message = str(exc).lower()
    return "http 401" in message and "invalid api key" in message


def _decorate_minimax_error(exc: AICaptureError, attempted_base_urls: list[str]) -> AICaptureError:
    if not _is_retryable_invalid_api_key(exc):
        return exc
    attempted_text = "、".join(attempted_base_urls)
    return AICaptureError(
        "MiniMax 认证失败：当前 API Key 没有通过校验。"
        f"已尝试地址：{attempted_text}。"
        f"如果你使用中国大陆服务，请在设置里把 MiniMax Base URL 设为 {MINIMAX_BASE_URL}；"
        f"如果你使用 Global 服务，请设为 {MINIMAX_GLOBAL_BASE_URL}。"
    )
