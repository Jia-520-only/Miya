"""
通用文件下载工具

弥娅通用资源下载工具：
- 下载任意 URL 资源（图片、视频、程序、文档、压缩包等）
- 自动按类型分类存放（image / video / program / document / archive / audio / other）
- 支持用户指定任意目录（绝对路径或相对路径）
- 从 text_config.json 读取默认行为（目录、是否分类、大小上限）
"""

import asyncio
import contextlib
import html as html_lib
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse

import aiohttp

from webnet.ToolNet.base import BaseTool, ToolContext
from webnet.ToolNet.file_categories import classify as _classify

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _default_ua() -> str:
    """返回下载请求使用的默认 UA。"""
    return _DEFAULT_USER_AGENT


def _get_config():
    try:
        from config.config_utils import get_qq_config, get_text

        return {
            "delete_after_send": get_text("download_manager", "delete_after_send", default=True),
            "default_dir": get_text("download_manager", "default_download_dir", default="data/downloads"),
            "auto_categorize": get_text("download_manager", "auto_categorize", default=True),
            "max_size_mb": get_text("download_manager", "max_file_size_mb", default=0),
            "timeout": get_qq_config("download_manager", "timeout_seconds", default=600),
            "max_retries": get_qq_config("download_manager", "max_retries", default=2),
        }
    except Exception:
        return {
            "delete_after_send": True,
            "default_dir": "data/downloads",
            "auto_categorize": True,
            "max_size_mb": 0,
            "timeout": 600,
            "max_retries": 2,
        }


def _safe_filename(name: str) -> str:
    """去除路径分隔符，防止路径穿越（../ 等）"""
    name = name.replace("\\", "/")
    name = Path(name).name
    name = name.strip()
    if not name or name in (".", ".."):
        return "downloaded"
    return name


def _as_bool(value: Any, default: bool = True) -> bool:
    """将配置/模型可能传入的字符串布尔值正确归一化。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"false", "0", "no", "off", "否"}:
            return False
        if lowered in {"true", "1", "yes", "on", "是"}:
            return True
    return default if value is None else bool(value)


def _as_number(value: Any, default: float, minimum: float = 0) -> float:
    try:
        return max(float(value), minimum)
    except (TypeError, ValueError):
        return default


def _validate_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return "❌ 仅支持 http/https 文件 URL"
    return None


def _normalize_url(raw: Any) -> str:
    """Accept URLs copied from escaped search-page JSON."""
    value = html_lib.unescape(str(raw or "")).strip()
    for _ in range(2):
        value = value.replace("\\\\/", "/").replace("\\/", "/")
        value = re.sub(
            r"\\\\u([0-9a-fA-F]{4})|\\u([0-9a-fA-F]{4})",
            lambda m: chr(int(m.group(1) or m.group(2), 16)),
            value,
        )
    return value.strip().rstrip("\\`);'\" ,")


def _extract_filename(url: str, content_type: str = "") -> str:
    path = unquote(urlparse(url).path)
    name = Path(path).name
    if name and "." in name:
        name = name.split("?")[0]
        return name

    ct_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/vnd.android.package-archive": ".apk",
        "audio/mpeg": ".mp3",
        "audio/wav": ".wav",
    }
    ext = ct_map.get(content_type, ".bin")
    return f"downloaded{ext}"


def _filename_from_content_disposition(value: str) -> str:
    """Extract a server-provided filename, including RFC 5987 encoding."""
    if not value:
        return ""
    match = re.search(r"filename\*\s*=\s*[^']*'[^']*'([^;]+)", value, re.I)
    if match:
        return unquote(match.group(1).strip().strip('"'))
    match = re.search(r"filename\s*=\s*(\"[^\"]+\"|[^;]+)", value, re.I)
    return match.group(1).strip().strip('"') if match else ""


def _resolve_dir(user_dir: Optional[str], base_dir: Path, categorize: bool, filename: str) -> Path:
    if user_dir:
        p = Path(user_dir)
        if not p.is_absolute():
            p = base_dir / p
    else:
        p = base_dir

    if categorize:
        category = _classify(filename)
        p = p / category

    p.mkdir(parents=True, exist_ok=True)
    return p


class DownloadFileTool(BaseTool):
    """通用文件下载工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "download_file",
            "description": (
                "下载任意 URL 资源到本地。支持图片、视频、程序、文档、压缩包等所有文件类型。"
                "自动按类型分类存放（image/video/program/document/archive/audio/other）。"
                "下载后返回本地路径，可配合 send_platform_file 发送给用户。"
                "当用户说「下载这个」「存到桌面」「把这个图存起来」「下这个安装包」时必须使用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "文件直链 URL"},
                    "save_dir": {
                        "type": "string",
                        "description": "保存目录，可以是绝对路径（如 D:\\Desktop）或相对路径（如 downloads/my_stuff），不指定则使用默认 data/downloads/",
                    },
                    "filename": {"type": "string", "description": "自定义文件名（含扩展名），不指定则从 URL 自动提取"},
                    "categorize": {
                        "type": "boolean",
                        "description": "是否按类型自动分到子目录（image/video/program 等），默认 true",
                        "default": True,
                    },
                },
                "required": ["url"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        url = _normalize_url(args.get("url"))
        save_dir = str(args.get("save_dir") or "")
        filename = str(args.get("filename") or "")
        categorize = _as_bool(args.get("categorize", True), True)

        if not url:
            return "❌ 请提供文件 URL"
        invalid_url = _validate_url(url)
        if invalid_url:
            return invalid_url

        if filename:
            filename = _safe_filename(filename)

        cfg = _get_config()
        max_size_mb = _as_number(cfg["max_size_mb"], 0)
        max_size = max_size_mb * 1024 * 1024 if max_size_mb > 0 else float("inf")
        timeout = _as_number(cfg["timeout"], 600, minimum=1)
        max_retries = max(1, int(_as_number(cfg["max_retries"], 2)))

        miya_root = Path(__file__).resolve().parent.parent.parent.parent.parent

        # _resolve_dir 内部会自行拼接 user_dir，save_dir 非空时只需项目根作为基准
        default_base = miya_root if save_dir else miya_root / cfg["default_dir"]

        last_err = "未知错误"
        for attempt in range(1, max_retries + 1):
            try:
                # 需要特定 Referer 的站点（pixiv 图床防盗链）
                headers = {"User-Agent": _default_ua()}
                if "i.pximg.net" in url or "pximg.net" in url:
                    headers["Referer"] = "https://www.pixiv.net/"
                elif "files.yande.re" in url:
                    headers["Referer"] = "https://yande.re/"
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url, timeout=aiohttp.ClientTimeout(total=timeout), headers=headers
                    ) as resp:
                        if resp.status < 200 or resp.status >= 300:
                            last_err = f"HTTP {resp.status}"
                            if resp.status in {401, 403, 404}:
                                return f"❌ 下载失败 (HTTP {resp.status})"
                            raise aiohttp.ClientResponseError(
                                resp.request_info, resp.history, status=resp.status, message="download failed"
                            )

                        content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()

                        content_length = _as_number(resp.headers.get("Content-Length"), 0)
                        if content_length and content_length > max_size:
                            return f"❌ 文件超过大小限制 ({max_size_mb:g} MB)"

                        if not filename:
                            filename = _safe_filename(
                                _filename_from_content_disposition(resp.headers.get("Content-Disposition", ""))
                                or _extract_filename(url, content_type)
                            )

                        dest_dir = _resolve_dir(save_dir, default_base, categorize, filename)
                        dest_path = dest_dir / filename

                        # 避免覆盖：同名文件加序号
                        if dest_path.exists():
                            stem, ext = os.path.splitext(filename)
                            counter = 1
                            while dest_path.exists():
                                dest_path = dest_dir / f"{stem}_{counter}{ext}"
                                counter += 1

                        logger.info(f"[下载] {url} -> {dest_path}")

                        downloaded = 0
                        chunk_size = 64 * 1024
                        temp_path = dest_path.with_name(f".{dest_path.name}.part")
                        with open(temp_path, "wb") as f:
                            async for chunk in resp.content.iter_chunked(chunk_size):
                                downloaded += len(chunk)
                                if downloaded > max_size:
                                    f.close()
                                    with contextlib.suppress(OSError):
                                        os.unlink(temp_path)
                                    return f"❌ 文件超过大小限制 ({max_size_mb:g} MB)"
                                f.write(chunk)
                        os.replace(temp_path, dest_path)

                size_mb = dest_path.stat().st_size / (1024 * 1024)
                category = _classify(filename)

                return (
                    f"✅ 已下载到本地\n"
                    f"📁 路径: {dest_path}\n"
                    f"📦 大小: {size_mb:.1f} MB\n"
                    f"🏷️ 类型: {category}\n"
                    f"💡 需要发送时: 使用 send_platform_file source=local file_path={dest_path}"
                )

            except asyncio.TimeoutError:
                last_err = "下载超时"
                logger.error(f"[下载] 超时 (第{attempt}次): {url}")
            except aiohttp.ClientError as e:
                last_err = f"网络错误: {e}"
                logger.error(f"[下载] 网络错误 (第{attempt}次): {e}")
            except Exception as e:
                last_err = str(e)
                logger.error(f"[下载] 异常 (第{attempt}次): {e}", exc_info=True)

            # 无论是超时、网络错误还是其他异常，都清理本次尝试留下的临时文件。
            with contextlib.suppress(OSError):
                if "temp_path" in locals() and temp_path.exists():
                    temp_path.unlink()

            if attempt < max_retries:
                await asyncio.sleep(1 * attempt)

        if last_err == "下载超时":
            return f"❌ 下载超时（{timeout} 秒），请重试"
        return f"❌ 下载失败: {last_err}"
