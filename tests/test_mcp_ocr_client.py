from __future__ import annotations

import io
import json
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from strawberry_customer_management.mcp_ocr_client import McpOCRClient, _resolve_mcp_command


def _sample_png_bytes() -> bytes:
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff4b6e"))
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(byte_array)


class _WritableBuffer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, value: str) -> int:
        self.lines.append(value)
        return len(value)

    def flush(self) -> None:
        return None


class FakeProcess:
    def __init__(self, responses: list[dict]) -> None:
        self.stdin = _WritableBuffer()
        self.stdout = io.StringIO("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in responses))
        self.stderr = io.StringIO("")

    def terminate(self) -> None:
        return None

    def wait(self, timeout=None) -> int:
        return 0

    def kill(self) -> None:
        return None


def test_mcp_ocr_client_calls_understand_image_over_stdio(monkeypatch):
    captured: dict[str, object] = {}
    responses = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "content": [{"type": "text", "text": "客户：爱慕\n需求：补充品牌推广"}],
                "isError": False,
            },
        },
    ]

    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        captured["args"] = args
        captured["env"] = env
        process = FakeProcess(responses)
        captured["process"] = process
        return process

    monkeypatch.setattr("strawberry_customer_management.mcp_ocr_client.shutil.which", lambda name: "/Users/gd/.local/bin/uvx")
    monkeypatch.setattr("strawberry_customer_management.mcp_ocr_client.subprocess.Popen", fake_popen)

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    text = client.extract_text(_sample_png_bytes())

    assert text == "客户：爱慕\n需求：补充品牌推广"
    assert captured["args"] == ["/Users/gd/.local/bin/uvx", "minimax-coding-plan-mcp", "-y"]
    assert captured["env"]["MINIMAX_API_KEY"] == "secret"
    assert captured["env"]["MINIMAX_API_HOST"] == "https://api.minimaxi.com"
    assert "/Users/gd/.local/bin" in captured["env"]["PATH"]
    written_lines = [json.loads(line) for line in captured["process"].stdin.lines]
    assert written_lines[2]["params"]["name"] == "understand_image"
    assert "客户聊天截图" in written_lines[2]["params"]["arguments"]["prompt"]
    assert Path(written_lines[2]["params"]["arguments"]["image_source"]).suffix == ".png"


def test_mcp_ocr_client_surfaces_missing_command_clearly(monkeypatch):
    def fake_popen(args, stdin=None, stdout=None, stderr=None, text=None, env=None):
        raise FileNotFoundError("uvx")

    monkeypatch.setattr("strawberry_customer_management.mcp_ocr_client.subprocess.Popen", fake_popen)

    client = McpOCRClient(
        command="uvx minimax-coding-plan-mcp -y",
        api_key="secret",
        api_host="https://api.minimaxi.com",
    )

    try:
        client.extract_text(_sample_png_bytes())
    except ValueError as exc:
        assert "未找到 MCP 命令" in str(exc)
    else:
        raise AssertionError("expected missing-command error")


def test_mcp_ocr_client_resolves_uvx_from_common_app_paths(monkeypatch, tmp_path):
    fake_uvx = tmp_path / "uvx"
    fake_uvx.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_uvx.chmod(0o755)

    monkeypatch.setattr("strawberry_customer_management.mcp_ocr_client.shutil.which", lambda name: None)
    monkeypatch.setattr(
        "strawberry_customer_management.mcp_ocr_client._candidate_uvx_paths",
        lambda: (fake_uvx,),
    )

    command = _resolve_mcp_command("uvx minimax-coding-plan-mcp -y")

    assert command == f"{fake_uvx} minimax-coding-plan-mcp -y"
