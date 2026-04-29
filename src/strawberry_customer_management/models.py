from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


CUSTOMER_TYPES = ("品牌客户", "网店KA客户", "网店店群客户", "博主")
PROJECT_CUSTOMER_TYPES = ("品牌客户", "网店KA客户", "博主")
SECONDARY_TAGS = (
    "小时达",
    "微信",
    "AI商品图",
    "AI详情页",
    "抖店",
    "小红书",
    "天猫",
    "短视频",
    "直播",
    "图文",
    "内容种草",
    "集采点数",
)
CUSTOMER_STAGES = ("潜客", "沟通中", "已合作", "暂缓", "已归档")
PROJECT_STAGES = ("待确认", "推进中", "已归档", "暂缓")
PROJECT_TYPES = (
    "待补充",
    "合同项目",
    "视频项目",
    "图文项目",
    "小红书项目",
    "KA客户运营",
    "博主推广",
    "品牌资料",
    "授权资料",
    "其他项目",
)


@dataclass(frozen=True)
class CommunicationEntry:
    entry_date: str
    summary: str = ""
    new_info: str = ""
    risk: str = ""
    next_step: str = ""


@dataclass(frozen=True)
class ApprovalEntry:
    entry_date: str
    approval_type: str = ""
    title_or_usage: str = ""
    counterparty: str = ""
    approval_status: str = ""
    approval_result: str = ""
    current_node: str = ""
    completed_at: str = ""
    attachment_clue: str = ""
    note: str = ""
    source: str = "钉钉审批"


@dataclass(frozen=True)
class PartyAInfo:
    brand: str = ""
    company: str = ""
    contact: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""

    def is_empty(self) -> bool:
        return not any(
            [
                self.brand.strip(),
                self.company.strip(),
                self.contact.strip(),
                self.phone.strip(),
                self.email.strip(),
                self.address.strip(),
            ]
        )

    def resolved_with(self, fallback: "PartyAInfo") -> "PartyAInfo":
        return PartyAInfo(
            brand=self.brand or fallback.brand,
            company=self.company or fallback.company,
            contact=self.contact or fallback.contact,
            phone=self.phone or fallback.phone,
            email=self.email or fallback.email,
            address=self.address or fallback.address,
        )


@dataclass(frozen=True)
class ProjectRole:
    name: str
    role: str = ""
    responsibility: str = ""
    note: str = ""


@dataclass(frozen=True)
class ProjectProgressNode:
    node_name: str
    status: str = ""
    owner: str = ""
    collaborators: str = ""
    planned_date: str = ""
    completed_date: str = ""
    risk: str = ""
    note: str = ""
    next_action: str = ""


@dataclass(frozen=True)
class CustomerRecord:
    name: str
    customer_type: str
    stage: str
    secondary_tags: str = ""
    business_direction: str = ""
    current_need: str = ""
    recent_progress: str = ""
    next_action: str = ""
    next_follow_up_date: str = ""
    contact: str = ""
    page_link: str = ""
    updated_at: str = ""
    shop_scale: str = ""
    page_path: Path | None = None


@dataclass(frozen=True)
class CustomerDetail(CustomerRecord):
    company: str = ""
    phone: str = ""
    wechat_id: str = ""
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
    party_a_brand: str = ""
    party_a_company: str = ""
    party_a_contact: str = ""
    party_a_phone: str = ""
    party_a_email: str = ""
    party_a_address: str = ""
    pending_approval_entries: list[ApprovalEntry] = field(default_factory=list)
    pending_approval_count: int = 0
    raw_text: str = ""

    @property
    def party_a_info(self) -> PartyAInfo:
        return PartyAInfo(
            brand=self.party_a_brand,
            company=self.party_a_company,
            contact=self.party_a_contact,
            phone=self.party_a_phone,
            email=self.party_a_email,
            address=self.party_a_address,
        )


@dataclass(frozen=True)
class CustomerDraft:
    name: str
    customer_type: str
    stage: str
    original_name: str = ""
    secondary_tags: str = ""
    business_direction: str = ""
    contact: str = ""
    phone: str = ""
    wechat_id: str = ""
    company: str = ""
    source: str = ""
    main_work_path: str = ""
    external_material_path: str = ""
    shop_scale: str = ""
    current_need: str = ""
    recent_progress: str = ""
    next_action: str = ""
    next_follow_up_date: str = ""
    party_a_brand: str = ""
    party_a_company: str = ""
    party_a_contact: str = ""
    party_a_phone: str = ""
    party_a_email: str = ""
    party_a_address: str = ""
    pending_approval_entries: list[ApprovalEntry] = field(default_factory=list)
    pending_approval_count: int = 0
    communication: CommunicationEntry | None = None
    updated_at: str | None = None

    def resolved_updated_at(self) -> str:
        if self.updated_at:
            return self.updated_at
        if self.communication and self.communication.entry_date:
            return self.communication.entry_date
        return date.today().isoformat()

    @property
    def party_a_info(self) -> PartyAInfo:
        return PartyAInfo(
            brand=self.party_a_brand,
            company=self.party_a_company,
            contact=self.party_a_contact,
            phone=self.party_a_phone,
            email=self.party_a_email,
            address=self.party_a_address,
        )


@dataclass(frozen=True)
class ProjectRecord:
    brand_customer_name: str
    project_name: str
    stage: str
    year: str = ""
    project_type: str = ""
    current_focus: str = ""
    next_action: str = ""
    next_follow_up_date: str = ""
    page_link: str = ""
    updated_at: str = ""
    main_work_path: str = ""
    page_path: Path | None = None
    path_status: str = ""
    latest_approval_status: str = ""


@dataclass(frozen=True)
class ProjectDetail(ProjectRecord):
    customer_page_link: str = ""
    risk: str = ""
    party_a_source: str = ""
    default_party_a_info: PartyAInfo = field(default_factory=PartyAInfo)
    party_a_info: PartyAInfo = field(default_factory=PartyAInfo)
    participant_roles: list[ProjectRole] = field(default_factory=list)
    participant_roles_markdown: str = ""
    progress_nodes: list[ProjectProgressNode] = field(default_factory=list)
    progress_markdown: str = ""
    materials_markdown: str = ""
    notes_markdown: str = ""
    approval_entries: list[ApprovalEntry] = field(default_factory=list)
    raw_text: str = ""


@dataclass(frozen=True)
class ProjectDraft:
    brand_customer_name: str
    project_name: str
    stage: str
    original_project_name: str = ""
    year: str = ""
    project_type: str = ""
    current_focus: str = ""
    next_action: str = ""
    next_follow_up_date: str = ""
    risk: str = ""
    customer_page_link: str = ""
    main_work_path: str = ""
    path_status: str = ""
    party_a_source: str = "继承客户默认甲方信息"
    default_party_a_info: PartyAInfo = field(default_factory=PartyAInfo)
    party_a_info: PartyAInfo = field(default_factory=PartyAInfo)
    override_party_a: bool = False
    participant_roles: list[ProjectRole] = field(default_factory=list)
    participant_roles_markdown: str = ""
    progress_nodes: list[ProjectProgressNode] = field(default_factory=list)
    progress_markdown: str = ""
    materials_markdown: str = ""
    notes_markdown: str = ""
    approval_entries: list[ApprovalEntry] = field(default_factory=list)
    latest_approval_status: str = ""
    updated_at: str | None = None

    def resolved_updated_at(self) -> str:
        return self.updated_at or date.today().isoformat()

    @property
    def effective_party_a_info(self) -> PartyAInfo:
        if self.override_party_a:
            return self.party_a_info.resolved_with(self.default_party_a_info)
        return self.default_party_a_info
