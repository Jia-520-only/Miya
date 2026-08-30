"""
网络测速工具

测试网络下载和上传速度。
"""

import logging
import os
from typing import Any, Dict

import httpx

from core.system_config import get_api_url
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

XXAPI_BASE_URL = os.environ.get("XXAPI_BASE_URL", get_api_url("xxapi") or "https://v2.xxapi.cn")


class SpeedTestTool(BaseTool):
    """网络测速工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "speed_test",
            "description": """网络测速工具。

当用户需要测试网络带宽时使用此工具。
可以测试网络下载和上传速度。

示例:
- 测速: 测试网速
- 带宽: 测一下网速""",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        try:
            url = f"{XXAPI_BASE_URL}/api/speed"

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 200:
                    return f"测速失败: {data.get('msg', '未知错误')}"

                speed_data = data.get("data", {})
                download = speed_data.get("download", "N/A")
                upload = speed_data.get("upload", "N/A")
                ping = speed_data.get("ping", "N/A")

                result = "【网络测速结果】\n\n"
                result += f"下载速度: {download}\n"
                result += f"上传速度: {upload}\n"
                result += f"延迟: {ping}\n"

                return result

        except httpx.TimeoutException:
            logger.error("测速请求超时")
            return "测速超时，请稍后重试"
        except httpx.HTTPStatusError as e:
            logger.error(f"测速HTTP错误: {e}")
            return f"测速失败：HTTP {e.response.status_code}"
        except Exception as e:
            logger.exception(f"测速失败: {e}")
            return f"测速失败：{str(e)}"


def get_speed_test_tool():
    return SpeedTestTool()
