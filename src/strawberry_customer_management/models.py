from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


CUSTOMER_TYPES = ("品牌客户", "网店店群客户")
CUSTOMER_STAGES = ("潜客", "沟通中", "已合作", "暂缓")


@dataclass(frozen=True)
class CommunicationEntry:
    entry_date: str
    summary: str = ""
    new_info: str = ""
    risk: str = ""
    next_step: str = ""


@dataclass(frozen=True)
class CustomerRecord:
    name: str
    customer_type: str
    stage: str
    business_direction: str = ""
    current_need: str = ""
    recent_progress: str = ""
    next_action: str = ""
    contact: str = ""
    page_link: str = ""
    updated_at: str = ""
    shop_scale: str = ""
    page_path: Path | None = None


@dataclass(frozen=True)
class CustomerDetail(CustomerRecord):
    company: str = ""
    source: str = ""
    main_work_path: str = ""
    external_material_path: str = ""
    typical_need: str = ""
    contract_payment: str = ""
    current_focus: str = ""
    likelihood: str = ""
    goal: str = ""
    deliverable: str = ""
    time_requirement: str = ""
    budget_clue: str = ""
    constraints: str = ""
    communication_entries: list[CommunicationEntry] = field(default_factory=list)
    raw_text: str = ""


@dataclass(frozen=True)
class CustomerDraft:
    name: str
    customer_type: str
    stage: str
    business_direction: str = ""
    contact: str = ""
    company: str = ""
    source: str = ""
    main_work_path: str = ""
    external_material_path: str = ""
    shop_scale: str = ""
    current_need: str = ""
    recent_progress: str = ""
    next_action: str = ""
    communication: CommunicationEntry | None = None
    updated_at: str | None = None

    def resolved_updated_at(self) -> str:
        if self.updated_at:
            return self.updated_at
        if self.communication and self.communication.entry_date:
            return self.communication.entry_date
        return date.today().isoformat()

