from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from strawberry_customer_management.models import (
    ApprovalEntry,
    CommunicationEntry,
    CustomerDetail,
    CustomerDraft,
    CustomerRecord,
)
from strawberry_customer_management.paths import default_customer_root


SUMMARY_FILE = "00 客户总表.md"
CUSTOMER_DIR = "客户"
PLACEHOLDER_NAMES = {"待录入", "暂无"}
PLACEHOLDER_UPDATED_AT = {"", "待同步", "待补充", "待确认", "待补日期"}


def _split_multi_value(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*/\s*|[，,、]", value) if part.strip()]


def _has_customer_type(value: str, customer_type: str) -> bool:
    return customer_type in _split_multi_value(value)


def _strip_code(value: str) -> str:
    value = value.strip()
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        return value[1:-1]
    return value


def _clean_cell(value: str) -> str:
    return value.replace("\\|", "|").strip()


def _extract_wikilink_target(value: str) -> str:
    match = re.search(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", value)
    return match.group(1).strip() if match else value.strip()


def _split_markdown_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [_clean_cell(cell) for cell in stripped.split("|")]


def _format_markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in cells)


def _section_body(text: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.M | re.S)
    return match.group("body") if match else ""


def _replace_section_body(text: str, heading: str, body: str) -> str:
    pattern = rf"(^## {re.escape(heading)}\n)(?P<body>.*?)(?=^## |\Z)"
    replacement = rf"\1{body}"
    return re.sub(pattern, replacement, text, count=1, flags=re.M | re.S)


def _ensure_section(text: str, heading: str, default_body: str = "") -> str:
    if re.search(rf"^## {re.escape(heading)}\s*$", text, flags=re.M):
        return text
    normalized_body = default_body.rstrip()
    if normalized_body:
        normalized_body = "\n" + normalized_body + "\n"
    else:
        normalized_body = "\n"
    return text.rstrip() + f"\n\n## {heading}{normalized_body}"


def _replace_table_header(text: str, heading: str, header_body: str) -> str:
    body = _section_body(text, heading)
    lines = body.splitlines()
    table_indexes = [index for index, line in enumerate(lines) if line.strip().startswith("|")]
    header_lines = header_body.splitlines()
    if len(table_indexes) < 2 or len(header_lines) < 2:
        return text
    target_header = _split_markdown_row(header_lines[0])
    target_separator = _split_markdown_row(header_lines[1])
    old_header = _split_markdown_row(lines[table_indexes[0]])
    lines[table_indexes[0]] = _format_markdown_row(target_header)
    lines[table_indexes[1]] = _format_markdown_row(target_separator)
    for row_index in table_indexes[2:]:
        cells = _split_markdown_row(lines[row_index])
        if _is_separator_row(cells):
            continue
        if len(cells) < len(old_header):
            cells.extend([""] * (len(old_header) - len(cells)))
        by_header = dict(zip(old_header, cells))
        lines[row_index] = _format_markdown_row([by_header.get(column, "") for column in target_header])
    return _replace_section_body(text, heading, "\n".join(lines).rstrip() + "\n")


def _bullet_map(section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^-\s*([^：:]+)[：:]\s*(.*)$", line.strip())
        if match:
            result[match.group(1).strip()] = _strip_code(match.group(2).strip())
    return result


def _replace_or_add_bullet(text: str, section_heading: str, key: str, value: str) -> str:
    if value == "":
        return text
    pattern = rf"(^## {re.escape(section_heading)}\n)(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.M | re.S)
    if not match:
        return text
    body = match.group("body")
    line_pattern = rf"^- {re.escape(key)}[：:].*$"
    replacement_line = f"- {key}：{value}"
    if re.search(line_pattern, body, flags=re.M):
        body = re.sub(line_pattern, replacement_line, body, count=1, flags=re.M)
    else:
        body = body.rstrip() + f"\n{replacement_line}\n"
    return text[: match.start("body")] + body + text[match.end("body") :]


def _replace_page_title(text: str, name: str) -> str:
    return re.sub(r"^# 客户--.*$", f"# 客户--{name}", text, count=1, flags=re.M)


def _parse_table(section: str) -> list[dict[str, str]]:
    lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []
    header = _split_markdown_row(lines[0])
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = _split_markdown_row(line)
        if _is_separator_row(cells):
            continue
        if len(cells) < len(header):
            cells.extend([""] * (len(header) - len(cells)))
        rows.append(dict(zip(header, cells)))
    return rows


def _format_brand_row(record: CustomerRecord) -> str:
    return (
        f"| {record.name} | {record.stage} | {record.business_direction} | "
        f"{record.current_need} | {record.recent_progress} | {record.next_action} | {record.next_follow_up_date} | "
        f"{record.contact} | [[客户/客户--{record.name}]] | {record.updated_at} |"
    )


def _format_shop_group_row(record: CustomerRecord) -> str:
    return (
        f"| {record.name} | {record.stage} | {record.business_direction} | {record.shop_scale} | "
        f"{record.current_need} | {record.recent_progress} | {record.next_action} | {record.next_follow_up_date} | "
        f"{record.contact} | [[客户/客户--{record.name}]] | {record.updated_at} |"
    )


def _format_shop_ka_row(record: CustomerRecord) -> str:
    return (
        f"| {record.name} | {record.stage} | {record.business_direction} | {record.shop_scale} | "
        f"{record.current_need} | {record.recent_progress} | {record.next_action} | {record.next_follow_up_date} | "
        f"{record.contact} | [[客户/客户--{record.name}]] | {record.updated_at} |"
    )


def _format_blogger_row(record: CustomerRecord) -> str:
    secondary_tags = record.secondary_tags or "待补充"
    return (
        f"| {record.name} | {record.stage} | {record.business_direction} | {record.customer_type} | {secondary_tags} | "
        f"{record.current_need} | {record.recent_progress} | {record.next_action} | {record.next_follow_up_date} | "
        f"{record.contact} | [[客户/客户--{record.name}]] | {record.updated_at} |"
    )


def _format_communication_block(entry: CommunicationEntry) -> str:
    summary = entry.summary or "待补充"
    new_info = entry.new_info or "待补充"
    risk = entry.risk or "待补充"
    next_step = entry.next_step or "待补充"
    return (
        f"### {entry.entry_date}\n"
        f"- 本次沟通结论：{summary}\n"
        f"- 新增信息：{new_info}\n"
        f"- 风险/顾虑：{risk}\n"
        f"- 下一步：{next_step}\n"
    )


def sort_project_records(records: list[ProjectRecord]) -> list[ProjectRecord]:
    return [
        record
        for _index, record in sorted(
            enumerate(records),
            key=lambda item: (_project_updated_at_sort_key(item[1].updated_at), -item[0]),
            reverse=True,
        )
    ]


def _parse_approval_entries(text: str, heading: str) -> list[ApprovalEntry]:
    body = _section_body(text, heading)
    entries: list[ApprovalEntry] = []
    for match in re.finditer(r"^### (?P<head>.+?)\n(?P<body>.*?)(?=^### |\Z)", body, flags=re.M | re.S):
        head = match.group("head").strip()
        head_match = re.match(r"(?P<date>\d{4}-\d{2}-\d{2})(?:\s+(?P<title>.*))?$", head)
        entry_date = head_match.group("date").strip() if head_match else head
        heading_title = head_match.group("title").strip() if head_match and head_match.group("title") else ""
        data = _bullet_map(match.group("body"))
        title = data.get("审批标题/用途说明", "")
        if title in {"", "待补充"}:
            title = heading_title
        entries.append(
            ApprovalEntry(
                entry_date=entry_date,
                approval_type=data.get("审批类型", ""),
                title_or_usage=title,
                counterparty=data.get("对应公司", ""),
                approval_status=data.get("审批状态", ""),
                approval_result=data.get("审批结果", ""),
                current_node=data.get("当前节点", ""),
                completed_at=data.get("审批完成时间", ""),
                attachment_clue=data.get("附件线索", ""),
                note=data.get("备注", ""),
                source=data.get("来源", "钉钉审批") or "钉钉审批",
            )
        )
    return sort_approval_entries(entries)


def _format_approval_block(entry: ApprovalEntry) -> str:
    title = (entry.title_or_usage or "审批记录").strip()
    return (
        f"### {entry.entry_date} {title}\n"
        f"- 审批类型：{entry.approval_type or '待补充'}\n"
        f"- 审批标题/用途说明：{title}\n"
        f"- 对应公司：{entry.counterparty or '待补充'}\n"
        f"- 审批状态：{entry.approval_status or '待补充'}\n"
        f"- 审批结果：{entry.approval_result or '--'}\n"
        f"- 当前节点：{entry.current_node or '--'}\n"
        f"- 审批完成时间：{entry.completed_at or '--'}\n"
        f"- 附件线索：{entry.attachment_clue or '待补充'}\n"
        f"- 备注：{entry.note or '待补充'}\n"
        f"- 来源：{entry.source or '钉钉审批'}\n"
    )


def _format_approval_section(entries: list[ApprovalEntry], empty_line: str) -> str:
    if not entries:
        return f"{empty_line.rstrip()}\n"
    return "\n".join(_format_approval_block(entry).rstrip() for entry in entries).rstrip() + "\n"


def _approval_identity(entry: ApprovalEntry) -> tuple[str, str, str]:
    return (
        entry.entry_date.strip(),
        entry.title_or_usage.strip(),
        entry.counterparty.strip(),
    )


def _merge_approval_entries(existing: list[ApprovalEntry], new_entries: list[ApprovalEntry]) -> list[ApprovalEntry]:
    merged: list[ApprovalEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in [*new_entries, *existing]:
        identity = _approval_identity(entry)
        if identity in seen:
            continue
        seen.add(identity)
        merged.append(entry)
    return sort_approval_entries(merged)


def sort_approval_entries(entries: list[ApprovalEntry]) -> list[ApprovalEntry]:
    return [
        entry
        for _index, entry in sorted(
            enumerate(entries),
            key=lambda item: (_approval_sort_key(item[1]), -item[0]),
            reverse=True,
        )
    ]


def _project_updated_at_sort_key(value: str) -> tuple[int, int, int, int, int, int]:
    normalized = (value or "").strip()
    if not normalized or normalized in PLACEHOLDER_UPDATED_AT:
        return (0, 0, 0, 0, 0, 0)
    parsed = _parse_datetime_like(normalized)
    if parsed is None:
        return (0, 0, 0, 0, 0, 0)
    return _datetime_sort_components(parsed, present=1)


def _approval_sort_key(entry: ApprovalEntry) -> tuple[int, int, int, int, int, int]:
    for candidate in (entry.completed_at, entry.entry_date):
        normalized = (candidate or "").strip()
        if normalized and normalized not in {"--", "待补充", "待确认", "待补日期"}:
            parsed = _parse_datetime_like(normalized)
            if parsed is not None:
                return _datetime_sort_components(parsed, present=1)
            return (1, 0, 0, 0, 0, 0)
    return (0, 0, 0, 0, 0, 0)


def _datetime_sort_components(value: datetime | date, *, present: int) -> tuple[int, int, int, int, int, int]:
    if isinstance(value, datetime):
        return (present, value.year, value.month, value.day, value.hour, value.minute)
    return (present, value.year, value.month, value.day, 0, 0)


def _parse_datetime_like(value: str) -> datetime | date | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    match = re.search(r"(20\d{2}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)", normalized)
    if match:
        candidate = match.group(1).replace(" ", "T")
        for parser in (datetime.fromisoformat, date.fromisoformat):
            try:
                return parser(candidate)  # type: ignore[return-value]
            except ValueError:
                continue
    for parser in (datetime.fromisoformat, date.fromisoformat):
        try:
            return parser(normalized)  # type: ignore[return-value]
        except ValueError:
            continue
    return None


def summarize_approval_entry(entry: ApprovalEntry | None) -> str:
    if entry is None:
        return "暂无审批记录"
    status = entry.approval_status or entry.approval_result or "待补审批状态"
    detail = next(
        (
            value
            for value in (entry.current_node, entry.completed_at, entry.counterparty)
            if value and value not in {"--", "待补充"}
        ),
        "",
    )
    if detail and detail not in {"--", "待补充"}:
        return f"{status} · {detail}"
    return status


class MarkdownCustomerStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_customer_root()
        self.summary_path = self.root / SUMMARY_FILE
        self.customer_dir = self.root / CUSTOMER_DIR

    def list_customers(self) -> list[CustomerRecord]:
        if not self.summary_path.exists():
            return []
        text = self.summary_path.read_text(encoding="utf-8")
        records = self._records_from_section(text, "品牌客户总表", "品牌客户")
        records.extend(self._records_from_section(text, "网店KA客户总表", "网店KA客户"))
        records.extend(self._records_from_section(text, "网店店群客户总表", "网店店群客户"))
        records.extend(self._records_from_section(text, "博主总表", "博主"))
        return records

    def list_focus_customers(self) -> list[CustomerRecord]:
        return [record for record in self.list_customers() if record.stage not in {"暂缓", "已归档"}][:3]

    def get_customer(self, name: str) -> CustomerDetail:
        path = self._customer_path(name)
        if not path.exists():
            raise KeyError(name)
        text = path.read_text(encoding="utf-8")
        basic = _bullet_map(_section_body(text, "基本信息"))
        profile = _bullet_map(_section_body(text, "业务画像"))
        judgement = _bullet_map(_section_body(text, "当前判断"))
        need = _bullet_map(_section_body(text, "当前需求"))
        party_a = _bullet_map(_section_body(text, "甲方信息"))
        entries = self._parse_communications(text)
        pending_approvals = _parse_approval_entries(text, "待归属审批")
        latest_summary = entries[0].summary if entries else ""
        return CustomerDetail(
            name=basic.get("客户名称", name),
            customer_type=basic.get("客户类型", ""),
            stage=judgement.get("阶段", ""),
            secondary_tags=basic.get("二级标签", ""),
            business_direction=profile.get("主要业务方向", ""),
            current_need=need.get("需求一句话", ""),
            recent_progress=latest_summary,
            next_action=judgement.get("下次动作", ""),
            next_follow_up_date=judgement.get("下次跟进日期", ""),
            contact=basic.get("当前联系人", ""),
            page_link=f"[[客户/客户--{name}]]",
            updated_at=judgement.get("更新时间", ""),
            shop_scale=profile.get("关键数量/规模", ""),
            page_path=path,
            company=basic.get("所属公司/主体", ""),
            phone=basic.get("联系电话", ""),
            wechat_id=basic.get("微信号", ""),
            source=basic.get("来源", ""),
            main_work_path=basic.get("主业文件路径", ""),
            external_material_path=basic.get("对外资料路径", ""),
            typical_need=profile.get("典型诉求", ""),
            contract_payment=profile.get("合同/付款特征", ""),
            current_focus=judgement.get("当前重点", ""),
            likelihood=judgement.get("合作可能性", ""),
            goal=need.get("目标", ""),
            deliverable=need.get("交付物/采购内容", ""),
            time_requirement=need.get("时间要求", ""),
            budget_clue=need.get("预算/报价线索", ""),
            constraints=need.get("限制条件", ""),
            communication_entries=entries,
            party_a_brand=party_a.get("甲方品牌", ""),
            party_a_company=party_a.get("对应公司/主体", ""),
            party_a_contact=party_a.get("收件联系人", ""),
            party_a_phone=party_a.get("联系电话", ""),
            party_a_email=party_a.get("电子邮箱", ""),
            party_a_address=party_a.get("通讯地址", ""),
            pending_approval_entries=pending_approvals,
            pending_approval_count=len(pending_approvals),
            raw_text=text,
        )

    def upsert_customer(self, draft: CustomerDraft) -> CustomerDetail:
        self.root.mkdir(parents=True, exist_ok=True)
        self.customer_dir.mkdir(parents=True, exist_ok=True)
        updated_at = draft.resolved_updated_at()
        original_name = draft.original_name.strip()
        source_name = original_name or draft.name
        source_path = self._customer_path(source_name)
        target_path = self._customer_path(draft.name)
        is_rename = bool(original_name and original_name != draft.name)
        existing_pending_approvals: list[ApprovalEntry] = []

        if is_rename:
            if target_path.exists():
                raise ValueError(f"客户「{draft.name}」已存在，不能重命名覆盖。")
            if not source_path.exists():
                raise KeyError(source_name)
            text = source_path.read_text(encoding="utf-8")
            existing_pending_approvals = _parse_approval_entries(text, "待归属审批")
            text = _replace_page_title(text, draft.name)
        elif target_path.exists():
            text = target_path.read_text(encoding="utf-8")
            existing_pending_approvals = _parse_approval_entries(text, "待归属审批")
            text = self._update_existing_page(text, draft, updated_at)
        else:
            text = self._build_new_page(draft, updated_at)
        if is_rename:
            text = self._update_existing_page(text, draft, updated_at)
        if draft.communication:
            text = self._upsert_communication(text, draft.communication)
        pending_approvals = draft.pending_approval_entries or existing_pending_approvals
        text = self._replace_pending_approval_section(text, pending_approvals)
        target_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        if is_rename:
            source_path.unlink(missing_ok=True)
        self._upsert_summary_row(draft, updated_at)
        return self.get_customer(draft.name)

    def _records_from_section(self, text: str, section_name: str, customer_type: str) -> list[CustomerRecord]:
        records: list[CustomerRecord] = []
        for row in _parse_table(_section_body(text, section_name)):
            name = row.get("客户", "").strip()
            if not name or name in PLACEHOLDER_NAMES:
                continue
            page_link = row.get("对应客户页", "").strip()
            page_path = None
            if page_link:
                target = _extract_wikilink_target(page_link)
                page_path = self.root / f"{target}.md"
            records.append(
                CustomerRecord(
                    name=name,
                    customer_type=(row.get("客户类型", "").strip() or customer_type),
                    stage=row.get("阶段", "").strip(),
                    secondary_tags=row.get("二级标签", "").strip(),
                    business_direction=row.get("业务方向", "").strip(),
                    current_need=row.get("当前需求", "").strip(),
                    recent_progress=row.get("最近推进", "").strip(),
                    next_action=row.get("下次动作", "").strip(),
                    next_follow_up_date=row.get("下次跟进日期", "").strip(),
                    contact=row.get("主联系人", "").strip(),
                    page_link=page_link,
                    updated_at=row.get("更新时间", "").strip(),
                    shop_scale=(row.get("店铺规模", "") or row.get("店铺/产品状态", "")).strip(),
                    page_path=page_path,
                )
            )
        return records

    def _customer_path(self, name: str) -> Path:
        return self.customer_dir / f"客户--{name}.md"

    def _parse_communications(self, text: str) -> list[CommunicationEntry]:
        body = _section_body(text, "沟通沉淀")
        entries: list[CommunicationEntry] = []
        for match in re.finditer(r"^### (?P<date>.+?)\n(?P<body>.*?)(?=^### |\Z)", body, flags=re.M | re.S):
            data = _bullet_map(match.group("body"))
            entries.append(
                CommunicationEntry(
                    entry_date=match.group("date").strip(),
                    summary=data.get("本次沟通结论", ""),
                    new_info=data.get("新增信息", ""),
                    risk=data.get("风险/顾虑", ""),
                    next_step=data.get("下一步", ""),
                )
            )
        return entries

    def _build_new_page(self, draft: CustomerDraft, updated_at: str) -> str:
        is_shop_group = _has_customer_type(draft.customer_type, "网店店群客户")
        is_shop_ka = _has_customer_type(draft.customer_type, "网店KA客户")
        is_blogger = _has_customer_type(draft.customer_type, "博主")
        default_main_work_path = (
            f"/Users/gd/Desktop/主业/品牌项目/品牌--{draft.name}/"
            if _has_customer_type(draft.customer_type, "品牌客户")
            else "待补充"
        )
        contract_payment_parts: list[str] = []
        if is_shop_group:
            contract_payment_parts.append("关注批量折扣、付款方式、开票/合同需求")
        if is_shop_ka:
            contract_payment_parts.append("已付费产品使用深化、功能跟进、增购/新功能转化")
        if is_blogger:
            contract_payment_parts.insert(0, "功能推广合作、内容排期、样稿/报价及使用者转化情况")
        contract_payment = "；".join(contract_payment_parts) or "待补充"
        return f"""# 客户--{draft.name}

## 基本信息
- 客户类型：{draft.customer_type}
- 二级标签：{draft.secondary_tags or "待补充"}
- 客户名称：{draft.name}
- 所属公司/主体：{draft.company or "待补充"}
- 当前联系人：{draft.contact or "待补充"}
- 联系电话：{draft.phone or "待补充"}
- 微信号：{draft.wechat_id or "待补充"}
- 来源：{draft.source or "快速录入"}
- 主业文件路径：`{draft.main_work_path or default_main_work_path}`
- 对外资料路径：{draft.external_material_path or "待补充"}

## 甲方信息
- 甲方品牌：{draft.party_a_brand or "待补充"}
- 对应公司/主体：{draft.party_a_company or "待补充"}
- 收件联系人：{draft.party_a_contact or "待补充"}
- 联系电话：{draft.party_a_phone or "待补充"}
- 电子邮箱：{draft.party_a_email or "待补充"}
- 通讯地址：{draft.party_a_address or "待补充"}

## 业务画像
- 主要业务方向：{draft.business_direction or "待补充"}
- 典型诉求：{draft.current_need or "待补充"}
- 关键数量/规模：{draft.shop_scale or "待补充"}
- 合同/付款特征：{contract_payment}

## 当前判断
- 阶段：{draft.stage}
- 当前重点：{draft.current_need or "待补充"}
- 合作可能性：待补充
- 下次动作：{draft.next_action or "待补充"}
- 下次跟进日期：{draft.next_follow_up_date or "待补充"}
- 更新时间：{updated_at}

## 当前需求
- 需求一句话：{draft.current_need or "待补充"}
- 目标：待补充
- 交付物/采购内容：{draft.business_direction or "待补充"}
- 时间要求：待补充
- 预算/报价线索：待补充
- 限制条件：待补充

## 关系人
- 暂无关系人

## 沟通沉淀

## 待归属审批
{_format_approval_section(draft.pending_approval_entries, "- 暂无待归属审批")}

## 历史推进
- {updated_at}：通过草莓客户管理系统快速录入

## 待补资料
- 所属公司/主体
- 当前联系人
- 预算/报价线索
"""

    def _update_existing_page(self, text: str, draft: CustomerDraft, updated_at: str) -> str:
        text = self._ensure_customer_sections(text)
        updates = [
            ("基本信息", "客户类型", draft.customer_type),
            ("基本信息", "二级标签", draft.secondary_tags),
            ("基本信息", "客户名称", draft.name),
            ("基本信息", "所属公司/主体", draft.company),
            ("基本信息", "当前联系人", draft.contact),
            ("基本信息", "联系电话", draft.phone),
            ("基本信息", "微信号", draft.wechat_id),
            ("基本信息", "来源", draft.source),
            ("基本信息", "主业文件路径", f"`{draft.main_work_path}`" if draft.main_work_path else ""),
            ("基本信息", "对外资料路径", draft.external_material_path),
            ("甲方信息", "甲方品牌", draft.party_a_brand),
            ("甲方信息", "对应公司/主体", draft.party_a_company),
            ("甲方信息", "收件联系人", draft.party_a_contact),
            ("甲方信息", "联系电话", draft.party_a_phone),
            ("甲方信息", "电子邮箱", draft.party_a_email),
            ("甲方信息", "通讯地址", draft.party_a_address),
            ("业务画像", "主要业务方向", draft.business_direction),
            ("业务画像", "典型诉求", draft.current_need),
            ("业务画像", "关键数量/规模", draft.shop_scale),
            ("当前判断", "阶段", draft.stage),
            ("当前判断", "当前重点", draft.current_need),
            ("当前判断", "下次动作", draft.next_action),
            ("当前判断", "下次跟进日期", draft.next_follow_up_date),
            ("当前判断", "更新时间", updated_at),
            ("当前需求", "需求一句话", draft.current_need),
            ("当前需求", "交付物/采购内容", draft.business_direction),
        ]
        for section, key, value in updates:
            text = _replace_or_add_bullet(text, section, key, value)
        return text

    def _ensure_customer_sections(self, text: str) -> str:
        text = _ensure_section(
            text,
            "甲方信息",
            (
                "- 甲方品牌：待补充\n"
                "- 对应公司/主体：待补充\n"
                "- 收件联系人：待补充\n"
                "- 联系电话：待补充\n"
                "- 电子邮箱：待补充\n"
                "- 通讯地址：待补充"
            ),
        )
        text = _ensure_section(text, "待归属审批", "- 暂无待归属审批")
        text = _ensure_section(text, "关系人", "- 暂无关系人")
        return text

    def append_pending_approval(self, customer_name: str, entry: ApprovalEntry) -> CustomerDetail:
        detail = self.get_customer(customer_name)
        draft = CustomerDraft(
            name=detail.name,
            customer_type=detail.customer_type,
            stage=detail.stage,
            business_direction=detail.business_direction,
            contact=detail.contact,
            phone=detail.phone,
            wechat_id=detail.wechat_id,
            company=detail.company,
            source=detail.source,
            main_work_path=detail.main_work_path,
            external_material_path=detail.external_material_path,
            shop_scale=detail.shop_scale,
            secondary_tags=detail.secondary_tags,
            current_need=detail.current_need,
            recent_progress=detail.recent_progress,
            next_action=detail.next_action,
            next_follow_up_date=detail.next_follow_up_date,
            party_a_brand=detail.party_a_brand,
            party_a_company=detail.party_a_company,
            party_a_contact=detail.party_a_contact,
            party_a_phone=detail.party_a_phone,
            party_a_email=detail.party_a_email,
            party_a_address=detail.party_a_address,
            pending_approval_entries=_merge_approval_entries(detail.pending_approval_entries, [entry]),
            updated_at=detail.updated_at or entry.entry_date,
        )
        return self.upsert_customer(draft)

    def _upsert_communication(self, text: str, entry: CommunicationEntry) -> str:
        body = _section_body(text, "沟通沉淀")
        block = _format_communication_block(entry)
        pattern = rf"^### {re.escape(entry.entry_date)}\n.*?(?=^### |\Z)"
        if re.search(pattern, body, flags=re.M | re.S):
            body = re.sub(pattern, block.rstrip() + "\n", body, count=1, flags=re.M | re.S)
        else:
            body = (block + "\n" + body.lstrip()).rstrip() + "\n"
        return _replace_section_body(text, "沟通沉淀", body)

    def _replace_pending_approval_section(self, text: str, entries: list[ApprovalEntry]) -> str:
        text = self._ensure_customer_sections(text)
        return _replace_section_body(text, "待归属审批", _format_approval_section(entries, "- 暂无待归属审批"))

    def _upsert_summary_row(self, draft: CustomerDraft, updated_at: str) -> None:
        if not self.summary_path.exists():
            self.summary_path.write_text(self._default_summary_text(), encoding="utf-8")
        text = self._ensure_summary_sections(self.summary_path.read_text(encoding="utf-8"))
        original_name = draft.original_name.strip()
        if original_name and original_name != draft.name:
            for section_name in ("本周重点跟进", "品牌客户总表", "网店KA客户总表", "网店店群客户总表", "博主总表", "暂缓 / 待观察"):
                text = self._remove_row_in_section(text, section_name, original_name)
        record = CustomerRecord(
            name=draft.name,
            customer_type=draft.customer_type,
            stage=draft.stage,
            secondary_tags=draft.secondary_tags,
            business_direction=draft.business_direction,
            current_need=draft.current_need,
            recent_progress=draft.recent_progress,
            next_action=draft.next_action,
            next_follow_up_date=draft.next_follow_up_date,
            contact=draft.contact,
            page_link=f"[[客户/客户--{draft.name}]]",
            updated_at=updated_at,
            shop_scale=draft.shop_scale,
        )
        if _has_customer_type(draft.customer_type, "博主"):
            text = self._upsert_row_in_section(text, "博主总表", draft.name, _format_blogger_row(record))
        elif _has_customer_type(draft.customer_type, "网店店群客户"):
            text = self._upsert_row_in_section(text, "网店店群客户总表", draft.name, _format_shop_group_row(record))
        elif _has_customer_type(draft.customer_type, "网店KA客户"):
            text = self._upsert_row_in_section(text, "网店KA客户总表", draft.name, _format_shop_ka_row(record))
        else:
            text = self._upsert_row_in_section(text, "品牌客户总表", draft.name, _format_brand_row(record))
        text = re.sub(r"^更新时间：.*$", f"更新时间：{updated_at}", text, count=1, flags=re.M)
        self.summary_path.write_text(text.rstrip() + "\n", encoding="utf-8")

    def _ensure_summary_sections(self, text: str) -> str:
        sections = {
            "本周重点跟进": (
                "| 客户 | 客户类型 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 对应客户页 | 更新时间 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- |"
            ),
            "品牌客户总表": (
                "| 客户 | 阶段 | 业务方向 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
            ),
            "网店KA客户总表": (
                "| 客户 | 阶段 | 业务方向 | 店铺/产品状态 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
            ),
            "网店店群客户总表": (
                "| 客户 | 阶段 | 业务方向 | 店铺规模 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
            ),
            "博主总表": (
                "| 客户 | 阶段 | 业务方向 | 客户类型 | 二级标签 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |\n"
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
            ),
            "暂缓 / 待观察": (
                "| 客户 | 客户类型 | 暂缓原因 | 下次观察点 | 下次跟进日期 | 对应客户页 | 更新时间 |\n"
                "| --- | --- | --- | --- | --- | --- | --- |"
            ),
        }
        for heading, body in sections.items():
            text = _ensure_section(text, heading, body)
            text = _replace_table_header(text, heading, body)
        return text

    def _remove_row_in_section(self, text: str, section_name: str, name: str) -> str:
        body = _section_body(text, section_name)
        table_lines = [line for line in body.splitlines() if line.strip().startswith("|")]
        if len(table_lines) < 2:
            return text

        header_line = table_lines[0]
        separator_line = table_lines[1]
        data_lines = table_lines[2:]
        kept_lines: list[str] = []
        for line in data_lines:
            cells = _split_markdown_row(line)
            if not cells:
                continue
            if cells[0].strip() == name:
                continue
            kept_lines.append(line)

        new_body = "\n" + "\n".join([header_line, separator_line, *kept_lines]) + "\n\n"
        return _replace_section_body(text, section_name, new_body)

    def _upsert_row_in_section(self, text: str, section_name: str, name: str, row_text: str) -> str:
        body = _section_body(text, section_name)
        table_lines = [line for line in body.splitlines() if line.strip().startswith("|")]
        if len(table_lines) < 2:
            new_body = f"\n{row_text}\n"
            return _replace_section_body(text, section_name, new_body)

        header_line = table_lines[0]
        separator_line = table_lines[1]
        data_lines = table_lines[2:]

        new_data_lines: list[str] = []
        replaced = False
        for line in data_lines:
            cells = _split_markdown_row(line)
            if not cells:
                continue
            first = cells[0].strip()
            if first in PLACEHOLDER_NAMES:
                continue
            if first == name:
                new_data_lines.append(row_text)
                replaced = True
            else:
                new_data_lines.append(line)
        if not replaced:
            new_data_lines.append(row_text)

        new_body = "\n" + "\n".join([header_line, separator_line, *new_data_lines]) + "\n\n"
        return _replace_section_body(text, section_name, new_body)

    def _default_summary_text(self) -> str:
        return """# 客户总表

更新时间：

## 本周重点跟进

| 客户 | 客户类型 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- |

## 品牌客户总表

| 客户 | 阶段 | 业务方向 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 网店KA客户总表

| 客户 | 阶段 | 业务方向 | 店铺/产品状态 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 网店店群客户总表

| 客户 | 阶段 | 业务方向 | 店铺规模 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 博主总表

| 客户 | 阶段 | 业务方向 | 客户类型 | 二级标签 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 暂缓 / 待观察

| 客户 | 客户类型 | 暂缓原因 | 下次观察点 | 下次跟进日期 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- |
"""
