from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from strawberry_customer_management.app import build_app
from strawberry_customer_management.models import (
    ApprovalEntry,
    CommunicationEntry,
    CustomerDetail,
    CustomerDraft,
    CustomerRecord,
    PartyAInfo,
    ProjectDetail,
    ProjectDraft,
    ProjectRecord,
)
from strawberry_customer_management.ui.pages.overview_page import OverviewPage
from strawberry_customer_management.ui.pages.project_management_page import ProjectManagementPage
from strawberry_customer_management.ui.pages.quick_capture_page import QuickCapturePage
from strawberry_customer_management.ui.pages.settings_page import SettingsPage


DEFAULT_OUTPUT_DIR = Path("/tmp/strawberry-customer-ui-qa")
DEFAULT_SIZES = ((1440, 900), (1200, 760))


def _build_overview_page() -> OverviewPage:
    page = OverviewPage()
    records = [
        CustomerRecord(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            current_need="合同已收到，待拍摄产品寄出",
            recent_progress="2026-04 合同甲方已收到回寄，拍摄产品待寄出",
            next_action="2026-04-27 跟进产",
            contact="李岩",
            updated_at="2026-04-23",
        ),
        CustomerRecord(
            name="青竹画材官方旗舰店",
            customer_type="网店KA客户",
            stage="已合作",
            business_direction="KA版 / AI裂变 / AI详情页",
            current_need="明确 AI详情页接入和下一批功能试用",
            recent_progress="客户确认一键生成方向可行，关心更新频率和主图切换",
            next_action="跟进新一轮测试反馈",
            contact="待补充",
            shop_scale="抖店 · 已订购 KA版",
            updated_at="2026-04-24",
        ),
        CustomerRecord(
            name="blackhead",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="小红书营销",
            current_need="补齐年份、联系人和当前是否仍需推进",
            recent_progress="小红书营销合同资料已归档，年份待确认",
            next_action="补齐年份、联系人和当前是否仍需推进",
            updated_at="2026-04-20",
        ),
        CustomerRecord(
            name="待补日期客户",
            customer_type="品牌客户",
            stage="沟通中",
            business_direction="视频项目",
            current_need="补一句话需求",
            recent_progress="待补最新进度",
            next_action="先补联系人",
            updated_at="待补日期",
        ),
    ]
    detail = CustomerDetail(
        name="爱慕儿童",
        customer_type="品牌客户",
        stage="已合作",
        business_direction="视频拍摄 / 品牌合作 / 新业务推进",
        current_need="爱慕儿童26年春夏短视频拍摄制作服务已形成合同与归档；新业务需求待继续补充。",
        current_focus="继续确认拍摄排期、产品寄送和新业务线索。",
        next_action="2026-04-27 跟进产",
        contact="李岩",
        phone="17778019272",
        wechat_id="rellaliyan",
        main_work_path="/Users/gd/Desktop/主业/品牌项目/品牌--爱慕儿童/",
        party_a_contact="李岩",
        party_a_phone="17778019272",
        party_a_email="rellaliyan@aimer.com.cn",
        party_a_address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
        pending_approval_entries=[
            ApprovalEntry(
                entry_date="2026-04-21",
                title_or_usage="爱慕春夏项目确认单",
                approval_status="审批通过",
            )
        ],
        pending_approval_count=1,
        communication_entries=[
            CommunicationEntry(
                entry_date="2026-04-23",
                summary="合同已收到回寄，拍摄产品待寄出。",
                new_info="当前优先看产品寄送和排期确认。",
                risk="新业务需求一句话仍偏散。",
                next_step="跟进产并补一句话需求。",
            )
        ],
    )
    related_projects = [
        ProjectRecord(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="拍摄产待寄出",
            next_action="跟进拍摄排期",
            latest_approval_status="审批通过 · 合同已回寄",
        )
    ]
    page.set_customers(records, selected_name="爱慕儿童")
    page.show_customer_detail(detail)
    page.set_related_projects(related_projects, detail.customer_type)
    return page


def _build_quick_capture_page() -> QuickCapturePage:
    page = QuickCapturePage()
    page.set_target_customer("爱慕儿童", mode_label="更新老客户")
    page.set_raw_text(
        "爱慕儿童补充需求：合同已收到，拍摄产品待寄出；新业务想继续推进，"
        "需要把一句话需求、预算线索和下一步补完整。"
    )
    page.apply_draft(
        CustomerDraft(
            name="爱慕儿童",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作 / 新业务推进",
            contact="李岩",
            phone="17778019272",
            company="爱慕股份有限公司",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            party_a_contact="李岩",
            party_a_phone="17778019272",
            party_a_email="rellaliyan@aimer.com.cn",
            party_a_address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
            current_need="合同已回寄，待拍摄产寄出并补新业务需求一句话。",
            recent_progress="合同资料已归档，当前重点在拍摄产和新业务线索。",
            next_action="2026-04-27 跟进产",
            communication=CommunicationEntry(
                entry_date="2026-04-26",
                summary="已补当前客户信息并确认下一步。",
                new_info="客户对新业务仍有推进意向。",
                risk="一句话需求和预算线索还需要继续补。",
                next_step="跟进产并补预算线索。",
            ),
        )
    )
    page.set_status("当前为 QA 示例页，仅用于检查快速录入布局。")
    return page


def _build_project_management_page() -> ProjectManagementPage:
    page = ProjectManagementPage()
    records = [
        ProjectRecord(
            brand_customer_name="爱慕儿童",
            project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
            stage="推进中",
            year="2026",
            project_type="合同项目",
            current_focus="拍摄产品待寄出",
            next_action="跟进排期和新业务补充",
            updated_at="2026-04-23",
            latest_approval_status="审批通过 · 合同已回寄",
        ),
        ProjectRecord(
            brand_customer_name="青竹画材官方旗舰店",
            project_name="2026-04 青竹画材KA跟进",
            stage="推进中",
            year="2026",
            project_type="KA客户运营",
            current_focus="跟进 AI详情页和主图生成反馈",
            next_action="收测试结果",
            updated_at="2026-04-24",
            latest_approval_status="暂无审批记录",
        ),
    ]
    detail = ProjectDetail(
        brand_customer_name="爱慕儿童",
        project_name="2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
        stage="推进中",
        year="2026",
        project_type="合同项目",
        current_focus="拍摄产品待寄出，排期待确认。",
        next_action="2026-04-27 跟进产并补后续需求。",
        main_work_path="/Users/gd/Desktop/主业/品牌项目/品牌--爱慕儿童/2026/2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
        path_status="主业路径有效",
        risk="新业务需求一句话和预算线索还不完整。",
        latest_approval_status="审批通过 · 合同已回寄",
        default_party_a_info=PartyAInfo(
            brand="爱慕儿童",
            company="爱慕股份有限公司",
            contact="李岩",
            phone="17778019272",
            email="rellaliyan@aimer.com.cn",
            address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
        ),
        materials_markdown="- 合同回寄件\n- 确认单\n- 拍摄需求草稿",
        notes_markdown="- 当前项目已归档部分合同资料。\n- 新业务需求仍在继续补充。",
        approval_entries=[
            ApprovalEntry(
                entry_date="2026-04-21",
                title_or_usage="爱慕春夏项目确认单",
                counterparty="爱慕股份有限公司",
                approval_status="审批通过",
                current_node="已结束",
            )
        ],
    )
    page.set_projects(records, selected_project=("爱慕儿童", "2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同"))
    page.set_project_detail(detail)
    page.set_approval_inbox_path("/Users/gd/Desktop/主业/钉钉审批导入")
    page.set_approval_import_text("草莓提交的用印申请\n品牌：爱慕股份有限公司\n审批通过")
    page.set_approval_import_preview(
        [
            "1. 2026-04-21 · 审批通过 · 爱慕儿童 / 2026-04 爱慕儿童26年春夏短视频拍摄制作服务合同",
        ]
    )
    page.set_status("当前为 QA 示例页，仅用于检查项目管理布局。")
    return page


def _build_settings_page() -> SettingsPage:
    page = SettingsPage()
    page.set_values(
        customer_root="/Users/gd/Library/Mobile Documents/iCloud~md~obsidian/Documents/项目管理/草莓客户管理系统--主业/客户数据",
        project_root="/Users/gd/Library/Mobile Documents/iCloud~md~obsidian/Documents/项目管理/草莓客户管理系统--主业/项目数据",
        main_work_root="/Users/gd/Desktop/主业",
        approval_inbox_root="/Users/gd/Desktop/主业/钉钉审批导入",
        minimax_api_key="sk-cp-demo-key",
        minimax_model="MiniMax-M2.7",
        minimax_base_url="https://api.minimaxi.com/v1",
    )
    page.set_status("路径和 MiniMax 配置已载入，当前为 QA 示例页。")
    return page


def _render_page(page: QWidget, output_dir: Path, page_name: str, sizes: tuple[tuple[int, int], ...]) -> list[Path]:
    created: list[Path] = []
    for width, height in sizes:
        page.resize(width, height)
        page.show()
        app = page.window().windowHandle()
        if app is not None:
            app.requestActivate()
        build_app().processEvents()
        output_path = output_dir / f"{page_name}-{width}x{height}.png"
        page.grab().save(str(output_path), "PNG")
        created.append(output_path)
    page.close()
    build_app().processEvents()
    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render offscreen UI QA screenshots for 草莓客户管理系统.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for screenshots. Default: {DEFAULT_OUTPUT_DIR}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    app = build_app()
    pages = {
        "OverviewPage": _build_overview_page(),
        "QuickCapturePage": _build_quick_capture_page(),
        "ProjectManagementPage": _build_project_management_page(),
        "SettingsPage": _build_settings_page(),
    }

    created: list[Path] = []
    for name, page in pages.items():
        created.extend(_render_page(page, output_dir, name, DEFAULT_SIZES))

    for path in created:
        print(path)
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
