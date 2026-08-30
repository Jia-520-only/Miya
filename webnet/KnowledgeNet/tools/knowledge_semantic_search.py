"""
语义检索知识库
"""
from typing import Dict, Any
import logging
import os
from webnet.tools.base import BaseTool, ToolContext
from core.constants import Encoding


logger = logging.getLogger(__name__)


class KnowledgeSemanticSearch(BaseTool):
    """KnowledgeSemanticSearch"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "knowledge_semantic_search",
            "description": "语义检索知识库（基于关键词匹配，未来可升级为向量检索）。当用户用自然语言查询知识库内容时必须调用此工具。重要：此工具执行实际检索操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索查询（支持自然语言）"
                    },
                    "path": {
                        "type": "string",
                        "description": "检索路径，默认为 knowledge/ 目录"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回的最大结果数，默认5",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["query"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """执行工具"""
        query = args.get("query", "").strip()
        path = args.get("path", "")
        limit = args.get("limit", 5)

        if not query:
            return "❌ 查询不能为空"

        try:
            # 确定检索路径
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

            # 提取查询关键词
            keywords = [kw.strip() for kw in query.split() if len(kw.strip()) > 1]
            if not keywords:
                keywords = [query]

            # 搜索并计算相关性分数
            results = []
            for root, dirs, filenames in os.walk(path):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.md', '.txt', '.json', '.yaml', '.yml', '.py']:
                        try:
                            file_path = os.path.join(root, filename)
                            with open(file_path, 'r', encoding=Encoding.UTF8) as f:
                                content = f.read()

                            # 计算相关性
                            score = 0
                            for keyword in keywords:
                                keyword_lower = keyword.lower()
                                content_lower = content.lower()

                                # 精确匹配
                                if keyword_lower in content_lower:
                                    score += 1

                                # 标题匹配（文件名）
                                if keyword_lower in filename.lower():
                                    score += 2

                                # 多次出现
                                score += content_lower.count(keyword_lower) * 0.1

                            if score > 0:
                                results.append({
                                    'file': filename,
                                    'path': os.path.relpath(file_path, path),
                                    'score': score,
                                    'content': content[:500]
                                })

                        except UnicodeDecodeError:
                            pass
                        except Exception as e:
                            logger.debug(f"读取文件失败 {file_path}: {e}")

            # 按分数排序并限制结果
            results.sort(key=lambda x: x['score'], reverse=True)
            results = results[:limit]

            if not results:
                return f"🔍 未找到与 '{query}' 相关的内容"

            # 格式化输出
            result = f"🔍 语义检索: '{query}'\n路径: {path}\n共 {len(results)} 个相关结果\n\n"
            for i, r in enumerate(results, 1):
                content_preview = r['content'][:150] + "..." if len(r['content']) > 150 else r['content']
                result += f"{i}. **{r['path']}** (相关性: {r['score']:.1f})\n"
                result += f"   {content_preview}\n\n"

            return result

        except Exception as e:
            logger.error(f"语义检索失败: {e}", exc_info=True)
            return f"❌ 检索失败: {str(e)}"
