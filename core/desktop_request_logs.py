"""Keep desktop access logs in the desktop console and the shared log buffer.

Only access/connection messages are redirected. Business logs, warnings and
exceptions keep their normal handlers, including for desktop-triggered work.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from ipaddress import ip_address

from core.log_stream import log_desktop_request

_desktop_request: ContextVar[bool] = ContextVar("miya_desktop_request", default=False)


def _is_desktop_scope(scope) -> bool:
    if scope.get("type") not in {"http", "websocket"}:
        return False
    headers = dict(scope.get("headers", []))
    client = scope.get("client")
    try:
        local = bool(client and ip_address(client[0]).is_loopback)
    except ValueError:
        local = False
    return local and headers.get(b"x-miya-client") == b"desktop"


class _DesktopAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno != logging.INFO:
            return True
        desktop = _desktop_request.get()
        if not desktop and record.name == "uvicorn.error":
            # websockets emits open/close from its protocol task, outside ASGI context.
            scope = getattr(getattr(record, "websocket", None), "scope", {})
            desktop = _is_desktop_scope(scope)
        if not desktop:
            return True
        message = str(record.msg)
        is_access = record.name == "uvicorn.access"
        is_ws_access = record.name == "uvicorn.error" and (
            '"WebSocket %s"' in message
            or message in {"connection open", "connection closed"}
        )
        is_management_connection = record.name == "Miya.ManagementAPI" and message.startswith(
            ("WS 客户端连接", "WS 客户端断开")
        )
        if not (is_access or is_ws_access or is_management_connection):
            return True
        try:
            level = "INFO"
            if is_access and isinstance(record.args, tuple) and len(record.args) == 5:
                status = int(record.args[4])
                level = "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
            log_desktop_request(record.getMessage(), level=level)
        except Exception:
            # A log capture failure must never swallow the original record.
            return True
        return False


def _install_access_filters() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "Miya.ManagementAPI"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, _DesktopAccessFilter) for f in logger.filters):
            logger.addFilter(_DesktopAccessFilter())


class DesktopRequestLogMiddleware:
    """Pure ASGI middleware: preserve streaming and isolate concurrent requests."""

    def __init__(self, app):
        self.app = app
        # Middleware is built after Uvicorn has configured its logging handlers.
        _install_access_filters()

    async def __call__(self, scope, receive, send):
        token = _desktop_request.set(_is_desktop_scope(scope))
        try:
            await self.app(scope, receive, send)
        finally:
            _desktop_request.reset(token)
