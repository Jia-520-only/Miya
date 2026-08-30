"""
抖音热搜工具 - info_agent专用
"""

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


async def execute(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """获取抖音热搜榜单"""
    limit = args.get("limit", 10)

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            resp = await client.get(
                "https://www.douyin.com/aweme/v1/web/hot/search/list/",
                params={"device_platform": "webapp", "aid": "6383"},
            )

            if resp.status_code != 200:
                return f"获取抖音热搜失败: HTTP {resp.status_code}"

            data = resp.json()
            word_list = data.get("data", {}).get("word_list", [])

            if not word_list:
                return "暂无抖音热搜数据"

            result = f"【抖音热搜 TOP {min(limit, len(word_list))}】\n\n"

            for idx, item in enumerate(word_list[:limit], 1):
                word = item.get("word", "")
                hot = item.get("hot_value", 0)
                if word:
                    result += f"{idx}. {word}\n"
                    if hot:
                        result += f"   热度: {hot}\n"

            return result

    except Exception as e:
        logger.error(f"获取抖音热搜失败: {e}")
        return f"获取抖音热搜失败: {str(e)[:50]}"
