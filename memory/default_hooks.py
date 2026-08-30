"""
弥娅预置注入 Hook

将 CognitiveEngine、WorkingMemory、Historian、SkillManager 等
现有模块对接入 InjectionPipeline，实现统一的 Prompt 组装。
"""

import logging
from typing import Any, Dict, List, Optional

from memory.injection_pipeline import (
    CacheStrategy,
    HookContext,
    InjectionHook,
    InjectionPoint,
    get_injection_pipeline,
)

logger = logging.getLogger(__name__)


class IdentityHook(InjectionHook):
    """
    身份锚点注入 — system.prefix
    一次计算，整个 session 复用。
    """

    injection_point = InjectionPoint.SYSTEM_PREFIX
    cache_strategy = CacheStrategy.SESSION_INIT
    priority = 10

    def __init__(self):
        super().__init__("identity_hook")

    async def build(self, ctx: HookContext) -> str:
        try:
            import json
            from pathlib import Path

            project_root = Path(__file__).parent.parent
            anchor_path = project_root / "data" / "memory_anchors_identity.json"
            if not anchor_path.exists():
                return ""

            with open(anchor_path, "r", encoding="utf-8") as f:
                anchors = json.load(f)

            facts = [a.get("fact", "") for a in anchors if a.get("fact")]
            if facts:
                return "【弥娅身份与原则】\n" + "\n".join(f"- {fact}" for fact in facts)
        except Exception as e:
            logger.debug(f"[IdentityHook] 加载失败: {e}")
        return ""


class UserProfileHook(InjectionHook):
    """
    用户画像注入 — system.prefix
    一次计算，整个 session 复用。
    """

    injection_point = InjectionPoint.SYSTEM_PREFIX
    cache_strategy = CacheStrategy.SESSION_INIT
    priority = 20

    def __init__(self):
        super().__init__("user_profile_hook")

    async def build(self, ctx: HookContext) -> str:
        if not ctx.user_id:
            return ""

        lines = [f"【关于 {ctx.user_id} 的事情】"]
        seen_contents: List[str] = []

        def _append(content: str):
            content = (content or "").strip()
            if not content:
                return
            # 与已收集内容做前缀去重
            for existing in seen_contents:
                short = content[:30] if len(content) >= 30 else content
                if short and short in existing:
                    return
            if len(content) > 100:
                content = content[:97] + "..."
            lines.append(f"- {content}")
            seen_contents.append(content)

        try:
            # 【V4.1.12】记忆锚点文件直读兜底：
            # 无论检索链路是否健康，佳的核心信息（memory_anchors_user.json）都必须注入。
            # 仅当 ctx.user_id 与所有者规范 ID 等价时才注入，避免把佳的信息泄漏给其他用户。
            import json
            from pathlib import Path

            from memory.identity_resolver import get_identity_resolver

            resolver = get_identity_resolver()
            aliases = resolver.expand(ctx.user_id)
            owner_canonical = resolver.owner_canonical_id
            is_owner = bool(owner_canonical) and (
                ctx.user_id == owner_canonical or (aliases and owner_canonical in aliases)
            )

            if is_owner:
                anchor_path = Path(__file__).parent.parent / "data" / "memory_anchors_user.json"
                if anchor_path.exists():
                    with open(anchor_path, "r", encoding="utf-8") as f:
                        anchors = json.load(f)
                    if isinstance(anchors, list):
                        for anchor in anchors[:20]:
                            if isinstance(anchor, dict) and anchor.get("fact"):
                                _append(anchor["fact"])
        except Exception as e:
            logger.debug(f"[UserProfileHook] 锚点文件注入失败: {e}")

        try:
            from memory import get_user_profile

            profile = await get_user_profile(ctx.user_id)
            if profile and profile.get("memories"):
                for m in profile["memories"][:10]:
                    content = m.content if hasattr(m, "content") else str(m)
                    _append(content)
        except Exception as e:
            logger.debug(f"[UserProfileHook] 加载失败: {e}")

        return "\n".join(lines) if len(lines) > 1 else ""


class MemoryContextHook(InjectionHook):
    """
    记忆上下文注入 — user.before
    每次用户消息前检索相关记忆。
    """

    injection_point = InjectionPoint.USER_BEFORE
    cache_strategy = CacheStrategy.NONE
    priority = 50

    def __init__(self, limit: int = 5):
        super().__init__("memory_context_hook")
        self.limit = limit

    async def build(self, ctx: HookContext) -> str:
        if not ctx.user_input or len(ctx.user_input.strip()) < 3:
            return ""

        try:
            from memory.cognitive_engine import get_cognitive_engine

            engine = get_cognitive_engine()
            context_text = await engine.build_context(
                user_input=ctx.user_input,
                conversation_history=ctx.conversation_history,
                limit=self.limit,
                user_id=ctx.user_id or None,
                group_id=ctx.group_id or None,
            )
            return context_text
        except Exception as e:
            logger.debug(f"[MemoryContextHook] 构建失败: {e}")
        return ""


class WorkingMemoryHook(InjectionHook):
    """
    工作记忆注入 — user.before
    当前会话的活跃话题和背景话题。
    """

    injection_point = InjectionPoint.USER_BEFORE
    cache_strategy = CacheStrategy.NONE
    priority = 40

    def __init__(self):
        super().__init__("working_memory_hook")

    async def build(self, ctx: HookContext) -> str:
        try:
            from memory.working_memory import get_working_memory

            wmm = get_working_memory()
            if not ctx.user_input or not ctx.conversation_history:
                return ""

            active_topic = wmm._detect_active_topic(ctx.conversation_history)
            background = wmm.get_folded_background(session_id=getattr(ctx, "session_id", ""))

            parts = []
            if active_topic:
                parts.append(f"【当前话题: {active_topic}】")
            if background:
                parts.append(f"【背景信息】{background[:200]}")

            return "\n".join(parts) if parts else ""
        except Exception as e:
            logger.debug(f"[WorkingMemoryHook] 构建失败: {e}")
        return ""


class SkillInjectionHook(InjectionHook):
    """
    技能注入 — system.before_tools
    搜索匹配的技能并注入工具列表前。
    """

    injection_point = InjectionPoint.SYSTEM_BEFORE_TOOLS
    cache_strategy = CacheStrategy.SESSION_INIT
    priority = 30

    def __init__(self):
        super().__init__("skill_injection_hook")
        self._last_input: str = ""

    async def build(self, ctx: HookContext) -> str:
        try:
            from memory.skill_manager import get_skill_manager

            manager = get_skill_manager()
            await manager.initialize()

            context = await manager.search_and_inject(
                user_input=ctx.user_input or "",
                available_tools=ctx.available_tools,
                limit=3,
            )
            return context
        except Exception as e:
            logger.debug(f"[SkillInjectionHook] 加载失败: {e}")
        return ""

    def invalidate_cache(self):
        super().invalidate_cache()
        self._last_input = ""


def register_default_hooks(pipeline=None) -> "InjectionPipeline":
    """
    注册弥娅所有默认 Hook 到 InjectionPipeline。

    调用一次即可，通常在系统启动时执行。
    """
    if pipeline is None:
        pipeline = get_injection_pipeline()

    pipeline.register(IdentityHook())
    pipeline.register(UserProfileHook())
    pipeline.register(MemoryContextHook(limit=5))
    pipeline.register(WorkingMemoryHook())
    pipeline.register(SkillInjectionHook())

    logger.info("[InjectionPipeline] 默认 Hook 已注册")
    return pipeline
