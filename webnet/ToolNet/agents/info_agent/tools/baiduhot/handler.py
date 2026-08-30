"""
百度热搜工具 - info_agent专用
"""

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


async def execute(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """获取百度热搜榜单"""
    limit = args.get("limit", 10)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://top.baidu.com/board", headers={"User-Agent": "Mozilla/5.0"})

            if resp.status_code != 200:
                return f"获取百度热搜失败: HTTP {resp.status_code}"

            import json
            import re

            # 尝试从页面提取数据
            html = resp.text
            pattern = r'"hotList":(\[.*?\])'
            match = re.search(pattern, html)

            if match:
                hot_list = json.loads(match.group(1))
                result = f"【百度热搜 TOP {min(limit, len(hot_list))}】\n\n"

                for idx, item in enumerate(hot_list[:limit], 1):
                    word = item.get("word", "")
                    hot = item.get("hotScore", 0)
                    if word:
                        result += f"{idx}. {word}\n"
                        if hot:
                            result += f"   热度: {hot}\n"

                return result

            return "暂无百度热搜数据"

    except Exception as e:
        logger.error(f"获取百度热搜失败: {e}")
        return f"获取百度热搜失败: {str(e)[:50]}"
