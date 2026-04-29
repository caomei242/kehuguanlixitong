from __future__ import annotations

from datetime import date

from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.models import ApprovalEntry, CommunicationEntry, CustomerDraft, CUSTOMER_STAGES, ProjectDraft, ProjectRecord


def write_seed_vault(root):
    customer_dir = root / "客户"
    customer_dir.mkdir(parents=True)
    (root / "00 客户总表.md").write_text(
        """# 客户总表

更新时间：2026-04-20

## 本周重点跟进

| 客户 | 客户类型 | 当前需求 | 最近推进 | 下次动作 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- |
| 爱慕 | 品牌客户 | 继续跟进新业务机会 | 已有合同沉淀 | 补充新业务需求 | [[客户/客户--爱慕]] | 2026-04-20 |

## 品牌客户总表

| 客户 | 阶段 | 业务方向 | 当前需求 | 最近推进 | 下次动作 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 爱慕 | 已合作 | 视频拍摄 / 品牌合作 | 新业务待继续补需求 | 完成合同审批口径 | 补齐新业务需求 | 张三 | [[客户/客户--爱慕]] | 2026-04-20 |

## 网店店群客户总表

| 客户 | 阶段 | 业务方向 | 店铺规模 | 当前需求 | 最近推进 | 下次动作 | 主联系人 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 星河店群 | 潜客 | 集采点数 / 店铺软件批量采购 | 30家店 | 想问批量折扣 | 初次询价 | 确认采购量 | 李四 | [[客户/客户--星河店群]] | 2026-04-20 |

## 暂缓 / 待观察

| 客户 | 客户类型 | 暂缓原因 | 下次观察点 | 对应客户页 | 更新时间 |
| --- | --- | --- | --- | --- | --- |
""",
        encoding="utf-8",
    )
    (customer_dir / "客户--爱慕.md").write_text(
        """# 客户--爱慕

## 基本信息
- 客户类型：品牌客户
- 客户名称：爱慕
- 所属公司/主体：爱慕股份有限公司
- 当前联系人：张三
- 联系电话：13800001111
- 微信号：amu_zhangsan
- 来源：既有品牌合作
- 主业文件路径：`/Users/gd/Desktop/主业/品牌项目/品牌--爱慕/`
- 对外资料路径：待补充

## 业务画像
- 主要业务方向：视频拍摄 / 品牌合作
- 典型诉求：围绕品牌内容制作继续推进
- 关键数量/规模：待补充
- 合同/付款特征：已有合同资料

## 当前判断
- 阶段：已合作
- 当前重点：补齐新业务需求
- 合作可能性：已有合作基础
- 下次动作：补充新业务需求
- 更新时间：2026-04-20

## 当前需求
- 需求一句话：新业务待继续补需求
- 目标：完成既有合作交付与后续新业务机会推进
- 交付物/采购内容：短视频拍摄制作服务
- 时间要求：待补充
- 预算/报价线索：待补充
- 限制条件：正式合作需以合同及附件为准

## 沟通沉淀
### 2026-04-16
- 本次沟通结论：完成合同审批口径整理
- 新增信息：合同内容为短视频拍摄制作服务
- 风险/顾虑：新业务需重新确认
- 下一步：补充新业务需求

## 待归属审批
### 2026-04-18 供应商用印待确认
- 审批类型：其他证明&申请单
- 审批标题/用途说明：供应商用印待确认
- 对应公司：厦门市邱熊网络科技有限公司
- 审批状态：审批中
- 审批结果：--
- 当前节点：业务Owner / tiger
- 审批完成时间：--
- 附件线索：2.26邱熊-爱慕股份有限公司策划项目确认单.docx
- 备注：当前只能确认到爱慕品牌，具体项目待归位
- 来源：钉钉审批

## 历史推进
- 2026-04-16：完成合同审批明细整理

## 待补资料
- 当前联系人
""",
        encoding="utf-8",
    )


def test_customer_archived_stage_and_project_follow_up_date_models_are_available():
    assert "已归档" in CUSTOMER_STAGES
    assert ProjectRecord("爱慕", "爱慕推广", "推进中", next_follow_up_date="2026-04-30").next_follow_up_date == "2026-04-30"
    assert ProjectDraft("爱慕", "爱慕推广", "推进中", next_follow_up_date="2026-04-30").next_follow_up_date == "2026-04-30"


def test_lists_customers_from_brand_and_shop_group_tables(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    records = store.list_customers()

    assert [record.name for record in records] == ["爱慕", "星河店群"]
    assert records[0].customer_type == "品牌客户"
    assert records[0].stage == "已合作"
    assert records[1].customer_type == "网店店群客户"
    assert records[1].shop_scale == "30家店"
    assert records[0].next_follow_up_date == ""
    assert records[1].next_follow_up_date == ""


def test_focus_customers_excludes_archived_and_suspended(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    store.upsert_customer(
        CustomerDraft(
            name="MW1",
            customer_type="品牌客户",
            stage="已归档",
            business_direction="短视频拍摄",
            current_need="去年项目已结束",
            next_action="仅保留历史查询",
            next_follow_up_date="已归档",
            communication=CommunicationEntry(entry_date="2026-04-27", summary="确认收档"),
        )
    )
    store.upsert_customer(
        CustomerDraft(
            name="暂缓客户",
            customer_type="品牌客户",
            stage="暂缓",
            business_direction="品牌推广",
            current_need="暂不推进",
            next_action="后续有触发再看",
            communication=CommunicationEntry(entry_date="2026-04-27", summary="转暂缓"),
        )
    )

    assert [record.name for record in store.list_focus_customers()] == ["爱慕", "星河店群"]


def test_reads_customer_detail_sections(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    detail = store.get_customer("爱慕")

    assert detail.name == "爱慕"
    assert detail.customer_type == "品牌客户"
    assert detail.stage == "已合作"
    assert detail.phone == "13800001111"
    assert detail.wechat_id == "amu_zhangsan"
    assert detail.current_need == "新业务待继续补需求"
    assert detail.next_follow_up_date == ""
    assert detail.communication_entries[0].entry_date == "2026-04-16"
    assert detail.communication_entries[0].summary == "完成合同审批口径整理"
    assert detail.pending_approval_count == 1
    assert detail.pending_approval_entries[0].counterparty == "厦门市邱熊网络科技有限公司"


def test_updates_customer_party_a_info_section(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    detail = store.upsert_customer(
        CustomerDraft(
            name="爱慕",
            customer_type="品牌客户",
            stage="已合作",
            business_direction="视频拍摄 / 品牌合作",
            contact="张三",
            company="爱慕股份有限公司",
            current_need="新业务待继续补需求",
            next_action="补充新业务需求",
            party_a_brand="爱慕儿童",
            party_a_company="爱慕股份有限公司",
            party_a_contact="李岩",
            party_a_phone="17778019272",
            party_a_email="rellaliyan@aimer.com.cn",
            party_a_address="北京市朝阳区望京开发区利泽中园2区218、219号楼爱慕大厦",
            communication=CommunicationEntry(entry_date="2026-04-21", summary="补录甲方收件信息"),
        )
    )

    assert detail.party_a_brand == "爱慕儿童"
    assert detail.party_a_contact == "李岩"
    text = (tmp_path / "客户" / "客户--爱慕.md").read_text(encoding="utf-8")
    assert "## 甲方信息" in text
    assert "- 收件联系人：李岩" in text
    assert "- 电子邮箱：rellaliyan@aimer.com.cn" in text


def test_appends_pending_customer_approval_without_losing_existing_data(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    detail = store.append_pending_approval(
        "爱慕",
        ApprovalEntry(
            entry_date="2026-04-21",
            approval_type="其他证明&申请单",
            title_or_usage="爱慕补充确认单审批",
            counterparty="爱慕股份有限公司",
            approval_status="审批中",
            current_node="直属Owner / 花茶",
            note="补录到客户待归属审批",
        ),
    )

    assert detail.pending_approval_count == 2
    assert detail.pending_approval_entries[0].title_or_usage == "爱慕补充确认单审批"
    text = (tmp_path / "客户" / "客户--爱慕.md").read_text(encoding="utf-8")
    assert "## 待归属审批" in text
    assert "爱慕补充确认单审批" in text


def test_creates_shop_group_customer_and_updates_summary(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    store.upsert_customer(
        CustomerDraft(
            name="云舟店群",
            customer_type="网店店群客户",
            stage="潜客",
            business_direction="集采点数 / 店铺软件批量采购",
            contact="王五",
            phone="13812345678",
            wechat_id="yunzhou_shop_01",
            shop_scale="50家店",
            current_need="想确认 50 家店批量购买是否有阶梯折扣",
            recent_progress="初次录入",
            next_action="确认采购软件、点数数量和期望折扣",
            next_follow_up_date="2026-04-22",
            communication=CommunicationEntry(
                entry_date="2026-04-20",
                summary="客户有 50 家店，想问批量采购折扣",
                new_info="关注店铺软件和点数价格",
                risk="暂未确认采购时间",
                next_step="补齐采购数量",
            ),
        )
    )

    detail_path = tmp_path / "客户" / "客户--云舟店群.md"
    assert detail_path.exists()
    detail_text = detail_path.read_text(encoding="utf-8")
    assert "- 客户类型：网店店群客户" in detail_text
    assert "- 联系电话：13812345678" in detail_text
    assert "- 微信号：yunzhou_shop_01" in detail_text
    assert "- 关键数量/规模：50家店" in detail_text
    assert "- 下次跟进日期：2026-04-22" in detail_text
    summary_text = (tmp_path / "00 客户总表.md").read_text(encoding="utf-8")
    assert "| 客户 | 阶段 | 业务方向 | 店铺规模 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |" in summary_text
    assert "| 云舟店群 | 潜客 | 集采点数 / 店铺软件批量采购 | 50家店 | 想确认 50 家店批量购买是否有阶梯折扣 | 初次录入 | 确认采购软件、点数数量和期望折扣 | 2026-04-22 | 王五 | [[客户/客户--云舟店群]] | 2026-04-20 |" in summary_text


def test_creates_shop_ka_customer_and_adds_missing_summary_section(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    store.upsert_customer(
        CustomerDraft(
            name="青竹画材官方旗舰店",
            customer_type="网店KA客户",
            stage="已合作",
            business_direction="KA版 / AI裂变 / AI详情页",
            contact="待补充",
            shop_scale="抖店 · 已订购 KA版",
            current_need="已使用 AI裂变，并对 AI详情页功能有明确兴趣",
            recent_progress="从临时店群分类修正为 KA 客户运营",
            next_action="跟进 AI详情页介绍、试用安排和增购可能",
            communication=CommunicationEntry(
                entry_date="2026-04-23",
                summary="确认青竹画材官方旗舰店属于网店KA客户",
                new_info="抖店已订购 KA版，主要使用 AI裂变",
                next_step="继续跟进 AI详情页功能兴趣",
            ),
        )
    )

    detail_path = tmp_path / "客户" / "客户--青竹画材官方旗舰店.md"
    assert detail_path.exists()
    detail_text = detail_path.read_text(encoding="utf-8")
    assert "- 客户类型：网店KA客户" in detail_text
    assert "- 关键数量/规模：抖店 · 已订购 KA版" in detail_text
    assert "- 合同/付款特征：已付费产品使用深化、功能跟进、增购/新功能转化" in detail_text
    summary_text = (tmp_path / "00 客户总表.md").read_text(encoding="utf-8")
    assert "## 网店KA客户总表" in summary_text
    assert "| 客户 | 阶段 | 业务方向 | 店铺/产品状态 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |" in summary_text
    assert "| 青竹画材官方旗舰店 | 已合作 | KA版 / AI裂变 / AI详情页 | 抖店 · 已订购 KA版 | 已使用 AI裂变，并对 AI详情页功能有明确兴趣 | 从临时店群分类修正为 KA 客户运营 | 跟进 AI详情页介绍、试用安排和增购可能 |  | 待补充 | [[客户/客户--青竹画材官方旗舰店]] | 2026-04-23 |" in summary_text


def test_creates_blogger_customer_and_adds_blogger_summary_section(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    store.upsert_customer(
        CustomerDraft(
            name="那山那水那人",
            customer_type="博主 / 网店店群客户",
            stage="沟通中",
            secondary_tags="小时达 / 微信 / AI商品图 / AI详情页",
            business_direction="新功能推广 / AI商品图 / AI详情页",
            contact="孙总",
            shop_scale="博主推广者，同时也是小时达/微信场景使用者",
            current_need="评估是否合作推广 AI 商品图/详情页新功能",
            recent_progress="已发功能说明和示例图，博主表示这两天没在，回去后沟通",
            next_action="等待孙总回去后确认推广合作意向和报价/排期",
            communication=CommunicationEntry(
                entry_date="2026-04-27",
                summary="新增博主线索，那山那水那人可能合作推广新功能",
                new_info="该对象既可能是推广者，也可能是小时达/微信场景使用者",
                next_step="继续确认推广合作意向、报价和排期",
            ),
        )
    )

    detail_path = tmp_path / "客户" / "客户--那山那水那人.md"
    assert detail_path.exists()
    detail_text = detail_path.read_text(encoding="utf-8")
    assert "- 客户类型：博主 / 网店店群客户" in detail_text
    assert "- 二级标签：小时达 / 微信 / AI商品图 / AI详情页" in detail_text
    assert "- 合同/付款特征：功能推广合作、内容排期、样稿/报价及使用者转化情况" in detail_text
    summary_text = (tmp_path / "00 客户总表.md").read_text(encoding="utf-8")
    assert "## 博主总表" in summary_text
    assert "| 客户 | 阶段 | 业务方向 | 客户类型 | 二级标签 | 当前需求 | 最近推进 | 下次动作 | 下次跟进日期 | 主联系人 | 对应客户页 | 更新时间 |" in summary_text
    assert "| 那山那水那人 | 沟通中 | 新功能推广 / AI商品图 / AI详情页 | 博主 / 网店店群客户 | 小时达 / 微信 / AI商品图 / AI详情页 | 评估是否合作推广 AI 商品图/详情页新功能 | 已发功能说明和示例图，博主表示这两天没在，回去后沟通 | 等待孙总回去后确认推广合作意向和报价/排期 |  | 孙总 | [[客户/客户--那山那水那人]] | 2026-04-27 |" in summary_text


def test_updates_existing_customer_without_creating_duplicate_page(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    store.upsert_customer(
        CustomerDraft(
            name="爱慕",
            customer_type="品牌客户",
            stage="沟通中",
            business_direction="视频拍摄 / 品牌推广",
            contact="张三",
            current_need="新业务需要补充品牌推广需求",
            recent_progress="补充新业务沟通",
            next_action="确认推广节奏和预算",
            communication=CommunicationEntry(
                entry_date=date(2026, 4, 20).isoformat(),
                summary="追加新业务沟通",
                new_info="关注品牌推广节奏",
                risk="预算未确认",
                next_step="确认预算",
            ),
        )
    )

    customer_files = list((tmp_path / "客户").glob("客户--爱慕*.md"))
    assert len(customer_files) == 1
    detail = store.get_customer("爱慕")
    assert detail.stage == "沟通中"
    assert detail.current_need == "新业务需要补充品牌推广需求"
    assert any(entry.entry_date == "2026-04-20" for entry in detail.communication_entries)


def test_renames_existing_customer_without_leaving_duplicate_summary_row(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)
    store.upsert_customer(
        CustomerDraft(
            name="星河店群",
            customer_type="网店店群客户",
            stage="潜客",
            business_direction="集采点数 / 店铺软件批量采购",
            contact="李四",
            shop_scale="30家店",
            current_need="想问批量折扣",
            recent_progress="初次询价",
            next_action="确认采购量",
            communication=CommunicationEntry(entry_date="2026-04-20", summary="初次询价"),
        )
    )

    detail = store.upsert_customer(
        CustomerDraft(
            original_name="星河店群",
            name="星河抖店店群",
            customer_type="网店店群客户",
            stage="沟通中",
            business_direction="集采点数 / 店铺软件批量采购",
            contact="李四",
            phone="13900001111",
            shop_scale="30家店",
            current_need="继续确认批量折扣",
            recent_progress="客户名称已确认",
            next_action="按新名称继续报价",
            communication=CommunicationEntry(
                entry_date="2026-04-20",
                summary="客户名称从星河店群确认成星河抖店店群",
            ),
        )
    )

    assert detail.name == "星河抖店店群"
    assert not (tmp_path / "客户" / "客户--星河店群.md").exists()
    renamed_text = (tmp_path / "客户" / "客户--星河抖店店群.md").read_text(encoding="utf-8")
    assert renamed_text.startswith("# 客户--星河抖店店群")
    assert "- 客户名称：星河抖店店群" in renamed_text
    assert "- 联系电话：13900001111" in renamed_text
    summary_text = (tmp_path / "00 客户总表.md").read_text(encoding="utf-8")
    assert "| 星河店群 |" not in summary_text
    assert "| 星河抖店店群 | 沟通中 | 集采点数 / 店铺软件批量采购 | 30家店 | 继续确认批量折扣 | 客户名称已确认 | 按新名称继续报价 |  | 李四 | [[客户/客户--星河抖店店群]] | 2026-04-20 |" in summary_text
