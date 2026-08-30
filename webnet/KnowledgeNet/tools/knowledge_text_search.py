"""
关键词搜索知识库
"""
from typing import Dict, Any
import logging
import os
from webnet.tools.base import BaseTool, ToolContext
from core.constants import Encoding


logger = logging.getLogger(__name__)


class KnowledgeTextSearch(BaseTool):
    """KnowledgeTextSearch"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "knowledge_text_search",
            "description": "在知识库中搜索关键词。当用户说'搜索知识库'、'查找知识'、'在知识库中找'等时必须调用此工具。重要：此工具执行实际搜索操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索路径，默认为 knowledge/ 目录"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大结果数，默认10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "是否区分大小写，默认false",
                        "default": False
                    }
                },
                "required": ["keyword"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        keyword = args.get("keyword", "").strip()
        path = args.get("path", "")
        limit = args.get("limit", 10)
        case_sensitive = args.get("case_sensitive", False)

        if not keyword:
            return "❌ 关键词不能为空"

        try:
            # 确定搜索路径
            if not path:
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
                    path = "."

            if not os.path.exists(path):
                return f"❌ 路径不存在: {path}"

            # 搜索关键词
            results = []
            search_keyword = keyword if case_sensitive else keyword.lower()

            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    # 只搜索文本文件
                    if ext in ['.md', '.txt', '.json', '.yaml', '.yml', '.py', '.js', '.html', '.css']:
                        try:
                            file_path = os.path.join(root, filename)
                            with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                                lines = f.readlines()

                            # 搜索每一行
                            for line_num, line in enumerate(lines, 1):
                                search_line = line if case_sensitive else line.lower()
                                if search_keyword in search_line:
                                    results.append({
                                        'file': filename,
                                        'path': os.path.relpath(file_path, path),
                                        'line': line_num,
                                        'content': line.strip()
                                    })
                        except UnicodeDecodeError:
                            # 跳过非UTF-8文件
                            pass
                        except Exception as e:
                            logger.debug(f"读取文件失败 {file_path}: {e}")

            # 限制结果
            results = results[:limit]

            if not results:
                return f"🔍 未找到包含 '{keyword}' 的内容"

            # 格式化输出
            result = f"🔍 搜索结果: '{keyword}'\n路径: {path}\n共 {len(results)} 处匹配\n\n"
            for i, r in enumerate(results, 1):
                content_preview = r['content'][:100] + "..." if len(r['content']) > 100 else r['content']
                result += f"{i}. **{r['path']}:{r['line']}**\n"
                result += f"   {content_preview}\n\n"

            return result

        except Exception as e:
            logger.error(f"搜索知识库失败: {e}", exc_info=True)
            return f"❌ 搜索失败: {str(e)}"
