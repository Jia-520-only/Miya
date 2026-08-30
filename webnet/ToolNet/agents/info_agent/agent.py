"""
info_agent - 信息查询助手
整合天气、热搜、论文搜索等工具
"""

import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger("info_agent")


class InfoAgent(BaseTool):
    """信息查询助手Agent"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "info_agent",
            "description": "信息查询助手，提供天气查询、微博热搜、arXiv论文搜索、网络诊断等多种实用信息查询功能。当用户询问天气、新闻、论文、网络问题等时自动调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "用户的查询需求，如'北京天气'、'今日热搜'、'搜索diffusion论文'",
                    }
                },
                "required": ["prompt"],
            },
        }

    async def execute(self, context: ToolContext, **kwargs) -> str:
        args = kwargs.get("args", {}) if kwargs else {}
        prompt = args.get("prompt", "")

        if not prompt:
            return "请提供查询需求"

        return await self._handle_query(prompt, context)

    async def _handle_query(self, prompt: str, context: ToolContext) -> str:
        """处理查询"""
        prompt_lower = prompt.lower()

        # 天气查询
        if any(kw in prompt_lower for kw in ["天气", "气温", "温度", "下雨", "晴"]):
            from webnet.ToolNet.tools.network.weather_query import WeatherQueryTool

            city = self._extract_city(prompt)
            if city:
                tool = WeatherQueryTool()
                return await tool.execute(context, args={"city": city})

        # 热搜查询（优先微博，失败后回退百度/抖音）
        if any(kw in prompt_lower for kw in ["热搜", "微博", "新闻", "热门"]):
            from webnet.ToolNet.tools.network.weibohot import WeiboHotTool

            tool = WeiboHotTool()
            result = await tool.execute(context, args={"limit": 10})
            if "失败" not in result and "错误" not in result:
                return result

            logger.info("微博热搜获取失败，尝试百度热搜作为回退")
            try:
                from webnet.ToolNet.agents.info_agent.tools.baiduhot.handler import (
                    execute as baiduhot_execute,
                )

                baidu_result = await baiduhot_execute({"limit": 10}, {})
                if "失败" not in baidu_result and "暂无数据" not in baidu_result:
                    return f"[微博热搜暂时不可用，为您展示百度热搜]\n\n{baidu_result}"
            except Exception as e:
                logger.warning(f"百度热搜回退也失败: {e}")

            try:
                from webnet.ToolNet.agents.info_agent.tools.douyinhot.handler import (
                    execute as douyinhot_execute,
                )

                douyin_result = await douyinhot_execute({"limit": 10}, {})
                if "失败" not in douyin_result and "暂无数据" not in douyin_result:
                    return f"[微博/百度热搜暂不可用，为您展示抖音热搜]\n\n{douyin_result}"
            except Exception as e:
                logger.warning(f"抖音热搜回退也失败: {e}")

            return result

        # arXiv论文搜索
        if any(kw in prompt_lower for kw in ["论文", "paper", "arxiv", "学术"]):
            from webnet.ToolNet.tools.network.arxiv_search import ArxivSearchTool

            query = self._extract_query(prompt)
            if query:
                tool = ArxivSearchTool()
                return await tool.execute(context, args={"query": query, "max_results": 5})

        # 网络诊断
        if any(kw in prompt_lower for kw in ["ping", "网速", "延迟", "检测"]):
            from webnet.ToolNet.tools.network.speed_test import SpeedTestTool

            tool = SpeedTestTool()
            return await tool.execute(context, args={})

        # 域名查询
        if any(kw in prompt_lower for kw in ["whois", "域名"]):
            from webnet.ToolNet.tools.network.whois_query import WhoisQueryTool

            domain = self._extract_domain(prompt)
            if domain:
                tool = WhoisQueryTool()
                return await tool.execute(context, args={"domain": domain})

        # 无法识别
        return "我理解你的查询，但需要更具体的说明。比如：'北京天气'、'微博热搜'、'搜索论文python'等"

    def _extract_city(self, text: str) -> str:
        """提取城市名"""
        import re

        patterns = [
            r"(.+?)天气",
            r"(.+?)气温",
            r"查(.+?)天气",
            r"(.+?)的温度",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1).strip()
        return text.strip()

    def _extract_query(self, text: str) -> str:
        """提取搜索关键词"""
        import re

        patterns = [
            r"搜索(.+)论文",
            r"(.+)论文",
            r"关于(.+)的论文",
            r"paper[:\s]+(.+)",
            r"arxiv[:\s]+(.+)",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return text.strip()

    def _extract_domain(self, text: str) -> str:
        """提取域名"""
        import re

        m = re.search(r"(?:whois|域名|domain)[:\s]*([a-zA-Z0-9.-]+)", text, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"(https?://)?([a-zA-Z0-9.-]+)", text)
        if m:
            return m.group(2)
        return ""


def get_info_agent():
    return InfoAgent()
