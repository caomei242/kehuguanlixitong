from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from strawberry_customer_management.models import ApprovalEntry, CustomerDetail, CustomerRecord, ProjectDetail, ProjectRecord


PROJECT_DESTINATION = "project"
CUSTOMER_DESTINATION = "customer"
UNASSIGNED_DESTINATION = "unassigned"


@dataclass(frozen=True)
class ApprovalImportCandidate:
    entry: ApprovalEntry
    destination: str
    customer_name: str = ""
    project_name: str = ""
    confidence: int = 0
    reason: str = ""
    raw_text: str = ""

    def destination_label(self) -> str:
        if self.destination == PROJECT_DESTINATION:
            return f"项目：{self.customer_name} / {self.project_name}"
        if self.destination == CUSTOMER_DESTINATION:
            return f"客户待归属：{self.customer_name}"
        return "兜底待归属"


def build_approval_import_candidates(
    raw_text: str,
    projects: list[ProjectRecord],
    customers: list[CustomerRecord],
    project_details: dict[tuple[str, str], ProjectDetail] | None = None,
    customer_details: dict[str, CustomerDetail] | None = None,
    today: str | None = None,
) -> list[ApprovalImportCandidate]:
    project_details = project_details or {}
    customer_details = customer_details or {}
    entries = parse_dingtalk_approval_entries(raw_text, today=today)
    candidates: list[ApprovalImportCandidate] = []
    for entry, chunk in entries:
        candidates.append(
            _match_approval_destination(
                entry=entry,
                raw_text=chunk,
                projects=projects,
                customers=customers,
                project_details=project_details,
                customer_details=customer_details,
            )
        )
    return candidates


def parse_dingtalk_approval_entries(raw_text: str, today: str | None = None) -> list[tuple[ApprovalEntry, str]]:
    chunks = _split_approval_chunks(raw_text)
    current_date = today or date.today().isoformat()
    return [(_parse_entry(chunk, current_date), chunk) for chunk in chunks]


def _split_approval_chunks(raw_text: str) -> list[str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []
    if _looks_like_dingtalk_approval_form(raw_text):
        return [raw_text.strip()]

    row_like_lines = [
        line
        for line in lines
        if _looks_like_approval_text(line)
        and (re.search(r"20\d{2}-\d{2}-\d{2}", line) or any(status in line for status in ("审批通过", "审批中", "已撤销", "处理中")))
    ]
    if len(row_like_lines) >= 2:
        return row_like_lines

    blocks = [block.strip() for block in re.split(r"\n\s*\n+", raw_text.strip()) if block.strip()]
    approval_blocks = [block for block in blocks if _looks_like_approval_text(block)]
    if len(approval_blocks) >= 2:
        return approval_blocks
    return [raw_text.strip()]


def _parse_entry(chunk: str, today: str) -> ApprovalEntry:
    title = _extract_title(chunk)
    usage = _extract_usage(chunk) or title or "钉钉审批"
    approval_type = _extract_approval_type(chunk, title)
    status = _extract_status(chunk)
    result = _extract_result(chunk, status)
    dates = re.findall(r"20\d{2}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?", chunk)
    entry_date = _extract_labeled_value(chunk, ("发起时间", "创建时间", "申请时间")) or (dates[0] if dates else today)
    completed_at = (
        _extract_labeled_value(chunk, ("审批完成时间", "完成时间"))
        or _extract_flow_completed_at(chunk, status)
        or (_last_completed_date(dates, status) if dates else "")
    )
    current_node = _extract_labeled_value(chunk, ("当前节点", "流程状态")) or _extract_current_node(chunk)
    counterparty = _extract_counterparty(chunk)
    attachment_clue = _extract_attachment_clue(chunk)
    note = _compact_note(chunk)
    return ApprovalEntry(
        entry_date=_date_part(entry_date),
        approval_type=approval_type,
        title_or_usage=usage,
        counterparty=counterparty,
        approval_status=status,
        approval_result=result,
        current_node=current_node,
        completed_at=completed_at,
        attachment_clue=attachment_clue,
        note=note,
        source="钉钉审批",
    )


def _match_approval_destination(
    entry: ApprovalEntry,
    raw_text: str,
    projects: list[ProjectRecord],
    customers: list[CustomerRecord],
    project_details: dict[tuple[str, str], ProjectDetail],
    customer_details: dict[str, CustomerDetail],
) -> ApprovalImportCandidate:
    best_project: tuple[int, ProjectRecord, str] | None = None
    for project in projects:
        detail = project_details.get((project.brand_customer_name, project.project_name))
        score, reason = _score_project(raw_text, entry, project, detail)
        if score > 0 and (best_project is None or score > best_project[0]):
            best_project = (score, project, reason)
    if best_project is not None and best_project[0] >= 6:
        project = best_project[1]
        return ApprovalImportCandidate(
            entry=entry,
            destination=PROJECT_DESTINATION,
            customer_name=project.brand_customer_name,
            project_name=project.project_name,
            confidence=best_project[0],
            reason=best_project[2],
            raw_text=raw_text,
        )

    best_customer: tuple[int, CustomerRecord, str] | None = None
    for customer in customers:
        detail = customer_details.get(customer.name)
        score, reason = _score_customer(raw_text, entry, customer, detail)
        if score > 0 and (best_customer is None or score > best_customer[0]):
            best_customer = (score, customer, reason)
    if best_customer is not None and best_customer[0] >= 3:
        customer = best_customer[1]
        return ApprovalImportCandidate(
            entry=entry,
            destination=CUSTOMER_DESTINATION,
            customer_name=customer.name,
            confidence=best_customer[0],
            reason=best_customer[2],
            raw_text=raw_text,
        )

    return ApprovalImportCandidate(
        entry=entry,
        destination=UNASSIGNED_DESTINATION,
        confidence=0,
        reason="未匹配到明确客户或项目",
        raw_text=raw_text,
    )


def _score_project(raw_text: str, entry: ApprovalEntry, project: ProjectRecord, detail: ProjectDetail | None) -> tuple[int, str]:
    haystack = _normalize_match_text(" ".join([raw_text, entry.title_or_usage, entry.counterparty, entry.attachment_clue, entry.note]))
    score = 0
    reasons: list[str] = []

    for alias in _project_aliases(project):
        normalized_alias = _normalize_match_text(alias)
        if len(normalized_alias) >= 6 and normalized_alias in haystack:
            score += 8
            reasons.append(f"命中项目名片段「{alias}」")
            break

    if _contains_alias(haystack, project.brand_customer_name):
        score += 3
        reasons.append(f"命中关联客户「{project.brand_customer_name}」")

    for token in _important_tokens(project.project_name):
        if token in haystack:
            score += 1
    if detail:
        for value in (
            detail.default_party_a_info.company,
            detail.party_a_info.company,
            detail.default_party_a_info.brand,
            detail.party_a_info.brand,
        ):
            if _contains_alias(haystack, value):
                score += 2
                reasons.append(f"命中甲方信息「{value}」")
                break

    return score, "；".join(reasons) or "项目字段弱匹配"


def _score_customer(raw_text: str, entry: ApprovalEntry, customer: CustomerRecord, detail: CustomerDetail | None) -> tuple[int, str]:
    haystack = _normalize_match_text(" ".join([raw_text, entry.title_or_usage, entry.counterparty, entry.attachment_clue, entry.note]))
    aliases = [customer.name, customer.business_direction]
    if detail:
        aliases.extend(
            [
                detail.company,
                detail.party_a_brand,
                detail.party_a_company,
                detail.contact,
                detail.party_a_contact,
            ]
        )
    score = 0
    reasons: list[str] = []
    for alias in aliases:
        if _contains_alias(haystack, alias):
            score += 3
            reasons.append(f"命中客户线索「{alias}」")
            break
    if entry.counterparty and _contains_alias(haystack, entry.counterparty):
        score += 1
    return score, "；".join(reasons) or "客户字段弱匹配"


def _project_aliases(project: ProjectRecord) -> list[str]:
    aliases = [project.project_name]
    without_date = re.sub(r"^\s*20\d{2}(?:[-_./年]\d{1,2})?\s*", "", project.project_name).strip()
    if without_date:
        aliases.append(without_date)
    without_customer = without_date.replace(project.brand_customer_name, "").strip()
    if without_customer:
        aliases.append(without_customer)
    if "2026" in project.project_name:
        aliases.append(project.project_name.replace("2026", "26"))
    return aliases


def _important_tokens(value: str) -> list[str]:
    normalized = _normalize_match_text(value)
    tokens = re.findall(r"20\d{2}|\d{2,4}|[\u4e00-\u9fa5A-Za-z]{3,}", normalized)
    return [token for token in tokens if len(token) >= 3]


def _contains_alias(haystack: str, alias: str) -> bool:
    normalized_alias = _normalize_match_text(alias)
    return len(normalized_alias) >= 2 and normalized_alias in haystack


def _normalize_match_text(value: str) -> str:
    return re.sub(r"\s+|[，。；、:：/\\_\-—（）()《》【】\[\]·.]", "", value or "").lower()


def _looks_like_approval_text(value: str) -> bool:
    return any(keyword in value for keyword in ("审批", "用印", "确认单", "合同", "申请"))


def _looks_like_dingtalk_approval_form(value: str) -> bool:
    return "审批编号" in value and "审批流程" in value and any(keyword in value for keyword in ("用印申请", "合同审批", "请假申请"))


def _extract_title(chunk: str) -> str:
    match = re.search(r"[\u4e00-\u9fa5A-Za-z0-9（）()]+申请", chunk)
    if match:
        return match.group(0).strip()[:80]
    for line in chunk.splitlines():
        stripped = line.strip()
        if _looks_like_approval_text(stripped):
            return stripped[:80]
    match = re.search(r"草莓提交的[^\n，。；]*?(?:申请|审批)", chunk)
    return match.group(0).strip() if match else ""


def _extract_usage(chunk: str) -> str:
    labeled = _extract_labeled_value(chunk, ("用印文件名称及用途说明", "用途说明", "主题内容", "申请内容"))
    if labeled:
        return labeled[:120]
    form_usage = _extract_dingtalk_form_usage(chunk)
    if form_usage:
        return form_usage[:160]
    for pattern in (r"([\u4e00-\u9fa5A-Za-z0-9（）()\-_.]+确认单)", r"([\u4e00-\u9fa5A-Za-z0-9（）()\-_.]+合同)"):
        match = re.search(pattern, chunk)
        if match:
            return match.group(1).strip()
    return ""


def _extract_approval_type(chunk: str, title: str) -> str:
    source = f"{title} {chunk}"
    if "用印" in source:
        return "用印申请"
    if "合同" in source and "审批" in source:
        return "合同审批"
    if "请假" in source:
        return "请假申请"
    if "确认单" in source:
        return "确认单审批"
    return "钉钉审批"


def _extract_status(chunk: str) -> str:
    if "审批通过" in chunk or "已通过" in chunk:
        return "审批通过"
    if "已同意" in chunk and "审批流程" in chunk and "审批中" not in chunk and "处理中" not in chunk:
        return "审批通过"
    if "审批中" in chunk or "处理中" in chunk:
        return "审批中"
    if "已撤销" in chunk:
        return "已撤销"
    if "审批拒绝" in chunk or "已拒绝" in chunk:
        return "审批拒绝"
    return "待补充"


def _extract_result(chunk: str, status: str) -> str:
    if status in {"审批通过", "审批拒绝", "已撤销"}:
        return status
    return "--"


def _extract_labeled_value(chunk: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*[：:]\s*(?P<value>[^\n]+)", chunk)
        if match:
            return match.group("value").strip()
    return ""


def _extract_current_node(chunk: str) -> str:
    match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9（）() /]+?)\s*处理中", chunk)
    return match.group(1).strip() if match else ""


def _extract_counterparty(chunk: str) -> str:
    for label in ("品牌方", "品牌", "客户", "甲方", "我司为", "公司名称", "其他公司名称"):
        match = re.search(rf"{label}\s*[：:为]?\s*(?P<company>[\u4e00-\u9fa5A-Za-z0-9（）()]+(?:有限公司|股份有限公司|集团股份有限公司))", chunk)
        if match:
            return match.group("company").strip()
    companies = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9（）()]+(?:有限公司|股份有限公司|集团股份有限公司)", chunk)
    return companies[0].strip() if companies else ""


def _extract_attachment_clue(chunk: str) -> str:
    files = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9（）()_\- .]+?\.(?:docx?|pdf|xlsx?)", chunk, flags=re.I)
    if files:
        unique_files: list[str] = []
        seen: set[str] = set()
        for file in files:
            cleaned = _clean_attachment_file(file)
            if cleaned in seen:
                continue
            seen.add(cleaned)
            unique_files.append(cleaned)
        return "；".join(unique_files[:3])
    usage = _extract_usage(chunk)
    return usage if any(keyword in usage for keyword in ("确认单", "合同", "用印")) else ""


def _clean_attachment_file(value: str) -> str:
    cleaned = value.strip(" ：:；;，,。[]【】()（）")
    parts = [part.strip(" ：:；;，,。[]【】()（）") for part in re.split(r"\s+", cleaned) if part.strip()]
    for part in reversed(parts):
        if re.search(r"\.(?:docx?|pdf|xlsx?)$", part, flags=re.I):
            return part
    return cleaned


def _compact_note(chunk: str) -> str:
    compact = re.sub(r"\s+", " ", chunk).strip()
    return compact[:220]


def _extract_dingtalk_form_usage(chunk: str) -> str:
    compact = re.sub(r"\s+", " ", chunk).strip()
    match = re.search(r"用印文件名称及用途说\s*明\s*(?P<usage>.+?)(?:附件|公司名称|所属部门|审批流程)", compact)
    if match:
        return _compact_dingtalk_form_usage(match.group("usage").strip(" ：:"))
    return ""


def _compact_dingtalk_form_usage(usage: str) -> str:
    project_match = re.search(r"(?:（(?P<brand>[^）]+)）)?(?P<title>[\u4e00-\u9fa5A-Za-z0-9]+?项目[\u4e00-\u9fa5A-Za-z0-9]*确认单)", usage)
    if not project_match:
        return usage
    title = project_match.group("title").strip()
    brand = (project_match.group("brand") or "").strip()
    if brand and not title.startswith(brand):
        title = f"{brand}{title}"
    amount_match = re.search(r"含税金额为?\s*(?P<amount>[\d,.]+元)", usage)
    if amount_match:
        title = f"{title} · {amount_match.group('amount')}"
    return title


def _extract_flow_completed_at(chunk: str, status: str) -> str:
    if status not in {"审批通过", "审批拒绝", "已撤销"}:
        return ""
    approvals = re.findall(r"已同意\s*(20\d{2}-\d{2}-\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?)", chunk)
    return approvals[-1] if approvals else ""


def _last_completed_date(dates: list[str], status: str) -> str:
    if status in {"审批通过", "审批拒绝", "已撤销"} and dates:
        return dates[-1]
    return ""


def _date_part(value: str) -> str:
    match = re.search(r"20\d{2}-\d{2}-\d{2}", value)
    return match.group(0) if match else value
