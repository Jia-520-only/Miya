"""
网页爬取工具 - web_agent专用
"""

import logging
import re
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)


async def execute(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """爬取网页内容"""
    url = args.get("url", "")
    max_length = args.get("max_length", 2000)

    if not url:
        return "请提供要爬取的URL"

    # 确保URL有协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
            resp = await client.get(url)

            if resp.status_code != 200:
                return f"爬取失败: HTTP {resp.status_code}"

            html = resp.text

            # 提取标题
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
            title = title_match.group(1) if title_match else ""

            # 简单提取正文（移除script和style）
            content = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
            content = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.IGNORECASE | re.DOTALL)
            content = re.sub(r"<[^>]+>", " ", content)
            content = re.sub(r"\s+", " ", content)
            content = content.strip()

            # 截取长度
            if len(content) > max_length:
                content = content[:max_length] + "..."

            result = "【网页内容】\n"
            if title:
                result += f"标题: {title}\n"
            result += f"URL: {url}\n\n"
            result += f"内容:\n{content}"

            return result

    except Exception as e:
        logger.error(f"爬取网页失败: {e}")
        return f"爬取失败: {str(e)[:50]}"
