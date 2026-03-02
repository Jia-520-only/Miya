"""Agent配置管理器 - 弥娅Agent配置和映射管理

整合VCPToolBox AgentManager的配置能力：
- Agent别名映射
- Prompt缓存
- 热重载支持
- 文件系统扫描
- 文件夹结构管理
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent配置"""
    alias: str
    filename: str
    description: str = ""
    enabled: bool = True
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentConfigHandler(FileSystemEventHandler):
    """文件系统事件处理器"""

    def __init__(self, manager: 'AgentConfigManager'):
        self.manager = manager

    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory:
            asyncio.create_task(self.manager._on_file_changed(event.src_path))

    def on_created(self, event: FileCreatedEvent):
        if not event.is_directory:
            asyncio.create_task(self.manager._on_file_created(event.src_path))

    def on_deleted(self, event: FileDeletedEvent):
        if not event.is_directory:
            asyncio.create_task(self.manager._on_file_deleted(event.src_path))


class AgentConfigManager:
    """Agent配置管理器"""

    def __init__(
        self,
        agent_dir: Optional[str] = None,
        map_file: Optional[str] = None,
        auto_reload: bool = True
    ):
        self.agent_dir = Path(agent_dir) if agent_dir else Path("agents")
        self.map_file = Path(map_file) if map_file else Path("agent_map.json")
        self.auto_reload = auto_reload

        # 配置存储
        self.agent_configs: Dict[str, AgentConfig] = {}  # alias -> AgentConfig
        self.filename_to_alias: Dict[str, str] = {}  # filename -> alias

        # Prompt缓存
        self.prompt_cache: Dict[str, str] = {}

        # 文件系统
        self.agent_files: List[str] = []
        self.folder_structure: Dict[str, Dict] = {}

        # 文件监视器
        self.observer: Optional[Observer] = None

        # 锁
        self._lock = asyncio.Lock()

    async def initialize(self, debug_mode: bool = False) -> bool:
        """初始化管理器"""
        try:
            logger.info(f"[AgentConfig] 初始化Agent配置管理器...")
            logger.info(f"[AgentConfig] Agent目录: {self.agent_dir}")
            logger.info(f"[AgentConfig] 映射文件: {self.map_file}")

            # 加载映射文件
            await self.load_map()

            # 扫描Agent文件
            await self.scan_agent_files()

            # 启动文件监视
            if self.auto_reload:
                self.start_watching()

            logger.info(f"[AgentConfig] 初始化完成，已加载 {len(self.agent_configs)} 个Agent配置")
            return True

        except Exception as e:
            logger.error(f"[AgentConfig] 初始化失败: {e}")
            return False

    async def load_map(self) -> bool:
        """加载agent映射文件"""
        try:
            if not self.map_file.exists():
                logger.warning(f"[AgentConfig] 映射文件不存在: {self.map_file}")
                return False

            with open(self.map_file, "r", encoding="utf-8") as f:
                map_data = json.load(f)

            async with self._lock:
                self.agent_configs.clear()
                self.filename_to_alias.clear()

                for alias, filename in map_data.items():
                    config = AgentConfig(
                        alias=alias,
                        filename=filename
                    )
                    self.agent_configs[alias] = config
                    self.filename_to_alias[filename] = alias

            # 清除prompt缓存（映射已变更）
            self.prompt_cache.clear()

            logger.info(f"[AgentConfig] 已加载 {len(self.agent_configs)} 个Agent映射")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"[AgentConfig] 映射文件JSON解析失败: {e}")
            return False
        except Exception as e:
            logger.error(f"[AgentConfig] 加载映射文件失败: {e}")
            return False

    async def scan_agent_files(self) -> List[str]:
        """扫描Agent文件"""
        async with self._lock:
            self.agent_files = []
            self.folder_structure = {}

            try:
                # 确保目录存在
                self.agent_dir.mkdir(parents=True, exist_ok=True)

                # 递归扫描
                await self._scan_directory(self.agent_dir, "")

                logger.info(f"[AgentConfig] 扫描完成，找到 {len(self.agent_files)} 个Agent文件")
                return self.agent_files

            except Exception as e:
                logger.error(f"[AgentConfig] 扫描Agent文件失败: {e}")
                return []

    async def _scan_directory(self, dir_path: Path, relative_path: str):
        """递归扫描目录"""
        try:
            for entry in dir_path.iterdir():
                entry_relative = str(Path(relative_path) / entry.name) if relative_path else entry.name

                if entry.is_file():
                    # 只处理.txt和.md文件
                    if entry.suffix.lower() in ('.txt', '.md'):
                        self.agent_files.append(entry_relative)
                        self._add_to_folder_structure(entry_relative, "file", entry_relative)

                elif entry.is_dir():
                    self._add_to_folder_structure(entry_relative, "folder")
                    await self._scan_directory(entry, entry_relative)

        except PermissionError as e:
            logger.warning(f"[AgentConfig] 权限不足，跳过目录 {dir_path}: {e}")
        except Exception as e:
            logger.error(f"[AgentConfig] 扫描目录失败 {dir_path}: {e}")

    def _add_to_folder_structure(self, path: str, entry_type: str, value: Any = None):
        """添加到文件夹结构"""
        parts = path.split('/')
        current = self.folder_structure

        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {}

            if i == len(parts) - 1:
                # 最后一级，添加类型信息
                if entry_type == "file":
                    current[part]["_type"] = "file"
                    current[part]["_path"] = value
                elif entry_type == "folder":
                    current[part]["_type"] = "folder"
            else:
                current = current[part]

    def start_watching(self):
        """启动文件监视"""
        try:
            if self.observer and self.observer.is_alive():
                logger.info("[AgentConfig] 文件监视器已在运行")
                return

            event_handler = AgentConfigHandler(self)
            self.observer = Observer()

            # 监视映射文件
            if self.map_file.exists():
                self.observer.schedule(event_handler, str(self.map_file), recursive=False)

            # 监视Agent目录
            if self.agent_dir.exists():
                self.observer.schedule(event_handler, str(self.agent_dir), recursive=True)

            self.observer.start()
            logger.info("[AgentConfig] 文件监视器已启动")

        except Exception as e:
            logger.error(f"[AgentConfig] 启动文件监视失败: {e}")

    def stop_watching(self):
        """停止文件监视"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("[AgentConfig] 文件监视器已停止")

    # ==================== 配置查询 ====================

    def get_config(self, alias: str) -> Optional[AgentConfig]:
        """获取Agent配置"""
        return self.agent_configs.get(alias)

    def get_config_by_filename(self, filename: str) -> Optional[AgentConfig]:
        """通过文件名获取Agent配置"""
        alias = self.filename_to_alias.get(filename)
        return self.agent_configs.get(alias) if alias else None

    def get_all_configs(self) -> List[AgentConfig]:
        """获取所有Agent配置"""
        return list(self.agent_configs.values())

    def search_configs(self, keyword: str) -> List[AgentConfig]:
        """搜索Agent配置"""
        keyword_lower = keyword.lower()
        matched = []

        for config in self.agent_configs.values():
            if (keyword_lower in config.alias.lower() or
                keyword_lower in config.filename.lower() or
                keyword_lower in config.description.lower() or
                any(keyword_lower in tag.lower() for tag in config.tags)):
                matched.append(config)

        return matched

    def get_folder_structure(self) -> Dict[str, Any]:
        """获取文件夹结构"""
        return self.folder_structure

    def get_available_files(self) -> List[str]:
        """获取可用的Agent文件列表"""
        return self.agent_files.copy()

    # ==================== Prompt管理 ====================

    async def get_prompt(self, alias: str) -> Optional[str]:
        """获取Agent prompt（带缓存）"""
        config = self.agent_configs.get(alias)
        if not config:
            return None

        # 检查缓存
        if alias in self.prompt_cache:
            return self.prompt_cache[alias]

        # 读取文件
        file_path = self.agent_dir / config.filename
        if not file_path.exists():
            logger.warning(f"[AgentConfig] Agent文件不存在: {file_path}")
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 缓存
            self.prompt_cache[alias] = content
            return content

        except Exception as e:
            logger.error(f"[AgentConfig] 读取Agent文件失败 {file_path}: {e}")
            return None

    def clear_prompt_cache(self, alias: Optional[str] = None):
        """清除prompt缓存"""
        if alias:
            self.prompt_cache.pop(alias, None)
            logger.debug(f"[AgentConfig] 清除Agent prompt缓存: {alias}")
        else:
            self.prompt_cache.clear()
            logger.debug("[AgentConfig] 清除所有prompt缓存")

    # ==================== 文件事件处理 ====================

    async def _on_file_changed(self, file_path: str):
        """文件变更处理"""
        try:
            relative_path = str(Path(file_path).relative_to(self.agent_dir))

            # 查找对应的Agent
            config = self.get_config_by_filename(relative_path)
            if config:
                self.clear_prompt_cache(config.alias)
                logger.info(f"[AgentConfig] Agent文件变更，清除缓存: {config.alias}")

            # 重新扫描文件列表
            await self.scan_agent_files()

        except Exception as e:
            logger.error(f"[AgentConfig] 处理文件变更失败 {file_path}: {e}")

    async def _on_file_created(self, file_path: str):
        """文件创建处理"""
        try:
            logger.info(f"[AgentConfig] 新文件检测: {file_path}")
            await self.scan_agent_files()

        except Exception as e:
            logger.error(f"[AgentConfig] 处理文件创建失败 {file_path}: {e}")

    async def _on_file_deleted(self, file_path: str):
        """文件删除处理"""
        try:
            relative_path = str(Path(file_path).relative_to(self.agent_dir))
            config = self.get_config_by_filename(relative_path)

            if config:
                self.clear_prompt_cache(config.alias)
                logger.info(f"[AgentConfig] Agent文件删除: {config.alias}")

            await self.scan_agent_files()

        except Exception as e:
            logger.error(f"[AgentConfig] 处理文件删除失败 {file_path}: {e}")

    # ==================== 配置操作 ====================

    async def add_config(self, alias: str, filename: str, **kwargs) -> bool:
        """添加Agent配置"""
        async with self._lock:
            if alias in self.agent_configs:
                logger.warning(f"[AgentConfig] Agent配置已存在: {alias}")
                return False

            config = AgentConfig(alias=alias, filename=filename, **kwargs)
            self.agent_configs[alias] = config
            self.filename_to_alias[filename] = alias

            # 保存到文件
            return await self._save_map()

    async def update_config(self, alias: str, **kwargs) -> bool:
        """更新Agent配置"""
        config = self.agent_configs.get(alias)
        if not config:
            return False

        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)

            # 更新文件名映射
            if "filename" in kwargs:
                old_filename = self.filename_to_alias.get(alias)
                if old_filename:
                    del self.filename_to_alias[old_filename]
                self.filename_to_alias[kwargs["filename"]] = alias

            return await self._save_map()

    async def delete_config(self, alias: str) -> bool:
        """删除Agent配置"""
        config = self.agent_configs.get(alias)
        if not config:
            return False

        async with self._lock:
            # 删除配置
            del self.agent_configs[alias]

            # 删除文件名映射
            if config.filename in self.filename_to_alias:
                del self.filename_to_alias[config.filename]

            # 清除缓存
            self.clear_prompt_cache(alias)

            return await self._save_map()

    async def _save_map(self) -> bool:
        """保存映射文件"""
        try:
            map_data = {
                alias: config.filename
                for alias, config in self.agent_configs.items()
            }

            with open(self.map_file, "w", encoding="utf-8") as f:
                json.dump(map_data, f, ensure_ascii=False, indent=2)

            logger.info(f"[AgentConfig] 映射文件已保存: {self.map_file}")
            return True

        except Exception as e:
            logger.error(f"[AgentConfig] 保存映射文件失败: {e}")
            return False

    # ==================== 统计信息 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_agents": len(self.agent_configs),
            "total_files": len(self.agent_files),
            "cached_prompts": len(self.prompt_cache),
            "enabled_agents": sum(1 for c in self.agent_configs.values() if c.enabled),
            "watching": self.observer.is_alive() if self.observer else False
        }

    async def cleanup(self):
        """清理资源"""
        logger.info("[AgentConfig] 清理Agent配置管理器...")

        self.stop_watching()
        self.agent_configs.clear()
        self.filename_to_alias.clear()
        self.prompt_cache.clear()
        self.agent_files.clear()
        self.folder_structure.clear()

        logger.info("[AgentConfig] 清理完成")


# 全局单例
_AGENT_CONFIG_MANAGER: Optional[AgentConfigManager] = None


def get_agent_config_manager(
    agent_dir: Optional[str] = None,
    auto_reload: bool = True
) -> AgentConfigManager:
    """获取Agent配置管理器单例"""
    global _AGENT_CONFIG_MANAGER

    if _AGENT_CONFIG_MANAGER is None:
        _AGENT_CONFIG_MANAGER = AgentConfigManager(
            agent_dir=agent_dir,
            auto_reload=auto_reload
        )

    return _AGENT_CONFIG_MANAGER


def reset_agent_config_manager():
    """重置Agent配置管理器（主要用于测试）"""
    global _AGENT_CONFIG_MANAGER
    _AGENT_CONFIG_MANAGER = None
