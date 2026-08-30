"""
弥娅文件库 — 持久化文件存储与索引

所有平台接收到的文件统一存储到 data/downloads/，
通过 JSON 索引实现长期记忆和检索能力。
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.file_context import FileContext, FileType, get_downloads_dir

logger = logging.getLogger("Miya.FileLibrary")

LIBRARY_INDEX_FILE = "file_library.json"


@dataclass
class FileEntry:
    """文件库中的单条记录"""

    file_id: str = ""
    file_name: str = ""
    file_path: str = ""
    file_size: int = 0
    file_type: str = ""
    mime_type: str = ""
    platform: str = ""
    user_id: str = ""
    received_at: str = ""
    analysis_result: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def extension(self) -> str:
        if self.file_name and "." in self.file_name:
            return self.file_name.rsplit(".", 1)[-1].lower()
        return ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["file_type"] = self.file_type
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> FileEntry:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_file_context(cls, fc: FileContext, platform: str = "", user_id: str = "") -> FileEntry:
        return cls(
            file_id=str(uuid.uuid4()),
            file_name=fc.file_name,
            file_path=fc.file_path if fc.is_downloaded else "",
            file_size=fc.file_size if fc.file_size > 0 else (len(fc.file_data) if fc.file_data else 0),
            file_type=fc.file_type if isinstance(fc.file_type, str) else fc.file_type.value,
            mime_type=fc.mime_type,
            platform=platform,
            user_id=str(user_id),
            received_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            analysis_result=fc.analysis_result,
            metadata=dict(fc.metadata),
        )


class FileLibrary:
    """弥娅文件库单例"""

    _instance: Optional[FileLibrary] = None
    _lock = threading.Lock()

    def __new__(cls) -> FileLibrary:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def _init(self):
        if self._initialized:
            return
        self._downloads_root = Path(get_downloads_dir())
        self._index_path = self._downloads_root / LIBRARY_INDEX_FILE
        self._entries: Dict[str, FileEntry] = {}
        self._load_index()
        self._initialized = True
        logger.info(f"[FileLibrary] 初始化完成, 已加载 {len(self._entries)} 个文件")

    def _load_index(self):
        if self._index_path.exists():
            try:
                with open(self._index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for fid, d in data.get("files", {}).items():
                    self._entries[fid] = FileEntry.from_dict(d)
            except Exception as e:
                logger.warning(f"[FileLibrary] 索引加载失败: {e}")

    def _save_index(self):
        try:
            data = {"files": {fid: e.to_dict() for fid, e in self._entries.items()}}
            tmp = str(self._index_path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, str(self._index_path))
        except Exception as e:
            logger.error(f"[FileLibrary] 索引保存失败: {e}")

    # ==================== 公开 API ====================

    def add_file(
        self,
        file_context: FileContext,
        platform: str = "",
        user_id: str = "",
    ) -> Optional[FileEntry]:
        """添加文件到文件库，返回 FileEntry 或 None"""
        self._init()

        if not file_context.file_data:
            if file_context.file_path and os.path.exists(file_context.file_path):
                with open(file_context.file_path, "rb") as f:
                    file_context.file_data = f.read()
            else:
                logger.warning("[FileLibrary] 无文件数据，跳过")
                return None

        entry = FileEntry.from_file_context(file_context, platform, user_id)
        if not entry.file_name:
            entry.file_name = f"unknown_{entry.file_id}{file_context.extension or '.bin'}"

        # 写入磁盘
        platform_dir = platform if platform else "unknown"
        target_dir = self._downloads_root / platform_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_name = entry.file_name.replace("\\", "_").replace("/", "_")
        disk_path = target_dir / safe_name
        # 去重：同名文件加序号
        counter = 1
        while disk_path.exists():
            stem, ext = os.path.splitext(safe_name)
            disk_path = target_dir / f"{stem}_{counter}{ext}"
            counter += 1

        try:
            with open(disk_path, "wb") as f:
                f.write(file_context.file_data)
            entry.file_path = str(disk_path)
            entry.file_size = file_context.file_size or len(file_context.file_data)
        except Exception as e:
            logger.error(f"[FileLibrary] 写入磁盘失败: {e}")
            return None

        self._entries[entry.file_id] = entry
        self._save_index()

        logger.info(f"[FileLibrary] 已入库: {entry.file_name} ({entry.file_size / 1024:.1f}KB, {platform})")
        return entry

    def get_file(self, file_id: str) -> Optional[FileEntry]:
        self._init()
        return self._entries.get(file_id)

    def list_files(
        self,
        platform: str = "",
        user_id: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[FileEntry]:
        self._init()
        entries = sorted(
            self._entries.values(),
            key=lambda e: e.received_at,
            reverse=True,
        )
        if platform:
            entries = [e for e in entries if e.platform == platform]
        if user_id:
            entries = [e for e in entries if e.user_id == str(user_id)]
        return entries[offset : offset + limit]

    def search_files(self, query: str, limit: int = 20) -> List[FileEntry]:
        self._init()
        q = query.lower()
        results = []
        for e in self._entries.values():
            if q in e.file_name.lower() or q in e.file_type.lower():
                results.append(e)
        results.sort(key=lambda e: e.received_at, reverse=True)
        return results[:limit]

    def read_file(self, file_id: str) -> Optional[FileContext]:
        """读取文件内容并返回 FileContext（含字节数据）"""
        self._init()
        entry = self._entries.get(file_id)
        if not entry:
            return None

        path = entry.file_path
        if not path or not os.path.exists(path):
            return None

        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            logger.warning(f"[FileLibrary] 读取失败: {e}")
            return None

        fc = FileContext.from_file(
            file_name=entry.file_name,
            file_path=path,
            file_size=len(data),
            mime_type=entry.mime_type,
        )
        fc.file_data = data
        fc.file_id = entry.file_id
        if entry.analysis_result:
            fc.analysis_result = entry.analysis_result
        return fc

    def read_and_analyze(self, file_id: str) -> Optional[str]:
        """读取文件并分析内容"""
        fc = self.read_file(file_id)
        if not fc:
            return None
        result = fc.analyze_content()
        if result:
            entry = self._entries.get(file_id)
            if entry:
                entry.analysis_result = result
                self._save_index()
        return result

    def get_recent_files(self, user_id: str = "", minutes: int = 5, limit: int = 5) -> List[FileEntry]:
        """获取最近 N 分钟内收到的文件"""
        self._init()
        cutoff = time.time() - minutes * 60
        recent = [e for e in self._entries.values() if _parse_time(e.received_at) >= cutoff]
        if user_id:
            recent = [e for e in recent if e.user_id == str(user_id)]
        recent.sort(key=lambda e: e.received_at, reverse=True)
        return recent[:limit]

    def delete_file(self, file_id: str) -> bool:
        self._init()
        entry = self._entries.pop(file_id, None)
        if not entry:
            return False
        if entry.file_path and os.path.exists(entry.file_path):
            try:
                os.remove(entry.file_path)
            except Exception as e:
                logger.warning(f"[FileLibrary] 删除文件失败: {e}")
        self._save_index()
        return True

    def stats(self) -> Dict[str, Any]:
        self._init()
        total_size = sum(e.file_size for e in self._entries.values())
        by_type: Dict[str, int] = {}
        by_platform: Dict[str, int] = {}
        for e in self._entries.values():
            by_type[e.file_type] = by_type.get(e.file_type, 0) + 1
            by_platform[e.platform] = by_platform.get(e.platform, 0) + 1
        return {
            "total_files": len(self._entries),
            "total_size_kb": round(total_size / 1024, 1),
            "by_type": by_type,
            "by_platform": by_platform,
        }


def _parse_time(ts: str) -> float:
    try:
        return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0


def get_file_library() -> FileLibrary:
    return FileLibrary()
