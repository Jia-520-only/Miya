from collections.abc import AsyncGenerator

from astrbot.core.platform import AstrMessageEvent
from astrbot.core.platform.sources.webchat.webchat_event import WebChatMessageEvent
from astrbot.core.platform.sources.wecom_ai_bot.wecomai_event import (
    WecomAIBotMessageEvent,
)
from astrbot.core.utils.active_event_registry import active_event_registry
from core.astrbot_compat import logger

from .bootstrap import ensure_builtin_stages_registered
from .context import PipelineContext
from .stage import registered_stages
from .stage_order import STAGES_ORDER


class PipelineScheduler:
    """管道调度器，负责调度各个阶段的执行"""

    def __init__(self, context: PipelineContext) -> None:
        ensure_builtin_stages_registered()
        registered_stages.sort(
            key=lambda x: STAGES_ORDER.index(x.__name__),
        )
        self.ctx = context
        self.stages = []

    async def initialize(self) -> None:
        """初始化管道调度器时, 初始化所有阶段"""
        for stage_cls in registered_stages:
            stage_instance = stage_cls()
            await stage_instance.initialize(self.ctx)
            self.stages.append(stage_instance)

    async def _process_stages(self, event: AstrMessageEvent, from_stage=0) -> None:
        """依次执行各个阶段"""
        for i in range(from_stage, len(self.stages)):
            stage = self.stages[i]
            coroutine = stage.process(event)

            if isinstance(coroutine, AsyncGenerator):
                async for _ in coroutine:
                    if event.is_stopped():
                        logger.debug(f"阶段 {stage.__class__.__name__} 已终止事件传播。")
                        break
                    await self._process_stages(event, i + 1)
                    if event.is_stopped():
                        logger.debug(f"阶段 {stage.__class__.__name__} 已终止事件传播。")
                        break
            else:
                await coroutine
                if event.is_stopped():
                    logger.debug(f"阶段 {stage.__class__.__name__} 已终止事件传播。")
                    break

    async def execute(self, event: AstrMessageEvent) -> None:
        """执行 pipeline"""
        active_event_registry.register(event)
        try:
            await self._process_stages(event)

            if isinstance(event, WebChatMessageEvent | WecomAIBotMessageEvent):
                await event.send(None)

            # ★ 统一 LifeBook 记录 — 覆盖所有 AstrBot 平台
            await self._record_to_lifebook(event)

            logger.debug("pipeline 执行完毕。")
        finally:
            event.cleanup_temporary_local_files()
            active_event_registry.unregister(event)

    async def _record_to_lifebook(self, event: AstrMessageEvent) -> None:
        """从 AstrBot 事件提取交互数据，写入 LifeBook

        覆盖 QQ(Official/OneBot)、Discord、Telegram、KOOK、Slack、
        WeChat、Satori、Misskey、Mattermost、WeCom、LINE、DingTalk、Lark、WebChat
        共 14+ 个平台适配器。
        """
        try:
            result = event.get_result()
            if not result:
                return

            response_text = self._extract_result_text(result)
            user_msg = event.get_message_str() or event.get_message_outline()
            if not response_text or not user_msg:
                return

            from memory.lifebook import get_lifebook

            lifebook = get_lifebook()
            platform_name = event.get_platform_name() or "astrbot"
            await lifebook.record_interaction(
                user_message=user_msg,
                lover_response=response_text,
                topics=[platform_name],
                emotion="平静",
            )
        except Exception:
            pass

    @staticmethod
    def _extract_result_text(result) -> str:
        """从 MessageEventResult 提取纯文本"""
        chain = getattr(result, "chain", None)
        if not chain:
            message = getattr(result, "message", None)
            if callable(message):
                try:
                    chain = message()
                except Exception:
                    pass
            elif isinstance(message, str):
                return message

        if not chain:
            return ""

        texts = []
        for comp in chain:
            text = getattr(comp, "text", None)
            if text:
                texts.append(str(text))
        return " ".join(texts) if texts else ""
