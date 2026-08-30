"""
天气查询工具
"""

import logging
import time
from typing import Any, Dict

import httpx

from config.config_utils import get_api_key
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_WEATHER_CACHE: Dict[str, tuple[float, str]] = {}
_WEATHER_CACHE_TTL = 600


def _get_weather_api_key() -> str:
    """从 .env 读取心知天气 API Key"""
    return get_api_key("SENIVERSE_API_KEY") or get_api_key("WEATHER_API_KEY")


class WeatherQueryTool(BaseTool):
    """天气查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "weather_query",
            "description": "查询指定城市的天气情况，包括温度、天气状况、湿度、风力等。当用户问'天气'、'气温'、'下雨'等相关问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "要查询的城市名称，如'北京'、'上海'、'杭州'",
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
        cached = _WEATHER_CACHE.get(city)
        if cached and time.monotonic() - cached[0] < _WEATHER_CACHE_TTL:
            return cached[1] + "\n（来自最近 10 分钟缓存）"
        api_key = _get_weather_api_key()
        if not api_key:
            return (
                f"【{city}】天气查询暂未配置 API Key。\n请在 config/.env 中设置 SENIVERSE_API_KEY（心知天气）后重试。"
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.seniverse.com/v3/weather/now.json",
                    params={
                        "key": api_key,
                        "location": city,
                        "language": "zh-Hans",
                        "unit": "c",
                    },
                )

                if resp.status_code != 200:
                    return f"【{city}】天气查询服务返回 HTTP {resp.status_code}"
                data = resp.json()
                results = data.get("results") or []
                if not results:
                    return f"【{city}】没有找到天气结果，请检查城市名称"
                result = results[0]
                now = result.get("now") or {}
                location = result.get("location") or {}
                direction = str(now.get("wind_direction") or "").strip()
                scale = str(now.get("wind_scale") or "").strip()
                wind = " ".join(x for x in (direction, f"{scale}级" if scale else "") if x) or "未知"
                rendered = (
                    f"【{location.get('name', city)}天气】\n"
                    f"温度: {now.get('temperature', '未知')}°C\n"
                    f"天气: {now.get('text', '未知')}\n"
                    f"风力: {wind}\n"
                    f"数据源: 心知天气"
                )
                _WEATHER_CACHE[city] = (time.monotonic(), rendered)
                return rendered

        except Exception as e:
            logger.error(f"天气查询失败: {e}")
            return f"查询天气失败: {str(e)[:50]}"


def get_weather_query_tool():
    return WeatherQueryTool()
