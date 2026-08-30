"""
QQ等级查询工具

查询QQ号的等级信息。
"""

import logging
import os
from typing import Any, Dict

import httpx

from core.system_config import get_api_url
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

XXAPI_BASE_URL = os.environ.get("XXAPI_BASE_URL", get_api_url("xxapi") or "https://v2.xxapi.cn")


class QQLevelTool(BaseTool):
    """QQ等级查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "qq_level",
            "description": """QQ等级查询工具。

当用户需要查询QQ号等级时使用此工具。
可以查询QQ的等级、天数等信息。

示例:
- 查询: 查询QQ等级 123456789
- 等级: 我的QQ多少级""",
            "parameters": {
                "type": "object",
                "properties": {
                    "qq": {
                        "type": "string",
                        "description": "要查询的QQ号",
                    }
                },
                "required": ["qq"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        qq = args.get("qq", "").strip()
        if not qq:
            return "请提供要查询的QQ号"

        try:
            url = f"{XXAPI_BASE_URL}/api/qqlevel"
            params = {"qq": qq}

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 200:
                    return f"查询失败: {data.get('msg', '未知错误')}"

                level_data = data.get("data", {})
                level = level_data.get("level", "N/A")
                days = level_data.get("days", "N/A")
                rank = level_data.get("rank", "N/A")

                result = f"【QQ {qq} 等级信息】\n\n"
                result += f"等级: {level}\n"
                result += f"等级天数: {days}天\n"
                if rank and rank != "N/A":
                    result += f"排名: {rank}\n"

                return result

        except httpx.TimeoutException:
            logger.error("QQ等级查询超时")
            return "查询超时，请稍后重试"
        except httpx.HTTPStatusError as e:
            logger.error(f"QQ等级查询HTTP错误: {e}")
            return f"查询失败：HTTP {e.response.status_code}"
        except Exception as e:
            logger.exception(f"QQ等级查询失败: {e}")
            return f"查询失败：{str(e)}"


def get_qq_level_tool():
    return QQLevelTool()
