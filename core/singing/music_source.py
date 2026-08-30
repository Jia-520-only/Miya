"""
弥娅内置唱歌引擎 — 音乐源抽象层

支持:
- LocalFileSource: 本地文件目录
- NeteaseMusicSource: 网易云音乐 API (高音质)
- BilibiliMusicSource: B站 API + yutto CLI 下载
- AutoMusicSource: 自动多源回退 (local → netease → bilibili)
"""

import asyncio
import logging
import os
import shutil
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SongResult:
    song_id: str
    song_name: str
    artist: str = ""
    source: str = ""


class MusicSource(ABC):
    """音乐源抽象基类"""

    def __init__(self, name: str):
        self.name = name
        self.is_initialized = False

    @abstractmethod
    def initialize(self, config: dict) -> bool:
        pass

    @abstractmethod
    async def search(self, query: str) -> Optional[SongResult]:
        pass

    @abstractmethod
    async def download(self, song: SongResult, output_dir: str) -> Optional[str]:
        pass

    def cleanup(self):
        self.is_initialized = False


class LocalFileSource(MusicSource):
    """本地文件音乐源 — 多目录递归扫描"""

    AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".mkv", ".mp4"}

    def __init__(self):
        super().__init__("local")
        self.input_dirs: List[str] = []

    def initialize(self, config: dict) -> bool:
        dirs = config.get("input_dirs") or [config.get("input_dir", "data/singing_input")]
        if isinstance(dirs, str):
            dirs = [dirs]
        self.input_dirs = [d for d in dirs if d]
        for d in self.input_dirs:
            os.makedirs(d, exist_ok=True)
        self.is_initialized = True
        return True

    def _iter_audio_files(self):
        """递归列出所有目录中的音频文件 → (文件路径, stem)"""
        for d in self.input_dirs:
            if not os.path.isdir(d):
                continue
            for root, _dirs, files in os.walk(d):
                for f in files:
                    name, ext = os.path.splitext(f)
                    if ext.lower() in self.AUDIO_EXTS:
                        yield os.path.join(root, f), name

    @staticmethod
    def _fuzzy_key(s: str) -> str:
        """宽松匹配键：去掉所有空格/标点/符号，只留中英文数字"""
        import re

        return re.sub(r"[\W_]+", "", s, flags=re.UNICODE)

    async def search(self, query: str) -> Optional[SongResult]:
        query = (query or "").strip()
        if not query:
            return None
        q_fuzzy = self._fuzzy_key(query)
        for path, name in self._iter_audio_files():
            if query in name:
                return SongResult(song_id=f"local:{name}", song_name=name, source="local")
            if len(q_fuzzy) >= 2 and q_fuzzy in self._fuzzy_key(name):
                return SongResult(song_id=f"local:{name}", song_name=name, source="local")
        return None

    async def download(self, song: SongResult, output_dir: str) -> Optional[str]:
        for path, name in self._iter_audio_files():
            if name != song.song_name:
                continue
            os.makedirs(output_dir, exist_ok=True)
            dst = os.path.join(output_dir, os.path.basename(path))
            if os.path.abspath(path) == os.path.abspath(dst):
                return dst  # 文件已在目标目录
            shutil.copy2(path, dst)
            return dst
        return None


class NeteaseMusicSource(MusicSource):
    """网易云音乐源 — 通过 NeteaseCloudMusicApi 搜索/下载，支持 exhigh 高音质"""

    def __init__(self):
        super().__init__("netease")
        self.api_url: str = "http://localhost:3000"
        self.timeout: int = 30
        self.quality: str = "exhigh"

    def initialize(self, config: dict) -> bool:
        self.api_url = config.get("netease_api", "http://localhost:3000").rstrip("/")
        self.timeout = config.get("timeout", 30)
        self.quality = config.get("quality", "exhigh")
        self.is_initialized = True
        return True

    async def _get(self, path: str):
        import requests

        url = f"{self.api_url}{path}"
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: requests.get(url, timeout=(5, self.timeout))
        )
        resp.raise_for_status()
        return resp.json()

    async def search(self, query: str) -> Optional[SongResult]:
        from urllib.parse import quote

        try:
            data = await self._get(f"/search?keywords={quote(query)}&limit=5")
            songs = data.get("result", {}).get("songs", [])
            if not songs:
                return None
            s = songs[0]
            return SongResult(
                song_id=str(s["id"]),
                song_name=s["name"],
                artist=s.get("ar", [{}])[0].get("name", ""),
                source="netease",
            )
        except Exception:
            return None

    async def download(self, song: SongResult, output_dir: str) -> Optional[str]:
        import re

        import requests

        try:
            data = await self._get(f"/song/url/v1?id={song.song_id}&level={self.quality}")
            dl_url = data.get("data", [{}])[0].get("url", "")
            if not dl_url:
                return None

            os.makedirs(output_dir, exist_ok=True)
            ext = os.path.splitext(dl_url.split("?")[0])[1] or ".mp3"
            safe = re.sub(r'[\[\]<>:"/\\|?*.]', "", song.song_name).strip(". ")
            path = os.path.join(output_dir, f"{safe}{ext}")

            resp = await asyncio.get_event_loop().run_in_executor(
                None, lambda: requests.get(dl_url, timeout=(10, 120), stream=True)
            )
            resp.raise_for_status()
            with open(path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            logger.info(f"Netease: {song.song_name} ({os.path.getsize(path)}B, q={self.quality})")
            return path
        except Exception as e:
            logger.warning(f"Netease download failed: {e}")
            return None


class BilibiliMusicSource(MusicSource):
    """B站音乐源 — 搜索用 API，下载用 yutto CLI"""

    def __init__(self):
        super().__init__("bilibili")
        self.timeout: int = 30
        self.python_exe: str = "python"
        self.download_dir: str = ""

    def initialize(self, config: dict) -> bool:
        self.timeout = config.get("timeout", 30)
        self.python_exe = config.get("bilibili_python", sys.executable)
        self.download_dir = config.get("download_dir", "data/singing_bili_dl")
        os.makedirs(self.download_dir, exist_ok=True)
        self.is_initialized = True
        return True

    async def search(self, query: str) -> Optional[SongResult]:
        from urllib.parse import quote

        import requests

        url = (
            f"https://api.bilibili.com/x/web-interface/search/type"
            f"?search_type=video&keyword={quote(query + ' 音乐 高音质')}"
        )
        try:
            resp = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": "https://www.bilibili.com",
                    },
                    timeout=(5, self.timeout),
                ),
            )
            resp.raise_for_status()
            videos = resp.json().get("data", {}).get("result", [])
            if not videos:
                return None
            v = videos[0]
            title = v.get("title", query).replace('<em class="keyword">', "").replace("</em>", "")
            return SongResult(
                song_id=v.get("bvid", ""),
                song_name=title,
                artist=v.get("author", ""),
                source="bilibili",
            )
        except Exception:
            return None

    async def download(self, song: SongResult, output_dir: str) -> Optional[str]:
        import re
        import subprocess as _sp

        bv_id = song.song_id
        if not bv_id:
            return None

        video_url = f"https://www.bilibili.com/video/{bv_id}"
        dl_dir = os.path.abspath(self.download_dir)
        os.makedirs(dl_dir, exist_ok=True)
        before = set(os.listdir(dl_dir))

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _sp.run(
                    [
                        self.python_exe,
                        "-m",
                        "yutto",
                        video_url,
                        "--audio-only",
                        "--output-format-audio-only",
                        "mkv",
                        "-d",
                        dl_dir,
                        "--no-danmaku",
                    ],
                    capture_output=True,
                    timeout=120,
                ),
            )
        except Exception as e:
            logger.warning(f"Bilibili yutto failed: {e}")
            return None

        new_files = set(os.listdir(dl_dir)) - before
        if not new_files:
            return None

        src = new_files.pop()
        src_path = os.path.join(dl_dir, src)
        safe = re.sub(r'[&@#$%^【】。，\'：；"《》？（）\s]+', "_", os.path.splitext(src)[0])
        ext = os.path.splitext(src)[1] or ".mkv"
        dst = os.path.join(output_dir, f"{safe}{ext}")
        os.makedirs(output_dir, exist_ok=True)
        shutil.move(src_path, dst)
        logger.info(f"Bilibili: {song.song_name} -> {dst}")
        return dst


class AutoMusicSource(MusicSource):
    """自动多源音乐源 — local → netease → bilibili 依次回退"""

    def __init__(self):
        super().__init__("auto")
        self.sources: List[MusicSource] = []

    def initialize(self, config: dict) -> bool:
        self.sources = []
        for cls in [LocalFileSource, NeteaseMusicSource, BilibiliMusicSource]:
            try:
                src = cls()
                if src.initialize(config):
                    self.sources.append(src)
            except Exception as e:
                logger.warning(f"Auto: {cls.__name__} init failed: {e}")
        if not self.sources:
            logger.error("Auto: no sources available")
            return False
        self.is_initialized = True
        logger.info(f"AutoMusicSource: {[s.name for s in self.sources]}")
        return True

    async def search(self, query: str) -> Optional[SongResult]:
        for src in self.sources:
            try:
                result = await src.search(query)
                if result and result.song_id:
                    logger.info(f"Auto search [{src.name}]: {result.song_name}")
                    result.source = f"auto:{src.name}"
                    return result
            except Exception:
                continue
        return None

    async def download(self, song: SongResult, output_dir: str) -> Optional[str]:
        actual = song.source.removeprefix("auto:") if song.source.startswith("auto:") else ""
        candidates = self.sources
        if actual:
            candidates = [s for s in self.sources if s.name == actual] + [s for s in self.sources if s.name != actual]
        for src in candidates:
            try:
                path = await src.download(song, output_dir)
                if path and os.path.exists(path):
                    return path
            except Exception:
                continue
        return None

    def cleanup(self):
        for s in self.sources:
            s.cleanup()
        self.is_initialized = False
