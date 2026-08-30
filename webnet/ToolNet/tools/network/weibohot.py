"""
热搜查询工具 - 微博热搜
"""

import logging
from typing import Any, Dict

import httpx

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class WeiboHotTool(BaseTool):
    """微博热搜工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "weibohot",
            "description": "获取微博实时热搜榜。当用户问'热搜'、'微博热搜'、'有什么新闻'时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认为10",
                        "default": 10,
                    }
                },
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        limit = args.get("limit", 10)

        return await self._get_hot_list(limit)

    async def _fetch_weibo_official(self, limit: int) -> str | None:
        """尝试微博官方 API（需先获取 Cookie）"""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            }
            async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
                await client.get("https://weibo.com/")

                api_headers = {
                    "Referer": "https://weibo.com/",
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                }
                resp = await client.get("https://weibo.com/ajax/side/hotSearch", headers=api_headers)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok") == 1:
                        realtime = data.get("data", {}).get("realtime", [])
                        if realtime:
                            lines = ["【微博热搜榜】"]
                            for i, item in enumerate(realtime[:limit]):
                                word = item.get("word", "")
                                if word:
                                    lines.append(f"{i + 1}. {word}")
                            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"微博官方 API 失败: {e}")
        return None

    async def _get_hot_list(self, limit: int) -> str:
        """获取热搜列表"""
        result = await self._fetch_weibo_official(limit)
        if result:
            return result

        return "获取微博热搜失败，请稍后再试。可以尝试使用「百度热搜」或「抖音热搜」关键词查询其他平台热门。"


def get_weibohot_tool():
    return WeiboHotTool()
