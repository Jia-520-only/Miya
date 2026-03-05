"""
实时状态同步
基于Agentic-Sync，实现Agent间实时状态同步
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum
from pathlib import Path
from core.constants import Encoding

logger = logging.getLogger(__name__)


class StateChangeType(Enum):
    """状态变更类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class StateSnapshot:
    """状态快照"""
    snapshot_id: str
    agent_id: str
    state_key: str
    state_value: Any
    change_type: StateChangeType
    timestamp: float = field(default_factory=time.time)
    version: int = 0


@dataclass
class StateSubscription:
    """状态订阅"""
    subscription_id: str
    subscriber_id: str
    state_keys: List[str]
    callback: Callable[[StateSnapshot], Any]
    last_synced_version: Dict[str, int] = field(default_factory=dict)


class RealTimeStateSync:
    """实时状态同步"""

    def __init__(
        self,
        agent_id: str,
        sync_interval: float = 5.0,  # 同步间隔（秒）
        max_snapshots: int = 1000
    ):
        self.agent_id = agent_id
        self.sync_interval = sync_interval
        self.max_snapshots = max_snapshots

        # 状态存储（键值对）
        self.state_store: Dict[str, Any] = {}

        # 快照历史
        self.snapshots: List[StateSnapshot] = []

        # 版本号
        self.state_versions: Dict[str, int] = {}

        # 订阅
        self.subscriptions: Dict[str, StateSubscription] = {}

        # 冲突解决策略
        self.conflict_resolution = "last_writer_wins"

        # 同步任务
        self._sync_task = None
        self._sync_running = False

        # 网络同步器（可选）
        self.network_syncer = None

        # 统计信息
        self.stats = {
            'total_changes': 0,
            'sync_count': 0,
            'conflict_count': 0,
            'notification_sent': 0
        }

    def set_state(
        self,
        state_key: str,
        value: Any,
        broadcast: bool = True
    ) -> bool:
        """
        设置状态

        Args:
            state_key: 状态键
            value: 状态值
            broadcast: 是否广播

        Returns:
            是否成功
        """
        old_value = self.state_store.get(state_key)

        # 创建快照
        change_type = (
            StateChangeType.CREATE if old_value is None
            else StateChangeType.UPDATE
        )

        # 更新状态
        self.state_store[state_key] = value
        self.state_versions[state_key] = self.state_versions.get(state_key, 0) + 1

        # 创建快照
        snapshot = StateSnapshot(
            snapshot_id=self._generate_snapshot_id(),
            agent_id=self.agent_id,
            state_key=state_key,
            state_value=value,
            change_type=change_type,
            version=self.state_versions[state_key]
        )

        self.snapshots.append(snapshot)

        # 清理旧快照
        self._cleanup_old_snapshots()

        self.stats['total_changes'] += 1

        # 通知订阅者
        self._notify_subscribers(snapshot)

        # 广播（如果启用）
        if broadcast and self.network_syncer:
            asyncio.create_task(
                self.network_syncer.broadcast_state_change(snapshot)
            )

        logger.debug(
            f"[StateSync] 状态变更: {state_key}, "
            f"类型: {change_type.value}, 版本: {snapshot.version}"
        )

        return True

    def get_state(self, state_key: str, version: Optional[int] = None) -> Optional[Any]:
        """
        获取状态

        Args:
            state_key: 状态键
            version: 版本号（可选）

        Returns:
            状态值
        """
        if state_key not in self.state_store:
            return None

        # 如果指定了版本，查找该版本的快照
        if version is not None:
            for snapshot in reversed(self.snapshots):
                if (snapshot.state_key == state_key and
                    snapshot.version == version):
                    return snapshot.state_value
            return None

        return self.state_store[state_key]

    def delete_state(self, state_key: str, broadcast: bool = True) -> bool:
        """
        删除状态

        Args:
            state_key: 状态键
            broadcast: 是否广播

        Returns:
            是否成功
        """
        if state_key not in self.state_store:
            return False

        value = self.state_store[state_key]
        del self.state_store[state_key]

        # 创建删除快照
        snapshot = StateSnapshot(
            snapshot_id=self._generate_snapshot_id(),
            agent_id=self.agent_id,
            state_key=state_key,
            state_value=value,
            change_type=StateChangeType.DELETE,
            version=self.state_versions[state_key]
        )

        self.snapshots.append(snapshot)

        self.stats['total_changes'] += 1

        # 通知订阅者
        self._notify_subscribers(snapshot)

        # 广播
        if broadcast and self.network_syncer:
            asyncio.create_task(
                self.network_syncer.broadcast_state_change(snapshot)
            )

        logger.debug(f"[StateSync] 状态删除: {state_key}")
        return True

    def subscribe_state(
        self,
        subscriber_id: str,
        state_keys: List[str],
        callback: Callable[[StateSnapshot], Any]
    ) -> str:
        """
        订阅状态变更

        Args:
            subscriber_id: 订阅者ID
            state_keys: 状态键列表
            callback: 回调函数

        Returns:
            订阅ID
        """
        subscription_id = self._generate_subscription_id()

        subscription = StateSubscription(
            subscription_id=subscription_id,
            subscriber_id=subscriber_id,
            state_keys=state_keys.copy(),
            callback=callback
        )

        self.subscriptions[subscription_id] = subscription

        # 初始化同步版本
        for key in state_keys:
            if key in self.state_versions:
                subscription.last_synced_version[key] = self.state_versions[key]

        logger.debug(
            f"[StateSync] 订阅: {subscriber_id}, "
            f"键: {state_keys}"
        )

        return subscription_id

    def unsubscribe_state(self, subscription_id: str) -> bool:
        """
        取消订阅

        Args:
            subscription_id: 订阅ID

        Returns:
            是否成功
        """
        if subscription_id not in self.subscriptions:
            return False

        del self.subscriptions[subscription_id]
        logger.debug(f"[StateSync] 取消订阅: {subscription_id}")
        return True

    async def apply_remote_change(
        self,
        snapshot: StateSnapshot,
        resolve_conflict: bool = True
    ) -> bool:
        """
        应用远程状态变更

        Args:
            snapshot: 状态快照
            resolve_conflict: 是否解决冲突

        Returns:
            是否成功
        """
        current_version = self.state_versions.get(snapshot.state_key, 0)

        # 检查冲突（远程版本比当前版本旧）
        if current_version > snapshot.version:
            if resolve_conflict:
                # 冲突解决
                if self.conflict_resolution == "last_writer_wins":
                    # 覆盖本地状态
                    self.state_store[snapshot.state_key] = snapshot.state_value
                    self.state_versions[snapshot.state_key] = snapshot.version

                    logger.info(
                        f"[StateSync] 冲突解决（LWW）: "
                        f"{snapshot.state_key}, 版本: {current_version} -> {snapshot.version}"
                    )

                    self.stats['conflict_count'] += 1
                    return True
                else:
                    logger.warning(
                        f"[StateSync] 状态冲突（远程版本过旧）: "
                        f"{snapshot.state_key}"
                    )
                    return False

        # 应用变更
        if snapshot.change_type == StateChangeType.DELETE:
            if snapshot.state_key in self.state_store:
                del self.state_store[snapshot.state_key]
        else:
            self.state_store[snapshot.state_key] = snapshot.state_value
            self.state_versions[snapshot.state_key] = snapshot.version

        # 记录快照
        self.snapshots.append(snapshot)
        self._cleanup_old_snapshots()

        # 通知订阅者
        self._notify_subscribers(snapshot)

        logger.debug(f"[StateSync] 应用远程变更: {snapshot.state_key}")
        return True

    async def start_sync(self):
        """启动同步任务"""
        if self._sync_running:
            return

        self._sync_running = True

        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"[StateSync] 启动同步: 间隔={self.sync_interval}s")

    async def stop_sync(self):
        """停止同步任务"""
        self._sync_running = False

        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        logger.info("[StateSync] 停止同步")

    async def _sync_loop(self):
        """同步循环"""
        while self._sync_running:
            await asyncio.sleep(self.sync_interval)

            if self.network_syncer:
                # 同步远程状态
                await self._sync_remote_states()

            self.stats['sync_count'] += 1

    async def _sync_remote_states(self):
        """同步远程状态（通过network_syncer）"""
        # 获取远程状态快照
        remote_snapshots = await self.network_syncer.fetch_remote_changes()

        for snapshot in remote_snapshots:
            await self.apply_remote_change(snapshot)

    def _notify_subscribers(self, snapshot: StateSnapshot):
        """通知订阅者"""
        for subscription in self.subscriptions.values():
            if snapshot.state_key in subscription.state_keys:
                try:
                    subscription.callback(snapshot)
                    self.stats['notification_sent'] += 1
                except Exception as e:
                    logger.error(f"[StateSync] 通知失败: {e}")

    def _cleanup_old_snapshots(self):
        """清理旧快照"""
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots:]

    def _generate_snapshot_id(self) -> str:
        """生成快照ID"""
        import uuid
        return f"snap_{self.agent_id}_{uuid.uuid4().hex[:12]}_{int(time.time())}"

    def _generate_subscription_id(self) -> str:
        """生成订阅ID"""
        import uuid
        return f"sub_{uuid.uuid4().hex[:12]}"

    def get_state_history(
        self,
        state_key: str,
        limit: int = 10
    ) -> List[StateSnapshot]:
        """
        获取状态历史

        Args:
            state_key: 状态键
            limit: 返回数量

        Returns:
            快照列表
        """
        snapshots = [
            s for s in reversed(self.snapshots)
            if s.state_key == state_key
        ]

        return snapshots[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'agent_id': self.agent_id,
            'total_states': len(self.state_store),
            'total_snapshots': len(self.snapshots),
            'total_subscriptions': len(self.subscriptions),
            'total_changes': self.stats['total_changes'],
            'sync_count': self.stats['sync_count'],
            'conflict_count': self.stats['conflict_count'],
            'notification_sent': self.stats['notification_sent']
        }

    def save_state(self, filepath: Optional[str] = None):
        """保存状态到磁盘"""
        if filepath is None:
            filepath = "data/state_sync.json"

        data = {
            'agent_id': self.agent_id,
            'state_store': self.state_store,
            'state_versions': self.state_versions,
            'snapshots': [
                {
                    'snapshot_id': s.snapshot_id,
                    'agent_id': s.agent_id,
                    'state_key': s.state_key,
                    'state_value': s.state_value,
                    'change_type': s.change_type.value,
                    'timestamp': s.timestamp,
                    'version': s.version
                }
                for s in self.snapshots[-100:]  # 只保留最近100个
            ],
            'statistics': self.stats,
            'saved_at': time.time()
        }

        with open(filepath, 'w', encoding=Encoding.UTF8) as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("[StateSync] 保存状态成功")
