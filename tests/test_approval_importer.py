from __future__ import annotations

from strawberry_customer_management.approval_importer import (
    CUSTOMER_DESTINATION,
    PROJECT_DESTINATION,
    UNASSIGNED_DESTINATION,
    build_approval_import_candidates,
    parse_dingtalk_approval_entries,
)
from strawberry_customer_management.models import CustomerDetail, CustomerRecord, PartyAInfo, ProjectDetail, ProjectRecord


def test_parses_copied_dingtalk_approval_text() -> None:
    raw_text = """草莓提交的用印申请
用印文件名称及用途说明：供应商：厦门市邱熊网络科技有限公司 品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同
发起时间：2026-04-21
完成时间：2026-04-21 14:52
审批通过
当前节点：内部Owner"""

    entries = parse_dingtalk_approval_entries(raw_text, today="2026-04-23")

    assert len(entries) == 1
    entry = entries[0][0]
    assert entry.entry_date == "2026-04-21"
    assert entry.approval_type == "用印申请"
    assert "26年春夏短视频拍摄制作服务合同" in entry.title_or_usage
    assert entry.counterparty == "爱慕股份有限公司"
    assert entry.approval_status == "审批通过"
    assert entry.completed_at == "2026-04-21 14:52"
    assert entry.source == "钉钉审批"


def test_matches_approval_to_project_first_when_project_token_is_clear() -> None:
    raw_text = """草莓提交的用印申请
用印文件名称及用途说明：供应商：厦门市邱熊网络科技有限公司 品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同
发起时间：2026-04-21
完成时间：2026-04-21
审批通过"""
    project = ProjectRecord(
        brand_customer_name="爱慕儿童",
        project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
        stage="推进中",
        year="2026",
        project_type="合同项目",
    )
    customer = CustomerRecord(
        name="爱慕儿童",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="视频拍摄 / 品牌合作",
    )
    project_detail = ProjectDetail(
        brand_customer_name="爱慕儿童",
        project_name=project.project_name,
        stage="推进中",
        year="2026",
        project_type="合同项目",
        default_party_a_info=PartyAInfo(brand="爱慕儿童", company="爱慕股份有限公司"),
    )
    customer_detail = CustomerDetail(
        name="爱慕儿童",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="视频拍摄 / 品牌合作",
        company="爱慕股份有限公司",
        party_a_brand="爱慕儿童",
        party_a_company="爱慕股份有限公司",
    )

    candidates = build_approval_import_candidates(
        raw_text=raw_text,
        projects=[project],
        customers=[customer],
        project_details={("爱慕儿童", project.project_name): project_detail},
        customer_details={"爱慕儿童": customer_detail},
        today="2026-04-23",
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.destination == PROJECT_DESTINATION
    assert candidate.customer_name == "爱慕儿童"
    assert candidate.project_name == project.project_name
    assert candidate.confidence >= 6


def test_falls_back_to_customer_pending_when_only_brand_is_clear() -> None:
    raw_text = """草莓提交的用印申请
用印文件名称及用途说明：供应商：厦门市邱熊网络科技有限公司 品牌：爱慕股份有限公司 项目确认资料待补
发起时间：2026-04-21
审批中
当前节点：业务Owner / 内部负责人B"""
    project = ProjectRecord(
        brand_customer_name="爱慕儿童",
        project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
        stage="推进中",
        year="2026",
        project_type="合同项目",
    )
    customer = CustomerRecord(
        name="爱慕儿童",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="视频拍摄 / 品牌合作",
    )
    project_detail = ProjectDetail(
        brand_customer_name="爱慕儿童",
        project_name=project.project_name,
        stage="推进中",
        year="2026",
        project_type="合同项目",
        default_party_a_info=PartyAInfo(brand="爱慕儿童", company="爱慕股份有限公司"),
    )
    customer_detail = CustomerDetail(
        name="爱慕儿童",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="视频拍摄 / 品牌合作",
        company="爱慕股份有限公司",
        party_a_company="爱慕股份有限公司",
    )

    candidates = build_approval_import_candidates(
        raw_text=raw_text,
        projects=[project],
        customers=[customer],
        project_details={("爱慕儿童", project.project_name): project_detail},
        customer_details={"爱慕儿童": customer_detail},
        today="2026-04-23",
    )

    assert candidates[0].destination == CUSTOMER_DESTINATION
    assert candidates[0].customer_name == "爱慕儿童"
    assert candidates[0].project_name == ""
    assert candidates[0].entry.current_node == "业务Owner / 内部负责人B"


def test_unmatched_approval_goes_to_unassigned_bucket() -> None:
    raw_text = """草莓提交的用印申请
用印文件名称及用途说明：供应商：未知公司 临时资料盖章
发起时间：2026-04-21
审批中"""

    candidates = build_approval_import_candidates(
        raw_text=raw_text,
        projects=[],
        customers=[],
        today="2026-04-23",
    )

    assert candidates[0].destination == UNASSIGNED_DESTINATION
    assert "未匹配" in candidates[0].reason


def test_parses_dingtalk_pdf_form_as_one_approval_and_matches_project() -> None:
    raw_text = """草莓提交的用印申请202604211208000123741.pdf
用印申请
审批编号 202604211208000123741
创建人 草莓
用印需求类型 其它证明&申请单
用印文件名称及用途说
明
供应商 厦门市邱熊网络科技有限公司 为 品牌方 深圳汇洁集团股份有限公司
（曼妮芬棉质生活）达人种草视频项目供应商确认单盖章，
内容为40条达人种草视频及对应剪辑服务，
关联业务销售合同审批编号：202601291039000240904，
本次确认单含税金额为15200元，付款将于甲方付款至我司后，再支付给供应商。
附件（须上传电子文件） 邱熊2026确认单0306--曼妮芬棉质生活.docx
公司名称 厦门稿定股份有限公司
审批流程
【内部Owner】 内部负责人A 已同意 2026-04-21 13:25:33
【业务Owner】 内部负责人B 已同意 2026-04-21 13:26:44
【印章审批人】 法务A 已同意 2026-04-21 14:08:34
【审批人】 审批人A 已同意 2026-04-21 14:09:10
抄送阿豹,五花,彬彬 2026-04-21 14:09:10
用钉钉扫码稿定(厦门)科技有限公司 创建时间：2026-04-21"""
    project = ProjectRecord(
        brand_customer_name="曼妮芬棉质生活",
        project_name="2026-03 曼妮芬棉质生活达人种草视频项目",
        stage="已归档",
        year="2026",
        project_type="视频项目",
    )
    customer = CustomerRecord(
        name="曼妮芬棉质生活",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="达人种草视频",
    )
    customer_detail = CustomerDetail(
        name="曼妮芬棉质生活",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="达人种草视频",
        company="深圳汇洁集团股份有限公司",
    )

    entries = parse_dingtalk_approval_entries(raw_text, today="2026-04-24")
    candidates = build_approval_import_candidates(
        raw_text=raw_text,
        projects=[project],
        customers=[customer],
        project_details={("曼妮芬棉质生活", project.project_name): ProjectDetail(
            brand_customer_name="曼妮芬棉质生活",
            project_name=project.project_name,
            stage="已归档",
            year="2026",
            project_type="视频项目",
        )},
        customer_details={"曼妮芬棉质生活": customer_detail},
        today="2026-04-24",
    )

    assert len(entries) == 1
    entry = entries[0][0]
    assert entry.entry_date == "2026-04-21"
    assert entry.approval_type == "用印申请"
    assert entry.counterparty == "深圳汇洁集团股份有限公司"
    assert entry.approval_status == "审批通过"
    assert entry.completed_at == "2026-04-21 14:09:10"
    assert entry.title_or_usage == "曼妮芬棉质生活达人种草视频项目供应商确认单 · 15200元"
    assert entry.attachment_clue == "草莓提交的用印申请202604211208000123741.pdf；邱熊2026确认单0306--曼妮芬棉质生活.docx"
    assert candidates[0].destination == PROJECT_DESTINATION
    assert candidates[0].customer_name == "曼妮芬棉质生活"
    assert candidates[0].project_name == "2026-03 曼妮芬棉质生活达人种草视频项目"
