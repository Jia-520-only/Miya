"""
列出知识库
"""
from typing import Dict, Any
import logging
import os
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class KnowledgeList(BaseTool):
    """KnowledgeList"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "knowledge_list",
            "description": "列出项目中的知识库文件和目录。当用户说'查看知识库'、'列出知识库'、'知识库文件'、'知识库目录'等时必须调用此工具。重要：此工具执行实际查询操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "知识库路径，默认为 knowledge/ 目录"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "显示的最大文件数量，默认20",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": []
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        path = args.get("path", "")
        limit = args.get("limit", 20)

        try:
            # 确定知识库目录
            if not path:
                # 尝试常见的知识库目录
                possible_paths = [
                    "knowledge",
                    "docs",
                    "data/knowledge",
                    "storage/knowledge",
                ]
                for p in possible_paths:
                    if os.path.exists(p) and os.path.isdir(p):
                        path = p
                        break
                else:
                    path = "."  # 当前目录

            if not os.path.exists(path):
                return f"❌ 路径不存在: {path}"

            # 收集文件
            files = []
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    # 只包含常见文档格式
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.md', '.txt', '.pdf', '.doc', '.docx', '.json', '.yaml', '.yml']:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, path)
                        size = os.path.getsize(full_path)
                        files.append({
                            'name': filename,
                            'path': rel_path,
                            'size': size,
                            'full_path': full_path
                        })

            # 限制数量
            files = files[:limit]

            if not files:
                return f"📭 路径 '{path}' 中未找到知识库文件"

            # 格式化输出
            result = f"📚 知识库文件列表\n路径: {path}\n共 {len(files)} 个文件\n\n"
            for i, f in enumerate(files, 1):
                size_str = f"{f['size']} B" if f['size'] < 1024 else f"{f['size']/1024:.1f} KB"
                result += f"{i}. **{f['name']}**\n"
                result += f"   路径: {f['path']}\n"
                result += f"   大小: {size_str}\n\n"

            return result

        except Exception as e:
            logger.error(f"列出知识库失败: {e}", exc_info=True)
            return f"❌ 列出知识库失败: {str(e)}"
