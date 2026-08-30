"""
QQ等级查询工具 - info_agent专用
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def execute(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """查询QQ等级"""
    qq = args.get("qq", "")

    if not qq:
        return "请提供要查询的QQ号"

    try:
        import httpx

        # 使用免费API查询QQ等级
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.xingzhige.com/API/QQ_level/", params={"qq": qq})

            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 200:
                    nick = data.get("nick", "")
                    level = data.get("QQlevel", 0)
                    active_days = data.get("active_days", 0)
                    next_level = data.get("next_level", 0)
                    next_gap = data.get("next_gap", 0)

                    result = "【QQ等级查询】\n"
                    result += f"QQ号: {qq}\n"
                    if nick:
                        result += f"昵称: {nick}\n"
                    result += f"等级: {level}级\n"
                    result += f"活跃天数: {active_days}天\n"
                    if next_level > 0:
                        result += f"距离下一级:还需{next_gap}活跃天\n"
                    return result
                else:
                    return f"查询失败: {data.get('msg', '未知错误')}"
            else:
                return f"查询失败: HTTP {resp.status_code}"

    except Exception as e:
        logger.error(f"查询QQ等级失败: {e}")
        return f"查询QQ等级暂时不可用: {str(e)[:50]}"
