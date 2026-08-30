"""
终端格式化工具 - v7.1: 星夜配色方案

提供彩色终端输出的格式化文本。
注意：不自动 print，避免调用方再 print 时产生双倍输出。

配色：
  紫罗兰 — 标题 / 思考过程头部
  琥珀金 — 思考内容
  松石绿 — 成功/结果
  天蓝   — 步骤/流程
  薰衣草 — 元信息/分隔
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class TerminalFormatter:
    """终端格式化器 - 返回 ANSI 彩色文本"""

    # ── 基础样式 ──
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"

    # ── 8 色 ──
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # ── 亮色 (90-97) ──
    GRAY = "\033[90m"
    VIOLET = "\033[95m"  # 亮紫 — 标题/引擎
    AMBER = "\033[93m"  # 亮黄 — 思考内容
    TEAL = "\033[96m"  # 亮青 — 流程
    EMERALD = "\033[92m"  # 亮绿 — 成功
    ROSE = "\033[91m"  # 亮红 — 错误

    # ── 图标 ──
    BRAIN = "◈"
    LINK = "→"
    ARROW = "→"
    CHECK = "✓"
    CROSS = "✗"
    STAR = "★"
    BOLT = "✦"

    # ==================== 协作引擎 ====================

    @classmethod
    def separator(cls, label: str = "") -> str:
        """分隔线 — 淡紫罗兰"""
        line = "─" * 25
        if label:
            return f"\n{cls.DIM}{cls.VIOLET}{line}  {label}  {line}{cls.RESET}"
        return f"\n{cls.DIM}{cls.VIOLET}{line}{line}{cls.RESET}"

    @classmethod
    def collaboration_start(cls, mode: str, complexity: int) -> str:
        """协作引擎开始 — 紫罗兰标题"""
        mode_labels = {
            "single": "单模型",
            "chain": "链式协作",
            "parallel": "并行投票",
            "role": "角色分工",
        }
        label = mode_labels.get(mode, mode)
        stars = "★" * complexity + "☆" * (5 - complexity)
        text = (
            f"{cls.VIOLET}{cls.BOLD}[{cls.BRAIN} COLLAB]{cls.RESET}"
            f"  {cls.CYAN}{label}{cls.RESET}"
            f"  {cls.DIM}复杂度{cls.RESET} {cls.AMBER}{stars}{cls.RESET}"
        )
        return text

    @classmethod
    def result(cls, mode: str, models: list, token_str: str, reason: str) -> str:
        """协作结果 — 松石绿成功 + 紫罗兰元信息"""
        models_str = ", ".join(models) if models else "unknown"
        text = (
            f"{cls.EMERALD}{cls.BOLD}[{cls.CHECK} DONE]{cls.RESET}"
            f" {cls.WHITE}{mode}{cls.RESET}"
            f" {cls.DIM}|{cls.RESET} {cls.TEAL}{models_str}{cls.RESET}"
            f" {cls.DIM}|{cls.RESET} {cls.AMBER}{token_str}{cls.RESET}"
            f" {cls.DIM}| {reason}{cls.RESET}"
        )
        return text

    @classmethod
    def chain_step(cls, step: int, model_id: str, action: str) -> str:
        """链式协作步骤 — 天蓝色"""
        text = (
            f"  {cls.DIM}{cls.LINK}{cls.RESET}"
            f" {cls.TEAL}步骤{step}{cls.RESET}"
            f" {cls.DIM}:{cls.RESET}"
            f" {cls.CYAN}{model_id}{cls.RESET}"
            f" {cls.DIM}→ {action}{cls.RESET}"
        )
        return text

    @classmethod
    def parallel_step(cls, models: list) -> str:
        """并行投票步骤"""
        models_str = f"{cls.CYAN}, {cls.RESET}".join(f"{cls.CYAN}{m}{cls.RESET}" for m in models)
        text = f"  {cls.AMBER}{cls.BOLT}{cls.RESET} {cls.DIM}并行调用:{cls.RESET} {models_str}"
        return text

    @classmethod
    def role_step(cls, role: str, model_id: str) -> str:
        """角色协作步骤"""
        text = f"  {cls.VIOLET}[{role}]{cls.RESET} {cls.DIM}→{cls.RESET} {cls.TEAL}{model_id}{cls.RESET}"
        return text

    # ==================== 思考过程 ====================

    @classmethod
    def thinking_block(cls, thinking: str) -> str:
        """思考过程 — 紫罗兰头部 + 琥珀金内容"""
        text = f"{cls.VIOLET}{cls.BOLD}◇ 思考过程{cls.RESET}\n{cls.AMBER}{cls.ITALIC}{thinking}{cls.RESET}"
        return text

    # ==================== 工具调用 ====================

    @classmethod
    def tool_call(cls, tool_name: str, args: dict = None) -> str:
        """工具调用信息 — 天蓝图标 + 白色名称"""
        from core.gestalt import get_gestalt_controller

        gestalt = get_gestalt_controller()
        tool_source = gestalt.get_tool_source(tool_name)

        args_str = ""
        if args:
            args_str = f" {cls.DIM}|{cls.RESET} {', '.join(f'{k}={v}' for k, v in list(args.items())[:3])}"

        if tool_source:
            text = (
                f"{cls.TEAL}[⚡ TOOL]{cls.RESET}"
                f" {cls.WHITE}{cls.BOLD}{tool_name}{cls.RESET}"
                f" {cls.DIM}({tool_source}){args_str}{cls.RESET}"
            )
        else:
            text = f"{cls.TEAL}[{cls.BOLT} TOOL]{cls.RESET} {cls.WHITE}{cls.BOLD}{tool_name}{cls.RESET}{args_str}"
        return text

    @classmethod
    def tool_result(cls, tool_name: str, status: str = "ok") -> str:
        """工具执行结果"""
        icon = cls.CHECK if status == "ok" else cls.CROSS
        color = cls.EMERALD if status == "ok" else cls.AMBER
        text = f"  {cls.DIM}{cls.ARROW}{cls.RESET} {color}{icon} {cls.DIM}{tool_name}{cls.RESET}"
        return text

    @classmethod
    def model_call(cls, model_id: str, task_type: str) -> str:
        """模型调用信息"""
        text = (
            f"{cls.TEAL}{cls.BOLD}[{cls.BRAIN}]{cls.RESET}"
            f" {cls.CYAN}{model_id}{cls.RESET}"
            f" {cls.DIM}| {task_type}{cls.RESET}"
        )
        return text
