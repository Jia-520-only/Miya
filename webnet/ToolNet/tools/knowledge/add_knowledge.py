"""
添加知识工具 — 向本地知识库添加知识条目
"""

import logging
from typing import Any, Dict

from config.config_utils import get_text_message
from webnet.ToolNet.base import BaseTool
from webnet.ToolNet.tools.knowledge.knowledge_store import get_knowledge_store

logger = logging.getLogger(__name__)


class AddKnowledgeTool(BaseTool):
    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "add_knowledge",
            "description": "向弥娅的本地知识库添加新知识条目。当你学到新知识、用户告诉你需要记住的信息、或者需要保存重要的对话内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "知识内容（完整文本，支持Markdown）"},
                    "title": {"type": "string", "description": "知识标题（简洁描述，用于检索）"},
                    "category": {"type": "string", "description": "知识分类（可选，如：技术、生活、游戏、学习等）"},
                    "source": {"type": "string", "description": "知识来源（可选，如：用户对话、网页、文件等）"},
                },
                "required": ["content"],
            },
        }

    async def execute(self, args: Dict[str, Any], context) -> str:
        content = args.get("content", "")
        title = args.get("title", "")
        category = args.get("category", "")
        source = args.get("source", "对话")

        if not content.strip():
            return get_text_message("knowledge_base", "content_required")

        store = get_knowledge_store()
        knowledge_id = await store.add(
            content=content.strip(),
            title=title.strip(),
            category=category.strip(),
            source=source.strip(),
        )

        return get_text_message(
            "knowledge_base",
            "added",
            knowledge_id=knowledge_id,
            title=title or content[:60],
            category=category or "通用",
            length=len(content),
        )
