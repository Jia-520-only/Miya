"""
弥娅器官基类 (MiyaOrgan)

所有挂载在 MiyaSpine 脊柱上的组件的基础类。
每个器官通过实现 on_soul_state() 来接收弥娅的灵魂状态广播，
以及其他生命周期钩子来同步自身的启停。

这是弥娅从"各自为政的组件"变为"统一活体"的关键机制——
每个器官不再自己决定什么时候做什么，
而是跟随弥娅的统一心跳和生命周期。
"""

from __future__ import annotations

import logging
import copy
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.miya_life_event import MiyaEvent
    from core.miya_soul_state import MiyaSoulState, LifecyclePhase

logger = logging.getLogger("Miya.Organ")


class MiyaOrgan(ABC):
    """
    弥娅脊柱上的一个器官。

    使用方法：
        class MyOrgan(MiyaOrgan):
            def on_soul_state(self, state: MiyaSoulState) -> None:
                # 收到弥娅的灵魂状态快照
                # 根据 state 的生命状态字段调整行为

            def on_lifecycle_change(self, old_phase, new_phase) -> None:
                # 弥娅的生命周期发生了变化
                # 例如从 RUNNING → DROWSY 时降低轮询频率

            async def on_start(self) -> None:
                # 器官启动时的初始化

            async def on_shutdown(self) -> None:
                # 器官关闭时的清理

    优先级决定广播顺序，数值越小越先收到。
    """

    def __init__(self, name: str, priority: int = 100):
        self.name = name
        self.priority = priority
        self._started = False
        self._spine = None  # 由 MiyaSpine 在注册时设置

    @property
    def spine(self):
        """获取所属的脊柱实例"""
        return self._spine

    @property
    def started(self) -> bool:
        return self._started

    def bind_spine(self, spine) -> None:
        self._spine = spine

    # ── 生命周期钩子 ──

    async def on_start(self) -> None:
        """器官启动，由 Spine 在注册后调用"""
        self._started = True
        logger.debug(f"Organ [{self.name}] started")

    async def on_shutdown(self) -> None:
        """器官关闭，由 Spine 在关闭时调用"""
        self._started = False
        logger.debug(f"Organ [{self.name}] shutdown")

    def on_lifecycle_change(self, old_phase: LifecyclePhase, new_phase: LifecyclePhase) -> None:
        """
        弥娅生命周期阶段变更通知。

        器官可以重写此方法来响应状态变化：
        - RUNNING → IDLE: 降低轮询频率
        - IDLE → DROWSY: 进入节能模式
        - DROWSY → WAKE: 恢复全功能
        """
        pass

    # ── 核心钩子：接收灵魂状态广播 ──

    def on_soul_state(self, state: MiyaSoulState) -> None:
        """
        收到弥娅的灵魂状态快照。

        这是脊柱神经的核心机制：每次心跳 tick 后，
        脊柱将弥娅的完整灵魂状态快照广播给所有器官。

        器官应在此方法中读取关心的状态字段并做出决策。
        注意：此方法在心跳线程中调用，不应阻塞。
        """
        pass

    # ── 事件注入钩子 ──

    def on_user_message(self, message: str, user_id: str = "") -> None:
        """
        收到用户消息事件。

        由脊柱在收到外部消息时广播。
        器官可以据此调整内部状态（如重置无聊度）。
        """
        pass

    def on_action_result(self, action: str, result: dict) -> None:
        """
        行动结果回流。

        器官执行某个行动后，结果通过脊柱回流传给所有器官。
        这使得弥娅可以"感受"到自己行为的后果。
        """
        pass

    def on_system_event(self, event: str, data: dict | None = None) -> None:
        """
        系统事件通知。

        如：系统休眠、唤醒、网络变化等。
        """
        pass

    def on_life_event(self, event: MiyaEvent, state: MiyaSoulState) -> None:
        """统一生命事件钩子。旧事件钩子仍由脊柱兼容调用。"""
        pass

    # ── 元信息 ──

    def status(self) -> dict:
        """返回器官的状态摘要"""
        return {
            "name": self.name,
            "started": self._started,
            "priority": self.priority,
        }

    def __repr__(self) -> str:
        return f"MiyaOrgan({self.name}, started={self._started})"


class MiyaOrganGroup(MiyaOrgan):
    """
    器官组：将多个器官组合为一个逻辑器官。

    用于批量注册和批量管理，例如：
        Spine.register_group("platforms", [QQOrgan, TelegramOrgan, ...])
    """

    def __init__(self, name: str, organs: list[MiyaOrgan] | None = None):
        super().__init__(name, priority=0)  # 组本身的 priority 不生效
        self._children: list[MiyaOrgan] = organs or []

    def add(self, organ: MiyaOrgan) -> None:
        if self.started:
            raise RuntimeError("请在器官组启动前添加子器官")
        organ.bind_spine(self._spine)
        self._children.append(organ)

    def bind_spine(self, spine) -> None:
        super().bind_spine(spine)
        for child in self._children:
            child.bind_spine(spine)

    async def on_start(self) -> None:
        for child in self._children:
            try:
                await child.on_start()
            except Exception as exc:
                logger.warning("Organ [%s/%s] start failed: %s", self.name, child.name, exc)
        await super().on_start()

    async def on_shutdown(self) -> None:
        for child in reversed(self._children):
            try:
                await child.on_shutdown()
            except Exception as exc:
                logger.warning("Organ [%s/%s] shutdown failed: %s", self.name, child.name, exc)
        await super().on_shutdown()

    def _forward(self, hook: str, *args) -> None:
        for child in self._children:
            try:
                getattr(child, hook)(*copy.deepcopy(args))
            except Exception as exc:
                logger.warning("Organ [%s/%s] %s failed: %s", self.name, child.name, hook, exc)

    def on_lifecycle_change(self, old_phase, new_phase) -> None:
        self._forward("on_lifecycle_change", old_phase, new_phase)

    def on_soul_state(self, state) -> None:
        self._forward("on_soul_state", state)

    def on_user_message(self, message: str, user_id: str = "") -> None:
        self._forward("on_user_message", message, user_id)

    def on_action_result(self, action: str, result: dict) -> None:
        self._forward("on_action_result", action, result)

    def on_system_event(self, event: str, data: dict | None = None) -> None:
        self._forward("on_system_event", event, data)

    def on_life_event(self, event, state) -> None:
        self._forward("on_life_event", event, state)
