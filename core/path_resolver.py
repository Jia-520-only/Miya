"""
弥娅路径解析器 — 冻结与开发模式统一

用法:
    from core.path_resolver import get_config_dir, get_data_dir, get_logs_dir, get_models_dir, get_project_root

所有模块应通过此模块获取路径，不再使用 Path("config/...") 或 Path("data/...") 等 CWD 相对路径。
"""

from __future__ import annotations

import sys
from pathlib import Path


def _resolve_root() -> Path:
    """获取项目根目录

    冻结模式 (PyInstaller): sys._MEIPASS 指向 _internal/ 目录。
    开发模式: 本文件位于 core/path_resolver.py，向上两级即项目根。
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


_ROOT: Path | None = None


def get_project_root() -> Path:
    global _ROOT
    if _ROOT is None:
        _ROOT = _resolve_root()
    return _ROOT


def get_config_dir() -> Path:
    p = get_project_root() / "config"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_data_dir() -> Path:
    p = get_project_root() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logs_dir() -> Path:
    p = get_project_root() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_models_dir() -> Path:
    p = get_project_root() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_subdirs(*subpaths: str) -> None:
    """确保 data/ 下的子目录存在"""
    for sub in subpaths:
        (get_data_dir() / sub).mkdir(parents=True, exist_ok=True)
