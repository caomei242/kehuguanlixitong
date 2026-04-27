from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from strawberry_customer_management.models import CustomerDetail, PartyAInfo, ProjectDraft


YEAR_DIR_PATTERN = re.compile(r"^\d{4}$")


@dataclass(frozen=True)
class ProjectDiscoveryResult:
    resolved_brand_path: Path | None = None
    corrected_main_work_path: str = ""
    projects: list[ProjectDraft] = field(default_factory=list)


class DesktopProjectDiscoveryService:
    def __init__(self, main_work_root: Path) -> None:
        self.main_work_root = main_work_root
        self.brand_projects_root = self.main_work_root / "品牌项目"

    def discover_for_customer(self, detail: CustomerDetail) -> ProjectDiscoveryResult:
        if detail.customer_type != "品牌客户":
            return ProjectDiscoveryResult()
        brand_path = self._resolve_brand_path(detail)
        if brand_path is None:
            return ProjectDiscoveryResult()

        projects: list[ProjectDraft] = []
        for year_dir in self._iter_year_dirs(brand_path):
            year_label = year_dir.name
            for project_dir in sorted([path for path in year_dir.iterdir() if path.is_dir()], key=lambda path: path.name, reverse=True):
                projects.append(self._build_project_draft(detail, year_label, project_dir))
        return ProjectDiscoveryResult(
            resolved_brand_path=brand_path,
            corrected_main_work_path=str(brand_path) + "/",
            projects=projects,
        )

    def _resolve_brand_path(self, detail: CustomerDetail) -> Path | None:
        candidates: list[Path] = []
        if detail.main_work_path:
            candidates.append(Path(detail.main_work_path))
        candidates.append(self.brand_projects_root / f"品牌--{detail.name}")
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                return candidate
        if not self.brand_projects_root.exists():
            return None
        exact_name = f"品牌--{detail.name}"
        for path in self.brand_projects_root.iterdir():
            if not path.is_dir():
                continue
            if path.name == exact_name:
                return path
        normalized_target = detail.name.replace("品牌--", "").strip().lower()
        for path in self.brand_projects_root.iterdir():
            if not path.is_dir() or not path.name.startswith("品牌--"):
                continue
            brand_name = path.name.replace("品牌--", "", 1).strip().lower()
            if brand_name == normalized_target or normalized_target in brand_name:
                return path
        return None

    def _iter_year_dirs(self, brand_path: Path) -> list[Path]:
        return [
            path
            for path in sorted(brand_path.iterdir(), key=lambda item: item.name, reverse=True)
            if path_is_year_dir(path)
        ]

    def _build_project_draft(self, detail: CustomerDetail, year_label: str, project_dir: Path) -> ProjectDraft:
        project_name = project_dir.name
        project_type = infer_project_type(project_name, project_dir.parent.name)
        stage = "待确认" if year_label == "待确认年份" else "已归档"
        files = sorted(
            [path.name for path in project_dir.iterdir() if path.is_file() and not path.name.startswith(".")],
            reverse=False,
        )
        material_lines = [
            f"- 主业项目路径：`{project_dir}`",
            f"- 文件数量：{len(files)}",
        ]
        material_lines.extend([f"- 文件：{name}" for name in files[:12]])
        if len(files) > 12:
            material_lines.append(f"- 其余文件：还有 {len(files) - 12} 个，已省略")

        notes_markdown = f"- {project_name} 已从桌面品牌项目目录自动同步，后续可继续补充项目重点、风险和推进动作。"
        return ProjectDraft(
            brand_customer_name=detail.name,
            project_name=project_name,
            stage=stage,
            year=year_label,
            project_type=project_type,
            current_focus="已同步桌面项目资料，待补项目当前重点",
            next_action="补充项目当前重点、下一步和风险判断",
            risk="待补充",
            customer_page_link=f"[[客户/客户--{detail.name}]]",
            main_work_path=str(project_dir),
            path_status="主业路径有效",
            party_a_source="客户默认甲方信息",
            default_party_a_info=detail.party_a_info,
            party_a_info=PartyAInfo(),
            override_party_a=False,
            materials_markdown="\n".join(material_lines),
            notes_markdown=notes_markdown,
        )


def path_is_year_dir(path: Path) -> bool:
    return path.is_dir() and (YEAR_DIR_PATTERN.fullmatch(path.name) is not None or path.name == "待确认年份")


def infer_project_type(project_name: str, year_label: str) -> str:
    lowered = f"{year_label} {project_name}".lower()
    if "授权" in lowered:
        return "授权资料"
    if "品牌资料" in lowered:
        return "品牌资料"
    if "小红书" in lowered:
        return "小红书项目"
    if "视频" in lowered:
        return "视频项目"
    if "图" in lowered:
        return "图文项目"
    if "合同" in lowered or "确认单" in lowered:
        return "合同项目"
    return "其他项目"
