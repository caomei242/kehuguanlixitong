from __future__ import annotations

import zipfile

from strawberry_customer_management.approval_inbox import ApprovalInboxScanner


def test_approval_inbox_reads_csv_and_moves_imported_file(tmp_path):
    scanner = ApprovalInboxScanner(tmp_path / "钉钉审批导入")
    scanner.ensure_directories()
    csv_path = scanner.pending_dir / "审批导出.csv"
    csv_path.write_text(
        "标题,用印文件名称及用途说明,发起时间,审批状态\n"
        "草莓提交的用印申请,品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同,2026-04-21,审批通过\n",
        encoding="utf-8",
    )

    files = scanner.scan_pending()

    assert len(files) == 1
    assert "标题：草莓提交的用印申请" in files[0].extracted_text
    assert "审批状态：审批通过" in files[0].extracted_text

    moved_path = scanner.move_imported(csv_path)

    assert moved_path.parent.name == "已导入"
    assert moved_path.exists()
    assert not csv_path.exists()


def test_approval_inbox_scans_files_dropped_into_root(tmp_path):
    scanner = ApprovalInboxScanner(tmp_path / "钉钉审批导入")
    scanner.ensure_directories()
    text_path = scanner.root / "草莓提交的用印申请.txt"
    text_path.write_text("草莓提交的用印申请\n审批通过", encoding="utf-8")

    files = scanner.scan_pending()

    assert len(files) == 1
    assert files[0].path == text_path
    assert "审批通过" in files[0].extracted_text


def test_approval_inbox_import_files_copies_supported_exports_to_pending(tmp_path):
    scanner = ApprovalInboxScanner(tmp_path / "钉钉审批导入")
    source_dir = tmp_path / "下载"
    source_dir.mkdir()
    source_csv = source_dir / "审批导出.csv"
    unsupported_image = source_dir / "审批截图.png"
    source_csv.write_text("标题,审批状态\n草莓提交的用印申请,审批通过\n", encoding="utf-8")
    unsupported_image.write_bytes(b"png")

    imported, skipped = scanner.import_files([source_csv, unsupported_image])

    copied_path = scanner.pending_dir / "审批导出.csv"
    assert imported == [copied_path]
    assert skipped == [unsupported_image]
    assert copied_path.exists()
    assert source_csv.exists()

    files = scanner.scan_pending()

    assert len(files) == 1
    assert "审批状态：审批通过" in files[0].extracted_text


def test_approval_inbox_reads_basic_xlsx(tmp_path):
    scanner = ApprovalInboxScanner(tmp_path / "钉钉审批导入")
    scanner.ensure_directories()
    xlsx_path = scanner.pending_dir / "审批导出.xlsx"
    _write_minimal_xlsx(xlsx_path)

    files = scanner.scan_pending()

    assert len(files) == 1
    assert "标题：草莓提交的用印申请" in files[0].extracted_text
    assert "审批状态：审批通过" in files[0].extracted_text


def test_approval_inbox_reads_simple_pdf_literal_text(tmp_path):
    scanner = ApprovalInboxScanner(tmp_path / "钉钉审批导入")
    scanner.ensure_directories()
    pdf_path = scanner.pending_dir / "草莓提交的用印申请.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n(DingTalk approval)(approved)\n%%EOF")

    files = scanner.scan_pending()

    assert len(files) == 1
    assert "草莓提交的用印申请.pdf" in files[0].extracted_text
    assert "DingTalk approval" in files[0].extracted_text
    assert "approved" in files[0].extracted_text


def test_approval_inbox_reads_valid_pdf_text_with_pypdf(tmp_path):
    scanner = ApprovalInboxScanner(tmp_path / "钉钉审批导入")
    scanner.ensure_directories()
    pdf_path = scanner.pending_dir / "草莓提交的用印申请.pdf"
    _write_minimal_text_pdf(pdf_path)

    files = scanner.scan_pending()

    assert len(files) == 1
    assert "草莓提交的用印申请.pdf" in files[0].extracted_text
    assert "DingTalk approval approved 2026-04-21" in files[0].extracted_text


def _write_minimal_xlsx(path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <si><t>标题</t></si>
  <si><t>用印文件名称及用途说明</t></si>
  <si><t>审批状态</t></si>
  <si><t>草莓提交的用印申请</t></si>
  <si><t>品牌：爱慕股份有限公司 26年春夏短视频拍摄制作服务合同</t></si>
  <si><t>审批通过</t></si>
</sst>
""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1">
      <c r="A1" t="s"><v>0</v></c>
      <c r="B1" t="s"><v>1</v></c>
      <c r="C1" t="s"><v>2</v></c>
    </row>
    <row r="2">
      <c r="A2" t="s"><v>3</v></c>
      <c r="B2" t="s"><v>4</v></c>
      <c r="C2" t="s"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>
""",
        )


def _write_minimal_text_pdf(path) -> None:
    path.write_bytes(
        b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length 68 >> stream
BT /F1 12 Tf 40 120 Td (DingTalk approval approved 2026-04-21) Tj ET
endstream endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000241 00000 n 
0000000311 00000 n 
trailer << /Size 6 /Root 1 0 R >>
startxref
429
%%EOF
"""
    )
