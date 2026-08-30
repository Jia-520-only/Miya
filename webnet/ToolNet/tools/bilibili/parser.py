"""
B站标识符解析模块
从消息中提取 B站视频 BV号/AV号/b23.tv短链
"""

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BV_PATTERN = re.compile(r"BV1[1-9A-HJ-NP-Za-km-z]{9}")
AV_PATTERN = re.compile(r"av(\d+)", re.IGNORECASE)
URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.|m\.)?bilibili\.com/video/(BV1[1-9A-HJ-NP-Za-km-z]{9}|av\d+)",
    re.IGNORECASE,
)
SHORT_URL_PATTERN = re.compile(r"(?:https?://)?b23\.tv/([A-Za-z0-9]+)")

_AV2BV_TABLE = "fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF"
_AV2BV_TR = {c: i for i, c in enumerate(_AV2BV_TABLE)}
_AV2BV_S = [11, 10, 3, 8, 4, 6]
_AV2BV_XOR = 177451812
_AV2BV_ADD = 8728348608


def av_to_bv(avid: int) -> str:
    """AV号转BV号"""
    avid = (avid ^ _AV2BV_XOR) + _AV2BV_ADD
    bv = list("BV1  4 1 7  ")
    for i, pos in enumerate(_AV2BV_S):
        bv[pos] = _AV2BV_TABLE[avid // 58**i % 58]
    return "".join(bv)


async def resolve_short_url(short_url: str) -> Optional[str]:
    """解析 b23.tv 短链"""
    if not short_url.startswith("http"):
        short_url = f"https://{short_url}"
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            resp = await client.head(short_url)
            location = resp.headers.get("Location") or resp.headers.get("location")
            if location:
                return str(location)
    except Exception as e:
        logger.warning(f"[B站] 解析短链失败 {short_url}: {e}")
    return None


async def normalize_to_bvid(identifier: str) -> Optional[str]:
    """将各种格式统一转换为BV号"""
    identifier = identifier.strip()

    m = BV_PATTERN.search(identifier)
    if m:
        return m.group(0)

    m = SHORT_URL_PATTERN.search(identifier)
    if m:
        short_code = m.group(1)
        real_url = await resolve_short_url(f"b23.tv/{short_code}")
        if real_url:
            return await normalize_to_bvid(real_url)

    m = AV_PATTERN.search(identifier)
    if m:
        av_number = int(m.group(1))
        return av_to_bv(av_number)

    m = URL_PATTERN.search(identifier)
    if m:
        video_part = m.group(1)
        if video_part.lower().startswith("av"):
            return av_to_bv(int(video_part[2:]))
        return video_part

    return None


async def extract_from_message(message: str) -> Optional[str]:
    """从消息文本中提取B站视频标识并返回BV号"""
    if not message:
        return None

    bvid = await normalize_to_bvid(message)
    if bvid:
        logger.info(f"[B站] 提取到视频标识: {bvid}")
        return bvid

    return None


async def extract_all_from_message(message: str) -> list[str]:
    """从消息中提取所有B站视频BV号"""
    if not message:
        return []

    bvids = []

    for match in BV_PATTERN.finditer(message):
        bvids.append(match.group(0))

    short_urls = SHORT_URL_PATTERN.findall(message)
    for short_code in short_urls:
        real_url = await resolve_short_url(f"b23.tv/{short_code}")
        if real_url:
            bvid = await normalize_to_bvid(real_url)
            if bvid and bvid not in bvids:
                bvids.append(bvid)

    for match in AV_PATTERN.finditer(message):
        try:
            av_number = int(match.group(1))
            bvid = av_to_bv(av_number)
            if bvid not in bvids:
                bvids.append(bvid)
        except:
            pass

    for match in URL_PATTERN.finditer(message):
        video_part = match.group(1)
        bvid = await normalize_to_bvid(video_part)
        if bvid and bvid not in bvids:
            bvids.append(bvid)

    return bvids
