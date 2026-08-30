"""
MusicNet - 弥娅音乐工作站子网

弥娅的 AI 作曲、编曲、MIDI 编辑能力。
核心数据模型来自 ATRI 的 music_project.py，
以弥娅 ToolNet 工具的形式暴露给 AI Agent 使用。

架构:
    MusicNet/
    ├── __init__.py           # 子网入口
    ├── music_project.py      # 音乐项目数据模型 (DAW JSON 持久化)
    ├── midi_tools.py         # MIDI 作曲工具 (5 个 BaseTool)
    └── subnet.py             # MusicNet 子网基类
"""

import logging

logger = logging.getLogger(__name__)

__all__ = [
    "get_music_subnet",
    "load_music_project",
    "save_music_project",
    "MusicSubnet",
]

_music_subnet = None


def get_music_subnet():
    global _music_subnet
    if _music_subnet is None:
        from .subnet import MusicSubnet

        _music_subnet = MusicSubnet()
        logger.info("MusicNet \u5b50\u7f51\u5df2\u521d\u59cb\u5316")
    return _music_subnet


def load_music_project():
    from .music_project import load_project

    return load_project()


def save_music_project(project):
    from .music_project import save_project

    return save_project(project)
