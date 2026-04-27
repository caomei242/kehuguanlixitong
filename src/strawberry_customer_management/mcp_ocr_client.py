from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


MAX_OCR_IMAGE_SIDE = 2200
DEFAULT_MCP_COMMAND = "uvx minimax-coding-plan-mcp -y"


class McpOCRClient:
    def __init__(self, command: str, api_key: str, api_host: str):
        self.command = _resolve_mcp_command(command.strip() or DEFAULT_MCP_COMMAND)
        self.api_key = api_key.strip()
        self.api_host = _normalize_api_host(api_host)

    def extract_text(self, image_bytes: bytes) -> str:
        if not self.command:
            raise ValueError("请先配置 MCP 命令。")
        if not self.api_key:
            raise ValueError("请先配置 MiniMax API Key。")

        image_path = self._write_temp_image(image_bytes)
        try:
            return self._call_understand_image(image_path)
        finally:
            image_path.unlink(missing_ok=True)

    def _call_understand_image(self, image_path: Path) -> str:
        args = shlex.split(self.command)
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = self.api_key
        env["MINIMAX_API_HOST"] = self.api_host
        env["PATH"] = _app_safe_path(env.get("PATH", ""))

        try:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ValueError("未找到 MCP 命令。请确认本机已安装 uvx，或重启 App 后再试。") from exc

        try:
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "strawberry-customer-management",
                            "version": "0.1.0",
                        },
                    },
                },
            )
            self._read_response(process, 1)
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
            )
            self._send(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "understand_image",
                        "arguments": {
                            "prompt": (
                                "请识别这张客户聊天截图、需求截图或沟通截图，输出尽量完整、可解析的中文原始文本。"
                                "尽量保留原始字段顺序、微信聊天口吻、电话、时间、联系人、品牌名、店铺数量、需求和预算线索。"
                                "不要总结，不要解释，不要补充截图里没有出现的内容。"
                            ),
                            "image_source": str(image_path),
                        },
                    },
                },
            )
            payload = self._read_response(process, 2)
        finally:
            self._close_process(process)

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise ValueError("MCP OCR 返回格式无效")
        if result.get("isError"):
            error_text = self._extract_text_result(result) or "MCP OCR 调用失败"
            raise ValueError(self._friendly_error(error_text))

        text = self._extract_text_result(result)
        if not text:
            raise ValueError("MCP OCR 未返回可识别文本")
        return text

    @staticmethod
    def _send(process, payload: dict) -> None:
        if process.stdin is None:
            raise ValueError("MCP 进程未提供 stdin")
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()

    @staticmethod
    def _read_response(process, expected_id: int) -> dict:
        if process.stdout is None:
            raise ValueError("MCP 进程未提供 stdout")
        while True:
            line = process.stdout.readline()
            if line == "":
                stderr_output = process.stderr.read() if process.stderr is not None else ""
                raise ValueError(f"MCP 进程提前退出。{stderr_output}".strip())
            payload = json.loads(line)
            if "id" not in payload:
                continue
            if payload["id"] != expected_id:
                continue
            if "error" in payload:
                error = payload["error"]
                if isinstance(error, dict):
                    raise ValueError(str(error.get("message", "MCP 调用失败")))
                raise ValueError("MCP 调用失败")
            return payload

    @staticmethod
    def _extract_text_result(result: dict) -> str:
        content = result.get("content")
        if not isinstance(content, list):
            return ""
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(str(item.get("text", "")).strip())
        return "\n".join(text for text in texts if text).strip()

    @staticmethod
    def _write_temp_image(image_bytes: bytes) -> Path:
        image = QImage()
        if not image.loadFromData(image_bytes):
            raise ValueError("截图内容不是可识别的图片格式")
        max_side = max(image.width(), image.height())
        if max_side > MAX_OCR_IMAGE_SIDE:
            image = image.scaled(
                MAX_OCR_IMAGE_SIDE,
                MAX_OCR_IMAGE_SIDE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as handle:
            temp_path = Path(handle.name)
        if not image.save(str(temp_path), "PNG"):
            temp_path.unlink(missing_ok=True)
            raise ValueError("截图写入临时文件失败")
        return temp_path

    @staticmethod
    def _friendly_error(error_text: str) -> str:
        text = str(error_text or "").strip()
        lowered = text.lower()
        network_markers = (
            "httpsconnectionpool",
            "connectionpool",
            "max retries",
            "connectionerror",
            "connection error",
            "timeout",
            "timed out",
        )
        if any(marker in lowered for marker in network_markers):
            return (
                "截图识别连接 MiniMax 失败，请稍后重试；如果连续失败，请检查网络、"
                f"MiniMax Base URL 和 API Key。原始错误：{text}"
            )
        return text

    @staticmethod
    def _close_process(process) -> None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def _normalize_api_host(api_host: str) -> str:
    raw = api_host.strip()
    if not raw:
        return raw
    parts = urlsplit(raw)
    path = parts.path.rstrip("/")
    if path == "/v1":
        path = ""
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _resolve_mcp_command(command: str) -> str:
    args = shlex.split(command)
    if not args:
        return command
    executable = args[0]
    if "/" in executable or executable != "uvx":
        return command

    resolved_uvx = shutil.which("uvx")
    if not resolved_uvx:
        for candidate in _candidate_uvx_paths():
            if candidate.is_file() and os.access(candidate, os.X_OK):
                resolved_uvx = str(candidate)
                break
    if not resolved_uvx:
        return command

    return " ".join(shlex.quote(part) for part in (resolved_uvx, *args[1:]))


def _candidate_uvx_paths() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / ".local/bin/uvx",
        home / ".cargo/bin/uvx",
        Path("/opt/homebrew/bin/uvx"),
        Path("/usr/local/bin/uvx"),
    )


def _app_safe_path(existing_path: str) -> str:
    common_dirs = (
        str(Path.home() / ".local/bin"),
        str(Path.home() / ".cargo/bin"),
        "/opt/homebrew/bin",
        "/usr/local/bin",
    )
    parts = [part for part in existing_path.split(os.pathsep) if part]
    for common_dir in reversed(common_dirs):
        if common_dir not in parts:
            parts.insert(0, common_dir)
    return os.pathsep.join(parts)
