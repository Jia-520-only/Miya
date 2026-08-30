"""
entertainment_agent - 娱乐助手
整合AI绘图、星座运势、文昌帝君等功能
"""

import logging
import re
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger("entertainment_agent")


class EntertainmentAgent(BaseTool):
    """娱乐助手Agent"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "entertainment_agent",
            "description": "娱乐助手，提供AI绘画、星座运势、文昌帝君求签、MC皮肤预览等娱乐功能。当用户请求画图、运势、抽签等时自动调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "用户的娱乐需求，如'画一只猫'、'白羊座今日运势'、'求签'",
                    }
                },
                "required": ["prompt"],
            },
        }

    async def execute(self, context: ToolContext, **kwargs) -> str:
        args = kwargs.get("args", {}) if kwargs else {}
        prompt = args.get("prompt", "")

        if not prompt:
            return "请提供娱乐需求"

        return await self._handle_entertainment(prompt, context)

    async def _handle_entertainment(self, prompt: str, context: ToolContext) -> str:
        """处理娱乐请求"""
        prompt_lower = prompt.lower()

        # AI绘图
        if any(kw in prompt_lower for kw in ["画", "绘图", "生成图片", "ai画"]):
            from webnet.ToolNet.tools.entertainment.ai_draw import AiDrawTool

            tool = AiDrawTool()
            return await tool.execute(context, args={"prompt": prompt})

        # 星座运势
        if any(kw in prompt_lower for kw in ["运势", "星座", "占卜"]):
            from webnet.ToolNet.tools.entertainment.horoscope import HoroscopeTool

            constellation = self._extract_constellation(prompt)
            if constellation:
                tool = HoroscopeTool()
                return await tool.execute(context, args={"constellation": constellation})
            return "请指定要查询的星座，如'白羊座今日运势'"

        # 文昌帝君求签
        if any(kw in prompt_lower for kw in ["求签", "抽签", "文昌", "考试运"]):
            from webnet.ToolNet.tools.entertainment.wenchang_dijun import (
                WenchangDijunTool,
            )

            tool = WenchangDijunTool()
            return await tool.execute(context, args={"action": "draw"})

        # MC皮肤
        if any(kw in prompt_lower for kw in ["mc皮肤", "minecraft", "我的世界"]):
            from webnet.ToolNet.tools.entertainment.minecraft_skin import (
                MinecraftSkinTool,
            )

            username = self._extract_mc_username(prompt)
            tool = MinecraftSkinTool()
            return await tool.execute(context, args={"username": username})

        # 拍一拍
        if any(kw in prompt_lower for kw in ["拍一拍", "戳一下"]):
            from webnet.ToolNet.tools.entertainment.send_poke import SendPoke

            tool = SendPoke()
            return await tool.execute(context, args={})

        # 无法识别
        return "我理解你的娱乐需求，但无法处理。请尝试：'画一只猫'、'白羊座运势'、'求签'等"

    def _extract_constellation(self, text: str) -> str:
        """提取星座"""
        constellations = [
            "白羊座",
            "金牛座",
            "双子座",
            "巨蟹座",
            "狮子座",
            "处女座",
            "天秤座",
            "天蝎座",
            "射手座",
            "摩羯座",
            "水瓶座",
            "双鱼座",
        ]
        for c in constellations:
            if c in text:
                return c
        return ""

    def _extract_mc_username(self, text: str) -> str:
        """提取MC用户名"""
        patterns = [
            r"(?:mc|minecraft|我的世界)[:\s]+(.+)",
            r"(.+?)的皮肤",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""


def get_entertainment_agent():
    return EntertainmentAgent()
