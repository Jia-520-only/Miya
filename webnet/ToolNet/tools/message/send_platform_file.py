"""
跨平台文件发送工具

弥娅统一文件发送接口。AI 可调用此工具将文件/图片发送到
当前会话的任意支持平台（QQ、Discord、Telegram 等）。

优先级策略：
  1. 优先从 data/ 目录查找已有文件（downloads/uploads/emoji/stickers 等）
  2. 找不到本地文件时，如果用户提供了 URL，再下载发送
  3. 除非用户明确要求从网络下载，否则不主动下载
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_DATA_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "data"

_DATA_SEARCH_DIRS = [
    "downloads",
    "uploads",
    "emoji",
    "stickers",
    "tts_audio",
    "temp",
    "singing",
    "singing_input",
    "singing_bili_dl",
    "artwork",
    "resources",
    "blog_cache",
    "music_workstation",
]


def _resolve_target(context: ToolContext, target_type: str = "private") -> str:
    """按会话类型解析目标，避免群聊误用发送者 ID。"""
    platform_user_id = getattr(context, "platform_user_id", None)
    if target_type == "private":
        return str(platform_user_id or context.user_id or context.group_id or "")
    return str(context.group_id or platform_user_id or context.user_id or "")


def _resolve_platform_adapter(context: ToolContext):
    adapter = getattr(context, "platform_adapter", None)
    if adapter:
        return adapter
    try:
        from core.platform_context import get_current_platform_adapter

        return get_current_platform_adapter()
    except ImportError:
        return None


def _platform_supports_file(platform) -> bool:
    """判断平台是否真正支持文件发送（显式能力声明优先，duck-typing 回退）"""
    if hasattr(platform, "supports_file_send"):
        try:
            return bool(platform.supports_file_send)
        except Exception:
            pass
    return hasattr(platform, "send_file")


def _platform_file_send_lock(platform) -> asyncio.Lock:
    """Return the per-adapter lock shared by all file-send tool calls."""
    lock = getattr(platform, "_miya_file_send_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        # Platform adapters are regular mutable instances. Keeping the lock on
        # the adapter makes concurrent tool calls for the same account share it.
        setattr(platform, "_miya_file_send_lock", lock)
    return lock


def _find_in_data(name_or_pattern: str) -> List[str]:
    """在 data/ 目录树中递归查找匹配的文件，按 mtime 倒序。"""
    results: List[str] = []

    query_lower = name_or_pattern.lower().strip()

    for subdir in _DATA_SEARCH_DIRS:
        search_path = _DATA_ROOT / subdir
        if not search_path.exists():
            continue
        try:
            for entry in search_path.rglob("*"):
                if not entry.is_file():
                    continue
                entry_lower = entry.name.lower()
                if query_lower in entry_lower or entry_lower == query_lower:
                    results.append(str(entry))
                    if len(results) >= 20:
                        break
        except PermissionError:
            continue

    results.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return results[:20]


def _valid_data_directory(directory: str) -> bool:
    """确保 list_data_files 的目录参数不会跳出 data/。"""
    if not directory:
        return True
    try:
        candidate = (_DATA_ROOT / directory).resolve()
        candidate.relative_to(_DATA_ROOT.resolve())
        return True
    except (OSError, ValueError):
        return False


def _resolve_local_path(file_path: str, auto_search: bool = True) -> Optional[str]:
    """解析文件路径：先精确匹配（支持任意路径），找不到再模糊搜索 data/"""

    if os.path.isfile(file_path):
        return os.path.abspath(file_path)

    resolved = os.path.join(str(_DATA_ROOT), file_path)
    if os.path.isfile(resolved):
        return os.path.abspath(resolved)

    resolved = os.path.abspath(file_path)
    if os.path.isfile(resolved):
        return resolved

    if auto_search:
        found = _find_in_data(os.path.basename(file_path) or file_path)
        if found:
            logger.info(f"在 data/ 中找到匹配文件: {found[0]}")
            return found[0]

    return None


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))


class SendPlatformFileTool(BaseTool):
    """跨平台文件/图片统一发送工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "send_platform_file",
            "description": (
                "弥娅统一的文件/图片发送工具，跨平台可用（QQ/微信/飞书/桌面端等）。支持：\n"
                "1) 电脑上任意路径的文件或图片（如 D:\\work\\report.pdf、D:\\pic\\photo.jpg）\n"
                "2) data/ 目录中的文件（downloads/uploads/emoji 等，可模糊搜索文件名）\n"
                "3) 远程 URL（自动下载后发送）\n"
                "当用户说「发文件」「发图片」「发张图」「发到QQ」「把这个发给我」时必须使用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件或图片路径（电脑上任意路径）、文件名（自动搜索 data/）、或远程 URL",
                    },
                    "file_name": {"type": "string", "description": "发送时显示的文件名（可选）"},
                    "caption": {"type": "string", "description": "附带文字说明（可选）"},
                    "source": {
                        "type": "string",
                        "description": "auto=自动判断; local=仅本地; url=强制下载",
                        "enum": ["auto", "local", "url"],
                        "default": "auto",
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标会话类型",
                        "enum": ["group", "private", "channel"],
                        "default": "group",
                    },
                },
                "required": ["file_path"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            file_path = str(args.get("file_path") or "").strip()
            file_name = str(args.get("file_name") or "").strip()
            caption = str(args.get("caption") or "")
            source = str(args.get("source") or "auto").strip().lower()
            target_type = str(args.get("target_type") or context.message_type or "private").strip().lower()
            if target_type not in {"private", "group", "channel"}:
                return f"❌ 未知的目标类型: {target_type}"

            if not file_path:
                return "❌ 请提供文件路径、文件名或 URL"

            platform = _resolve_platform_adapter(context)
            if not platform:
                return "❌ 当前平台不支持文件发送"
            if not _platform_supports_file(platform):
                return "❌ 当前平台不支持文件发送"

            target_id = _resolve_target(context, target_type)
            if not target_id:
                return "❌ 无法确定发送目标"

            # ── auto 模式：先本地搜索，再判断是否 URL ──
            if source == "auto":
                if _is_url(file_path):
                    source = "url"
                else:
                    resolved = _resolve_local_path(file_path)
                    if resolved:
                        file_path = resolved
                        source = "local"
                    else:
                        return (
                            f"❌ 未找到文件 '{file_path}'。\n"
                            f"请检查路径是否正确，或提供完整的远程 URL 让弥娅下载后发送。"
                        )

            # Serialize media sends per adapter. Several platforms rate-limit
            # upload/send requests even when each individual request succeeds.
            async with _platform_file_send_lock(platform):
                # ── URL 下载 ──
                if source == "url":
                    if hasattr(platform, "send_file_from_url"):
                        success = await platform.send_file_from_url(
                            target=target_id,
                            url=file_path,
                            file_name=file_name,
                            caption=caption,
                            message_type=target_type,
                        )
                    elif hasattr(platform, "download_attachment"):
                        local_path = await platform.download_attachment(file_path, file_name)
                        if not local_path:
                            return "❌ 文件下载失败"
                        success = await platform.send_file(
                            target=target_id,
                            file_path=local_path,
                            file_name=file_name,
                            caption=caption,
                            message_type=target_type,
                        )
                    else:
                        return "❌ 当前平台不支持 URL 文件下载"

                # ── 本地发送 ──
                elif source == "local":
                    if not os.path.isfile(file_path):
                        resolved = _resolve_local_path(file_path)
                        if resolved:
                            file_path = resolved
                        else:
                            return f"❌ 文件不存在: {file_path}"

                    fname = file_name or os.path.basename(file_path)
                    success = await platform.send_file(
                        target=target_id,
                        file_path=file_path,
                        file_name=fname,
                        caption=caption,
                        message_type=target_type,
                    )
                else:
                    return f"❌ 未知的 source 参数: {source}"

            if success:
                name = file_name or os.path.basename(file_path)
                url = getattr(platform, "last_file_url", "") if hasattr(platform, "last_file_url") else ""
                if url:
                    return f"✅ 文件 '{name}' 已就绪，下载链接: {url}"
                return f"✅ 文件 '{name}' 已发送"
            else:
                return "❌ 文件发送失败"

        except Exception as e:
            logger.error(f"平台文件发送失败: {e}", exc_info=True)
            return f"❌ 文件发送失败: {str(e)}"


class ListDataFilesTool(BaseTool):
    """列出 data/ 目录中的可用文件"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "list_data_files",
            "description": "列出 data/ 目录中已有的文件。发送文件前可先用此工具查看有哪些可用文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "搜索关键词（文件名模糊匹配）"},
                    "directory": {"type": "string", "description": "限定子目录（如 downloads/emoji/uploads 等）"},
                    "limit": {"type": "integer", "description": "返回条数上限", "default": 20},
                },
                "required": [],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            search = str(args.get("search") or "").strip()
            directory = str(args.get("directory") or "").strip().rstrip("/\\")
            try:
                limit = max(1, min(int(args.get("limit", 20)), 100))
            except (TypeError, ValueError):
                limit = 20
            if not _valid_data_directory(directory):
                return "❌ directory 必须位于 data/ 目录内"

            dirs = [directory] if directory else _DATA_SEARCH_DIRS

            results: List[str] = []
            for subdir in dirs:
                search_path = _DATA_ROOT / subdir
                if not search_path.exists():
                    continue
                try:
                    for entry in sorted(
                        (p for p in search_path.rglob("*") if p.is_file()),
                        key=lambda e: e.stat().st_mtime,
                        reverse=True,
                    ):
                        if not entry.is_file():
                            continue
                        if search and search.lower() not in entry.name.lower():
                            continue
                        size = entry.stat().st_size
                        if size < 1024:
                            sizestr = f"{size}B"
                        elif size < 1024 * 1024:
                            sizestr = f"{size / 1024:.1f}KB"
                        else:
                            sizestr = f"{size / (1024 * 1024):.1f}MB"
                        results.append(f"  data/{subdir}/{entry.name}  ({sizestr})")
                        if len(results) >= limit:
                            break
                except PermissionError:
                    continue
                if len(results) >= limit:
                    break

            if not results:
                if search:
                    return f"📁 data/ 中未找到匹配 '{search}' 的文件"
                return "📁 data/ 目录为空"

            header = f"📁 data/ 中的文件"
            if search:
                header += f"（搜索: '{search}'）"
            return header + "\n" + "\n".join(results[:limit])

        except Exception as e:
            logger.error(f"列出文件失败: {e}", exc_info=True)
            return f"❌ 列出文件失败: {str(e)}"
