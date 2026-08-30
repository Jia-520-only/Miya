"""
本地文件搜索工具 handler
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("local_file_finder")


async def execute(args: Dict[str, Any], context: Any) -> str:
    """执行本地文件搜索"""
    try:
        file_name = args.get("file_name", "")
        search_path = args.get("search_path", "")
        max_results = args.get("max_results", 10)

        if not file_name:
            return "❌ 请提供要搜索的文件名"

        # 确定搜索路径
        if not search_path:
            # 默认搜索用户目录
            home = Path.home()
            search_path = str(home)
            logger.info(f"[文件搜索] 使用默认搜索路径: {search_path}")

        if not os.path.exists(search_path):
            return f"❌ 搜索路径不存在: {search_path}"

        # 执行搜索
        results = _search_files(search_path, file_name, max_results)

        if not results:
            return f"🔍 未找到包含 '{file_name}' 的文件"

        # 格式化结果
        output = f"🔍 找到 {len(results)} 个相关文件:\n\n"
        for i, (path, size, mtime) in enumerate(results, 1):
            size_str = _format_size(size)
            mtime_str = mtime.strftime("%Y-%m-%d %H:%M") if mtime else "未知"
            output += f"{i}. 📄 {path.name}\n"
            output += f"   📍 {path.parent}\n"
            output += f"   💾 {size_str} | 📅 {mtime_str}\n\n"

        return output

    except Exception as e:
        logger.error(f"文件搜索失败: {e}", exc_info=True)
        return f"❌ 搜索失败: {str(e)}"


def _search_files(search_path: str, file_name: str, max_results: int) -> list:
    """搜索文件"""

    results = []
    search_name = file_name.lower()

    try:
        for root, dirs, files in os.walk(search_path):
            # 跳过系统目录
            dirs[:] = [
                d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "AppData")
            ]

            for filename in files:
                if search_name in filename.lower():
                    try:
                        filepath = Path(root) / filename
                        stat = filepath.stat()
                        results.append(
                            (
                                filepath,
                                stat.st_size,
                                None,  # 时间戳
                            )
                        )
                    except:
                        pass

                    if len(results) >= max_results:
                        return results

            # 限制遍历深度和数量，避免太慢
            if len(results) >= max_results:
                break

    except PermissionError:
        logger.warning(f"[文件搜索] 无权限访问: {search_path}")
    except Exception as e:
        logger.warning(f"[文件搜索] 搜索异常: {e}")

    return results


def _format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
