from __future__ import annotations

"""
弥娅 Browser Use Executor — 浏览器操作执行器

弥娅通过 DeepSeek Harness 执行浏览器操作。每个浏览器操作被选中后，
通过本执行器转换为 DSH 任务，由 DeepSeek Harness 实际执行。

执行流程:
  action::browser_* → BrowserUseExecutor.execute()
  → 构建自然语言指令 → DSH execute()
  → 等待执行结果 → 感知分析
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("miya_senses.browser_use")

try:
    from mcpserver.dsh.service import service as dsh_service

    _HAS_DSH = True
except ImportError:
    _HAS_DSH = False
    logger.warning("[BrowserUse] DSH 不可用，浏览器操作将受限")


@dataclass
class BrowserActionResult:
    action_id: str
    instruction: str
    success: bool
    reply: str = ""
    session_key: str = ""
    status: str = "unknown"
    error: str = ""
    latency_ms: float = 0.0
    extracted_data: dict = field(default_factory=dict)


class BrowserUseExecutor:
    """
    弥娅的浏览器操作执行器。

    弥娅的「手」——当弥娅需要操作浏览器时，
    本执行器将内部意图翻译为 DSH 可执行的自然语言指令。
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        default_timeout: float = 60.0,
        max_retries: int = 2,
        workspace: str = "",
        model: Optional[str] = None,
    ) -> None:
        self.enabled = bool(enabled)
        self.default_timeout = float(default_timeout)
        self.max_retries = max(1, int(max_retries))
        self.workspace = str(workspace or "")
        self.model = model
        self._last_result: Optional[BrowserActionResult] = None
        self._session_keys: dict[str, str] = {}
        self._execution_count: int = 0

    @property
    def is_available(self) -> bool:
        return _HAS_DSH and self.enabled

    async def execute(
        self,
        action_id: str,
        params: dict[str, Any] | None = None,
        *,
        context: str = "",
        session_key: str = "",
    ) -> BrowserActionResult:
        """
        执行一个浏览器操作。

        把「action::browser_click」这类内部想法
        转换成 DSH 可以理解的自然语言任务描述。
        """
        t_start = time.monotonic()
        params = params or {}
        self._execution_count += 1

        if not self.enabled:
            return BrowserActionResult(
                action_id=action_id,
                instruction="",
                success=False,
                error="BrowserUse 已禁用",
                latency_ms=(time.monotonic() - t_start) * 1000,
            )

        instruction = self._action_to_instruction(action_id, params, context)
        logger.info(f"[BrowserUse] 执行 #{self._execution_count}: {action_id} → {instruction[:80]}...")

        for attempt in range(self.max_retries):
            result = await self._do_execute(instruction, session_key)
            if result.success:
                self._last_result = result
                return result
            if attempt < self.max_retries - 1:
                logger.warning(f"[BrowserUse] 重试 {attempt + 1}/{self.max_retries}: {result.error[:100]}")
                await asyncio.sleep(1.0 * (attempt + 1))

        result.latency_ms = (time.monotonic() - t_start) * 1000
        self._last_result = result
        return result

    async def _do_execute(self, instruction: str, session_key: str) -> BrowserActionResult:
        t0 = time.monotonic()

        if not _HAS_DSH:
            return BrowserActionResult(
                action_id="",
                instruction=instruction,
                success=False,
                error="DSH 执行引擎不可用",
                latency_ms=(time.monotonic() - t0) * 1000,
            )

        try:
            raw = await dsh_service.handle_handoff({
                "tool_name": "execute",
                "task": instruction,
                "working_dir": self.workspace,
                "timeout": int(self.default_timeout),
            })
            response = json.loads(raw) if isinstance(raw, str) else raw
            success = bool(response.get("success", False))
            reply = str(response.get("output", "") or "")
            sk = session_key or ""

            if sk:
                self._session_keys[sk] = instruction[:40]

            return BrowserActionResult(
                action_id="",
                instruction=instruction,
                success=success,
                reply=reply,
                session_key=sk,
                status=str(response.get("status", "completed" if success else "error")),
                error="" if success else str(response.get("error", "未知错误")),
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            return BrowserActionResult(
                action_id="",
                instruction=instruction,
                success=False,
                error=str(exc),
                latency_ms=(time.monotonic() - t0) * 1000,
            )

    def _action_to_instruction(
        self,
        action_id: str,
        params: dict[str, Any],
        context: str,
    ) -> str:
        """将浏览器行动 ID 转换为 DSH 自然语言指令"""
        builder = _InstructionBuilder(context)
        return builder.build(action_id, params)

    def get_last_result(self) -> Optional[BrowserActionResult]:
        return self._last_result

    def get_session_keys(self) -> dict[str, str]:
        return dict(self._session_keys)

    async def cleanup(self) -> None:
        return None


class _InstructionBuilder:
    """弥娅的内部浏览器意图 → 自然语言指令"""

    def __init__(self, context: str = ""):
        self._ctx = str(context or "").strip()

    def build(self, action_id: str, params: dict[str, Any]) -> str:
        handler = {
            "action::browser_open": self._build_open,
            "action::browser_search": self._build_search,
            "action::browser_click": self._build_click,
            "action::browser_type": self._build_type,
            "action::browser_scroll": self._build_scroll,
            "action::browser_read_page": self._build_read,
            "action::browser_extract_data": self._build_extract,
            "action::browser_screenshot": self._build_screenshot,
            "action::browser_wait": self._build_wait,
            "action::browser_back": self._build_back,
        }.get(action_id, self._build_unknown)

        instruction = handler(params)
        if self._ctx:
            instruction = f"{self._ctx}\n{instruction}"
        return instruction

    def _build_open(self, p: dict) -> str:
        url = p.get("url", "about:blank")
        new_tab = p.get("new_tab", True)
        tab = "在新标签页中" if new_tab else "在当前页面"
        return f"请{tab}打开网址 {url}"

    def _build_search(self, p: dict) -> str:
        query = p.get("query", "")
        engine = p.get("engine", "默认搜索引擎")
        return f"请用{engine}搜索: {query}"

    def _build_click(self, p: dict) -> str:
        selector = p.get("selector", "")
        text = p.get("text", "")
        x, y = p.get("x"), p.get("y")
        if selector:
            return f"请点击页面元素: {selector}"
        if text:
            return f"请点击包含文字「{text}」的按钮或链接"
        if x is not None and y is not None:
            return f"请点击页面坐标 ({x}, {y}) 处"
        return "请点击目标元素"

    def _build_type(self, p: dict) -> str:
        selector = p.get("selector", "")
        text = p.get("text", "")
        if selector and text:
            return f'请在 "{selector}" 输入框中输入: {text}'
        if text:
            return f"请在当前激活的输入框中输入: {text}"
        return "请在输入框中输入文字"

    def _build_scroll(self, p: dict) -> str:
        direction = p.get("direction", "down")
        amount = p.get("amount", "一页")
        return f"请向{direction}滚动{amount}"

    def _build_read(self, p: dict) -> str:
        extract_type = p.get("extract_type", "全文")
        return f"请读取当前页面内容，返回{extract_type}。用中文总结关键信息。"

    def _build_extract(self, p: dict) -> str:
        query = p.get("query", "")
        fmt = p.get("format", "列表")
        if query:
            return f"请从当前页面提取以下信息并以{fmt}格式返回: {query}"
        return f"请提取当前页面的所有关键数据，以{fmt}格式返回"

    def _build_screenshot(self, p: dict) -> str:
        selector = p.get("selector", "")
        if selector:
            return f"请截取页面元素「{selector}」的截图"
        return "请截取当前页面的截图"

    def _build_wait(self, p: dict) -> str:
        condition = p.get("condition", "页面加载完成")
        timeout = p.get("timeout", 10)
        return f"请等待{condition}，超时 {timeout} 秒"

    def _build_back(self, p: dict) -> str:
        return "请返回上一页"

    def _build_unknown(self, p: dict) -> str:
        action = p.get("action_id", "未知操作")
        return f"请执行浏览器操作: {action}\n参数: {json.dumps(p, ensure_ascii=False)}"
