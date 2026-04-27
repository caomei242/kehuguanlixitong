from __future__ import annotations

import csv
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


PENDING_DIR_NAME = "待处理"
IMPORTED_DIR_NAME = "已导入"
NEEDS_REVIEW_DIR_NAME = "需人工确认"
SUPPORTED_APPROVAL_FILE_SUFFIXES = {".csv", ".xlsx", ".txt", ".md", ".pdf"}


@dataclass(frozen=True)
class ApprovalInboxFile:
    path: Path
    extracted_text: str
    file_type: str
    error: str = ""


class ApprovalInboxScanner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pending_dir = root / PENDING_DIR_NAME
        self.imported_dir = root / IMPORTED_DIR_NAME
        self.needs_review_dir = root / NEEDS_REVIEW_DIR_NAME

    def ensure_directories(self) -> None:
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.imported_dir.mkdir(parents=True, exist_ok=True)
        self.needs_review_dir.mkdir(parents=True, exist_ok=True)

    def scan_pending(self) -> list[ApprovalInboxFile]:
        self.ensure_directories()
        files: list[ApprovalInboxFile] = []
        pending_paths = [*self.pending_dir.iterdir(), *self.root.iterdir()]
        for path in sorted(pending_paths, key=lambda item: str(item)):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_APPROVAL_FILE_SUFFIXES:
                continue
            files.append(self._read_file(path))
        return files

    def import_files(self, paths: list[Path]) -> tuple[list[Path], list[Path]]:
        """Copy dropped/exported approval files into the pending inbox."""
        self.ensure_directories()
        imported: list[Path] = []
        skipped: list[Path] = []
        for path in _expand_source_paths(paths):
            if not path.is_file():
                skipped.append(path)
                continue
            if path.suffix.lower() not in SUPPORTED_APPROVAL_FILE_SUFFIXES:
                skipped.append(path)
                continue
            target = self.pending_dir / path.name
            if _same_file(path, target):
                imported.append(path)
                continue
            imported.append(_copy_unique(path, target))
        return imported, skipped

    def move_imported(self, path: Path) -> Path:
        self.ensure_directories()
        return _move_unique(path, self.imported_dir / path.name)

    def move_needs_review(self, path: Path) -> Path:
        self.ensure_directories()
        return _move_unique(path, self.needs_review_dir / path.name)

    def _read_file(self, path: Path) -> ApprovalInboxFile:
        suffix = path.suffix.lower()
        try:
            if suffix == ".csv":
                text = _extract_csv_text(path)
            elif suffix == ".xlsx":
                text = _extract_xlsx_text(path)
            elif suffix in {".txt", ".md"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".pdf":
                text = _extract_pdf_text(path)
            else:
                text = ""
        except Exception as exc:  # noqa: BLE001 - file import should never break the page.
            return ApprovalInboxFile(path=path, extracted_text=path.name, file_type=suffix.lstrip("."), error=str(exc))

        normalized_text = "\n".join(part for part in [path.name, text.strip()] if part).strip()
        return ApprovalInboxFile(path=path, extracted_text=normalized_text, file_type=suffix.lstrip("."))


def _extract_csv_text(path: Path) -> str:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="ignore")
    rows = list(csv.reader(text.splitlines()))
    return _rows_to_text(rows)


def _extract_xlsx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_names = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"))
        rows: list[list[str]] = []
        for sheet_name in sheet_names:
            rows.extend(_read_sheet_rows(archive, sheet_name, shared_strings))
    return _rows_to_text(rows)


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.iter():
        if _local_name(item.tag) != "si":
            continue
        texts = [node.text or "" for node in item.iter() if _local_name(node.tag) == "t"]
        values.append("".join(texts))
    return values


def _read_sheet_rows(archive: zipfile.ZipFile, sheet_name: str, shared_strings: list[str]) -> list[list[str]]:
    root = ElementTree.fromstring(archive.read(sheet_name))
    rows: list[list[str]] = []
    for row in root.iter():
        if _local_name(row.tag) != "row":
            continue
        values: list[str] = []
        for cell in row:
            if _local_name(cell.tag) != "c":
                continue
            cell_type = cell.attrib.get("t", "")
            raw_value = ""
            for child in cell:
                if _local_name(child.tag) == "v":
                    raw_value = child.text or ""
                    break
                if _local_name(child.tag) == "is":
                    raw_value = "".join(node.text or "" for node in child.iter() if _local_name(node.tag) == "t")
                    break
            if cell_type == "s" and raw_value.isdigit():
                index = int(raw_value)
                value = shared_strings[index] if index < len(shared_strings) else raw_value
            else:
                value = raw_value
            values.append(value.strip())
        if any(values):
            rows.append(values)
    return rows


def _extract_pdf_text(path: Path) -> str:
    pypdf_text = _extract_pdf_text_with_pypdf(path)
    if pypdf_text:
        return pypdf_text

    data = path.read_bytes()
    text = data.decode("latin-1", errors="ignore")
    literal_strings = re.findall(r"\(([^()]*)\)", text)
    extracted = "\n".join(_decode_pdf_literal(value) for value in literal_strings)
    readable = re.sub(r"[^\x09\x0a\x0d\x20-\x7e\u4e00-\u9fff]", " ", extracted)
    readable = re.sub(r"\s+", " ", readable).strip()
    return readable


def _extract_pdf_text_with_pypdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        page_texts = [page.extract_text() or "" for page in reader.pages]
    except Exception:  # noqa: BLE001 - keep the legacy PDF fallback available.
        return ""
    return "\n".join(text.strip() for text in page_texts if text.strip()).strip()


def _decode_pdf_literal(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\n")
        .replace(r"\t", "\t")
    )


def _rows_to_text(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = [cell.strip() for cell in rows[0]]
    body_rows = rows[1:] if len(rows) > 1 else []
    if not body_rows:
        return "\n".join(" ".join(cell for cell in row if cell).strip() for row in rows if any(row))

    lines: list[str] = []
    for row in body_rows:
        parts: list[str] = []
        for index, value in enumerate(row):
            cleaned_value = value.strip()
            if not cleaned_value:
                continue
            label = header[index].strip() if index < len(header) else ""
            parts.append(f"{label}：{cleaned_value}" if label else cleaned_value)
        if parts:
            lines.append("；".join(parts))
    return "\n".join(lines)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _move_unique(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    candidate = target
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}-{counter}{target.suffix}")
        counter += 1
    return source.rename(candidate)


def _copy_unique(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    candidate = target
    counter = 1
    while candidate.exists():
        candidate = target.with_name(f"{target.stem}-{counter}{target.suffix}")
        counter += 1
    shutil.copy2(source, candidate)
    return candidate


def _expand_source_paths(paths: list[Path]) -> list[Path]:
    expanded: list[Path] = []
    for path in paths:
        if path.is_dir():
            expanded.extend(sorted(child for child in path.rglob("*") if child.is_file()))
        else:
            expanded.append(path)
    return expanded


def _same_file(source: Path, target: Path) -> bool:
    try:
        return source.resolve() == target.resolve()
    except OSError:
        return False
