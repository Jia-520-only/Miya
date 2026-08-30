"""统一的请求上下文管理系统

基于 Python contextvars 实现请求级别的上下文隔离和自动传播。
借鉴 Undefined 的 RequestContext 设计。

特性:
- 自动分配唯一的 request_id (UUID)
- 完全的并发隔离（基于 contextvars，零竞态条件）
- 自动资源管理和清理
- 支持嵌套上下文
- 集成日志过滤器，自动注入请求信息
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


class RequestContext:
    """统一的请求上下文管理器

    使用方式:
        async with RequestContext(
            source="qq", group_id=123, user_id=456, personality="default"
        ):
            await process_message()

    在作用域内任意位置获取上下文:
        ctx = RequestContext.current()
    """

    def __init__(
        self,
        source: str = "terminal",
        group_id: int | None = None,
        user_id: int | None = None,
        sender_name: str | None = None,
        personality: str = "default",
        message_id: str | None = None,
        **metadata: Any,
    ):
        self.request_id = str(uuid.uuid4())
        self.timestamp = datetime.now()

        self.source = source
        self.group_id = group_id
        self.user_id = user_id
        self.sender_name = sender_name
        self.personality = personality
        self.message_id = message_id

        self.metadata = metadata
        self._resources: dict[str, Any] = {}
        self._token: Any = None

    def set_resource(self, name: str, value: Any) -> None:
        self._resources[name] = value

    def get_resource(self, name: str, default: Any = None) -> Any:
        return self._resources.get(name, default)

    def get_resources(self) -> dict[str, Any]:
        return dict(self._resources)

    @classmethod
    def current(cls) -> RequestContext | None:
        return _request_context.get()

    @classmethod
    def require(cls) -> RequestContext:
        ctx = cls.current()
        if ctx is None:
            raise RuntimeError("当前没有活跃的请求上下文。请确保在 'async with RequestContext(...)' 作用域内调用。")
        return ctx

    async def __aenter__(self) -> RequestContext:
        self._token = _request_context.set(self)
        logger.debug(
            "[请求上下文] 创建: request_id=%s source=%s group_id=%s user_id=%s personality=%s",
            self.request_id[:8],
            self.source,
            self.group_id,
            self.user_id,
            self.personality,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        logger.debug("[请求上下文] 清理: request_id=%s", self.request_id[:8])
        _request_context.reset(self._token)
        self._resources.clear()


# ============================================================================
# 便捷访问函数
# ============================================================================


def get_group_id() -> int | None:
    ctx = RequestContext.current()
    return ctx.group_id if ctx else None


def get_user_id() -> int | None:
    ctx = RequestContext.current()
    return ctx.user_id if ctx else None


def get_request_id() -> str | None:
    ctx = RequestContext.current()
    return ctx.request_id if ctx else None


def get_source() -> str | None:
    ctx = RequestContext.current()
    return ctx.source if ctx else None


def get_personality() -> str:
    ctx = RequestContext.current()
    return ctx.personality if ctx else "default"


def get_sender_name() -> str | None:
    ctx = RequestContext.current()
    return ctx.sender_name if ctx else None


# ============================================================================
# 日志集成
# ============================================================================


class RequestContextFilter(logging.Filter):
    """日志过滤器，自动为日志记录添加请求上下文信息

    使用方式:
        for handler in logging.root.handlers:
            handler.addFilter(RequestContextFilter())

    日志格式建议:
        '%(asctime)s [%(levelname)s] [%(request_id)s] [s:%(source)s|g:%(group_id)s|u:%(user_id)s] %(name)s: %(message)s'
    """

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = RequestContext.current()
        if ctx:
            record.request_id = ctx.request_id[:8]
            record.source = ctx.source or "-"
            record.group_id = str(ctx.group_id) if ctx.group_id else "-"
            record.user_id = str(ctx.user_id) if ctx.user_id else "-"
        else:
            record.request_id = "-"
            record.source = "-"
            record.group_id = "-"
            record.user_id = "-"
        return True
