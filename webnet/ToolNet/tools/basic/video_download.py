"""
视频下载工具

弥娅专用视频下载工具，封装 yt-dlp + ffmpeg：
- 支持 B站、N站、Iwara、YouTube 等主流视频平台
- UTF-8 强制编码，彻底避免 Windows GBK subprocess 乱码/崩溃
- 自动合并音视频（优先 static-ffmpeg，回退 system ffmpeg）
- 下载到 data/downloads/video/，可直接被 send_platform_file 找到发送
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from webnet.ToolNet.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)

_VIDEO_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "downloads" / "video"

_QUALITY_FORMATS = {
    "best": "bv*+ba/best",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]",
    "720p": "bv*[height<=720]+ba/b[height<=720]",
    "480p": "bv*[height<=480]+ba/b[height<=480]",
    "360p": "bv*[height<=360]+ba/b[height<=360]",
}


def _run_sync(cmd: List[str], timeout: int = 180, extra_env: dict = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )


def _find_ffmpeg() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path

    try:
        import static_ffmpeg

        paths = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        return paths[0] if isinstance(paths, (tuple, list)) else paths
    except Exception:
        pass

    return None


async def _ensure_ffmpeg() -> Optional[str]:
    path = _find_ffmpeg()
    if path:
        return path

    logger.info("ffmpeg 未安装，使用 static-ffmpeg...")
    try:
        loop = asyncio.get_event_loop()
        r = await loop.run_in_executor(
            None, lambda: _run_sync([sys.executable, "-m", "pip", "install", "static-ffmpeg", "-q"], timeout=120)
        )
        if r.returncode == 0:
            import static_ffmpeg

            paths = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
            return paths[0] if isinstance(paths, (tuple, list)) else paths.get("ffmpeg")
    except Exception as e:
        logger.warning(f"static-ffmpeg 安装失败: {e}")
    return None


def _ensure_ytdlp() -> Optional[str]:
    path = shutil.which("yt-dlp")
    if path:
        return path
    logger.info("yt-dlp 未安装，自动安装中...")
    r = _run_sync([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"], timeout=120)
    if r.returncode != 0:
        return None
    return shutil.which("yt-dlp")


def _find_newest_file(directory: Path, expected_filename: str = "") -> Optional[Path]:
    files = [f for f in directory.iterdir() if f.is_file()]
    if not files:
        return None
    # 排除 yt-dlp 中间分片文件（如 .f100113.mp4, .f30280.m4a）
    final_files = [f for f in files if not re.search(r"\.f\d+\.(mp4|m4a|webm)$", f.name.lower())]
    source = final_files if final_files else files
    # 优先匹配预期文件名
    if expected_filename:
        name_lower = expected_filename.lower()
        matches = [f for f in source if name_lower in f.name.lower()]
        if matches:
            source = matches
    source.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return source[0]


class VideoDownloadTool(BaseTool):
    """视频下载工具"""

    @property
    def config(self) -> Dict[str, Any]:
        return {
            "name": "video_download",
            "description": (
                "下载任意平台视频到本地。支持 B站、N站、Iwara、YouTube 等所有主流视频平台。"
                "自动合并音视频为 mp4。下载完成后返回本地文件路径，"
                "可配合 send_platform_file 发送给用户。"
                "当用户要求「下载视频」「找视频发给我」「下载镜流PV」等任务时必须使用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "视频页面 URL 或视频直链。支持 B站 BV/AV号、完整链接、短链接",
                    },
                    "quality": {
                        "type": "string",
                        "description": "画质",
                        "enum": ["best", "1080p", "720p", "480p", "360p"],
                        "default": "best",
                    },
                    "filename": {"type": "string", "description": "输出文件名（不含扩展名），不指定则使用视频标题"},
                },
                "required": ["url"],
            },
        }

    async def execute(self, args: Dict[str, Any], context: ToolContext) -> str:
        url = args.get("url", "").strip()
        quality = args.get("quality", "best")
        filename = args.get("filename", "")

        if not url:
            return "❌ 请提供视频 URL"

        _VIDEO_DIR.mkdir(parents=True, exist_ok=True)

        ytdlp = _ensure_ytdlp()
        if not ytdlp:
            return "❌ yt-dlp 安装失败，无法下载视频"

        ffmpeg = await _ensure_ffmpeg()
        if not ffmpeg:
            return "❌ ffmpeg 不可用，无法合并音视频。请安装后重试"

        fmt = _QUALITY_FORMATS.get(quality, _QUALITY_FORMATS["best"])

        # 独立临时目录，避免并发下载互相干扰，同时便于清理失败分片
        tmp_dir = _VIDEO_DIR / f".tmp_{uuid.uuid4().hex[:8]}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        output_template = str(tmp_dir / f"{filename}.%(ext)s") if filename else str(tmp_dir / "%(title)s.%(ext)s")

        cmd = [
            ytdlp,
            "--no-playlist",
            "--no-warnings",
            "--no-check-certificate",
            "-f",
            fmt,
            "--merge-output-format",
            "mp4",
            "--ffmpeg-location",
            ffmpeg,
            "-o",
            output_template,
            url,
        ]

        logger.info(f"[视频下载] {url} 画质={quality}")

        loop = asyncio.get_event_loop()

        try:
            r = await loop.run_in_executor(None, lambda: _run_sync(cmd, timeout=300))

            video = _find_newest_file(tmp_dir, filename)

            if video and video.exists():
                # 移动到正式目录（避免同名覆盖）
                final_name = f"{filename}.{video.suffix.lstrip('.')}" if filename else video.name
                final_path = _VIDEO_DIR / final_name
                if final_path.exists():
                    stem, ext = os.path.splitext(final_name)
                    counter = 1
                    while final_path.exists():
                        final_path = _VIDEO_DIR / f"{stem}_{counter}{ext}"
                        counter += 1
                shutil.move(str(video), str(final_path))

                size_mb = final_path.stat().st_size / (1024 * 1024)
                return (
                    f"✅ 视频下载完成\n"
                    f"📁 本地路径: {final_path}\n"
                    f"📦 文件大小: {size_mb:.1f} MB\n"
                    f"💡 下一步: 使用 send_platform_file 发送此文件，参数 source=local, file_path={final_path}"
                )

            return (
                f"❌ 下载完成但未找到输出文件\n"
                f"--- stdout (末尾) ---\n{r.stdout[-3000:]}\n"
                f"--- stderr (末尾) ---\n{r.stderr[-3000:]}"
            )

        except subprocess.TimeoutExpired:
            return "❌ 下载超时（5 分钟），请尝试降低画质后重试"
        except Exception as e:
            logger.error(f"[视频下载] 异常: {e}", exc_info=True)
            return f"❌ 下载失败: {str(e)}"
        finally:
            # 清理临时目录（含未合并的分片文件）
            shutil.rmtree(tmp_dir, ignore_errors=True)
