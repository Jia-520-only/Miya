"""
AI唱歌引擎抽象基类

定义所有唱歌引擎必须实现的接口。
唱歌与TTS不同：涉及歌曲搜索、AI学唱、下载、双轨播放等流程。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class LearnStatus(str, Enum):
    PROCESSING = "processing"
    PROCESSED = "processed"
    WAITING = "waiting"
    FAILED = "failed"


@dataclass
class SongInfo:
    song_id: str = ""
    song_name: str = ""
    source: str = ""


@dataclass
class LearnTask:
    song_name: str
    status: LearnStatus = LearnStatus.WAITING
    progress: int = 0


@dataclass
class SongOutput:
    song_name: str
    vocal_path: str = ""
    accompany_path: str = ""
    output_dir: str = ""
    skip_rvc: bool = False
    chord_path: str = ""
    vol_chord: int = 50


class SingingEngine(ABC):
    """AI唱歌引擎抽象基类"""

    def __init__(self, engine_name: str):
        self.engine_name = engine_name
        self.is_initialized = False

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def search_song(self, query: str) -> Optional[SongInfo]:
        """搜索歌曲，获取标准歌名与ID"""
        pass

    @abstractmethod
    async def get_available_songs(self) -> List[str]:
        """获取已学过的歌曲列表"""
        pass

    @abstractmethod
    async def request_learn(self, song_name: str) -> LearnTask:
        """请求AI学唱一首歌，返回学习任务"""
        pass

    @abstractmethod
    async def get_learn_status(self, song_name: str) -> LearnStatus:
        """查询学唱进度"""
        pass

    @abstractmethod
    async def download_vocal(self, song_name: str, output_dir: str) -> Optional[str]:
        """下载AI人声文件，返回文件路径"""
        pass

    @abstractmethod
    async def download_accompany(self, song_name: str, output_dir: str) -> Optional[str]:
        """下载伴奏文件，返回文件路径"""
        pass

    @abstractmethod
    async def download_origin(self, song_name: str, output_dir: str) -> Optional[str]:
        """下载原始歌曲（不转换音色），返回文件路径"""
        pass

    def get_engine_info(self) -> Dict[str, Any]:
        return {
            "name": self.engine_name,
            "initialized": self.is_initialized,
        }

    def cleanup(self):
        self.is_initialized = False

    def __repr__(self):
        return f"<SingingEngine: {self.engine_name}>"
