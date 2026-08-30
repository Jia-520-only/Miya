"""
Grok搜索工具

基于Grok AI的网络搜索功能，需要配置Grok模型才能使用。
"""

import logging
import os
from typing import Any, Dict

import httpx

from config.config_utils import get_api_key
from core.system_config import get_api_url
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

GROK_API_URL = os.environ.get("GROK_API_URL", get_api_url("grok_api") or "https://api.xai.ai/v1/chat/completions")
GROK_API_KEY = get_api_key("GROK_API_KEY")
GROK_MODEL = os.environ.get("GROK_MODEL", "grok-2-1212")


async def search_grok(query: str) -> str:
    """执行 Grok 搜索（唯一实现，供 ToolNet 工具与 web_agent handler 复用）"""
    if not GROK_API_KEY:
        return "Grok搜索功能未配置（缺少GROK_API_KEY环境变量）"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json",
            }
            data = {
                "model": GROK_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": f"请搜索以下内容并提供详细信息：{query}\n\n请提供搜索结果摘要和相关信息来源。",
                    }
                ],
                "max_tokens": 4096,
            }

            response = await client.post(GROK_API_URL, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            if content:
                return f"【Grok搜索结果】\n\n{content}"
            else:
                return "未获取到搜索结果"

    except httpx.TimeoutException:
        logger.error("Grok搜索超时")
        return "搜索超时，请稍后重试"
    except httpx.HTTPStatusError as e:
        logger.error(f"Grok搜索HTTP错误: {e}")
        return f"搜索失败：HTTP {e.response.status_code}"
    except Exception as e:
        logger.exception(f"Grok搜索失败: {e}")
        return f"搜索失败：{str(e)}"


class GrokSearchTool(BaseTool):
    """Grok AI搜索工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "grok_search",
            "description": """Grok AI 搜索工具。

当用户需要AI驱动的网络搜索结果时使用此工具。
Grok可以理解复杂问题并提供更智能的搜索结果。

示例:
- 搜索: 最近有什么AI新闻
- 查找: Python异步编程的最佳实践""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询内容",
                    }
                },
                "required": ["query"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        query = args.get("query", "").strip()
        if not query:
            return "请提供搜索内容"

        return await search_grok(query)


def get_grok_search_tool():
    return GrokSearchTool()
