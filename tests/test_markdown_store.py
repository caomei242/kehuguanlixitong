from __future__ import annotations

from datetime import date

from strawberry_customer_management.markdown_store import MarkdownCustomerStore
from strawberry_customer_management.models import CommunicationEntry, CustomerDraft


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

## 历史推进
- 2026-04-16：完成合同审批明细整理

## 待补资料
- 当前联系人
""",
        encoding="utf-8",
    )


def test_lists_customers_from_brand_and_shop_group_tables(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    records = store.list_customers()

    assert [record.name for record in records] == ["爱慕", "星河店群"]
    assert records[0].customer_type == "品牌客户"
    assert records[0].stage == "已合作"
    assert records[1].customer_type == "网店店群客户"
    assert records[1].shop_scale == "30家店"


def test_reads_customer_detail_sections(tmp_path):
    write_seed_vault(tmp_path)
    store = MarkdownCustomerStore(tmp_path)

    detail = store.get_customer("爱慕")

    assert detail.name == "爱慕"
    assert detail.customer_type == "品牌客户"
    assert detail.stage == "已合作"
    assert detail.current_need == "新业务待继续补需求"
    assert detail.communication_entries[0].entry_date == "2026-04-16"
    assert detail.communication_entries[0].summary == "完成合同审批口径整理"


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
            shop_scale="50家店",
            current_need="想确认 50 家店批量购买是否有阶梯折扣",
            recent_progress="初次录入",
            next_action="确认采购软件、点数数量和期望折扣",
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
    assert "- 关键数量/规模：50家店" in detail_text
    summary_text = (tmp_path / "00 客户总表.md").read_text(encoding="utf-8")
    assert "| 云舟店群 | 潜客 | 集采点数 / 店铺软件批量采购 | 50家店 | 想确认 50 家店批量购买是否有阶梯折扣 | 初次录入 | 确认采购软件、点数数量和期望折扣 | 王五 | [[客户/客户--云舟店群]] | 2026-04-20 |" in summary_text


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

