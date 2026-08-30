"""
QQ群文件下载工具 handler
"""

import logging
from pathlib import Path
from typing import Any, Dict

from webnet.ToolNet.file_categories import classify as _classify

logger = logging.getLogger("group_file_downloader")

# 默认下载目录
DEFAULT_DOWNLOAD_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "downloads"

# 规范分类 → 群文件保存文件夹名
_FOLDER_BY_CATEGORY = {
    "image": "images",
    "video": "video",
    "audio": "audio",
    "archive": "archives",
    "document": "documents",
    "code": "code",
    "program": "other",
}


def get_category_folder(file_name: str) -> str:
    """根据文件名获取分类文件夹（扩展名分类来自统一数据源）"""
    category = _classify(file_name)
    return _FOLDER_BY_CATEGORY.get(category, "other")


async def execute(args: Dict[str, Any], context: Any) -> str:
    """执行群文件下载操作"""
    try:
        action = args.get("action", "list")
        group_id = args.get("group_id")

        if not group_id:
            return "❌ 请提供群号 group_id"

        # 从 context 获取 onebot_client
        onebot_client = None

        logger.info(f"[group_file_downloader] 收到 context 类型: {type(context)}")

        if context:
            # ToolContext dataclass 对象
            if hasattr(context, "onebot_client"):
                onebot_client = context.onebot_client
                logger.info(f"[group_file_downloader] 从 dataclass 获取 onebot_client: {onebot_client}")
            # 字典类型
            elif isinstance(context, dict):
                onebot_client = context.get("onebot_client")
                logger.info(f"[group_file_downloader] 从 dict 获取 onebot_client: {onebot_client}")
                if not onebot_client:
                    ai_client = context.get("ai_client")
                    if ai_client and hasattr(ai_client, "tool_context"):
                        tool_ctx = getattr(ai_client, "tool_context", None)
                        if tool_ctx and isinstance(tool_ctx, dict):
                            onebot_client = tool_ctx.get("onebot_client")
                            logger.info(f"[group_file_downloader] 从 ai_client.tool_context 获取: {onebot_client}")

        logger.info(f"[group_file_downloader] 最终 onebot_client: {onebot_client}")

        if not onebot_client:
            return "❌ 无法获取 OneBot 客户端，请确保在 QQ 环境中使用"

        if action == "list":
            return await _list_group_files(onebot_client, group_id)
        elif action == "get_url":
            file_id = args.get("file_id")
            if not file_id:
                return "❌ 请提供文件ID"
            return await _get_file_url(onebot_client, group_id, file_id)
        elif action == "download":
            file_name = args.get("file_name")
            save_path = args.get("save_path")

            if not file_name:
                return "❌ 请提供文件名"

            # 如果没有提供保存路径，自动选择分类目录
            if not save_path:
                auto_path = get_auto_save_path(file_name)
                save_path = str(auto_path)
                logger.info(f"[群文件下载] 自动选择保存路径: {save_path}")

            return await _download_file(onebot_client, group_id, file_name, save_path)
        else:
            return f"❌ 不支持的操作: {action}"

    except Exception as e:
        logger.error(f"群文件操作失败: {e}", exc_info=True)
        return f"❌ 操作失败: {str(e)}"


async def _list_group_files(onebot_client, group_id: int) -> str:
    """列出群文件"""
    try:
        result = await onebot_client.get_group_root_files(group_id)
        files = result.get("files", [])
        folders = result.get("folders", [])

        if not files and not folders:
            return f"群 {group_id} 的文件列表为空"

        output = f"📁 群 {group_id} 的文件:\n\n"

        if folders:
            output += "📂 文件夹:\n"
            for folder in folders:
                name = folder.get("folder_name", "未知")
                file_count = folder.get("total_file_count", 0)
                output += f"  ├ {name} ({file_count} 个文件)\n"

        if files:
            output += "\n📄 文件:\n"
            for f in files:
                name = f.get("file_name", "未知")
                size = f.get("file_size", 0)
                file_id = f.get("file_id", "")
                size_str = _format_size(size)
                output += f"  ├ {name} ({size_str})\n  │   file_id: {file_id}\n"

        return output

    except Exception as e:
        return f"❌ 获取文件列表失败: {str(e)}"


async def _get_file_url(onebot_client, group_id: int, file_id: str) -> str:
    """获取文件下载链接"""
    try:
        url = await onebot_client.get_group_file_url(group_id, file_id)
        if url:
            return f"📥 文件下载链接:\n{url}"
        else:
            return "❌ 无法获取下载链接"
    except Exception as e:
        return f"❌ 获取链接失败: {str(e)}"


async def _download_file(onebot_client, group_id: int, file_name: str, save_path: str) -> str:
    """下载群文件"""
    try:
        # 先获取文件列表找到对应的 file_id
        result = await onebot_client.get_group_root_files(group_id)
        files = result.get("files", [])

        target_file = None
        for f in files:
            if f.get("file_name") == file_name:
                target_file = f
                break

        if not target_file:
            # 也搜索子文件夹
            folders = result.get("folders", [])
            for folder in folders:
                folder_id = folder.get("folder_id")
                folder_result = await onebot_client.get_group_files(group_id, folder_id)
                for f in folder_result.get("files", []):
                    if f.get("file_name") == file_name:
                        target_file = f
                        break
                if target_file:
                    break

        if not target_file:
            return f"❌ 未找到文件: {file_name}"

        file_id = target_file.get("file_id")

        # 获取下载链接
        url = await onebot_client.get_group_file_url(group_id, file_id)
        if not url:
            return "❌ 无法获取下载链接"

        # 下载文件
        success = await onebot_client.download_group_file(url, save_path)
        if success:
            size = target_file.get("file_size", 0)
            return f"✅ 文件下载成功!\n📄 {file_name}\n💾 大小: {_format_size(size)}\n📁 保存至: {save_path}"
        else:
            return "❌ 文件下载失败"

    except Exception as e:
        return f"❌ 下载失败: {str(e)}"


def _format_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def get_auto_save_path(file_name: str) -> Path:
    """根据文件类型自动选择保存路径"""
    category = get_category_folder(file_name)
    target_dir = DEFAULT_DOWNLOAD_DIR / category

    # 确保目录存在
    target_dir.mkdir(parents=True, exist_ok=True)

    return target_dir / file_name
