"""
TCPing工具

测试TCP端口连通性和延迟。
"""

import logging
import os
from typing import Any, Dict

import httpx

from core.system_config import get_api_url
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

XXAPI_BASE_URL = os.environ.get("XXAPI_BASE_URL", get_api_url("xxapi") or "https://v2.xxapi.cn")


class TCPingTool(BaseTool):
    """TCPing工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "tcping",
            "description": """TCP端口延迟测试工具。

当用户需要测试服务器端口连通性和延迟时使用此工具。
可以测试TCP端口是否开放以及响应延迟。

示例:
- 测试: tcping example.com 80
- 检查: 测试 baidu.com 的443端口""",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "要测试的IP地址或域名",
                    },
                    "port": {
                        "type": "integer",
                        "description": "要测试的端口号",
                    },
                },
                "required": ["address", "port"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        address = args.get("address", "").strip()
        port = args.get("port")

        if not address:
            return "请提供要测试的地址"
        if not port:
            return "请提供端口号"
        if not isinstance(port, int):
            try:
                port = int(port)
            except ValueError:
                return "端口必须是整数"
        if port < 1 or port > 65535:
            return "端口必须在1-65535之间"

        try:
            url = f"{XXAPI_BASE_URL}/api/tcping"
            params = {"address": address, "port": port}

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 200:
                    return f"TCPing失败: {data.get('msg', '未知错误')}"

                result_data = data.get("data", {})
                ping_result = result_data.get("ping")
                result_address = result_data.get("address", address)
                result_port = result_data.get("port", port)

                output_lines = [
                    "【TCPing测试结果】",
                    f"地址: {result_address}",
                    f"端口: {result_port}",
                ]
                if ping_result:
                    output_lines.append(f"延迟: {ping_result}")
                else:
                    output_lines.append("延迟: 无法获取")

                return "\n".join(output_lines)

        except httpx.TimeoutException:
            logger.error("TCPing请求超时")
            return "测试超时，请稍后重试"
        except httpx.HTTPStatusError as e:
            logger.error(f"TCPing HTTP错误: {e}")
            return f"测试失败：HTTP {e.response.status_code}"
        except Exception as e:
            logger.exception(f"TCPing失败: {e}")
            return f"测试失败：{str(e)}"


def get_tcping_tool():
    return TCPingTool()
