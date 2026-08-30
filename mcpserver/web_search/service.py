#!/usr/bin/env python3
"""
MCP Web Search 服务 - 提供网络搜索能力
"""

import json
from typing import Any, Dict
from urllib.parse import quote_plus

import httpx


class WebSearchService:
    """MCP Web Search 服务"""

    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )

    def __init__(self):
        self.name = "web_search"
        self.description = "网络搜索服务"
        self.version = "1.0.0"

    async def handle_handoff(self, tool_call: Dict[str, Any]) -> str:
        """处理工具调用"""
        tool_name = tool_call.get("tool_name", "")

        if "search" in tool_name.lower():
            return await self._search(tool_call)
        elif "fetch" in tool_name.lower() or "crawl" in tool_name.lower():
            return await self._fetch(tool_call)
        else:
            return json.dumps({"error": f"未知工具: {tool_name}"})

    async def _search(self, tool_call: Dict[str, Any]) -> str:
        """搜索网络"""
        query = tool_call.get("query", "")
        engine = tool_call.get("engine", "duckduckgo")
        count = tool_call.get("count", 10)

        if not query:
            return json.dumps({"error": "缺少 query 参数"})

        try:
            if engine == "google":
                url = f"https://www.google.com/search?q={quote_plus(query)}&num={count}"
            elif engine == "bing":
                url = f"https://www.bing.com/search?q={quote_plus(query)}&count={count}"
            else:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": self._USER_AGENT})
                resp.raise_for_status()
                content = resp.text

            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "engine": engine,
                    "results": content[:2000],
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    async def _fetch(self, tool_call: Dict[str, Any]) -> str:
        """获取网页内容"""
        url = tool_call.get("url", "")

        if not url:
            return json.dumps({"error": "缺少 url 参数"})

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": self._USER_AGENT})
                resp.raise_for_status()
                content = resp.text

            return json.dumps({"success": True, "url": url, "content": content[:5000]})
        except Exception as e:
            return json.dumps({"error": str(e)})


service = WebSearchService()


if __name__ == "__main__":

    async def test():
        result = await service.handle_handoff({"tool_name": "search", "query": "Python async"})
        print(result)

    asyncio.run(test())
