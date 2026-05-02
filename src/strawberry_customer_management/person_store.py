from __future__ import annotations

import re
from pathlib import Path

from strawberry_customer_management.markdown_store import (
    _bullet_map,
    _clean_cell,
    _extract_wikilink_target,
    _format_markdown_row,
    _is_separator_row,
    _section_body,
    _split_markdown_row,
)
from strawberry_customer_management.models import (
    INTERNAL_MAIN_WORK_NAME,
    PERSON_GENDERS,
    PERSON_SIDES,
    PersonDetail,
    PersonDraft,
    PersonProjectLink,
    PersonRecord,
)
from strawberry_customer_management.paths import default_person_root


SUMMARY_FILE = "00 关系人总表.md"
PERSON_DIR = "人员"
SUMMARY_SECTION = "关系人总表"
SUMMARY_HEADER = (
    "| 姓名 | 性别 | 所属方 | 所属组织 | 所属品牌 | 常见关系 | 关联客户 | 关联项目 | 对应人员页 | 更新时间 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)
PLACEHOLDER_VALUES = {"", "待补充", "待确认", "待判断", "--"}


def _safe_file_stem(value: str) -> str:
    cleaned = value.strip().replace("/", "-").replace(":", "-")
    return cleaned or "未命名人员"


def _person_page_link(name: str) -> str:
    return f"[[{PERSON_DIR}/{_safe_file_stem(name)}]]"


def _clean_optional(value: str) -> str:
    normalized = value.strip()
    return "" if normalized in PLACEHOLDER_VALUES else normalized


def _merge_text(new_value: str, old_value: str) -> str:
    return new_value.strip() or old_value.strip()


def _merge_list(*values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for items in values:
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            result.append(normalized)
            seen.add(normalized)
    return result


def _merge_project_links(*values: list[PersonProjectLink]) -> list[PersonProjectLink]:
    result: list[PersonProjectLink] = []
    seen: set[tuple[str, str, str, str]] = set()
    for items in values:
        for item in items:
            key = (item.customer_name.strip(), item.project_name.strip(), item.side.strip(), item.relation.strip())
            if not any(key) or key in seen:
                continue
            result.append(item)
            seen.add(key)
    return result


def _linked_customers_from_project_links(values: list[PersonProjectLink]) -> list[str]:
    return [
        link.customer_name
        for link in values
        if link.customer_name.strip() and link.customer_name.strip() != INTERNAL_MAIN_WORK_NAME
    ]


def _table_rows(section: str) -> list[dict[str, str]]:
    lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []
    header = _split_markdown_row(lines[0])
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if _is_separator_row(cells):
            continue
        if len(cells) < len(header):
            cells.extend([""] * (len(header) - len(cells)))
        rows.append(dict(zip(header, cells)))
    return rows


def _extract_name_from_link(value: str) -> str:
    target = _extract_wikilink_target(value)
    return Path(target).name.strip()


class MarkdownPersonStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_person_root()
        self.summary_path = self.root / SUMMARY_FILE
        self.person_dir = self.root / PERSON_DIR

    def list_people(self) -> list[PersonRecord]:
        if not self.summary_path.exists():
            return []
        text = self.summary_path.read_text(encoding="utf-8")
        records: list[PersonRecord] = []
        for row in _table_rows(_section_body(text, SUMMARY_SECTION)):
            name = row.get("姓名", "").strip()
            if not name:
                continue
            page_link = row.get("对应人员页", "").strip()
            page_path = self.root / f"{_extract_wikilink_target(page_link)}.md" if page_link else self._person_path(name)
            records.append(
                PersonRecord(
                    name=name,
                    gender=row.get("性别", "").strip() or "待判断",
                    side=row.get("所属方", "").strip(),
                    organization=row.get("所属组织", "").strip(),
                    brand=row.get("所属品牌", "").strip(),
                    common_relation=row.get("常见关系", "").strip(),
                    linked_customers=_split_list_cell(row.get("关联客户", "")),
                    linked_projects=_split_list_cell(row.get("关联项目", "")),
                    page_link=page_link or _person_page_link(name),
                    updated_at=row.get("更新时间", "").strip(),
                    page_path=page_path,
                )
            )
        return sorted(records, key=lambda record: (record.updated_at or "", record.name), reverse=True)

    def list_people_for_customer(self, customer_name: str) -> list[PersonRecord]:
        normalized = customer_name.strip()
        if not normalized:
            return []
        return [
            person
            for person in self.list_people()
            if normalized in person.linked_customers or normalized == person.brand
        ]

    def list_people_for_project(self, customer_name: str, project_name: str) -> list[PersonDetail]:
        result: list[PersonDetail] = []
        for record in self.list_people_for_customer(customer_name):
            try:
                detail = self.get_person(record.name)
            except KeyError:
                continue
            if any(link.project_name == project_name for link in detail.project_links):
                result.append(detail)
        return result

    def get_person(self, name: str) -> PersonDetail:
        path = self._person_path(name)
        if not path.exists():
            raise KeyError(name)
        text = path.read_text(encoding="utf-8")
        basic = _bullet_map(_section_body(text, "基本信息"))
        judgement = _bullet_map(_section_body(text, "我对这个人的判断"))
        project_links = _parse_project_links(_section_body(text, "关联项目"))
        linked_customers = _parse_linked_customers(_section_body(text, "关联客户"))
        if not linked_customers:
            linked_customers = _merge_list(_linked_customers_from_project_links(project_links))
        return PersonDetail(
            name=basic.get("姓名", name),
            gender=basic.get("性别", "待判断"),
            side=basic.get("所属方", ""),
            organization=basic.get("所属组织", ""),
            brand=basic.get("所属品牌", ""),
            common_relation=basic.get("常见关系", ""),
            contact=basic.get("联系方式", ""),
            phone=basic.get("联系电话", ""),
            wechat_id=basic.get("微信号", ""),
            linked_customers=linked_customers,
            linked_projects=_merge_list([link.project_name for link in project_links]),
            page_link=_person_page_link(name),
            updated_at=basic.get("更新时间", ""),
            page_path=path,
            judgement=judgement.get("一句话", ""),
            influence=judgement.get("影响力", ""),
            suitable_for=judgement.get("适合找他/她", ""),
            not_suitable_for=judgement.get("不适合找他/她", ""),
            likes=judgement.get("喜欢/在意", ""),
            dislikes=judgement.get("不喜欢/雷区", ""),
            project_links=project_links,
            relation_notes=_section_body(text, "关系沉淀").strip(),
            raw_text=text,
        )

    def upsert_person(self, draft: PersonDraft) -> PersonDetail:
        self.root.mkdir(parents=True, exist_ok=True)
        self.person_dir.mkdir(parents=True, exist_ok=True)
        path = self._person_path(draft.name)
        existing: PersonDetail | None = None
        if path.exists():
            existing = self.get_person(draft.name)

        linked_customers = _merge_list(
            draft.linked_customers,
            _linked_customers_from_project_links(draft.project_links),
            existing.linked_customers if existing else [],
        )
        project_links = _merge_project_links(draft.project_links, existing.project_links if existing else [])
        linked_projects = _merge_list([link.project_name for link in project_links])
        gender = draft.gender if draft.gender in PERSON_GENDERS else "待判断"
        if existing and gender in {"", "待判断"} and existing.gender:
            gender = existing.gender
        side = draft.side if draft.side in PERSON_SIDES else draft.side
        if existing and not side:
            side = existing.side

        merged = PersonDetail(
            name=draft.name.strip(),
            gender=gender,
            side=side,
            organization=_merge_text(draft.organization, existing.organization if existing else ""),
            brand=_merge_text(draft.brand, existing.brand if existing else ""),
            common_relation=_merge_text(draft.common_relation, existing.common_relation if existing else ""),
            contact=_merge_text(draft.contact, existing.contact if existing else ""),
            phone=_merge_text(draft.phone, existing.phone if existing else ""),
            wechat_id=_merge_text(draft.wechat_id, existing.wechat_id if existing else ""),
            linked_customers=linked_customers,
            linked_projects=linked_projects,
            page_link=_person_page_link(draft.name),
            updated_at=draft.resolved_updated_at(),
            page_path=path,
            judgement=_merge_text(draft.judgement, existing.judgement if existing else ""),
            influence=_merge_text(draft.influence, existing.influence if existing else ""),
            suitable_for=_merge_text(draft.suitable_for, existing.suitable_for if existing else ""),
            not_suitable_for=_merge_text(draft.not_suitable_for, existing.not_suitable_for if existing else ""),
            likes=_merge_text(draft.likes, existing.likes if existing else ""),
            dislikes=_merge_text(draft.dislikes, existing.dislikes if existing else ""),
            project_links=project_links,
            relation_notes=_merge_text(draft.relation_notes, existing.relation_notes if existing else ""),
        )

        path.write_text(_format_person_page(merged), encoding="utf-8")
        self._upsert_summary_row(merged)
        return self.get_person(merged.name)

    def _person_path(self, name: str) -> Path:
        return self.person_dir / f"{_safe_file_stem(name)}.md"

    def _upsert_summary_row(self, detail: PersonDetail) -> None:
        if not self.summary_path.exists():
            self.summary_path.parent.mkdir(parents=True, exist_ok=True)
            self.summary_path.write_text(f"# 关系人总表\n\n## {SUMMARY_SECTION}\n{SUMMARY_HEADER}\n", encoding="utf-8")
        records = [record for record in self.list_people() if record.name != detail.name]
        records.append(
            PersonRecord(
                name=detail.name,
                gender=detail.gender,
                side=detail.side,
                organization=detail.organization,
                brand=detail.brand,
                common_relation=detail.common_relation,
                linked_customers=detail.linked_customers,
                linked_projects=detail.linked_projects,
                page_link=detail.page_link,
                updated_at=detail.updated_at,
                page_path=detail.page_path,
            )
        )
        records = sorted(records, key=lambda record: (record.updated_at or "", record.name), reverse=True)
        rows = [SUMMARY_HEADER]
        rows.extend(_format_summary_row(record) for record in records)
        text = self.summary_path.read_text(encoding="utf-8")
        if not _section_body(text, SUMMARY_SECTION):
            text = f"# 关系人总表\n\n## {SUMMARY_SECTION}\n"
        summary_body = "\n".join(rows).rstrip() + "\n"
        text = re.sub(
            rf"(^## {re.escape(SUMMARY_SECTION)}\n)(?P<body>.*?)(?=^## |\Z)",
            lambda match: match.group(1) + summary_body,
            text,
            count=1,
            flags=re.M | re.S,
        )
        self.summary_path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _format_summary_row(record: PersonRecord) -> str:
    return _format_markdown_row(
        [
            record.name,
            record.gender,
            record.side,
            record.organization,
            record.brand,
            record.common_relation,
            "、".join(record.linked_customers),
            "、".join(record.linked_projects),
            record.page_link or _person_page_link(record.name),
            record.updated_at,
        ]
    )


def _format_person_page(detail: PersonDetail) -> str:
    return f"""# {detail.name}

## 基本信息
- 姓名：{detail.name}
- 性别：{detail.gender or "待判断"}
- 所属方：{detail.side or "待补充"}
- 所属组织：{detail.organization or "待补充"}
- 所属品牌：{detail.brand or "待补充"}
- 常见关系：{detail.common_relation or "待补充"}
- 联系方式：{detail.contact or "待补充"}
- 联系电话：{detail.phone or "待补充"}
- 微信号：{detail.wechat_id or "待补充"}
- 更新时间：{detail.updated_at}

## 我对这个人的判断
- 一句话：{detail.judgement or "待补充"}
- 影响力：{detail.influence or "待补充"}
- 适合找他/她：{detail.suitable_for or "待补充"}
- 不适合找他/她：{detail.not_suitable_for or "待补充"}
- 喜欢/在意：{detail.likes or "待补充"}
- 不喜欢/雷区：{detail.dislikes or "待补充"}

## 关联客户
{_format_linked_customers(detail.linked_customers)}

## 关联项目
{_format_project_links(detail.project_links)}

## 关系沉淀
{detail.relation_notes or "- 待补关系沉淀"}
"""


def _format_linked_customers(values: list[str]) -> str:
    if not values:
        return "- 暂无关联客户"
    lines: list[str] = []
    for value in values:
        if value == INTERNAL_MAIN_WORK_NAME:
            lines.append(f"- {INTERNAL_MAIN_WORK_NAME}")
        else:
            lines.append(f"- [[客户/客户--{value}]]")
    return "\n".join(lines)


def _format_project_links(values: list[PersonProjectLink]) -> str:
    if not values:
        return "- 暂无关联项目"
    rows = [
        "| 所属方 | 关系 | 关联客户 | 关联项目 | 备注 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for link in values:
        rows.append(
            _format_markdown_row(
                [
                    link.side,
                    link.relation,
                    link.customer_name,
                    link.project_name,
                    link.note,
                ]
            )
        )
    return "\n".join(rows)


def _split_list_cell(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*[、,，/]\s*", value) if part.strip()]


def _parse_linked_customers(section: str) -> list[str]:
    values: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        content = stripped[2:].strip()
        if not content or content.startswith("暂无"):
            continue
        values.append(_extract_name_from_link(content).removeprefix("客户--"))
    return _merge_list(values)


def _parse_project_links(section: str) -> list[PersonProjectLink]:
    rows = _table_rows(section)
    if rows:
        return [
            PersonProjectLink(
                customer_name=row.get("关联客户", "").strip(),
                project_name=row.get("关联项目", "").strip(),
                side=row.get("所属方", "").strip(),
                relation=row.get("关系", "").strip(),
                note=row.get("备注", "").strip(),
            )
            for row in rows
            if row.get("关联项目", "").strip() or row.get("关联客户", "").strip()
        ]
    links: list[PersonProjectLink] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        content = stripped[2:].strip()
        if not content or content.startswith("暂无"):
            continue
        project_name = _extract_name_from_link(content).removeprefix("项目--")
        relation = ""
        if "：" in content:
            relation = content.split("：", 1)[1].strip()
        links.append(PersonProjectLink(project_name=project_name, relation=relation))
    return links
