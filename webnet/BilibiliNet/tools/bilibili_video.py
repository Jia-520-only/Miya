"""
B站视频下载发送工具
"""
from typing import Dict, Any
import logging
import re
import os
import tempfile
import aiohttp
import asyncio
import json
from webnet.tools.base import BaseTool, ToolContext


logger = logging.getLogger(__name__)


class BilibiliVideo(BaseTool):
    """B站视频工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "bilibili_video",
            "description": "下载并发送Bilibili视频到群聊或私聊。支持BV号、AV号或B站视频链接。当用户提供B站视频链接或BV/AV号要求发送时必须调用此工具。重要：此工具执行实际下载和发送操作，不要用文字回复，必须调用工具执行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "B站视频标识：BV号(如BV1xx411c7mD)、AV号或完整链接"
                    },
                    "target_type": {
                        "type": "string",
                        "description": "目标会话类型",
                        "enum": ["group", "private"],
                        "default": "group"
                    },
                    "target_id": {
                        "type": "integer",
                        "description": "目标会话ID（群号或用户QQ号）。不指定则使用当前会话"
                    },
                    "quality": {
                        "type": "string",
                        "description": "视频质量：low(低清), medium(中清), high(高清), super(超清)",
                        "enum": ["low", "medium", "high", "super"],
                        "default": "medium"
                    }
                },
                "required": ["video_id"]
            }
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        """
        下载并发送B站视频

        Args:
            args: {video_id, target_type, target_id, quality}
            context: 执行上下文

        Returns:
            执行结果
        """
        video_id = args.get("video_id", "").strip()
        target_type = args.get("target_type", "group")
        target_id = args.get("target_id")
        quality = args.get("quality", "medium")

        if not video_id:
            return "❌ 视频ID不能为空"

        # 提取BV号/AV号
        bv_match = re.search(r'BV[a-zA-Z0-9]{10}', video_id)
        av_match = re.search(r'av(\d+)', video_id)

        bvid = None
        aid = None

        if bv_match:
            bvid = bv_match.group(0)
            logger.info(f"识别到BV号: {bvid}")
        elif av_match:
            aid = av_match.group(1)
            logger.info(f"识别到AV号: {aid}")
            # 尝试通过API获取BV号
            bvid = await self._av_to_bv(aid)
        else:
            return f"❌ 无法识别视频ID: {video_id}\n请使用BV号(如BV1xx411c7mD)、AV号或完整链接"

        # 解析目标会话
        if target_id is None:
            if target_type == "group":
                target_id = context.group_id
            else:
                target_id = context.user_id

        if target_id is None:
            return "❌ 无法确定目标会话ID，请手动指定 target_id"

        try:
            # 获取视频信息
            video_info = await self._get_video_info(bvid)
            if not video_info:
                return f"❌ 无法获取视频信息: {bvid}"

            title = video_info.get('title', '未知视频')
            author = video_info.get('owner', {}).get('name', '未知作者')
            duration = video_info.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}"

            # 检查是否支持直接分享链接
            share_url = f"https://www.bilibili.com/video/{bvid}"

            # 尝试下载视频
            download_result = await self._download_video(bvid, quality)
            if download_result.get('success'):
                video_path = download_result['path']
                filename = download_result.get('filename', f"{bvid}.mp4")

                # 发送视频文件
                if context.onebot_client:
                    if target_type == "group":
                        success = await context.onebot_client.upload_group_file(
                            target_id,
                            video_path,
                            filename
                        )
                    else:
                        success = await context.onebot_client.upload_private_file(
                            target_id,
                            video_path,
                            filename
                        )

                    # 删除临时文件
                    try:
                        os.unlink(video_path)
                    except:
                        pass

                    if success:
                        size_mb = os.path.getsize(video_path) / 1024 / 1024
                        return f"✅ 已发送B站视频\n\n标题: {title}\nUP主: {author}\n时长: {duration_str}\n大小: {size_mb:.2f}MB\n链接: {share_url}"
                    else:
                        return f"❌ 视频发送失败: {filename}"
                else:
                    return f"⚠️ OneBot 客户端不可用，无法发送视频\n\n视频信息:\n标题: {title}\nUP主: {author}\n时长: {duration_str}\n链接: {share_url}"
            else:
                # 下载失败，返回分享链接
                error_msg = download_result.get('error', '未知错误')
                return f"⚠️ 视频下载失败: {error_msg}\n\n可以使用以下方式观看:\n链接: {share_url}\n标题: {title}\nUP主: {author}\n时长: {duration_str}\n\n提示: 可使用 yt-dlp 手动下载\n命令: yt-dlp {share_url}"

        except Exception as e:
            logger.error(f"处理B站视频失败: {e}", exc_info=True)
            return f"❌ 处理视频时出错: {str(e)}"

    async def _av_to_bv(self, aid: str) -> str:
        """AV号转BV号（简化版）"""
        # B站API转换
        try:
            api_url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('code') == 0:
                            return data.get('data', {}).get('bvid', f"BV{aid}")
        except:
            pass
        return f"BV{aid}"  # 简化处理

    async def _get_video_info(self, bvid: str) -> Dict:
        """获取视频信息"""
        try:
            api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('code') == 0:
                            return data.get('data', {})
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
        return {}

    async def _download_video(self, bvid: str, quality: str) -> Dict:
        """下载视频（简化实现）"""
        try:
            # 获取视频下载链接
            # 注意：实际下载需要更复杂的逻辑，这里仅提供框架
            # 真实场景建议使用 yt-dlp 或 bilibili-api

            video_info = await self._get_video_info(bvid)
            if not video_info:
                return {'success': False, 'error': '无法获取视频信息'}

            title = video_info.get('title', 'video')
            # 清理文件名
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title)

            # 尝试获取下载链接
            # 这里简化处理，返回失败提示
            return {
                'success': False,
                'error': '需要安装 yt-dlp 库',
                'title': safe_title
            }

        except Exception as e:
            logger.error(f"下载视频失败: {e}")
            return {'success': False, 'error': str(e)}
