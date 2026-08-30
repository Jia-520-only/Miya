"""
微博热搜工具 - info_agent专用
"""

import logging
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


async def _fetch_weibo_official(limit: int) -> str | None:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
            await client.get("https://weibo.com/")

            api_headers = {
                "Referer": "https://weibo.com/",
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
            }
            resp = await client.get("https://weibo.com/ajax/side/hotSearch", headers=api_headers)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("ok") != 1:
                return None
            hot_list = data.get("data", {}).get("realtime", [])
            if not hot_list:
                return None
            result = f"【微博热搜 TOP {min(limit, len(hot_list))}】\n\n"
            for idx, item in enumerate(hot_list[:limit], 1):
                title = item.get("word", "")
                hot = item.get("num", 0)
                if title:
                    result += f"{idx}. {title}"
                    if hot:
                        result += f"  ({hot})"
                    result += "\n"
            return result
    except Exception as e:
        logger.warning(f"微博官方 API 失败: {e}")
    return None


async def execute(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """获取微博热搜榜单"""
    limit = args.get("limit", 10)

    if limit < 1 or limit > 50:
        return "热搜数量必须在1-50之间"

    result = await _fetch_weibo_official(limit)
    if result:
        return result

    return "获取微博热搜失败，请稍后再试"
