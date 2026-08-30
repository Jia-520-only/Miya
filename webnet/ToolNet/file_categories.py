"""
文件扩展名分类表（单一数据源）

download_file / group_file_downloader 等下载相关工具统一从这里读取，
避免各写一套扩展名映射导致不一致。
"""

from pathlib import Path
from typing import Dict, Set

EXT_CATEGORIES: Dict[str, Set[str]] = {
    "image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".avif", ".heic"},
    "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp", ".ts", ".mts"},
    "program": {
        ".exe",
        ".msi",
        ".dmg",
        ".pkg",
        ".apk",
        ".appimage",
        ".deb",
        ".rpm",
        ".sh",
        ".bat",
        ".ps1",
        ".cmd",
        ".run",
        ".appxbundle",
        ".msixbundle",
        ".snap",
        ".flatpak",
    },
    "document": {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".log",
        ".html",
        ".htm",
        ".rtf",
    },
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".lz4", ".iso"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".mid", ".midi"},
    "code": {".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".go", ".rs", ".php", ".rb", ".css", ".sql"},
}


def classify(filename: str) -> str:
    """按扩展名返回规范分类，未匹配返回 other"""
    ext = Path(filename).suffix.lower()
    for category, extensions in EXT_CATEGORIES.items():
        if ext in extensions:
            return category
    return "other"
