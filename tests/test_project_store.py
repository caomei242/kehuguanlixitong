from __future__ import annotations

from pathlib import Path

from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.markdown_store import _parse_approval_entries, summarize_approval_entry
from strawberry_customer_management.models import ApprovalEntry, CommunicationEntry, CustomerDraft, PartyAInfo, ProjectDraft
from strawberry_customer_management.project_discovery import DesktopProjectDiscoveryService
from strawberry_customer_management.project_store import MarkdownProjectStore


def seed_brand_customer(root: Path, main_work_path: str) -> MarkdownCustomerStore:
    store = MarkdownCustomerStore(root)
    store.upsert_customer(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            company="爱慕股份有限公司",
            contact="李岩",
            current_need="推进春夏短视频项目",
            next_action="继续补充后续项目需求",
            main_work_path=main_work_path,
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            party_a_contact="李岩",
            party_a_phone="17778019272",
            party_a_email="rellaliyan@aimer.com.cn",
            party_a_address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="已有品牌客户"),
        )
    )
    return store


def seed_brand_project_dirs(main_work_root: Path) -> None:
    project_dir = main_work_root / "品牌项目" / "品牌--爱慕儿童" / "2026" / "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同"
    project_dir.mkdir(parents=True)
    (project_dir / "合同模板.docx").write_text("stub", encoding="utf-8")
    (project_dir / "授权委托书.docx").write_text("stub", encoding="utf-8")


def test_desktop_project_discovery_repairs_customer_path_and_builds_project_draft(tmp_path):
    main_work_root = tmp_path / "主业"
    wrong_path = str(main_work_root / "品牌项目" / "品牌--爱慕") + "/"
    seed_brand_project_dirs(main_work_root)
    customer_store = seed_brand_customer(tmp_path / "客户数据", wrong_path)
    detail = customer_store.get_customer("爱慕儿童")

    discovery = DesktopProjectDiscoveryService(main_work_root)
    result = discovery.discover_for_customer(detail)

    assert result.corrected_main_work_path.endswith("品牌--爱慕儿童/")
    assert len(result.projects) == 1
    assert result.projects[0].project_name == "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同"
    assert result.projects[0].default_party_a_info.contact == "李岩"


def test_project_store_creates_and_renames_project_with_party_a_override(tmp_path):
    store = MarkdownProjectStore(tmp_path / "项目数据")
    default_party_a = PartyAInfo(
        brand="爱慕儿童",
        company="爱慕股份有限公司",
        contact="李岩",
        phone="17778019272",
        email="rellaliyan@aimer.com.cn",
        address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
    )

    store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="已归档",
            year="2026",
            project_type="合同项目",
            current_focus="已同步桌面资料",
            next_action="补充后续项目判断",
            customer_page_link="[[客户/客户--爱慕儿童]]",
            main_work_path="/tmp/fake-project",
            path_status="主业路径有效",
            default_party_a_info=default_party_a,
            materials_markdown="- 文件：合同模板.docx",
            notes_markdown="- 首次同步",
            approval_entries=[
                ApprovalEntry(
                    entry_date="2026-04-21",
                    approval_type="其他证明&申请单",
                    title_or_usage="爱慕春夏项目确认单",
                    counterparty="爱慕股份有限公司",
                    approval_status="审批中",
                    current_node="业务Owner / tiger",
                    attachment_clue="邱熊2026确认单0421--爱慕儿童.docx",
                    note="已关联确认单",
                )
            ],
        )
    )

    detail = store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            original_project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同-补充版",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="补充项目当前重点",
            next_action="确认寄送地址",
            risk="纸质文件寄送信息需再确认",
            customer_page_link="[[客户/客户--爱慕儿童]]",
            main_work_path="/tmp/fake-project",
            path_status="主业路径有效",
            party_a_source="项目覆盖甲方信息",
            default_party_a_info=default_party_a,
            party_a_info=PartyAInfo(contact="项目联系人", phone="18800001111"),
            override_party_a=True,
            materials_markdown="- 文件：合同模板.docx",
            notes_markdown="- 手动补充项目信息",
        )
    )

    assert detail.project_name.endswith("补充版")
    assert detail.party_a_info.contact == "项目联系人"
    assert detail.default_party_a_info.contact == "李岩"
    assert detail.approval_entries[0].title_or_usage == "爱慕春夏项目确认单"
    assert detail.latest_approval_status == "审批中 · 业务Owner / tiger"
    assert not (tmp_path / "项目数据" / "项目" / "爱慕儿童" / "项目--2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同.md").exists()
    assert (tmp_path / "项目数据" / "项目" / "爱慕儿童" / "项目--2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同-补充版.md").exists()
    summary_text = (tmp_path / "项目数据" / "00 品牌项目总表.md").read_text(encoding="utf-8")
    assert summary_text.startswith("# 项目总表")
    assert "| 关联客户 | 项目名称 | 项目状态 | 年份 | 项目类型 | 当前重点 | 下一步 | 主业项目路径 | 对应项目页 | 更新时间 |" in summary_text
    assert "项目--2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同-补充版" in summary_text


def test_project_store_supports_shop_ka_operation_project(tmp_path):
    store = MarkdownProjectStore(tmp_path / "项目数据")

    detail = store.upsert_project(
        ProjectDraft(
            brand_customer_name="青竹画材官方旗舰店",
            project_name="2026-04 青竹画材KA版与AI详情页跟进",
            stage="推进中",
            year="2026",
            project_type="KA客户运营",
            current_focus="已订购 KA版，当前主要使用 AI裂变，并关注 AI详情页",
            next_action="跟进 AI详情页功能介绍、试用安排和增购可能",
            customer_page_link="[[客户/客户--青竹画材官方旗舰店]]",
            main_work_path="暂未建立独立主业目录（客户功能跟进）",
            path_status="主业路径失效",
            notes_markdown="- KA 客户运营项目，不归入店群折扣或品牌内容项目。",
        )
    )

    assert detail.brand_customer_name == "青竹画材官方旗舰店"
    assert detail.project_type == "KA客户运营"
    page_text = (tmp_path / "项目数据" / "项目" / "青竹画材官方旗舰店" / "项目--2026-04 青竹画材KA版与AI详情页跟进.md").read_text(
        encoding="utf-8"
    )
    assert "- 关联客户：青竹画材官方旗舰店" in page_text
    summary_text = (tmp_path / "项目数据" / "00 品牌项目总表.md").read_text(encoding="utf-8")
    assert "| 青竹画材官方旗舰店 | 2026-04 青竹画材KA版与AI详情页跟进 | 推进中 | 2026 | KA客户运营 |" in summary_text


def test_project_store_lists_brand_projects_by_latest_update_first(tmp_path):
    store = MarkdownProjectStore(tmp_path / "项目数据")
    store.summary_path.parent.mkdir(parents=True, exist_ok=True)
    store.summary_path.write_text(
        """# 项目总表

## 项目总表
| 关联客户 | 项目名称 | 项目状态 | 年份 | 项目类型 | 当前重点 | 下一步 | 主业项目路径 | 对应项目页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 爱慕儿童 | 旧项目 | 推进中 | 2026 | 合同项目 | 旧项目重点 | 旧项目下一步 | /tmp/old | [[项目/爱慕儿童/项目--旧项目]] | 2026-04-20 |
| 爱慕儿童 | 最新项目 | 推进中 | 2026 | 合同项目 | 最新项目重点 | 最新项目下一步 | /tmp/new | [[项目/爱慕儿童/项目--最新项目]] | 2026-04-25 |
| 爱慕儿童 | 同日后录入项目 | 推进中 | 2026 | 合同项目 | 同日后录入重点 | 同日后录入下一步 | /tmp/same-day | [[项目/爱慕儿童/项目--同日后录入项目]] | 2026-04-25 |
""",
        encoding="utf-8",
    )

    records = store.list_projects_for_brand("爱慕儿童")

    assert [record.project_name for record in records] == ["最新项目", "同日后录入项目", "旧项目"]


def test_project_store_appends_approval_and_tracks_unassigned_entries(tmp_path):
    store = MarkdownProjectStore(tmp_path / "项目数据")
    default_party_a = PartyAInfo(contact="李岩")
    store.upsert_project(
        ProjectDraft(
            brand_customer_name="爱慕儿童",
            project_name="2025-05 爱慕儿童短视频拍摄制作服务合同",
            stage="推进中",
            year="2025",
            project_type="合同项目",
            current_focus="补录审批",
            next_action="继续跟进",
            customer_page_link="[[客户/客户--爱慕儿童]]",
            main_work_path="/tmp/fake-project",
            path_status="主业路径有效",
            default_party_a_info=default_party_a,
        )
    )

    detail = store.append_approval_entry(
        "爱慕儿童",
        "2025-05 爱慕儿童短视频拍摄制作服务合同",
        ApprovalEntry(
            entry_date="2026-02-26",
            approval_type="其他证明&申请单",
            title_or_usage="邱熊-爱慕股份有限公司策划项目确认单",
            counterparty="爱慕股份有限公司",
            approval_status="审批通过",
            approval_result="审批通过",
            completed_at="2026-02-26 12:06:24",
        ),
    )
    store.append_unassigned_approval(
        ApprovalEntry(
            entry_date="2026-04-21",
            approval_type="其他证明&申请单",
            title_or_usage="厦门市邱熊网络科技有限公司供应商用印",
            counterparty="厦门市邱熊网络科技有限公司",
            approval_status="审批中",
            current_node="直属Owner / 花茶",
            note="待归属到具体项目",
        )
    )

    assert detail.approval_entries[0].approval_result == "审批通过"
    assert detail.latest_approval_status == "审批通过 · 2026-02-26 12:06:24"
    unassigned = store.list_unassigned_approvals()
    assert len(unassigned) == 1
    assert unassigned[0].counterparty == "厦门市邱熊网络科技有限公司"
    fallback_text = (tmp_path / "项目数据" / "00 待归属审批.md").read_text(encoding="utf-8")
    assert "## 待归属审批" in fallback_text
    assert "直属Owner / 花茶" in fallback_text


def test_project_store_reads_latest_approval_first_even_if_written_out_of_order(tmp_path):
    store = MarkdownProjectStore(tmp_path / "项目数据")
    project_path = tmp_path / "项目数据" / "项目" / "爱慕儿童" / "项目--2026-04 爱慕儿童春夏短视频项目.md"
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(
        """# 项目--2026-04 爱慕儿童春夏短视频项目

## 基本信息
- 关联客户：爱慕儿童
- 所属年份：2026
- 项目名称：2026-04 爱慕儿童春夏短视频项目
- 项目状态：推进中
- 项目类型：合同项目
- 关联客户页：[[客户/客户--爱慕儿童]]
- 主业项目路径：/tmp/fake-project
- 主业路径状态：主业路径有效
- 最近同步时间：2026-04-26

## 当前判断
- 当前重点：补录审批顺序
- 下一步：继续跟进
- 风险提醒：待补充
- 更新时间：2026-04-26

## 审批记录
### 2026-04-21 旧审批
- 审批类型：其他证明&申请单
- 审批标题/用途说明：旧审批
- 对应公司：爱慕股份有限公司
- 审批状态：审批通过
- 审批结果：审批通过
- 当前节点：业务Owner / tiger
- 审批完成时间：2026-04-21 09:00:00
- 附件线索：旧审批.docx
- 备注：先写入
- 来源：钉钉审批

### 2026-04-25 最新审批
- 审批类型：其他证明&申请单
- 审批标题/用途说明：最新审批
- 对应公司：爱慕股份有限公司
- 审批状态：审批通过
- 审批结果：审批通过
- 当前节点：业务Owner / tiger
- 审批完成时间：2026-04-25 18:00:00
- 附件线索：最新审批.docx
- 备注：后写入
- 来源：钉钉审批

## 资料概览
- 待同步桌面项目资料

## 项目沉淀
- 待补项目沉淀
""",
        encoding="utf-8",
    )

    entries = _parse_approval_entries(project_path.read_text(encoding="utf-8"), "审批记录")

    assert [entry.title_or_usage for entry in entries] == ["最新审批", "旧审批"]
    assert summarize_approval_entry(entries[0]) == "审批通过 · 业务Owner / tiger"
