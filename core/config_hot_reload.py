"""弥娅配置热更新系统 - 整合Undefined的配置热更新能力

该模块提供弥娅的配置热更新功能，支持：
- 配置文件监听
- 热更新应用
- 无需重启系统
- 智能识别需要重启的配置项

设计理念：符合弥娅的架构，属于config层的增强，不改变核心架构
"""

import asyncio
import copy
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.config_event_system import ConfigEvent
from core.constants import Encoding, NetworkTimeout

try:
    from watchdog.events import FileModifiedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # 创建虚拟类定义当watchdog不可用时
    class FileSystemEventHandler:
        """虚拟文件系统事件处理器"""

        pass

    class FileModifiedEvent:
        """虚拟文件修改事件"""

        def __init__(self, src_path):
            self.src_path = src_path
            self.is_directory = False

    class Observer:
        """虚拟观察者"""

        def schedule(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    logger = logging.getLogger(__name__)
    logger.warning("[配置热更新] watchdog未安装，热更新功能将被禁用")

logger = logging.getLogger(__name__)


_RESTART_REQUIRED_KEYS = {
    "database",
    "port",
    "host",
    "server",
    "api_keys",
    "admin_password",
}


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


class HotReloadContext:
    """热更新上下文（虚拟定义）"""

    pass


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

        # 事件订阅系统
        self._event_subscribers: Dict[str, List[Callable[[ConfigEvent], None]]] = {}
        self._all_subscribers: List[Callable[[ConfigEvent], None]] = []

        if not WATCHDOG_AVAILABLE:
            logger.warning("[配置热更新] watchdog不可用，请安装: pip install watchdog")

    def add_reload_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """添加配置更新回调"""
        self._reload_callbacks.append(callback)

    def subscribe_event(self, event_type: str, callback: Callable[[ConfigEvent], None]) -> None:
        """订阅特定类型的事件

        Args:
            event_type: 事件类型，如 'config_update', 'config_reload', 'error'
            callback: 回调函数，接收ConfigEvent对象
        """
        if event_type not in self._event_subscribers:
            self._event_subscribers[event_type] = []
        self._event_subscribers[event_type].append(callback)
        logger.debug(f"[配置热更新] 新增订阅者: event_type={event_type}")

    def subscribe_all_events(self, callback: Callable[[ConfigEvent], None]) -> None:
        """订阅所有事件

        Args:
            callback: 回调函数，接收ConfigEvent对象
        """
        self._all_subscribers.append(callback)
        logger.debug("[配置热更新] 新增全局订阅者")

    def unsubscribe_event(self, event_type: str, callback: Callable[[ConfigEvent], None]) -> None:
        """取消订阅特定类型的事件"""
        if event_type in self._event_subscribers and callback in self._event_subscribers[event_type]:
            self._event_subscribers[event_type].remove(callback)
            logger.debug(f"[配置热更新] 移除订阅者: event_type={event_type}")

    def unsubscribe_all_events(self, callback: Callable[[ConfigEvent], None]) -> None:
        """取消订阅所有事件"""
        if callback in self._all_subscribers:
            self._all_subscribers.remove(callback)
            logger.debug("[配置热更新] 移除全局订阅者")

    async def _publish_event(self, event: ConfigEvent) -> None:
        """发布事件到所有订阅者

        Args:
            event: 配置更新事件
        """
        try:
            # 先通知全局订阅者
            for callback in self._all_subscribers:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"[配置热更新] 全局订阅者回调异常: {e}", exc_info=True)

            # 再通知特定类型的订阅者
            if event.event_type in self._event_subscribers:
                for callback in self._event_subscribers[event.event_type]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event)
                        else:
                            callback(event)
                    except Exception as e:
                        logger.error(f"[配置热更新] 订阅者回调异常 (type={event.event_type}): {e}", exc_info=True)

            # 尝试通过WebSocket通知（如果有runtime_api）
            if self.context.runtime_api:
                await self._notify_via_websocket(event)

            logger.debug(f"[配置热更新] 事件已发布: type={event.event_type}, changes={list(event.changes.keys())}")

        except Exception as e:
            logger.error(f"[配置热更新] 事件发布失败: {e}", exc_info=True)

    async def _notify_via_websocket(self, event: ConfigEvent) -> None:
        """通过WebSocket通知前端

        Args:
            event: 配置更新事件
        """
        try:
            if hasattr(self.context.runtime_api, "notify_config_change"):
                await self.context.runtime_api.notify_config_change(
                    {
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                        "changes": event.changes,
                        "source": event.source,
                    }
                )
        except Exception as e:
            logger.debug(f"[配置热更新] WebSocket通知失败: {e}")

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

            with open(self.config_path, "r", encoding=Encoding.UTF8) as f:
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
        # 保存旧配置快照
        if not hasattr(self, "_config_snapshot"):
            self._config_snapshot = {}

        old_config = self._config_snapshot.copy()
        changes = {}

        # 深度对比配置变更
        all_keys = set(old_config.keys()) | set(new_config.keys())

        for key in all_keys:
            old_val = old_config.get(key)
            new_val = new_config.get(key)

            # 检查值是否改变
            if self._is_value_changed(old_val, new_val):
                changes[key] = (old_val, new_val)

        # 更新配置快照
        self._config_snapshot = self._deep_copy_config(new_config)

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

        # 更新人格系统
        if self.context.personality and "personality" in changed_keys:
            personality_config = new_config.get("personality", {})
            self._update_personality_config(personality_config)
            logger.info("[配置热更新] 人格配置已更新")

        # 更新情绪系统
        if self.context.emotion and "emotion" in changed_keys:
            emotion_config = new_config.get("emotion", {})
            self._update_emotion_config(emotion_config)
            logger.info("[配置热更新] 情绪配置已更新")

        # 更新记忆系统
        if self.context.memory and "memory" in changed_keys:
            memory_config = new_config.get("memory", {})
            self._update_memory_config(memory_config)
            logger.info("[配置热更新] 记忆配置已更新")

        # 更新AI后端配置
        if self.context.ai_backend and "ai_backend" in changed_keys:
            ai_config = new_config.get("ai_backend", {})
            self._update_ai_backend_config(ai_config)
            logger.info("[配置热更新] AI后端配置已更新")

        # 更新TTS配置
        if "tts" in changed_keys:
            tts_config = new_config.get("tts", {})
            self._update_tts_config(tts_config)
            logger.info("[配置热更新] TTS配置已更新")

        # 更新WebAPI配置
        if self.context.web_api and "web_api" in changed_keys:
            webapi_config = new_config.get("web_api", {})
            self._update_webapi_config(webapi_config)
            logger.info("[配置热更新] WebAPI配置已更新")

        # 更新终端管理器配置
        if self.context.terminal_manager and "terminal" in changed_keys:
            terminal_config = new_config.get("terminal", {})
            self._update_terminal_config(terminal_config)
            logger.info("[配置热更新] 终端管理器配置已更新")

        # 更新IoT管理器配置
        if self.context.iot_manager and "iot" in changed_keys:
            iot_config = new_config.get("iot", {})
            self._update_iot_config(iot_config)
            logger.info("[配置热更新] IoT管理器配置已更新")

        # 触发配置更新事件
        await self._trigger_config_update_event(changes)

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

    def _is_value_changed(self, old_val: Any, new_val: Any) -> bool:
        """检查值是否改变"""
        # 处理None值
        if old_val is None and new_val is None:
            return False
        if (old_val is None) != (new_val is None):
            return True

        # 处理字典
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            return self._is_dict_changed(old_val, new_val)

        # 处理列表
        if isinstance(old_val, list) and isinstance(new_val, list):
            return old_val != new_val

        # 处理其他类型
        return old_val != new_val

    def _is_dict_changed(self, old_dict: Dict, new_dict: Dict) -> bool:
        """检查字典是否改变"""
        old_keys = set(old_dict.keys())
        new_keys = set(new_dict.keys())

        # 键的数量不同
        if len(old_keys) != len(new_keys):
            return True

        # 检查每个键的值
        for key in old_keys | new_keys:
            if not self._is_value_changed(old_dict.get(key), new_dict.get(key)):
                continue
            return True

        return False

    def _deep_copy_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """深度复制配置"""
        return copy.deepcopy(config)

    def _update_personality_config(self, config: Dict[str, Any]) -> None:
        """更新人格配置"""
        if not self.context.personality:
            return

        try:
            # 更新人格向量
            vectors = config.get("vectors", {})
            for key, value in vectors.items():
                if hasattr(self.context.personality, "vectors") and key in self.context.personality.vectors:
                    self.context.personality.vectors[key] = value

            # 更新形态
            form = config.get("form")
            if form:
                self.context.personality.set_form(form)

        except Exception as e:
            logger.error(f"[配置热更新] 更新人格配置失败: {e}", exc_info=True)

    def _update_emotion_config(self, config: Dict[str, Any]) -> None:
        """更新情绪配置"""
        if not self.context.emotion:
            return

        try:
            # 更新情绪衰减率
            decay_rate = config.get("decay_rate")
            if decay_rate:
                # 验证衰减率范围（0.0 - 1.0）
                if 0.0 <= decay_rate <= 1.0:
                    if hasattr(self.context.emotion, "decay_rate"):
                        self.context.emotion.decay_rate = decay_rate
                        logger.info(f"[配置热更新] 情绪衰减率已更新: {decay_rate}")
                    elif hasattr(self.context.emotion, "set_decay_rate"):
                        self.context.emotion.set_decay_rate(decay_rate)
                        logger.info(f"[配置热更新] 情绪衰减率已更新: {decay_rate}")
                    else:
                        logger.warning("[配置热更新] 情绪系统不支持动态更新衰减率")
                else:
                    logger.warning(f"[配置热更新] 情绪衰减率超出范围 (0.0-1.0): {decay_rate}")

            # 更新情绪影响因子
            influence_factor = config.get("influence_factor")
            if influence_factor:
                # 验证影响因子范围（0.0 - 2.0）
                if 0.0 <= influence_factor <= 2.0:
                    if hasattr(self.context.emotion, "influence_factor"):
                        self.context.emotion.influence_factor = influence_factor
                        logger.info(f"[配置热更新] 情绪影响因子已更新: {influence_factor}")
                    elif hasattr(self.context.emotion, "set_influence_factor"):
                        self.context.emotion.set_influence_factor(influence_factor)
                        logger.info(f"[配置热更新] 情绪影响因子已更新: {influence_factor}")
                    else:
                        logger.warning("[配置热更新] 情绪系统不支持动态更新影响因子")
                else:
                    logger.warning(f"[配置热更新] 情绪影响因子超出范围 (0.0-2.0): {influence_factor}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新情绪配置失败: {e}", exc_info=True)

    def _update_memory_config(self, config: Dict[str, Any]) -> None:
        """更新记忆配置"""
        if not self.context.memory:
            return

        try:
            # 更新记忆保留天数
            retention_days = config.get("retention_days")
            if retention_days:
                # 验证保留天数（至少1天）
                if retention_days >= 1:
                    if hasattr(self.context.memory, "retention_days"):
                        old_retention = self.context.memory.retention_days
                        self.context.memory.retention_days = retention_days
                        logger.info(f"[配置热更新] 记忆保留天数已更新: {old_retention} -> {retention_days} 天")

                        # 如果新保留天数更短,触发旧记忆清理
                        if retention_days < old_retention:
                            if hasattr(self.context.memory, "cleanup_old_memories"):
                                asyncio.create_task(self.context.memory.cleanup_old_memories())
                                logger.info("[配置热更新] 已触发旧记忆清理")

                    elif hasattr(self.context.memory, "set_retention_days"):
                        self.context.memory.set_retention_days(retention_days)
                        logger.info(f"[配置热更新] 记忆保留天数已更新: {retention_days} 天")
                    else:
                        logger.warning("[配置热更新] 记忆系统不支持动态更新保留天数")
                else:
                    logger.warning(f"[配置热更新] 记忆保留天数必须大于等于1: {retention_days}")

            # 更新记忆最大容量
            max_size = config.get("max_size")
            if max_size:
                # 验证最大容量（至少100）
                if max_size >= 100:
                    if hasattr(self.context.memory, "max_size"):
                        old_size = self.context.memory.max_size
                        self.context.memory.max_size = max_size
                        logger.info(f"[配置热更新] 记忆最大容量已更新: {old_size} -> {max_size}")

                        # 如果新容量更小,触发记忆清理
                        if max_size < old_size:
                            if hasattr(self.context.memory, "cleanup_exceeded_memories"):
                                asyncio.create_task(self.context.memory.cleanup_exceeded_memories())
                                logger.info("[配置热更新] 已触发超额记忆清理")

                    elif hasattr(self.context.memory, "set_max_size"):
                        self.context.memory.set_max_size(max_size)
                        logger.info(f"[配置热更新] 记忆最大容量已更新: {max_size}")
                    else:
                        logger.warning("[配置热更新] 记忆系统不支持动态更新最大容量")
                else:
                    logger.warning(f"[配置热更新] 记忆最大容量必须大于等于100: {max_size}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新记忆配置失败: {e}", exc_info=True)

    def _update_ai_backend_config(self, config: Dict[str, Any]) -> None:
        """更新AI后端配置"""
        if not self.context.ai_backend:
            return

        try:
            # 更新API配置
            api_key = config.get("api_key")
            if api_key:
                # 安全地更新API密钥（注意：密钥更新可能需要重新初始化客户端）
                try:
                    if hasattr(self.context, "agent_manager") and self.context.agent_manager:
                        # 更新agent管理器的API密钥
                        if hasattr(self.context.agent_manager, "update_api_key"):
                            self.context.agent_manager.update_api_key(api_key)
                            logger.info("[配置热更新] Agent管理器API密钥已更新")
                    if hasattr(self.context, "config_manager") and self.context.config_manager:
                        # 更新配置管理器中的密钥
                        if hasattr(self.context.config_manager, "api_key"):
                            self.context.config_manager.api_key = api_key
                            logger.info("[配置热更新] 配置管理器API密钥已更新")
                except Exception as key_error:
                    logger.warning(f"[配置热更新] API密钥更新失败: {key_error}")

            model = config.get("model")
            if model:
                # 实现模型切换
                try:
                    if hasattr(self.context, "agent_manager") and self.context.agent_manager:
                        # 更新agent管理器的模型
                        if hasattr(self.context.agent_manager, "model"):
                            self.context.agent_manager.model = model
                            logger.info(f"[配置热更新] AI模型已切换到: {model}")
                except Exception as model_error:
                    logger.warning(f"[配置热更新] 模型切换失败: {model_error}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新AI后端配置失败: {e}", exc_info=True)

    def _update_tts_config(self, config: Dict[str, Any]) -> None:
        """更新TTS配置"""
        try:
            # 更新TTS引擎配置
            engine = config.get("engine")
            if engine:
                # 实现TTS引擎切换
                try:
                    # 尝试从context获取TTS引擎实例
                    tts_instance = None
                    if hasattr(self.context, "agent_manager") and self.context.agent_manager:
                        if hasattr(self.context.agent_manager, "tts_engine"):
                            tts_instance = self.context.agent_manager.tts_engine
                    elif hasattr(self.context, "config_manager") and self.context.config_manager:
                        if hasattr(self.context.config_manager, "tts_engine"):
                            tts_instance = self.context.config_manager.tts_engine

                    if tts_instance:
                        # 如果有engine_name属性，更新它
                        if hasattr(tts_instance, "engine_name"):
                            tts_instance.engine_name = engine
                        # 如果有set_engine方法，调用它
                        elif hasattr(tts_instance, "set_engine"):
                            tts_instance.set_engine(engine)
                        logger.info(f"[配置热更新] TTS引擎已切换到: {engine}")
                    else:
                        logger.warning("[配置热更新] 未找到TTS引擎实例，无法切换引擎")
                except Exception as tts_error:
                    logger.warning(f"[配置热更新] TTS引擎切换失败: {tts_error}")

            voice = config.get("voice")
            if voice:
                # 实现音色切换
                try:
                    # 尝试从context获取TTS引擎实例
                    tts_instance = None
                    if hasattr(self.context, "agent_manager") and self.context.agent_manager:
                        if hasattr(self.context.agent_manager, "tts_engine"):
                            tts_instance = self.context.agent_manager.tts_engine
                    elif hasattr(self.context, "config_manager") and self.context.config_manager:
                        if hasattr(self.context.config_manager, "tts_engine"):
                            tts_instance = self.context.config_manager.tts_engine

                    if tts_instance:
                        # 如果有voice属性，更新它
                        if hasattr(tts_instance, "voice"):
                            tts_instance.voice = voice
                        # 如果有set_voice方法，调用它
                        elif hasattr(tts_instance, "set_voice"):
                            tts_instance.set_voice(voice)
                        logger.info(f"[配置热更新] TTS音色已切换到: {voice}")
                    else:
                        logger.warning("[配置热更新] 未找到TTS引擎实例，无法切换音色")
                except Exception as voice_error:
                    logger.warning(f"[配置热更新] TTS音色切换失败: {voice_error}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新TTS配置失败: {e}", exc_info=True)

    def _update_webapi_config(self, config: Dict[str, Any]) -> None:
        """更新WebAPI配置"""
        if not self.context.web_api:
            return

        try:
            # 更新API密钥
            api_key = config.get("api_key")
            if api_key:
                # 安全地更新API密钥
                try:
                    # WebAPI密钥通常用于身份验证，需要谨慎处理
                    if hasattr(self.context.web_api, "api_key"):
                        self.context.web_api.api_key = api_key
                        logger.info("[配置热更新] WebAPI密钥已安全更新")
                    elif hasattr(self.context.web_api, "set_api_key"):
                        self.context.web_api.set_api_key(api_key)
                        logger.info("[配置热更新] WebAPI密钥已安全更新")
                    else:
                        logger.warning("[配置热更新] WebAPI实例不支持动态更新API密钥")
                except Exception as webapi_key_error:
                    logger.warning(f"[配置热更新] WebAPI密钥更新失败: {webapi_key_error}")

            # 更新CORS配置
            cors_origins = config.get("cors_origins")
            if cors_origins:
                # 更新CORS允许的源
                try:
                    # 转换为列表格式
                    if isinstance(cors_origins, str):
                        origins_list = [origin.strip() for origin in cors_origins.split(",")]
                    else:
                        origins_list = list(cors_origins)

                    # 尝试更新CORS配置
                    if hasattr(self.context.web_api, "cors_origins"):
                        self.context.web_api.cors_origins = origins_list
                        logger.info(f"[配置热更新] CORS源已更新: {origins_list}")
                    elif hasattr(self.context.web_api, "update_cors"):
                        self.context.web_api.update_cors(origins_list)
                        logger.info(f"[配置热更新] CORS源已更新: {origins_list}")
                    else:
                        # 尝试更新FastAPI应用的CORS中间件
                        if hasattr(self.context.web_api, "app"):
                            app = self.context.web_api.app
                            # 查找CORS中间件并更新
                            from fastapi.middleware.cors import CORSMiddleware

                            for middleware in app.user_middleware:
                                if isinstance(middleware, CORSMiddleware):
                                    middleware.kwargs["allow_origins"] = origins_list
                                    logger.info(f"[配置热更新] FastAPI CORS源已更新: {origins_list}")
                                    break
                            else:
                                logger.warning("[配置热更新] 未找到CORS中间件，无法更新CORS配置")
                        else:
                            logger.warning("[配置热更新] WebAPI实例不支持动态更新CORS配置")
                except Exception as cors_error:
                    logger.warning(f"[配置热更新] CORS源更新失败: {cors_error}")

            # 更新速率限制
            rate_limit = config.get("rate_limit")
            if rate_limit:
                # 实现API速率限制更新
                try:
                    # 验证速率限制值（必须为正整数）
                    if not isinstance(rate_limit, int) or rate_limit <= 0:
                        logger.warning(f"[配置热更新] 速率限制必须为正整数: {rate_limit}")
                        return

                    if hasattr(self.context.web_api, "rate_limit"):
                        old_limit = self.context.web_api.rate_limit
                        self.context.web_api.rate_limit = rate_limit
                        logger.info(f"[配置热更新] API速率限制已更新: {old_limit} -> {rate_limit}/分钟")

                    elif hasattr(self.context.web_api, "set_rate_limit"):
                        self.context.web_api.set_rate_limit(rate_limit)
                        logger.info(f"[配置热更新] API速率限制已更新: {rate_limit}/分钟")

                    # 尝试更新限流器
                    if hasattr(self.context.web_api, "limiter"):
                        limiter = self.context.web_api.limiter
                        if hasattr(limiter, "max_requests_per_minute"):
                            old_limit = limiter.max_requests_per_minute
                            limiter.max_requests_per_minute = rate_limit
                            logger.info(f"[配置热更新] 限流器已更新: {old_limit} -> {rate_limit}/分钟")
                        elif hasattr(limiter, "reset"):
                            limiter.reset()
                            logger.info(f"[配置热更新] 限流器已重置为: {rate_limit}/分钟")

                    # 尝试更新FastAPI应用的限流中间件
                    if hasattr(self.context.web_api, "app"):
                        app = self.context.web_api.app
                        # 查找并更新slowapi或类似限流中间件
                        for middleware in app.user_middleware:
                            middleware_cls_name = middleware.cls.__name__
                            if "RateLimit" in middleware_cls_name or "Limiter" in middleware_cls_name:
                                if "rate_limit" in middleware.kwargs:
                                    middleware.kwargs["rate_limit"] = rate_limit
                                    logger.info(f"[配置热更新] FastAPI限流中间件已更新: {rate_limit}/分钟")
                                    break
                        else:
                            logger.debug("[配置热更新] 未找到限流中间件")

                    logger.info(f"[配置热更新] API速率限制已更新: {rate_limit}/分钟")

                except Exception as rate_limit_error:
                    logger.warning(f"[配置热更新] API速率限制更新失败: {rate_limit_error}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新WebAPI配置失败: {e}", exc_info=True)

    def _update_terminal_config(self, config: Dict[str, Any]) -> None:
        """更新终端管理器配置"""
        if not self.context.terminal_manager:
            return

        try:
            # 更新终端超时
            timeout = config.get("timeout")
            if timeout:
                # 更新终端超时设置
                try:
                    # 验证超时值（必须为正数）
                    if not isinstance(timeout, (int, float)) or timeout <= 0:
                        logger.warning(f"[配置热更新] 终端超时必须为正数: {timeout}")
                        return

                    if hasattr(self.context.terminal_manager, "timeout"):
                        old_timeout = self.context.terminal_manager.timeout
                        self.context.terminal_manager.timeout = timeout
                        logger.info(f"[配置热更新] 终端超时已更新: {old_timeout} -> {timeout}秒")

                    elif hasattr(self.context.terminal_manager, "set_timeout"):
                        self.context.terminal_manager.set_timeout(timeout)
                        logger.info(f"[配置热更新] 终端超时已更新: {timeout}秒")

                    # 更新所有活跃终端的超时设置
                    if hasattr(self.context.terminal_manager, "active_terminals"):
                        for _terminal_id, terminal_info in self.context.terminal_manager.active_terminals.items():
                            if "process" in terminal_info and hasattr(terminal_info["process"], "timeout"):
                                terminal_info["process"].timeout = timeout
                        logger.debug(
                            f"[配置热更新] 已更新{len(self.context.terminal_manager.active_terminals)}个活跃终端的超时"
                        )

                except Exception as timeout_error:
                    logger.warning(f"[配置热更新] 终端超时更新失败: {timeout_error}")

            # 更新终端缓冲区大小
            buffer_size = config.get("buffer_size")
            if buffer_size:
                # 更新终端缓冲区大小
                try:
                    # 验证缓冲区大小（必须为正整数）
                    if not isinstance(buffer_size, int) or buffer_size <= 0:
                        logger.warning(f"[配置热更新] 终端缓冲区大小必须为正整数: {buffer_size}")
                        return

                    if hasattr(self.context.terminal_manager, "buffer_size"):
                        old_size = self.context.terminal_manager.buffer_size
                        self.context.terminal_manager.buffer_size = buffer_size
                        logger.info(f"[配置热更新] 终端缓冲区大小已更新: {old_size} -> {buffer_size}")

                    elif hasattr(self.context.terminal_manager, "set_buffer_size"):
                        self.context.terminal_manager.set_buffer_size(buffer_size)
                        logger.info(f"[配置热更新] 终端缓冲区大小已更新: {buffer_size}")

                    # 注意：缓冲区大小通常只影响新创建的终端
                    logger.debug("[配置热更新] 缓冲区大小更改仅影响新创建的终端")

                except Exception as buffer_error:
                    logger.warning(f"[配置热更新] 终端缓冲区大小更新失败: {buffer_error}")

            # 更新默认shell
            default_shell = config.get("default_shell")
            if default_shell:
                # 更新默认shell
                try:
                    # 验证shell路径
                    from pathlib import Path

                    shell_path = Path(default_shell)
                    if not shell_path.exists():
                        logger.warning(f"[配置热更新] 默认shell不存在: {default_shell}")
                        return

                    if hasattr(self.context.terminal_manager, "default_shell"):
                        old_shell = self.context.terminal_manager.default_shell
                        self.context.terminal_manager.default_shell = default_shell
                        logger.info(f"[配置热更新] 默认shell已更新: {old_shell} -> {default_shell}")

                    elif hasattr(self.context.terminal_manager, "set_default_shell"):
                        self.context.terminal_manager.set_default_shell(default_shell)
                        logger.info(f"[配置热更新] 默认shell已更新: {default_shell}")

                    # 注意：默认shell更改仅影响新创建的终端
                    logger.debug("[配置热更新] 默认shell更改仅影响新创建的终端")

                except Exception as shell_error:
                    logger.warning(f"[配置热更新] 默认shell更新失败: {shell_error}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新终端配置失败: {e}", exc_info=True)

    def _update_iot_config(self, config: Dict[str, Any]) -> None:
        """更新IoT管理器配置"""
        if not self.context.iot_manager:
            return

        try:
            # 更新设备超时
            device_timeout = config.get("device_timeout")
            if device_timeout:
                self.context.iot_manager.device_timeout = device_timeout
                logger.info(f"[配置热更新] IoT设备超时已更新: {device_timeout}秒")

            # 更新心跳间隔
            heartbeat_interval = config.get("heartbeat_interval")
            if heartbeat_interval:
                # 更新心跳间隔
                try:
                    # 验证心跳间隔值（必须为正数，通常建议5-60秒）
                    if not isinstance(heartbeat_interval, (int, float)) or heartbeat_interval <= 0:
                        logger.warning(f"[配置热更新] IoT心跳间隔必须为正数: {heartbeat_interval}")
                        return

                    if heartbeat_interval < 5:
                        logger.warning(f"[配置热更新] IoT心跳间隔过小({heartbeat_interval}秒)，建议至少5秒")

                    if hasattr(self.context.iot_manager, "heartbeat_interval"):
                        old_interval = self.context.iot_manager.heartbeat_interval
                        self.context.iot_manager.heartbeat_interval = heartbeat_interval
                        logger.info(f"[配置热更新] IoT心跳间隔已更新: {old_interval} -> {heartbeat_interval}秒")

                        # 如果有活跃的心跳定时器，需要重启
                        if (
                            hasattr(self.context.iot_manager, "heartbeat_task")
                            and self.context.iot_manager.heartbeat_task
                        ):
                            try:
                                # 取消旧的心跳任务
                                self.context.iot_manager.heartbeat_task.cancel()
                                logger.debug("[配置热更新] 已取消旧的心跳任务")

                                # 重新启动心跳定时器
                                if hasattr(self.context.iot_manager, "start_heartbeat"):
                                    self.context.iot_manager.start_heartbeat()
                                    logger.info(f"[配置热更新] 已使用新间隔重启心跳定时器: {heartbeat_interval}秒")
                            except Exception as heartbeat_error:
                                logger.warning(f"[配置热更新] 重启心跳定时器失败: {heartbeat_error}")

                    elif hasattr(self.context.iot_manager, "set_heartbeat_interval"):
                        self.context.iot_manager.set_heartbeat_interval(heartbeat_interval)
                        logger.info(f"[配置热更新] IoT心跳间隔已更新: {heartbeat_interval}秒")

                    # 更新所有IoT设备的心跳配置
                    if hasattr(self.context.iot_manager, "devices"):
                        for _device_id, device_info in self.context.iot_manager.devices.items():
                            if isinstance(device_info, dict) and "heartbeat_interval" in device_info:
                                device_info["heartbeat_interval"] = heartbeat_interval
                        logger.debug(f"[配置热更新] 已更新{len(self.context.iot_manager.devices)}个IoT设备的心跳间隔")

                    logger.info(f"[配置热更新] IoT心跳间隔已更新: {heartbeat_interval}秒")

                except Exception as heartbeat_error:
                    logger.warning(f"[配置热更新] IoT心跳间隔更新失败: {heartbeat_error}")

            # 更新自动化规则
            automation_rules = config.get("automation_rules")
            if automation_rules:
                # 批量更新自动化规则
                try:
                    # 验证自动化规则格式
                    if not isinstance(automation_rules, (list, dict)):
                        logger.warning(f"[配置热更新] 自动化规则格式错误: {type(automation_rules)}")
                        return

                    # 将列表格式转换为字典（如果需要）
                    if isinstance(automation_rules, list):
                        rules_dict = {rule.get("id", f"rule_{i}"): rule for i, rule in enumerate(automation_rules)}
                    else:
                        rules_dict = automation_rules

                    # 备份旧规则以便回滚
                    old_rules = None
                    if hasattr(self.context.iot_manager, "automation_rules"):
                        old_rules = (
                            dict(self.context.iot_manager.automation_rules)
                            if self.context.iot_manager.automation_rules
                            else {}
                        )

                    # 更新自动化规则
                    if hasattr(self.context.iot_manager, "automation_rules"):
                        self.context.iot_manager.automation_rules = rules_dict
                        logger.info(f"[配置热更新] IoT自动化规则已更新: {len(rules_dict)}条")

                    elif hasattr(self.context.iot_manager, "set_automation_rules"):
                        self.context.iot_manager.set_automation_rules(rules_dict)
                        logger.info(f"[配置热更新] IoT自动化规则已更新: {len(rules_dict)}条")

                    # 尝试重新加载和验证规则
                    if hasattr(self.context.iot_manager, "reload_automation_rules"):
                        try:
                            # 验证规则
                            validation_result = self.context.iot_manager.validate_rules(rules_dict)
                            if not validation_result.get("valid", True):
                                # 验证失败，回滚
                                if old_rules is not None:
                                    self.context.iot_manager.automation_rules = old_rules
                                logger.error(f"[配置热更新] 自动化规则验证失败: {validation_result.get('errors', [])}")
                                return

                            # 重新加载规则
                            reload_result = self.context.iot_manager.reload_automation_rules(rules_dict)
                            if reload_result.get("success", False):
                                logger.info(f"[配置热更新] IoT自动化规则已重新加载: {len(rules_dict)}条")
                            else:
                                # 加载失败，回滚
                                if old_rules is not None:
                                    self.context.iot_manager.automation_rules = old_rules
                                logger.error(
                                    f"[配置热更新] 自动化规则加载失败: {reload_result.get('error', 'Unknown error')}"
                                )
                                return

                        except Exception as validate_error:
                            # 验证或加载失败，回滚
                            if old_rules is not None:
                                self.context.iot_manager.automation_rules = old_rules
                            logger.error(f"[配置热更新] 自动化规则验证/加载异常: {validate_error}")
                            return

                    logger.info(f"[配置热更新] IoT自动化规则已更新: {len(rules_dict)}条")

                except Exception as automation_error:
                    logger.warning(f"[配置热更新] IoT自动化规则更新失败: {automation_error}")

        except Exception as e:
            logger.error(f"[配置热更新] 更新IoT配置失败: {e}", exc_info=True)

    async def _trigger_config_update_event(self, changes: Dict[str, Any]) -> None:
        """触发配置更新事件

        Args:
            changes: 配置变更字典
        """

        try:
            # 创建配置更新事件
            event = ConfigEvent(
                event_type="config_update",
                timestamp=time.time(),
                changes=changes,
                source="config_hot_reload",
                metadata={"config_file": str(self.config_path), "change_count": len(changes)},
            )

            # 发布事件到所有订阅者
            await self._publish_event(event)

            logger.info(f"[配置热更新] 配置变更已通知: {list(changes.keys())}")

        except Exception as e:
            logger.error(f"[配置热更新] 触发配置更新事件失败: {e}", exc_info=True)

    def stop(self) -> None:
        """停止配置热更新监听"""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=NetworkTimeout.OBSERVER_JOIN_TIMEOUT)
            self._observer = None
            logger.info("[配置热更新] 监听已停止")
