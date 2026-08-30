"""
WHOIS查询工具

查询域名或IP的WHOIS注册信息。
"""

import logging
import os
from typing import Any, Dict

import httpx

from core.system_config import get_api_url
from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

XXAPI_BASE_URL = os.environ.get("XXAPI_BASE_URL", get_api_url("xxapi") or "https://v2.xxapi.cn")


class WhoisQueryTool(BaseTool):
    """WHOIS查询工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "whois_query",
            "description": """WHOIS域名查询工具。

当用户需要查询域名的注册信息时使用此工具。
可以查询域名的注册商、注册时间、到期时间等信息。

示例:
- 查询: whois baidu.com
- 域名信息: 查询 example.com 的信息""",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "要查询的域名",
                    }
                },
                "required": ["domain"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        domain = args.get("domain", "").strip()
        if not domain:
            return "请提供要查询的域名"

        try:
            url = f"{XXAPI_BASE_URL}/api/whois"
            params = {"domain": domain}

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                if data.get("code") != 200:
                    return f"查询Whois失败: {data.get('msg', '未知错误')}"

                whois_data = data.get("data", {})
                result = f"【{domain} Whois信息】\n\n"

                domain_name = whois_data.get("Domain Name", "")
                registrar = whois_data.get("Sponsoring Registrar", "")
                registrar_url = whois_data.get("Registrar URL", "")
                registrant = whois_data.get("Registrant", "")
                registrant_email = whois_data.get("Registrant Contact Email", "")
                registration_time = whois_data.get("Registration Time", "")
                expiration_time = whois_data.get("Expiration Time", "")
                dns_servers = whois_data.get("DNS Serve", [])

                if domain_name:
                    result += f"域名: {domain_name}\n"
                if registrar:
                    result += f"注册商: {registrar}\n"
                if registrar_url:
                    result += f"注册商URL: {registrar_url}\n"
                if registrant:
                    result += f"注册人: {registrant}\n"
                if registrant_email:
                    result += f"注册人邮箱: {registrant_email}\n"
                if registration_time:
                    result += f"注册时间: {registration_time}\n"
                if expiration_time:
                    result += f"到期时间: {expiration_time}\n"
                if dns_servers:
                    result += f"DNS服务器: {', '.join(dns_servers)}\n"

                return result

        except httpx.TimeoutException:
            logger.error("WHOIS查询超时")
            return "查询超时，请稍后重试"
        except httpx.HTTPStatusError as e:
            logger.error(f"WHOIS查询HTTP错误: {e}")
            return f"查询失败：HTTP {e.response.status_code}"
        except Exception as e:
            logger.exception(f"WHOIS查询失败: {e}")
            return f"查询失败：{str(e)}"


def get_whois_query_tool():
    return WhoisQueryTool()
