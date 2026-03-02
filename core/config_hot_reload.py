"""弥娅配置热更新系统 - 整合Undefined的配置热更新能力

该模块提供弥娅的配置热更新功能，支持：
- 配置文件监听
- 热更新应用
- 无需重启系统
- 智能识别需要重启的配置项

设计理念：符合弥娅的架构，属于config层的增强，不改变核心架构
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Set, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("[配置热更新] watchdog未安装，热更新功能将被禁用")

logger = logging.getLogger(__name__)


# 需要重启才能生效的配置项
_RESTART_REQUIRED_KEYS: Set[str] = {
    "log_level",
    "log_file_path",
    "log_max_size",
    "log_backup_count",
    "mqtt_broker",
    "mqtt_port",
    "mqtt_username",
    "mqtt_password",
    "mcp_server_enabled",
    "mcp_server_host",
    "mcp_server_port",
    "api_enabled",
    "api_host",
    "api_port",
}


@dataclass
class HotReloadContext:
    """热更新上下文"""
    config_manager: Optional[Any] = None
    queue_manager: Optional[Any] = None
    agent_manager: Optional[Any] = None
    runtime_api: Optional[Any] = None


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变更处理器"""
    
    def __init__(
        self,
        config_path: Path,
        callback: Callable[[], None],
        debounce_seconds: float = 2.0,
    ):
        self.config_path = config_path.resolve()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._last_modified = 0.0
        self._debounce_task: Optional[asyncio.Task[None]] = None
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """文件修改事件"""
        if event.is_directory:
            return
        
        try:
            event_path = Path(event.src_path).resolve()
            if event_path != self.config_path:
                return
            
            # 防抖处理
            import time
            now = time.time()
            if now - self._last_modified < self.debounce_seconds:
                return
            
            self._last_modified = now
            
            logger.info("[配置热更新] 检测到配置文件变更: %s", self.config_path)
            
            # 异步触发回调
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()
            
            loop = asyncio.get_event_loop()
            self._debounce_task = loop.create_task(self._debounced_callback())
            
        except Exception as e:
            logger.error(
                "[配置热更新] 文件监听异常 error=%s",
                e,
                exc_info=True,
            )
    
    async def _debounced_callback(self) -> None:
        """防抖回调"""
        await asyncio.sleep(self.debounce_seconds)
        try:
            if self.callback:
                await self.callback()
        except Exception as e:
            logger.error(
                "[配置热更新] 回调执行异常 error=%s",
                e,
                exc_info=True,
            )


class ConfigHotReload:
    """配置热更新管理器
    
    职责：
    - 监听配置文件变更
    - 应用配置更新
    - 识别需要重启的配置项
    
    架构定位：属于config层，提供热更新能力
    """

    def __init__(
        self,
        config_path: Path,
        context: Optional[HotReloadContext] = None,
        debounce_seconds: float = 2.0,
        enabled: bool = True,
    ):
        self.config_path = config_path
        self.context = context or HotReloadContext()
        self.debounce_seconds = debounce_seconds
        self.enabled = enabled and WATCHDOG_AVAILABLE
        
        self._observer: Optional[Observer] = None
        self._reload_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        if not WATCHDOG_AVAILABLE:
            logger.warning(
                "[配置热更新] watchdog不可用，请安装: pip install watchdog"
            )
    
    def add_reload_callback(
        self,
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """添加配置更新回调"""
        self._reload_callbacks.append(callback)
    
    async def _on_config_changed(self) -> None:
        """配置文件变更回调"""
        logger.info("[配置热更新] 开始处理配置变更...")
        
        try:
            # 加载新配置
            new_config = self._load_config()
            if not new_config:
                logger.warning("[配置热更新] 配置加载失败")
                return
            
            # 检测变更
            changes = self._detect_changes(new_config)
            if not changes:
                logger.info("[配置热更新] 配置无变更")
                return
            
            logger.info(
                "[配置热更新] 检测到变更项: %s",
                ", ".join(sorted(changes.keys())),
            )
            
            # 识别需要重启的配置项
            restart_keys = changes.keys() & _RESTART_REQUIRED_KEYS
            if restart_keys:
                logger.warning(
                    "[配置热更新] 以下配置项需要重启才能生效: %s",
                    ", ".join(sorted(restart_keys)),
                )
            
            # 应用更新
            await self._apply_updates(new_config, changes)
            
            # 触发回调
            for callback in self._reload_callbacks:
                try:
                    callback(new_config)
                except Exception as e:
                    logger.error(
                        "[配置热更新] 回调执行异常 error=%s",
                        e,
                        exc_info=True,
                    )
            
            logger.info("[配置热更新] 配置更新完成")
            
        except Exception as e:
            logger.error(
                "[配置热更新] 处理异常 error=%s",
                e,
                exc_info=True,
            )
    
    def _load_config(self) -> Optional[Dict[str, Any]]:
        """加载配置文件"""
        try:
            import json
            
            if not self.config_path.exists():
                logger.error("[配置热更新] 配置文件不存在: %s", self.config_path)
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
            
        except Exception as e:
            logger.error(
                "[配置热更新] 配置加载异常 error=%s",
                e,
                exc_info=True,
            )
            return None
    
    def _detect_changes(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """检测配置变更
        
        返回: {配置键: (旧值, 新值)}
        """
        # 这里需要保存旧配置，简化实现
        changes = {}
        
        # TODO: 实现完整的变更检测
        # 需要保存旧配置并与新配置对比
        
        return changes
    
    async def _apply_updates(
        self,
        new_config: Dict[str, Any],
        changes: Dict[str, Any],
    ) -> None:
        """应用配置更新"""
        changed_keys = set(changes.keys())
        
        # 更新队列管理器
        if self.context.queue_manager and "queue_intervals" in changed_keys:
            intervals = new_config.get("queue_intervals", {})
            self.context.queue_manager.update_model_intervals(intervals)
            logger.info("[配置热更新] 队列间隔已更新")
        
        # 其他组件更新...
        # TODO: 根据需要添加更多组件的更新逻辑
    
    def start(self) -> bool:
        """启动配置热更新监听"""
        if not self.enabled or not WATCHDOG_AVAILABLE:
            logger.info("[配置热更新] 未启用或watchdog不可用")
            return False
        
        if self._observer:
            logger.warning("[配置热更新] 监听器已在运行")
            return False
        
        try:
            self._observer = Observer()
            handler = ConfigFileHandler(
                self.config_path,
                self._on_config_changed,
                self.debounce_seconds,
            )
            
            # 监听配置文件所在目录
            watch_dir = self.config_path.parent
            self._observer.schedule(handler, str(watch_dir), recursive=False)
            self._observer.start()
            
            logger.info(
                "[配置热更新] 监听已启动: %s",
                self.config_path,
            )
            return True
            
        except Exception as e:
            logger.error(
                "[配置热更新] 启动失败 error=%s",
                e,
                exc_info=True,
            )
            return False
    
    def stop(self) -> None:
        """停止配置热更新监听"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("[配置热更新] 监听已停止")
