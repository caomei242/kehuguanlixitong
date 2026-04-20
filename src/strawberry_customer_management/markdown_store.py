from __future__ import annotations

import re
from pathlib import Path

from strawberry_customer_management.models import (
    CommunicationEntry,
    CustomerDetail,
    CustomerDraft,
    CustomerRecord,
)
from strawberry_customer_management.paths import default_customer_root


SUMMARY_FILE = "00 客户总表.md"
CUSTOMER_DIR = "客户"
PLACEHOLDER_NAMES = {"待录入", "暂无"}


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
        f"{record.current_need} | {record.recent_progress} | {record.next_action} | "
        f"{record.contact} | [[客户/客户--{record.name}]] | {record.updated_at} |"
    )


def _format_shop_group_row(record: CustomerRecord) -> str:
    return (
        f"| {record.name} | {record.stage} | {record.business_direction} | {record.shop_scale} | "
        f"{record.current_need} | {record.recent_progress} | {record.next_action} | "
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
        records.extend(self._records_from_section(text, "网店店群客户总表", "网店店群客户"))
        return records

    def list_focus_customers(self) -> list[CustomerRecord]:
        return [record for record in self.list_customers() if record.stage != "暂缓"][:3]

    def get_customer(self, name: str) -> CustomerDetail:
        path = self._customer_path(name)
        if not path.exists():
            raise KeyError(name)
        text = path.read_text(encoding="utf-8")
        basic = _bullet_map(_section_body(text, "基本信息"))
        profile = _bullet_map(_section_body(text, "业务画像"))
        judgement = _bullet_map(_section_body(text, "当前判断"))
        need = _bullet_map(_section_body(text, "当前需求"))
        entries = self._parse_communications(text)
        latest_summary = entries[0].summary if entries else ""
        return CustomerDetail(
            name=basic.get("客户名称", name),
            customer_type=basic.get("客户类型", ""),
            stage=judgement.get("阶段", ""),
            business_direction=profile.get("主要业务方向", ""),
            current_need=need.get("需求一句话", ""),
            recent_progress=latest_summary,
            next_action=judgement.get("下次动作", ""),
            contact=basic.get("当前联系人", ""),
            page_link=f"[[客户/客户--{name}]]",
            updated_at=judgement.get("更新时间", ""),
            shop_scale=profile.get("关键数量/规模", ""),
            page_path=path,
            company=basic.get("所属公司/主体", ""),
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
            raw_text=text,
        )

    def upsert_customer(self, draft: CustomerDraft) -> CustomerDetail:
        self.root.mkdir(parents=True, exist_ok=True)
        self.customer_dir.mkdir(parents=True, exist_ok=True)
        updated_at = draft.resolved_updated_at()
        path = self._customer_path(draft.name)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            text = self._update_existing_page(text, draft, updated_at)
        else:
            text = self._build_new_page(draft, updated_at)
        if draft.communication:
            text = self._upsert_communication(text, draft.communication)
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
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
                    customer_type=customer_type,
                    stage=row.get("阶段", "").strip(),
                    business_direction=row.get("业务方向", "").strip(),
                    current_need=row.get("当前需求", "").strip(),
                    recent_progress=row.get("最近推进", "").strip(),
                    next_action=row.get("下次动作", "").strip(),
                    contact=row.get("主联系人", "").strip(),
                    page_link=page_link,
                    updated_at=row.get("更新时间", "").strip(),
                    shop_scale=row.get("店铺规模", "").strip(),
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
        is_shop_group = draft.customer_type == "网店店群客户"
        default_main_work_path = (
            f"/Users/gd/Desktop/主业/品牌项目/品牌--{draft.name}/"
            if draft.customer_type == "品牌客户"
            else "待补充"
        )
        return f"""# 客户--{draft.name}

## 基本信息
- 客户类型：{draft.customer_type}
- 客户名称：{draft.name}
- 所属公司/主体：{draft.company or "待补充"}
- 当前联系人：{draft.contact or "待补充"}
- 来源：{draft.source or "快速录入"}
- 主业文件路径：`{draft.main_work_path or default_main_work_path}`
- 对外资料路径：{draft.external_material_path or "待补充"}

## 业务画像
- 主要业务方向：{draft.business_direction or "待补充"}
- 典型诉求：{draft.current_need or "待补充"}
- 关键数量/规模：{draft.shop_scale or "待补充"}
- 合同/付款特征：{"关注批量折扣、付款方式、开票/合同需求" if is_shop_group else "待补充"}

## 当前判断
- 阶段：{draft.stage}
- 当前重点：{draft.current_need or "待补充"}
- 合作可能性：待补充
- 下次动作：{draft.next_action or "待补充"}
- 更新时间：{updated_at}

## 当前需求
- 需求一句话：{draft.current_need or "待补充"}
- 目标：待补充
- 交付物/采购内容：{draft.business_direction or "待补充"}
- 时间要求：待补充
- 预算/报价线索：待补充
- 限制条件：待补充

## 沟通沉淀

## 历史推进
- {updated_at}：通过草莓客户管理系统快速录入

## 待补资料
- 所属公司/主体
- 当前联系人
- 预算/报价线索
"""

    def _update_existing_page(self, text: str, draft: CustomerDraft, updated_at: str) -> str:
        updates = [
            ("基本信息", "客户类型", draft.customer_type),
            ("基本信息", "客户名称", draft.name),
            ("基本信息", "所属公司/主体", draft.company),
            ("基本信息", "当前联系人", draft.contact),
            ("基本信息", "来源", draft.source),
            ("基本信息", "主业文件路径", f"`{draft.main_work_path}`" if draft.main_work_path else ""),
            ("基本信息", "对外资料路径", draft.external_material_path),
            ("业务画像", "主要业务方向", draft.business_direction),
            ("业务画像", "典型诉求", draft.current_need),
            ("业务画像", "关键数量/规模", draft.shop_scale),
            ("当前判断", "阶段", draft.stage),
            ("当前判断", "当前重点", draft.current_need),
            ("当前判断", "下次动作", draft.next_action),
            ("当前判断", "更新时间", updated_at),
            ("当前需求", "需求一句话", draft.current_need),
            ("当前需求", "交付物/采购内容", draft.business_direction),
        ]
        for section, key, value in updates:
            text = _replace_or_add_bullet(text, section, key, value)
        return text

    def _upsert_communication(self, text: str, entry: CommunicationEntry) -> str:
        body = _section_body(text, "沟通沉淀")
        block = _format_communication_block(entry)
        pattern = rf"^### {re.escape(entry.entry_date)}\n.*?(?=^### |\Z)"
        if re.search(pattern, body, flags=re.M | re.S):
            body = re.sub(pattern, block.rstrip() + "\n", body, count=1, flags=re.M | re.S)
        else:
            body = (block + "\n" + body.lstrip()).rstrip() + "\n"
        return _replace_section_body(text, "沟通沉淀", body)

    def _upsert_summary_row(self, draft: CustomerDraft, updated_at: str) -> None:
        if not self.summary_path.exists():
            self.summary_path.write_text(self._default_summary_text(), encoding="utf-8")
        text = self.summary_path.read_text(encoding="utf-8")
        record = CustomerRecord(
            name=draft.name,
            customer_type=draft.customer_type,
            stage=draft.stage,
            business_direction=draft.business_direction,
            current_need=draft.current_need,
            recent_progress=draft.recent_progress,
            next_action=draft.next_action,
            contact=draft.contact,
            page_link=f"[[客户/客户--{draft.name}]]",
            updated_at=updated_at,
            shop_scale=draft.shop_scale,
        )
        if draft.customer_type == "网店店群客户":
            text = self._upsert_row_in_section(text, "网店店群客户总表", draft.name, _format_shop_group_row(record))
        else:
            text = self._upsert_row_in_section(text, "品牌客户总表", draft.name, _format_brand_row(record))
        text = re.sub(r"^更新时间：.*$", f"更新时间：{updated_at}", text, count=1, flags=re.M)
        self.summary_path.write_text(text.rstrip() + "\n", encoding="utf-8")

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

| 客户 | 客户类型 | 当前需求 | 最近推进 | 下次动作 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- |

## 品牌客户总表

| 客户 | 阶段 | 业务方向 | 当前需求 | 最近推进 | 下次动作 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 网店店群客户总表

| 客户 | 阶段 | 业务方向 | 店铺规模 | 当前需求 | 最近推进 | 下次动作 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 暂缓 / 待观察

| 客户 | 客户类型 | 暂缓原因 | 下次观察点 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- |
"""
