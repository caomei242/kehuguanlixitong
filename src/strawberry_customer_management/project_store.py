from __future__ import annotations

import re
from pathlib import Path

from strawberry_customer_management.markdown_store import (
    PLACEHOLDER_NAMES,
    _format_approval_section,
    _merge_approval_entries,
    _parse_approval_entries,
    _bullet_map,
    _clean_cell,
    _ensure_section,
    _extract_wikilink_target,
    _is_separator_row,
    _replace_or_add_bullet,
    _replace_section_body,
    _section_body,
    _split_markdown_row,
    sort_approval_entries,
    sort_project_records,
    summarize_approval_entry,
)
from strawberry_customer_management.models import ApprovalEntry, PartyAInfo, ProjectDetail, ProjectDraft, ProjectRecord
from strawberry_customer_management.paths import default_project_root


SUMMARY_FILE = "00 品牌项目总表.md"
PROJECT_DIR = "项目"
UNASSIGNED_APPROVALS_FILE = "00 待归属审批.md"
PLACEHOLDER_VALUES = {"", "待补充", "待确认", "待同步"}
PROJECT_SUMMARY_SECTION = "项目总表"
LEGACY_PROJECT_SUMMARY_SECTION = "品牌项目总表"


def _safe_file_stem(value: str) -> str:
    cleaned = value.strip().replace("/", "-").replace(":", "-")
    return cleaned or "未命名项目"


def _format_summary_row(record: ProjectRecord) -> str:
    return (
        f"| {record.brand_customer_name} | {record.project_name} | {record.stage} | {record.year} | "
        f"{record.project_type} | {record.current_focus} | {record.next_action} | {record.main_work_path} | "
        f"[[项目/{record.brand_customer_name}/项目--{_safe_file_stem(record.project_name)}]] | {record.updated_at} |"
    )


def _parse_table(section: str) -> list[dict[str, str]]:
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


def _project_summary_body(text: str) -> str:
    body = _section_body(text, PROJECT_SUMMARY_SECTION)
    if body:
        return body
    return _section_body(text, LEGACY_PROJECT_SUMMARY_SECTION)


def _party_a_section_default() -> str:
    return (
        "- 默认来源：客户默认甲方信息\n"
        "- 是否项目覆盖：否\n"
        "- 默认甲方品牌：待补充\n"
        "- 默认对应公司/主体：待补充\n"
        "- 默认收件联系人：待补充\n"
        "- 默认联系电话：待补充\n"
        "- 默认电子邮箱：待补充\n"
        "- 默认通讯地址：待补充\n"
        "- 项目覆盖甲方品牌：待补充\n"
        "- 项目覆盖对应公司/主体：待补充\n"
        "- 项目覆盖收件联系人：待补充\n"
        "- 项目覆盖联系电话：待补充\n"
        "- 项目覆盖电子邮箱：待补充\n"
        "- 项目覆盖通讯地址：待补充"
    )


class MarkdownProjectStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or default_project_root()
        self.summary_path = self.root / SUMMARY_FILE
        self.project_dir = self.root / PROJECT_DIR
        self.unassigned_approvals_path = self.root / UNASSIGNED_APPROVALS_FILE

    def list_projects(self) -> list[ProjectRecord]:
        if not self.summary_path.exists():
            return []
        text = self.summary_path.read_text(encoding="utf-8")
        records: list[ProjectRecord] = []
        for row in _parse_table(_project_summary_body(text)):
            project_name = row.get("项目名称", "").strip()
            brand_name = (row.get("关联客户", "") or row.get("品牌客户", "")).strip()
            if not project_name or not brand_name or project_name in PLACEHOLDER_NAMES or brand_name in PLACEHOLDER_NAMES:
                continue
            page_link = row.get("对应项目页", "").strip()
            page_path = None
            if page_link:
                target = _extract_wikilink_target(page_link)
                page_path = self.root / f"{target}.md"
            records.append(
                ProjectRecord(
                    brand_customer_name=brand_name,
                    project_name=project_name,
                    stage=row.get("项目状态", "").strip(),
                    year=row.get("年份", "").strip(),
                    project_type=row.get("项目类型", "").strip(),
                    current_focus=row.get("当前重点", "").strip(),
                    next_action=row.get("下一步", "").strip(),
                    main_work_path=row.get("主业项目路径", "").strip(),
                    page_link=page_link,
                    updated_at=row.get("更新时间", "").strip(),
                    page_path=page_path,
                    path_status="主业路径有效" if Path(row.get("主业项目路径", "").strip()).exists() else "主业路径失效",
                    latest_approval_status=self._read_latest_approval_status(page_path),
                )
            )
        return sort_project_records(records)

    def list_projects_for_brand(self, brand_customer_name: str) -> list[ProjectRecord]:
        records = [record for record in self.list_projects() if record.brand_customer_name == brand_customer_name]
        return sort_project_records(records)

    def list_brands(self) -> list[str]:
        return sorted({record.brand_customer_name for record in self.list_projects()})

    def list_years(self) -> list[str]:
        years = {record.year for record in self.list_projects() if record.year}
        return sorted(years, reverse=True)

    def get_project(self, brand_customer_name: str, project_name: str) -> ProjectDetail:
        path = self._project_path(brand_customer_name, project_name)
        if not path.exists():
            raise KeyError(f"{brand_customer_name}/{project_name}")
        text = path.read_text(encoding="utf-8")
        basic = _bullet_map(_section_body(text, "基本信息"))
        judgement = _bullet_map(_section_body(text, "当前判断"))
        party_a = _bullet_map(_section_body(text, "甲方信息"))
        default_party_a = PartyAInfo(
            brand=party_a.get("默认甲方品牌", ""),
            company=party_a.get("默认对应公司/主体", ""),
            contact=party_a.get("默认收件联系人", ""),
            phone=party_a.get("默认联系电话", ""),
            email=party_a.get("默认电子邮箱", ""),
            address=party_a.get("默认通讯地址", ""),
        )
        override_party_a = PartyAInfo(
            brand=party_a.get("项目覆盖甲方品牌", ""),
            company=party_a.get("项目覆盖对应公司/主体", ""),
            contact=party_a.get("项目覆盖收件联系人", ""),
            phone=party_a.get("项目覆盖联系电话", ""),
            email=party_a.get("项目覆盖电子邮箱", ""),
            address=party_a.get("项目覆盖通讯地址", ""),
        )
        override_enabled = party_a.get("是否项目覆盖", "") == "是"
        effective_party_a = override_party_a.resolved_with(default_party_a) if override_enabled else default_party_a
        materials_markdown = _section_body(text, "资料概览").strip()
        notes_markdown = _section_body(text, "项目沉淀").strip()
        approval_entries = sort_approval_entries(_parse_approval_entries(text, "审批记录"))
        main_work_path = basic.get("主业项目路径", "")
        return ProjectDetail(
            brand_customer_name=basic.get("关联客户", "") or basic.get("品牌客户", brand_customer_name),
            project_name=basic.get("项目名称", project_name),
            stage=basic.get("项目状态", ""),
            year=basic.get("所属年份", ""),
            project_type=basic.get("项目类型", ""),
            current_focus=judgement.get("当前重点", ""),
            next_action=judgement.get("下一步", ""),
            main_work_path=main_work_path,
            page_link=f"[[项目/{brand_customer_name}/项目--{_safe_file_stem(project_name)}]]",
            updated_at=judgement.get("更新时间", ""),
            page_path=path,
            path_status=basic.get("主业路径状态", "主业路径失效" if main_work_path and not Path(main_work_path).exists() else "主业路径有效"),
            latest_approval_status=summarize_approval_entry(approval_entries[0] if approval_entries else None),
            customer_page_link=basic.get("关联客户页", ""),
            risk=judgement.get("风险提醒", ""),
            party_a_source="项目覆盖甲方信息" if override_enabled else party_a.get("默认来源", ""),
            default_party_a_info=default_party_a,
            party_a_info=effective_party_a,
            materials_markdown=materials_markdown,
            notes_markdown=notes_markdown,
            approval_entries=approval_entries,
            raw_text=text,
        )

    def upsert_project(self, draft: ProjectDraft) -> ProjectDetail:
        self.root.mkdir(parents=True, exist_ok=True)
        self.project_dir.mkdir(parents=True, exist_ok=True)
        updated_at = draft.resolved_updated_at()
        source_name = draft.original_project_name.strip() or draft.project_name
        source_path = self._project_path(draft.brand_customer_name, source_name)
        target_path = self._project_path(draft.brand_customer_name, draft.project_name)
        is_rename = bool(draft.original_project_name.strip() and draft.original_project_name.strip() != draft.project_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        existing_approvals: list[ApprovalEntry] = []

        if is_rename:
            if target_path.exists():
                raise ValueError(f"项目「{draft.project_name}」已存在，不能重命名覆盖。")
            if not source_path.exists():
                raise KeyError(f"{draft.brand_customer_name}/{source_name}")
            text = source_path.read_text(encoding="utf-8")
            existing_approvals = _parse_approval_entries(text, "审批记录")
            text = re.sub(r"^# 项目--.*$", f"# 项目--{draft.project_name}", text, count=1, flags=re.M)
            text = self._ensure_project_sections(text)
            text = self._update_existing_page(text, draft, updated_at)
        elif target_path.exists():
            text = target_path.read_text(encoding="utf-8")
            existing_approvals = _parse_approval_entries(text, "审批记录")
            text = self._ensure_project_sections(text)
            text = self._update_existing_page(text, draft, updated_at)
        else:
            text = self._build_new_page(draft, updated_at)

        approval_entries = sort_approval_entries(draft.approval_entries or existing_approvals)
        text = self._replace_approval_section(text, approval_entries)

        target_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        if is_rename:
            source_path.unlink(missing_ok=True)
        self._upsert_summary_row(draft, updated_at)
        return self.get_project(draft.brand_customer_name, draft.project_name)

    def upsert_discovered_project(self, draft: ProjectDraft) -> ProjectDetail:
        path = self._project_path(draft.brand_customer_name, draft.project_name)
        if not path.exists():
            return self.upsert_project(draft)
        existing = self.get_project(draft.brand_customer_name, draft.project_name)
        override_enabled = existing.party_a_source.startswith("项目覆盖") or existing.party_a_info != existing.default_party_a_info
        merged = ProjectDraft(
            brand_customer_name=draft.brand_customer_name,
            project_name=draft.project_name,
            stage=existing.stage if existing.stage not in PLACEHOLDER_VALUES else draft.stage,
            original_project_name=existing.project_name,
            year=draft.year or existing.year,
            project_type=existing.project_type if existing.project_type not in PLACEHOLDER_VALUES else draft.project_type,
            current_focus=existing.current_focus if existing.current_focus not in PLACEHOLDER_VALUES else draft.current_focus,
            next_action=existing.next_action if existing.next_action not in PLACEHOLDER_VALUES else draft.next_action,
            risk=existing.risk if existing.risk not in PLACEHOLDER_VALUES else draft.risk,
            customer_page_link=draft.customer_page_link or existing.customer_page_link,
            main_work_path=draft.main_work_path or existing.main_work_path,
            path_status=draft.path_status or existing.path_status,
            party_a_source="项目覆盖甲方信息" if override_enabled else draft.party_a_source,
            default_party_a_info=draft.default_party_a_info or existing.default_party_a_info,
            party_a_info=existing.party_a_info if override_enabled else PartyAInfo(),
            override_party_a=override_enabled,
            materials_markdown=draft.materials_markdown or existing.materials_markdown,
            notes_markdown=existing.notes_markdown or draft.notes_markdown,
            approval_entries=existing.approval_entries or draft.approval_entries,
            updated_at=draft.updated_at,
        )
        return self.upsert_project(merged)

    def _project_path(self, brand_customer_name: str, project_name: str) -> Path:
        return self.project_dir / brand_customer_name / f"项目--{_safe_file_stem(project_name)}.md"

    def _build_new_page(self, draft: ProjectDraft, updated_at: str) -> str:
        effective_party_a = draft.effective_party_a_info
        return f"""# 项目--{draft.project_name}

## 基本信息
- 关联客户：{draft.brand_customer_name}
- 所属年份：{draft.year or "待确认年份"}
- 项目名称：{draft.project_name}
- 项目状态：{draft.stage}
- 项目类型：{draft.project_type or "待补充"}
- 关联客户页：{draft.customer_page_link or f"[[客户/客户--{draft.brand_customer_name}]]"}
- 主业项目路径：{draft.main_work_path}
- 主业路径状态：{draft.path_status or "主业路径有效"}
- 最近同步时间：{updated_at}

## 甲方信息
- 默认来源：{draft.party_a_source or "客户默认甲方信息"}
- 是否项目覆盖：{"是" if draft.override_party_a else "否"}
- 默认甲方品牌：{draft.default_party_a_info.brand or "待补充"}
- 默认对应公司/主体：{draft.default_party_a_info.company or "待补充"}
- 默认收件联系人：{draft.default_party_a_info.contact or "待补充"}
- 默认联系电话：{draft.default_party_a_info.phone or "待补充"}
- 默认电子邮箱：{draft.default_party_a_info.email or "待补充"}
- 默认通讯地址：{draft.default_party_a_info.address or "待补充"}
- 项目覆盖甲方品牌：{draft.party_a_info.brand or "待补充"}
- 项目覆盖对应公司/主体：{draft.party_a_info.company or "待补充"}
- 项目覆盖收件联系人：{draft.party_a_info.contact or "待补充"}
- 项目覆盖联系电话：{draft.party_a_info.phone or "待补充"}
- 项目覆盖电子邮箱：{draft.party_a_info.email or "待补充"}
- 项目覆盖通讯地址：{draft.party_a_info.address or "待补充"}

## 当前判断
- 当前重点：{draft.current_focus or "已同步桌面项目资料，待补项目当前重点"}
- 下一步：{draft.next_action or "补充项目当前重点、下一步和风险判断"}
- 风险提醒：{draft.risk or "待补充"}
- 更新时间：{updated_at}

## 审批记录
{_format_approval_section(draft.approval_entries, "- 暂无审批记录")}

## 资料概览
{draft.materials_markdown or "- 待同步桌面项目资料"}

## 项目沉淀
{draft.notes_markdown or "- 待补项目沉淀"}
"""

    def _ensure_project_sections(self, text: str) -> str:
        text = _ensure_section(text, "甲方信息", _party_a_section_default())
        text = _ensure_section(text, "审批记录", "- 暂无审批记录")
        text = _ensure_section(text, "资料概览", "- 待同步桌面项目资料")
        text = _ensure_section(text, "项目沉淀", "- 待补项目沉淀")
        return text

    def _update_existing_page(self, text: str, draft: ProjectDraft, updated_at: str) -> str:
        text = re.sub(r"^- 品牌客户：", "- 关联客户：", text, count=1, flags=re.M)
        updates = [
            ("基本信息", "关联客户", draft.brand_customer_name),
            ("基本信息", "所属年份", draft.year),
            ("基本信息", "项目名称", draft.project_name),
            ("基本信息", "项目状态", draft.stage),
            ("基本信息", "项目类型", draft.project_type),
            ("基本信息", "关联客户页", draft.customer_page_link),
            ("基本信息", "主业项目路径", draft.main_work_path),
            ("基本信息", "主业路径状态", draft.path_status or "主业路径有效"),
            ("基本信息", "最近同步时间", updated_at),
            ("甲方信息", "默认来源", draft.party_a_source or "客户默认甲方信息"),
            ("甲方信息", "是否项目覆盖", "是" if draft.override_party_a else "否"),
            ("甲方信息", "默认甲方品牌", draft.default_party_a_info.brand),
            ("甲方信息", "默认对应公司/主体", draft.default_party_a_info.company),
            ("甲方信息", "默认收件联系人", draft.default_party_a_info.contact),
            ("甲方信息", "默认联系电话", draft.default_party_a_info.phone),
            ("甲方信息", "默认电子邮箱", draft.default_party_a_info.email),
            ("甲方信息", "默认通讯地址", draft.default_party_a_info.address),
            ("甲方信息", "项目覆盖甲方品牌", draft.party_a_info.brand),
            ("甲方信息", "项目覆盖对应公司/主体", draft.party_a_info.company),
            ("甲方信息", "项目覆盖收件联系人", draft.party_a_info.contact),
            ("甲方信息", "项目覆盖联系电话", draft.party_a_info.phone),
            ("甲方信息", "项目覆盖电子邮箱", draft.party_a_info.email),
            ("甲方信息", "项目覆盖通讯地址", draft.party_a_info.address),
            ("当前判断", "当前重点", draft.current_focus),
            ("当前判断", "下一步", draft.next_action),
            ("当前判断", "风险提醒", draft.risk),
            ("当前判断", "更新时间", updated_at),
        ]
        for section, key, value in updates:
            text = _replace_or_add_bullet(text, section, key, value)
        text = _replace_section_body(text, "资料概览", f"{draft.materials_markdown.rstrip()}\n" if draft.materials_markdown else "- 待同步桌面项目资料\n")
        text = _replace_section_body(text, "项目沉淀", f"{draft.notes_markdown.rstrip()}\n" if draft.notes_markdown else "- 待补项目沉淀\n")
        return text

    def append_approval_entry(self, brand_customer_name: str, project_name: str, entry: ApprovalEntry) -> ProjectDetail:
        detail = self.get_project(brand_customer_name, project_name)
        draft = ProjectDraft(
            brand_customer_name=detail.brand_customer_name,
            project_name=detail.project_name,
            original_project_name=detail.project_name,
            stage=detail.stage,
            year=detail.year,
            project_type=detail.project_type,
            current_focus=detail.current_focus,
            next_action=detail.next_action,
            risk=detail.risk,
            customer_page_link=detail.customer_page_link,
            main_work_path=detail.main_work_path,
            path_status=detail.path_status,
            party_a_source=detail.party_a_source,
            default_party_a_info=detail.default_party_a_info,
            party_a_info=detail.party_a_info if detail.party_a_source.startswith("项目覆盖") else PartyAInfo(),
            override_party_a=detail.party_a_source.startswith("项目覆盖"),
            materials_markdown=detail.materials_markdown,
            notes_markdown=detail.notes_markdown,
            approval_entries=_merge_approval_entries(detail.approval_entries, [entry]),
            updated_at=entry.entry_date,
        )
        return self.upsert_project(draft)

    def list_unassigned_approvals(self) -> list[ApprovalEntry]:
        if not self.unassigned_approvals_path.exists():
            return []
        text = self.unassigned_approvals_path.read_text(encoding="utf-8")
        return _parse_approval_entries(text, "待归属审批")

    def append_unassigned_approval(self, entry: ApprovalEntry) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.unassigned_approvals_path.exists():
            self.unassigned_approvals_path.write_text(self._default_unassigned_approvals_text(), encoding="utf-8")
        text = self.unassigned_approvals_path.read_text(encoding="utf-8")
        merged = _merge_approval_entries(_parse_approval_entries(text, "待归属审批"), [entry])
        text = _replace_section_body(text, "待归属审批", _format_approval_section(merged, "- 暂无待归属审批"))
        text = re.sub(r"^更新时间：.*$", f"更新时间：{entry.entry_date}", text, count=1, flags=re.M)
        self.unassigned_approvals_path.write_text(text.rstrip() + "\n", encoding="utf-8")

    def _replace_approval_section(self, text: str, entries: list[ApprovalEntry]) -> str:
        text = self._ensure_project_sections(text)
        return _replace_section_body(text, "审批记录", _format_approval_section(sort_approval_entries(entries), "- 暂无审批记录"))

    def _read_latest_approval_status(self, page_path: Path | None) -> str:
        if page_path is None or not page_path.exists():
            return "暂无审批记录"
        text = page_path.read_text(encoding="utf-8")
        entries = sort_approval_entries(_parse_approval_entries(text, "审批记录"))
        return summarize_approval_entry(entries[0] if entries else None)

    def _upsert_summary_row(self, draft: ProjectDraft, updated_at: str) -> None:
        if not self.summary_path.exists():
            self.summary_path.write_text(self._default_summary_text(), encoding="utf-8")
        text = self._normalize_summary_text(self.summary_path.read_text(encoding="utf-8"))
        original_project_name = draft.original_project_name.strip()
        if original_project_name and original_project_name != draft.project_name:
            text = self._remove_row_in_section(text, PROJECT_SUMMARY_SECTION, draft.brand_customer_name, original_project_name)
        record = ProjectRecord(
            brand_customer_name=draft.brand_customer_name,
            project_name=draft.project_name,
            stage=draft.stage,
            year=draft.year,
            project_type=draft.project_type,
            current_focus=draft.current_focus,
            next_action=draft.next_action,
            main_work_path=draft.main_work_path,
            updated_at=updated_at,
            page_link=f"[[项目/{draft.brand_customer_name}/项目--{_safe_file_stem(draft.project_name)}]]",
            path_status=draft.path_status,
        )
        text = self._upsert_row_in_section(text, PROJECT_SUMMARY_SECTION, draft.brand_customer_name, draft.project_name, _format_summary_row(record))
        text = re.sub(r"^更新时间：.*$", f"更新时间：{updated_at}", text, count=1, flags=re.M)
        self.summary_path.write_text(text.rstrip() + "\n", encoding="utf-8")

    def _normalize_summary_text(self, text: str) -> str:
        text = re.sub(r"^# 品牌项目总表\s*$", "# 项目总表", text, count=1, flags=re.M)
        text = re.sub(r"^## 品牌项目总表\s*$", f"## {PROJECT_SUMMARY_SECTION}", text, count=1, flags=re.M)
        text = re.sub(r"^\| 品牌客户 \|", "| 关联客户 |", text, count=1, flags=re.M)
        if not _section_body(text, PROJECT_SUMMARY_SECTION):
            text = _ensure_section(text, PROJECT_SUMMARY_SECTION, self._default_project_table_body())
        return text

    def _remove_row_in_section(self, text: str, section_name: str, brand_name: str, project_name: str) -> str:
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
            if len(cells) < 2:
                continue
            if cells[0].strip() == brand_name and cells[1].strip() == project_name:
                continue
            kept_lines.append(line)
        new_body = "\n" + "\n".join([header_line, separator_line, *kept_lines]) + "\n\n"
        return _replace_section_body(text, section_name, new_body)

    def _upsert_row_in_section(self, text: str, section_name: str, brand_name: str, project_name: str, row_text: str) -> str:
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
            if len(cells) < 2:
                continue
            if cells[0].strip() in PLACEHOLDER_NAMES:
                continue
            if cells[0].strip() == brand_name and cells[1].strip() == project_name:
                new_data_lines.append(row_text)
                replaced = True
            else:
                new_data_lines.append(line)
        if not replaced:
            new_data_lines.append(row_text)
        new_body = "\n" + "\n".join([header_line, separator_line, *new_data_lines]) + "\n\n"
        return _replace_section_body(text, section_name, new_body)

    def _default_summary_text(self) -> str:
        return f"""# 项目总表

更新时间：

## {PROJECT_SUMMARY_SECTION}

{self._default_project_table_body()}"""

    def _default_project_table_body(self) -> str:
        return """| 关联客户 | 项目名称 | 项目状态 | 年份 | 项目类型 | 当前重点 | 下一步 | 主业项目路径 | 对应项目页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""

    def _default_unassigned_approvals_text(self) -> str:
        return """# 待归属审批

更新时间：

## 待归属审批
- 暂无待归属审批
"""
