"""
弥娅 Prompt 注入管线 (Injection Pipeline)

参考 TencentDB Agent Memory 的 MemoryProxy 注入架构，
将散落在各处的 Prompt 上下文化组装统一为一个注册式 Hook 系统。

架构：
┌──────────────────────────────────────────────────────────┐
│                    InjectionPipeline                      │
│                                                          │
│  system.prefix        → 系统提示前缀 (身份、人格)        │
│  system.before_tools  → 工具列表前 (技能、知识)          │
│  system.after_tools   → 工具列表后                       │
│  system.suffix        → 系统提示尾部 (记忆、规则)        │
│  user.first_turn      → 首轮用户消息前 (场景引导)        │
│  user.before          → 用户消息前 (记忆上下文)          │
│  user.after           → 用户消息后                       │
│  assistant.before     → 助手回复前                       │
│  assistant.after      → 助手回复后 (写回触发)            │
└──────────────────────────────────────────────────────────┘

优势：
1. 解耦 — 各模块独立注册，互不干扰
2. 可缓存 — 稳定内容标为 session_init，预计算一次跨轮复用
3. 可排序 — 优先级决定注入顺序
4. 可扩展 — 新增 Hook 无需改动核心代码
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class InjectionPoint(Enum):
    SYSTEM_PREFIX = "system.prefix"
    SYSTEM_BEFORE_TOOLS = "system.before_tools"
    SYSTEM_AFTER_TOOLS = "system.after_tools"
    SYSTEM_SUFFIX = "system.suffix"
    USER_FIRST_TURN = "user.first_turn"
    USER_BEFORE = "user.before"
    USER_AFTER = "user.after"
    ASSISTANT_BEFORE = "assistant.before"
    ASSISTANT_AFTER = "assistant.after"

    @property
    def phase(self) -> str:
        return self.value


class CacheStrategy(Enum):
    NONE = "none"
    SESSION_INIT = "session_init"


INJECTION_ORDER: List[InjectionPoint] = [
    InjectionPoint.SYSTEM_PREFIX,
    InjectionPoint.SYSTEM_BEFORE_TOOLS,
    InjectionPoint.SYSTEM_AFTER_TOOLS,
    InjectionPoint.SYSTEM_SUFFIX,
    InjectionPoint.USER_FIRST_TURN,
    InjectionPoint.USER_BEFORE,
    InjectionPoint.USER_AFTER,
    InjectionPoint.ASSISTANT_BEFORE,
    InjectionPoint.ASSISTANT_AFTER,
]


@dataclass
class HookContext:
    user_id: str = ""
    group_id: str = ""
    session_id: str = ""
    platform: str = "unknown"
    user_input: str = ""
    conversation_history: List[Dict] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_first_turn: bool = False


class InjectionHook(ABC):
    """
    注入 Hook 基类

    用法：
    ```python
    class MemoryHook(InjectionHook):
        injection_point = InjectionPoint.USER_BEFORE
        cache_strategy = CacheStrategy.SESSION_INIT
        priority = 50

        async def build(self, ctx: HookContext) -> str:
            return await cognitive_engine.build_context(ctx.user_input)
    ```
    """

    injection_point: InjectionPoint = InjectionPoint.SYSTEM_SUFFIX
    cache_strategy: CacheStrategy = CacheStrategy.NONE
    priority: int = 50

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._cached_content: Optional[str] = None
        self._cache_session_id: Optional[str] = None

    def cache_key(self, ctx: HookContext) -> str:
        session = ctx.session_id or ctx.user_id or "global"
        raw = f"{self.name}:{session}:{ctx.platform}:{ctx.is_first_turn}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    async def build(self, ctx: HookContext) -> str: ...

    async def execute(self, ctx: HookContext) -> str:
        if self.cache_strategy == CacheStrategy.SESSION_INIT:
            ck = self.cache_key(ctx)
            if self._cached_content is not None and self._cache_session_id == ck:
                return self._cached_content

            content = await self.build(ctx)
            self._cached_content = content
            self._cache_session_id = ck
            return content

        return await self.build(ctx)

    def invalidate_cache(self):
        self._cached_content = None
        self._cache_session_id = None


class InjectionPipeline:
    """
    Prompt 注入管线

    集中管理所有 Hook，按 InjectionPoint 有序执行。
    """

    def __init__(self):
        self._hooks: Dict[InjectionPoint, List[InjectionHook]] = {ip: [] for ip in InjectionPoint}
        self._all_hooks: List[InjectionHook] = []

    def register(self, hook: InjectionHook) -> "InjectionPipeline":
        self._hooks[hook.injection_point].append(hook)
        self._hooks[hook.injection_point].sort(key=lambda h: h.priority)
        self._all_hooks.append(hook)
        logger.debug(
            f"[InjectionPipeline] 注册 Hook: {hook.name} @ {hook.injection_point.value} (priority={hook.priority})"
        )
        return self

    def unregister(self, name: str):
        for ip in InjectionPoint:
            self._hooks[ip] = [h for h in self._hooks[ip] if h.name != name]
        self._all_hooks = [h for h in self._all_hooks if h.name != name]

    def get_hooks(self, point: InjectionPoint) -> List[InjectionHook]:
        return self._hooks.get(point, [])

    async def execute_at(self, point: InjectionPoint, ctx: HookContext) -> str:
        hooks = self._hooks.get(point, [])
        if not hooks:
            return ""

        parts = []
        for hook in hooks:
            try:
                content = await hook.execute(ctx)
                if content:
                    parts.append(content)
            except Exception as e:
                logger.warning(f"[InjectionPipeline] Hook {hook.name} 执行失败: {e}")

        return "\n".join(parts)

    async def build_system_context(self, ctx: HookContext) -> Dict[str, str]:
        prefix = await self.execute_at(InjectionPoint.SYSTEM_PREFIX, ctx)
        before_tools = await self.execute_at(InjectionPoint.SYSTEM_BEFORE_TOOLS, ctx)
        after_tools = await self.execute_at(InjectionPoint.SYSTEM_AFTER_TOOLS, ctx)
        suffix = await self.execute_at(InjectionPoint.SYSTEM_SUFFIX, ctx)

        return {
            "prefix": prefix,
            "before_tools": before_tools,
            "after_tools": after_tools,
            "suffix": suffix,
        }

    async def build_user_context(self, ctx: HookContext) -> Dict[str, str]:
        first_turn = await self.execute_at(InjectionPoint.USER_FIRST_TURN, ctx)
        before = await self.execute_at(InjectionPoint.USER_BEFORE, ctx)
        after = await self.execute_at(InjectionPoint.USER_AFTER, ctx)

        return {
            "first_turn": first_turn if ctx.is_first_turn else "",
            "before": before,
            "after": after,
        }

    async def assemble_prompt(
        self,
        system_prompt: str,
        ctx: HookContext,
    ) -> Dict[str, Any]:
        """
        完整组装 Prompt。

        Returns:
            {"system": "完整系统提示", "user_context": {first_turn, before, after}}
        """
        sc = await self.build_system_context(ctx)
        uc = await self.build_user_context(ctx)

        system_parts = []
        if sc["prefix"]:
            system_parts.append(sc["prefix"])
        system_parts.append(system_prompt)
        if sc["before_tools"]:
            system_parts.append(sc["before_tools"])
        if sc["after_tools"]:
            system_parts.append(sc["after_tools"])
        if sc["suffix"]:
            system_parts.append(sc["suffix"])

        return {
            "system": "\n\n".join(filter(None, system_parts)),
            "user_context": uc,
        }

    def invalidate_all_caches(self):
        for hook in self._all_hooks:
            hook.invalidate_cache()

    def stats(self) -> Dict[str, Any]:
        return {
            "total_hooks": len(self._all_hooks),
            "by_point": {ip.value: len(hooks) for ip, hooks in self._hooks.items() if hooks},
            "cached_hooks": sum(1 for h in self._all_hooks if h.cache_strategy == CacheStrategy.SESSION_INIT),
        }


_global_pipeline: Optional[InjectionPipeline] = None


def get_injection_pipeline() -> InjectionPipeline:
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = InjectionPipeline()
    return _global_pipeline
