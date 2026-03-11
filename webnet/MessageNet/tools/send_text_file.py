"""
发送文本文件工具
"""
from typing import Dict, Any
import logging
import os
import tempfile
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class SendTextFileTool(BaseTool):
    """发送文本文件工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "send_text_file",
            "description": "将文本内容作为文件发送（支持代码、配置文件等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "文件内容"
                    },
                    "filename": {
                        "type": "string",
                        "description": "文件名（如 code.py, config.json）"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "编码格式：utf-8, ascii, gbk",
                        "enum": ["utf-8", "ascii", "gbk"],
                        "default": "utf-8"
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标会话类型",
                        "enum": ["group", "private"],
                        "default": "group"
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标会话ID（群号或用户QQ号）。不指定则使用当前会话"
                    }
                },
                "required": ["content", "filename"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """发送文本文件"""
        content = args.get("content", "")
        filename = args.get("filename", "file.txt")
        encoding = args.get("encoding", "utf-8")
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id")

        if not content:
            return "❌ 文件内容不能为空"

        if not filename:
            return "❌ 文件名不能为空"

        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding=encoding,
                suffix=os.path.splitext(filename)[1],
                delete=False
            ) as f:
                f.write(content)
                temp_path = f.name

            # 解析目标会话
            if target_id is None:
                if target_type == "group":
                    target_id = context.group_id
                else:
                    target_id = context.user_id

            if target_id is None:
                return "❌ 无法确定目标会话ID，请手动指定 target_id"

            # 通过 OneBot 发送文件
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
                    return f"✅ 已发送文件: {filename} ({len(content)} 字符)"
                else:
                    return f"❌ 文件发送失败: {filename}"
            else:
                # OneBot 客户端不可用，显示文件内容
                logger.warning(f"onebot_client 不可用，无法发送文件: {filename}")
                return f"⚠️ OneBot 客户端不可用，无法发送文件\n\n文件内容预览:\n```\n{filename}\n{content[:500]}...\n```"

        except UnicodeEncodeError:
            return f"❌ 编码错误: 不支持 {encoding} 编码，请尝试其他编码"
        except Exception as e:
            logger.error(f"发送文件失败: {e}", exc_info=True)
            return f"❌ 发送文件时出错: {str(e)}"
