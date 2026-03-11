"""
发送URL文件工具
"""
from typing import Dict, Any
import logging
import os
import tempfile
import aiohttp
import asyncio
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SendUrlFileTool(BaseTool):
    """发送URL文件工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "send_url_file",
            "description": "下载URL中的文件并发送（最大100MB）",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "文件URL"
                    },
                    "filename": {
                        "type": "string",
                        "description": "保存的文件名（不指定则从URL提取）"
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标会话类型",
                        "enum": ["group", "private"],
                        "default": "group"
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标会话ID（群号或用户QQ号）"
                    },
                    "max_size": {
                        "type": "integer",
                        "description": "最大文件大小（MB）",
                        "default": 100
                    }
                },
                "required": ["url"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """发送URL文件"""
        url = args.get("url")
        filename = args.get("filename")
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id")
        max_size = args.get("max_size", 100) * 1024 * 1024  # MB to bytes

        if not url:
            return "❌ URL不能为空"

        try:
            # 从URL提取文件名
            if not filename:
                filename = url.split('/')[-1]
                if '?' in filename:
                    filename = filename.split('?')[0]
                if not filename or '.' not in filename:
                    filename = "downloaded_file"

            # 解析目标会话
            if target_id is None:
                if target_type == "group":
                    target_id = context.group_id
                else:
                    target_id = context.user_id

            if target_id is None:
                return "❌ 无法确定目标会话ID，请手动指定 target_id"

            # 下载文件
            async with aiohttp.ClientSession() as session:
                # 先获取文件大小
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return f"❌ 无法访问URL (HTTP {resp.status})"
                    content_length = int(resp.headers.get('Content-Length', 0))
                    if content_length > max_size:
                        size_mb = content_length / 1024 / 1024
                        return f"❌ 文件过大: {size_mb:.2f}MB (最大 {max_size / 1024 / 1024}MB)"

                # 下载文件
                logger.info(f"开始下载文件: {url} -> {filename}")
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                    if resp.status != 200:
                        return f"❌ 下载失败 (HTTP {resp.status})"

                    # 创建临时文件
                    with tempfile.NamedTemporaryFile(
                        mode='wb',
                        suffix=os.path.splitext(filename)[1],
                        delete=False
                    ) as f:
                        downloaded = 0
                        chunk_size = 8192
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            downloaded += len(chunk)
                            if downloaded > max_size:
                                f.close()
                                os.unlink(f.name)
                                return f"❌ 下载超过大小限制"
                            f.write(chunk)
                        temp_path = f.name

            # 发送文件
            if context.onebot_client:
                if target_type == "group":
                    success = await context.onebot_client.upload_group_file(
                        target_id,
                        temp_path,
                        filename
                    )
                else:
                    success = await context.onebot_client.upload_private_file(
                        target_id,
                        temp_path,
                        filename
                    )

                # 删除临时文件
                try:
                    os.unlink(temp_path)
                except:
                    pass

                if success:
                    size_mb = os.path.getsize(temp_path) / 1024 / 1024
                    return f"✅ 已发送文件: {filename} ({size_mb:.2f}MB)"
                else:
                    return f"❌ 文件发送失败: {filename}"
            else:
                logger.warning(f"onebot_client 不可用，无法发送文件")
                return f"⚠️ OneBot 客户端不可用，文件已下载但无法发送\n文件: {filename}"

        except asyncio.TimeoutError:
            return "❌ 下载超时，请重试"
        except aiohttp.ClientError as e:
            logger.error(f"下载文件失败: {e}", exc_info=True)
            return f"❌ 下载文件时出错: {str(e)}"
        except Exception as e:
            logger.error(f"发送URL文件失败: {e}", exc_info=True)
            return f"❌ 处理失败: {str(e)}"
