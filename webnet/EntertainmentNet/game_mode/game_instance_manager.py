"""
游戏实例管理器
为每个游戏实例提供独立的管理，实现故障隔离
"""

import logging
from typing import Dict, Optional, Callable
from datetime import datetime
from pathlib import Path
import json

from .mode_state import GameMode, GameModeType, GameState
from .state_transition_validator import StateTransitionValidator, StateTransitionError
from core.constants import Encoding


logger = logging.getLogger(__name__)


class GameInstance:
    """
    游戏实例

    职责：
    1. 封装单个游戏的所有状态和行为
    2. 提供独立的状态管理
    3. 支持错误隔离和恢复
    4. 提供实例级别的日志追踪
    """

    def __init__(
        self,
        chat_id: str,
        mode_type: GameModeType,
        game_mode: GameMode,
        on_state_change: Optional[Callable] = None
    ):
        self.chat_id = chat_id
        self.mode_type = mode_type
        self.game_mode = game_mode
        self.on_state_change = on_state_change

        self.created_at = datetime.now()
        self.last_active_at = datetime.now()
        self.error_count = 0
        self.is_healthy = True

        logger.info(
            f"[GameInstance] 创建游戏实例: {chat_id}, "
            f"模式: {mode_type.value}, 状态: {game_mode.game_state.value}"
        )

    def get_state(self) -> GameState:
        """获取当前状态"""
        return self.game_mode.game_state

    def transition_state(
        self,
        new_state: GameState,
        context: Optional[dict] = None,
        force: bool = False
    ) -> bool:
        """
        转换游戏状态

        Args:
            new_state: 新状态
            context: 转换上下文
            force: 是否强制转换（跳过验证）

        Returns:
            是否转换成功
        """
        old_state = self.get_state()

        if old_state == new_state:
            return True

        # 验证状态转换
        if not force:
            try:
                StateTransitionValidator.validate(old_state, new_state, context)
            except StateTransitionError as e:
                logger.error(f"[GameInstance] 状态转换失败: {e}")
                return False

        # 执行钩子
        context = StateTransitionValidator.execute_hooks(old_state, new_state, context)

        # 执行转换
        self.game_mode.game_state = new_state
        self.last_active_at = datetime.now()

        # 触发状态变更回调
        if self.on_state_change:
            try:
                self.on_state_change(self.chat_id, old_state, new_state, context)
            except Exception as e:
                logger.error(f"[GameInstance] 状态变更回调失败: {e}")

        logger.info(
            f"[GameInstance] {self.chat_id} 状态转换: "
            f"{old_state.value} -> {new_state.value}"
        )

        return True

    def record_error(self):
        """记录错误"""
        self.error_count += 1
        if self.error_count >= 5:
            self.is_healthy = False
            logger.warning(f"[GameInstance] {self.chat_id} 不健康，错误次数: {self.error_count}")

    def reset_health(self):
        """重置健康状态"""
        self.error_count = 0
        self.is_healthy = True

    def is_active(self) -> bool:
        """检查实例是否活跃"""
        # 超过24小时未活动视为不活跃
        inactive_seconds = (datetime.now() - self.last_active_at).total_seconds()
        return inactive_seconds < 86400  # 24小时

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'chat_id': self.chat_id,
            'mode_type': self.mode_type.value,
            'game_mode': self.game_mode.to_dict(),
            'created_at': self.created_at.isoformat(),
            'last_active_at': self.last_active_at.isoformat(),
            'error_count': self.error_count,
            'is_healthy': self.is_healthy,
        }


class GameInstanceManager:
    """
    游戏实例管理器

    职责：
    1. 管理所有游戏实例的生命周期
    2. 提供实例隔离和故障恢复
    3. 自动清理不活跃实例
    4. 提供实例级别的错误处理
    """

    def __init__(self, data_path: str = "data/game_instances.json"):
        self.data_path = Path(data_path)
        self.instances: Dict[str, GameInstance] = {}  # chat_id -> GameInstance
        self.load()

    def load(self):
        """
        加载实例数据（仅用于日志记录，完整恢复由 GameModeManager.load() 完成）

        注意：
        - GameInstance 必须依赖完整的 GameMode 对象
        - GameModeManager.load() 负责同时恢复模式和实例
        - 此方法仅用于日志记录历史实例数量
        """
        if self.data_path.exists():
            try:
                with open(self.data_path, 'r', encoding=Encoding.UTF8) as f:
                    data = json.load(f)
                    # 仅记录，不恢复（由 GameModeManager 统一恢复）
                    for instance_data in data:
                        chat_id = instance_data['chat_id']
                        logger.debug(f"[GameInstanceManager] 发现历史实例: {chat_id}")
                    logger.info(f"[GameInstanceManager] 发现 {len(data)} 个历史实例")
            except Exception as e:
                logger.error(f"[GameInstanceManager] 加载失败: {e}")

    def save(self):
        """保存实例数据"""
        try:
            self.data_path.parent.mkdir(parents=True, exist_ok=True)
            data = [instance.to_dict() for instance in self.instances.values()]
            with open(self.data_path, 'w', encoding=Encoding.UTF8) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[GameInstanceManager] 已保存 {len(self.instances)} 个实例")
        except Exception as e:
            logger.error(f"[GameInstanceManager] 保存失败: {e}")

    def create_instance(
        self,
        chat_id: str,
        mode_type: GameModeType,
        game_mode: GameMode,
        on_state_change: Optional[Callable] = None
    ) -> GameInstance:
        """
        创建游戏实例

        Args:
            chat_id: 聊天ID
            mode_type: 游戏模式类型
            game_mode: 游戏模式对象
            on_state_change: 状态变更回调

        Returns:
            游戏实例
        """
        if chat_id in self.instances:
            logger.warning(f"[GameInstanceManager] 实例已存在: {chat_id}，将覆盖")

        instance = GameInstance(
            chat_id=chat_id,
            mode_type=mode_type,
            game_mode=game_mode,
            on_state_change=on_state_change
        )

        self.instances[chat_id] = instance
        self.save()
        return instance

    def get_instance(self, chat_id: str) -> Optional[GameInstance]:
        """获取游戏实例"""
        return self.instances.get(chat_id)

    def remove_instance(self, chat_id: str):
        """移除游戏实例"""
        if chat_id in self.instances:
            del self.instances[chat_id]
            self.save()
            logger.info(f"[GameInstanceManager] 移除实例: {chat_id}")

    def transition_state(
        self,
        chat_id: str,
        new_state: GameState,
        context: Optional[dict] = None
    ) -> bool:
        """
        转换游戏实例状态

        Args:
            chat_id: 聊天ID
            new_state: 新状态
            context: 转换上下文

        Returns:
            是否转换成功
        """
        instance = self.get_instance(chat_id)
        if not instance:
            logger.error(f"[GameInstanceManager] 实例不存在: {chat_id}")
            return False

        return instance.transition_state(new_state, context)

    def cleanup_inactive_instances(self, max_inactive_hours: int = 24):
        """
        清理不活跃的实例

        Args:
            max_inactive_hours: 最大不活跃小时数
        """
        to_remove = []
        for chat_id, instance in self.instances.items():
            if not instance.is_active():
                inactive_seconds = (datetime.now() - instance.last_active_at).total_seconds()
                inactive_hours = inactive_seconds / 3600
                if inactive_hours >= max_inactive_hours:
                    to_remove.append(chat_id)
                    logger.info(
                        f"[GameInstanceManager] 实例 {chat_id} 不活跃 {inactive_hours:.1f} 小时，将清理"
                    )

        for chat_id in to_remove:
            self.remove_instance(chat_id)

        if to_remove:
            logger.info(f"[GameInstanceManager] 清理了 {len(to_remove)} 个不活跃实例")

    def get_unhealthy_instances(self) -> list:
        """获取不健康的实例列表"""
        return [
            (chat_id, instance.error_count)
            for chat_id, instance in self.instances.items()
            if not instance.is_healthy
        ]

    def is_instance_healthy(self, chat_id: str) -> bool:
        """检查实例是否健康"""
        instance = self.get_instance(chat_id)
        return instance.is_healthy if instance else True


# 全局单例
_instance_manager = None


def get_instance_manager() -> GameInstanceManager:
    """获取实例管理器单例"""
    global _instance_manager
    if _instance_manager is None:
        _instance_manager = GameInstanceManager()
    return _instance_manager
