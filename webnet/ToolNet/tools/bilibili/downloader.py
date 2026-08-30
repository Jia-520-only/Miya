"""
B站视频下载模块
使用B站API获取视频信息和下载链接
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BILIBILI_API_BASE = "https://api.bilibili.com"

QUALITY_MAP = {
    127: "8K",
    126: "杜比视界",
    125: "HDR",
    120: "4K",
    116: "1080P60",
    112: "1080P+",
    80: "1080P",
    64: "720P",
    32: "480P",
    16: "360P",
}


@dataclass
class VideoInfo:
    """视频信息"""

    bvid: str
    title: str
    duration: int
    cover_url: str
    up_name: str
    desc: str
    cid: int
    avid: int


async def get_video_info(bvid: str, cookie: str = "") -> Optional[VideoInfo]:
    """获取视频信息"""
    headers = {"User-Agent": "Mozilla/5.0"}
    if cookie:
        headers["Cookie"] = cookie

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BILIBILI_API_BASE}/x/web-interface/view",
                params={"bvid": bvid},
                headers=headers,
            )
            data = resp.json()

            if data.get("code") != 0:
                logger.warning(f"[B站] 获取视频信息失败: {data.get('message')}")
                return None

            info = data.get("data", {})
            return VideoInfo(
                bvid=bvid,
                title=info.get("title", ""),
                duration=info.get("duration", 0),
                cover_url=info.get("pic", ""),
                up_name=info.get("owner", {}).get("name", ""),
                desc=info.get("desc", ""),
                cid=info.get("cid", 0),
                avid=info.get("aid", 0),
            )
    except Exception as e:
        logger.error(f"[B站] 获取视频信息异常: {e}")
        return None


async def get_download_url(bvid: str, cid: int, quality: int = 80, cookie: str = "") -> Optional[dict]:
    """获取视频下载链接"""
    headers = {"User-Agent": "Mozilla/5.0"}
    if cookie:
        headers["Cookie"] = cookie

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{BILIBILI_API_BASE}/x/player/playurl",
                params={
                    "avid": await _get_avid(bvid),
                    "cid": cid,
                    "qn": quality,
                    "fnval": 4048,
                },
                headers=headers,
            )
            data = resp.json()

            if data.get("code") != 0:
                return None

            durl = data.get("data", {}).get("durl", [])
            if durl:
                return {
                    "url": durl[0].get("url", ""),
                    "size": durl[0].get("size", 0),
                    "length": durl[0].get("length", 0),
                }
    except Exception as e:
        logger.error(f"[B站] 获取下载链接异常: {e}")

    return None


async def _get_avid(bvid: str) -> int:
    """获取AV号"""
    if bvid.startswith("AV") or bvid.startswith("av"):
        return int(bvid[2:])

    info = await get_video_info(bvid)
    return info.avid if info else 0


def build_info_card(info: VideoInfo) -> str:
    """构造信息卡片"""
    parts = []
    if info.cover_url:
        parts.append(f"[CQ:image,file={info.cover_url}]")
    parts.append(f"【{info.title}】")
    parts.append(f"UP主: {info.up_name}")
    if info.desc:
        desc = info.desc[:200] + "..." if len(info.desc) > 200 else info.desc
        parts.append(f"简介: {desc}")
    parts.append(f"https://www.bilibili.com/video/{info.bvid}")
    return "\n".join(parts)


async def extract_video_info(video_id: str, cookie: str = "") -> Optional[VideoInfo]:
    """提取视频信息（支持BV/AV/URL）"""
    from webnet.ToolNet.tools.bilibili.parser import normalize_to_bvid

    bvid = await normalize_to_bvid(video_id)
    if not bvid:
        return None

    return await get_video_info(bvid, cookie)
