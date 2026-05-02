from __future__ import annotations

from strawberry_customer_management.models import INTERNAL_MAIN_WORK_NAME, PersonDraft, PersonProjectLink
from strawberry_customer_management.person_store import MarkdownPersonStore


def test_person_store_creates_summary_and_person_page_without_prefix(tmp_path):
    store = MarkdownPersonStore(tmp_path / "人员数据")

    detail = store.upsert_person(
        PersonDraft(
            name="内部负责人A",
            gender="女",
            side="我方",
            organization="厦门市邱熊网络科技有限公司",
            brand="草莓主业",
            common_relation="内部Owner",
            linked_customers=["爱慕儿童"],
            project_links=[
                PersonProjectLink(
                    customer_name="爱慕儿童",
                    project_name="2026-04 爱慕儿童春夏短视频项目",
                    side="我方",
                    relation="内部Owner",
                )
            ],
            judgement="内部关键协作人，适合承接审批和资源确认。",
            relation_notes="- 2026-05-02：首次整理关系人档案。",
            updated_at="2026-05-02",
        )
    )

    assert detail.page_path == tmp_path / "人员数据" / "人员" / "内部负责人A.md"
    assert detail.page_link == "[[人员/内部负责人A]]"
    assert detail.project_links[0].relation == "内部Owner"
    assert detail.relation_notes == "- 2026-05-02：首次整理关系人档案。"

    summary_text = (tmp_path / "人员数据" / "00 关系人总表.md").read_text(encoding="utf-8")
    assert "| 姓名 | 性别 | 所属方 | 所属组织 | 所属品牌 | 常见关系 | 关联客户 | 关联项目 | 对应人员页 | 更新时间 |" in summary_text
    assert "| 内部负责人A | 女 | 我方 | 厦门市邱熊网络科技有限公司 | 草莓主业 | 内部Owner | 爱慕儿童 | 2026-04 爱慕儿童春夏短视频项目 | [[人员/内部负责人A]] | 2026-05-02 |" in summary_text
    assert "关系人--内部负责人A" not in summary_text

    page_text = detail.page_path.read_text(encoding="utf-8")
    assert "# 内部负责人A" in page_text
    assert "## 基本信息" in page_text
    assert "## 我对这个人的判断" in page_text
    assert "## 关联客户" in page_text
    assert "## 关联项目" in page_text
    assert "## 关系沉淀" in page_text
    assert "| 我方 | 内部Owner | 爱慕儿童 | 2026-04 爱慕儿童春夏短视频项目 |" in page_text

    people = store.list_people()
    assert [person.name for person in people] == ["内部负责人A"]
    assert people[0].page_path == tmp_path / "人员数据" / "人员" / "内部负责人A.md"

    reloaded = store.get_person("内部负责人A")
    assert reloaded.gender == "女"
    assert reloaded.side == "我方"
    assert reloaded.linked_customers == ["爱慕儿童"]
    assert reloaded.project_links[0].project_name == "2026-04 爱慕儿童春夏短视频项目"


def test_person_store_updates_existing_person_without_losing_relation_notes(tmp_path):
    store = MarkdownPersonStore(tmp_path / "人员数据")
    store.upsert_person(
        PersonDraft(
            name="甲方联系人A",
            gender="待判断",
            side="客户方",
            organization="爱慕股份有限公司",
            brand="爱慕儿童",
            common_relation="品牌联系人",
            relation_notes="- 2026-05-01：负责合同回寄。",
            updated_at="2026-05-01",
        )
    )

    updated = store.upsert_person(
        PersonDraft(
            name="甲方联系人A",
            gender="女",
            side="客户方",
            organization="爱慕股份有限公司",
            brand="爱慕儿童",
            common_relation="甲方联系人",
            linked_customers=["爱慕儿童"],
            updated_at="2026-05-02",
        )
    )

    assert updated.gender == "女"
    assert updated.relation_notes == "- 2026-05-01：负责合同回寄。"
    assert updated.linked_customers == ["爱慕儿童"]

    summary_text = store.summary_path.read_text(encoding="utf-8")
    assert "甲方联系人" in summary_text
    assert "2026-05-02" in summary_text


def test_person_store_does_not_turn_internal_main_work_into_fake_customer(tmp_path):
    store = MarkdownPersonStore(tmp_path / "人员数据")

    detail = store.upsert_person(
        PersonDraft(
            name="内部负责人A",
            gender="男",
            side="内部支持",
            organization="内部业务线A / 稿定",
            brand=INTERNAL_MAIN_WORK_NAME,
            common_relation="内部负责人",
            project_links=[
                PersonProjectLink(
                    customer_name=INTERNAL_MAIN_WORK_NAME,
                    project_name="2026-05 内部业务线A组织关系与AI提效背景梳理",
                    side="内部支持",
                    relation="内部负责人",
                )
            ],
            updated_at="2026-05-02",
        )
    )

    assert detail.linked_customers == []
    page_text = detail.page_path.read_text(encoding="utf-8")
    assert "[[客户/客户--草莓主业]]" not in page_text
    assert "2026-05 内部业务线A组织关系与AI提效背景梳理" in page_text
