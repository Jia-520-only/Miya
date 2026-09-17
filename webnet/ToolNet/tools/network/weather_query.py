"""
天气查询工具
"""

import asyncio
import logging
from typing import Any, Dict

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

class WeatherQueryTool(BaseTool):
    """天气查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "weather_query",
            "description": "查询任意地点的真实天气与未来预报，包括解析地点、温度、湿度、风力、数据源和观测时间。当用户问天气、气温或是否下雨时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "要查询的地点名称，如'北京'、'杭州市西湖区'、'东京'或'Paris'",
                    }
                },
                "required": ["city"],
            },
        }

    async def execute(self, args: Dict, context: ToolContext) -> str:
        args = args or {}
        city = args.get("city", "")

        if not city:
            return "请提供要查询的城市名称"

        return await self._query_weather(city)

    async def _query_weather(self, city: str) -> str:
        """查询天气"""
        city = str(city or "").strip()
        if not city:
            return "请提供要查询的城市名称"
        try:
            from core.weather_service import format_weather_report, query_weather
            data = await asyncio.to_thread(query_weather, city, include_forecast=True, forecast_days=3)
            return format_weather_report(data)
        except Exception as e:
            logger.error(f"天气查询失败: {e}")
            return f"查询天气失败: {str(e)[:50]}"


def get_weather_query_tool():
    return WeatherQueryTool()
